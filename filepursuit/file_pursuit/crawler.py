"""
Crawler module for FilePursuit.

Handles async crawling of Apache/Nginx directory listings using aiohttp.
"""

import asyncio
import aiohttp
import time
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from .database import Database, FileEntry, CrawlTarget
from .parser import DirectoryParser
from .logger import ActivityLogger
from .utils import is_valid_url, extract_domain


@dataclass
class CrawlResult:
    """Result of a crawl operation."""
    files_discovered: int
    files_indexed: int
    errors_count: int
    duration_seconds: float
    status: str  # 'SUCCESS', 'PARTIAL', 'FAIL'


class Crawler:
    """Crawls directory listings and indexes files."""

    # Rate limiting: per-domain delay (milliseconds)
    RATE_LIMIT_MS = 200

    # Request timeout (seconds)
    REQUEST_TIMEOUT = 30

    # Max depth for crawling
    MAX_DEPTH = 10

    # Concurrent requests per domain
    MAX_CONCURRENT_PER_DOMAIN = 3

    def __init__(self, database: Database, logger: ActivityLogger):
        """Initialize crawler."""
        self.database = database
        self.logger = logger
        self.parser = DirectoryParser()
        self.session = None
        self._domain_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._last_request_time: Dict[str, float] = {}

    async def crawl_target(self, target: CrawlTarget) -> CrawlResult:
        """Crawl a single target."""
        start_time = time.time()

        try:
            self.logger.log_crawl_started(target.target_id, target.url)
            self.database.update_crawl_target_status(target.target_id, "crawling")

            # Initialize session
            if self.session is None:
                timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
                self.session = aiohttp.ClientSession(timeout=timeout)

            # Crawl the target
            files = await self._crawl_recursive(target.url, target.type, depth=0)

            # Index files
            indexed_count = self.database.insert_files(files, target.id)

            duration = time.time() - start_time

            # Update crawl target
            self.database.update_crawl_target_status(target.target_id, "idle")

            # Log completion
            self.logger.log_crawl_completed(
                target.target_id,
                target.url,
                len(files),
                indexed_count,
                len(files) - indexed_count,  # Errors/duplicates
                duration
            )

            return CrawlResult(
                files_discovered=len(files),
                files_indexed=indexed_count,
                errors_count=len(files) - indexed_count,
                duration_seconds=duration,
                status="SUCCESS" if len(files) > 0 else "PARTIAL"
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            self.database.update_crawl_target_status(
                target.target_id,
                "error",
                error_msg
            )

            self.logger.log_crawl_error(
                target.target_id,
                target.url,
                error_msg,
                duration
            )

            return CrawlResult(
                files_discovered=0,
                files_indexed=0,
                errors_count=1,
                duration_seconds=duration,
                status="FAIL"
            )

    async def _crawl_recursive(self, url: str, server_type: str,
                             depth: int = 0, visited: Optional[set] = None) -> List[FileEntry]:
        """Recursively crawl directory listings."""
        if visited is None:
            visited = set()

        # Stop at max depth
        if depth > self.MAX_DEPTH:
            return []

        # Check if already visited
        if url in visited:
            return []

        visited.add(url)

        files = []

        # Rate limiting
        await self._rate_limit(extract_domain(url))

        try:
            # Fetch the page
            content = await self._fetch_page(url)
            if not content:
                return files

            # Parse directory listing
            parsed_files, directories, detected_type = self.parser.parse_directory_listing(
                content,
                url
            )

            # Add files to result
            for file_entry in parsed_files:
                file_entry.crawl_source_id = 0  # Will be set on insert
                files.append(file_entry)

            # Recursively crawl subdirectories
            tasks = []
            for directory in directories:
                dir_url = directory["url"]
                # Respect robots.txt (simple check for /private/, /admin/, etc.)
                if not self._should_crawl(dir_url):
                    continue

                # Create task for recursive crawl
                task = self._crawl_recursive(dir_url, detected_type, depth + 1, visited)
                tasks.append(task)

            # Await all subdirectory crawls
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, list):
                        files.extend(result)

        except Exception as e:
            print(f"Error crawling {url}: {e}")

        return files

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content."""
        if not is_valid_url(url):
            return None

        try:
            if self.session is None:
                timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
                self.session = aiohttp.ClientSession(timeout=timeout)

            async with self.session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    return await response.text()
                return None
        except asyncio.TimeoutError:
            print(f"Timeout fetching {url}")
            return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    async def _rate_limit(self, domain: str):
        """Apply rate limiting."""
        if domain not in self._last_request_time:
            self._last_request_time[domain] = 0

        elapsed = time.time() - self._last_request_time[domain]
        delay_needed = (self.RATE_LIMIT_MS / 1000.0) - elapsed

        if delay_needed > 0:
            await asyncio.sleep(delay_needed)

        self._last_request_time[domain] = time.time()

    def _should_crawl(self, url: str) -> bool:
        """Check if URL should be crawled (robots.txt rules)."""
        # Simple heuristic: skip common private paths
        private_paths = ["/private/", "/admin/", "/.well-known/", "/cgi-bin/"]
        url_lower = url.lower()

        for path in private_paths:
            if path in url_lower:
                return False

        return True

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None


class ConcurrentCrawler:
    """Manages concurrent crawling of multiple targets."""

    def __init__(self, database: Database, logger: ActivityLogger,
                 max_workers: int = 4):
        """Initialize concurrent crawler."""
        self.database = database
        self.logger = logger
        self.max_workers = max_workers

    async def crawl_all(self, targets: Optional[List[CrawlTarget]] = None) -> List[CrawlResult]:
        """Crawl all or specified targets concurrently."""
        if targets is None:
            targets = self.database.list_crawl_targets()

        # Filter to crawlable targets
        targets = [t for t in targets if t.status != "paused"]

        if not targets:
            return []

        # Create crawler instance
        crawler = Crawler(self.database, self.logger)

        try:
            # Create tasks with concurrency limit
            semaphore = asyncio.Semaphore(self.max_workers)

            async def crawl_with_semaphore(target):
                async with semaphore:
                    return await crawler.crawl_target(target)

            # Crawl targets
            tasks = [crawl_with_semaphore(t) for t in targets]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Extract results
            crawl_results = []
            for result in results:
                if isinstance(result, CrawlResult):
                    crawl_results.append(result)
                elif isinstance(result, Exception):
                    print(f"Crawl error: {result}")

            return crawl_results

        finally:
            await crawler.close()


def run_crawl_sync(database: Database, logger: ActivityLogger,
                   targets: Optional[List[CrawlTarget]] = None,
                   max_workers: int = 4) -> List[CrawlResult]:
    """Synchronous wrapper for crawling (runs async event loop)."""
    concurrent_crawler = ConcurrentCrawler(database, logger, max_workers)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        results = loop.run_until_complete(concurrent_crawler.crawl_all(targets))
        return results
    finally:
        loop.close()
