"""
Dork Executor for FilePursuit.

Executes dork queries and fetches results from different sources.
"""

import time
import requests
from typing import List, Dict, Optional
from .dork_generator import DorkQuery, DorkGenerator
from .dork_parser import DorkResult, DorkParser


class DorkExecutor:
    """Execute dorks and fetch results."""

    # User-Agent string
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    # Request timeout
    REQUEST_TIMEOUT = 10

    # Rate limiting - delay between requests (seconds)
    RATE_LIMIT = 1.0

    # Maximum retries
    MAX_RETRIES = 2

    def __init__(self):
        """Initialize executor."""
        self.generator = DorkGenerator()
        self.parser = DorkParser()
        self._last_request_time = {}

    def execute_dork(self, dork_query: DorkQuery, api_key: Optional[str] = None) -> List[DorkResult]:
        """
        Execute a single dork query.

        Args:
            dork_query: DorkQuery object with query and site
            api_key: Optional API key for enhanced search (Shodan, Google, etc.)

        Returns:
            List of DorkResult objects
        """
        # Apply rate limiting
        self._rate_limit(dork_query.site)

        if dork_query.site == "google":
            return self._execute_google_dork(dork_query.query)
        elif dork_query.site == "archive.org":
            return self._execute_archive_dork(dork_query.query)
        elif dork_query.site == "github":
            return self._execute_github_dork(dork_query.query, api_key)
        elif dork_query.site == "pastebin":
            return self._execute_pastebin_dork(dork_query.query)
        else:
            return []

    def execute_dorks_batch(self, keyword: str, category: str, generated_by_site: Optional[Dict] = None) -> Dict[str, List[DorkResult]]:
        """
        Execute all dorks for a keyword and category.

        Args:
            keyword: Search keyword
            category: File category
            generated_by_site: Pre-generated dorks by site (if None, generates new ones)

        Returns:
            Dict mapping site to list of results
        """
        if generated_by_site is None:
            # Generate dorks for category
            dorks = self.generator.generate_dorks(keyword, category)
            generated_by_site = {}
            for dork in dorks:
                if dork.site not in generated_by_site:
                    generated_by_site[dork.site] = []
                generated_by_site[dork.site].append(dork)
        else:
            # Convert existing dorks
            dorks = []
            for site, site_dorks in generated_by_site.items():
                dorks.extend(site_dorks)

        # Execute dorks
        results_by_site = {}

        for dork in dorks:
            results = self.execute_dork(dork)
            if dork.site not in results_by_site:
                results_by_site[dork.site] = []
            results_by_site[dork.site].extend(results)

        return results_by_site

    def _execute_google_dork(self, dork_query: str) -> List[DorkResult]:
        """Execute Google dork query."""
        try:
            # Use Google search via URL parameters
            search_url = "https://www.google.com/search"
            params = {
                "q": dork_query,
                "num": 10,  # Return up to 10 results
            }

            headers = {"User-Agent": self.USER_AGENT}

            response = requests.get(
                search_url,
                params=params,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT,
                allow_redirects=True
            )

            if response.status_code == 200:
                results = self.parser.parse_google_results(response.text, dork_query)
                return results

            return []

        except Exception as e:
            print(f"Error executing Google dork: {e}")
            return []

    def _execute_archive_dork(self, dork_query: str) -> List[DorkResult]:
        """Execute archive.org search."""
        try:
            # archive.org has a direct search API
            search_url = "https://archive.org/advancedsearch.php"
            params = {
                "q": dork_query,
                "fl": ["identifier", "title", "date", "size"],
                "output": "json",
                "rows": 50,
            }

            headers = {"User-Agent": self.USER_AGENT}

            response = requests.get(
                search_url,
                params=params,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                try:
                    json_data = response.json()
                    results = []

                    for doc in json_data.get("response", {}).get("docs", []):
                        identifier = doc.get("identifier", "")
                        title = doc.get("title", identifier)
                        date_str = doc.get("date", "")
                        size = doc.get("size", 0)

                        url = f"https://archive.org/details/{identifier}"
                        snippet = f"Date: {date_str} | Size: {size} bytes"

                        results.append(DorkResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source_site="archive.org",
                            confidence=0.95
                        ))

                    return results
                except Exception as e:
                    print(f"Error parsing archive.org JSON: {e}")
                    return []

            return []

        except Exception as e:
            print(f"Error executing archive.org search: {e}")
            return []

    def _execute_github_dork(self, dork_query: str, api_key: Optional[str] = None) -> List[DorkResult]:
        """Execute GitHub search via API."""
        try:
            search_url = "https://api.github.com/search/code"
            params = {
                "q": dork_query,
                "per_page": 30,
            }

            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "application/vnd.github.v3+json"
            }

            # Add API key if provided
            if api_key:
                headers["Authorization"] = f"token {api_key}"

            response = requests.get(
                search_url,
                params=params,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                json_data = response.json()
                results = []

                for item in json_data.get("items", [])[:10]:
                    name = item.get("name", "")
                    url = item.get("html_url", "")
                    repo = item.get("repository", {})
                    repo_url = repo.get("html_url", "")

                    snippet = f"Repo: {repo.get('full_name', '')} | Language: {repo.get('language', 'Unknown')}"

                    results.append(DorkResult(
                        title=f"{name} ({repo.get('full_name', '')})",
                        url=url or repo_url,
                        snippet=snippet,
                        source_site="github",
                        confidence=0.95
                    ))

                return results

            return []

        except Exception as e:
            print(f"Error executing GitHub search: {e}")
            return []

    def _execute_pastebin_dork(self, dork_query: str) -> List[DorkResult]:
        """Execute pastebin search."""
        try:
            # Pastebin search via direct URL
            search_url = "https://pastebin.com/search"
            params = {
                "q": dork_query,
                "ps": "submit_search",
            }

            headers = {"User-Agent": self.USER_AGENT}

            response = requests.get(
                search_url,
                params=params,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT,
                allow_redirects=True
            )

            if response.status_code == 200:
                results = self.parser.parse_pastebin_results(response.text, dork_query)
                return results

            return []

        except Exception as e:
            print(f"Error executing pastebin search: {e}")
            return []

    def _rate_limit(self, site: str):
        """Apply rate limiting per site."""
        if site not in self._last_request_time:
            self._last_request_time[site] = 0

        elapsed = time.time() - self._last_request_time[site]
        delay_needed = self.RATE_LIMIT - elapsed

        if delay_needed > 0:
            time.sleep(delay_needed)

        self._last_request_time[site] = time.time()

    @staticmethod
    def get_all_results(results_by_site: Dict[str, List[DorkResult]]) -> List[DorkResult]:
        """Get all results combined and deduplicated."""
        all_results = []
        for results in results_by_site.values():
            all_results.extend(results)

        # Merge and deduplicate
        return DorkParser.merge_results(results_by_site)

    @staticmethod
    def is_file_url(url: str) -> bool:
        """Check if URL likely points to a file."""
        # Check for common file extensions
        file_extensions = [
            '.mp4', '.mp3', '.pdf', '.zip', '.exe', '.iso', '.rar',
            '.mkv', '.avi', '.mov', '.flac', '.wav', '.png', '.jpg',
            '.epub', '.mobi', '.docx', '.xlsx', '.pptx', '.py', '.js'
        ]

        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in file_extensions)
