"""
Dork Result Parser for FilePursuit.

Parses search results from various sources (Google, archive.org, GitHub, pastebin).
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
from urllib.parse import urlparse, parse_qs


@dataclass
class DorkResult:
    """Represents a single search result from dork execution."""
    title: str
    url: str
    snippet: str
    source_site: str  # 'google', 'archive.org', 'github', 'pastebin'
    found_at: str = ""
    confidence: float = 1.0  # 0.0 to 1.0 (how sure we are about the result)

    def __post_init__(self):
        if not self.found_at:
            self.found_at = datetime.utcnow().isoformat() + "Z"


class DorkParser:
    """Parse search results from different sources."""

    def __init__(self):
        """Initialize parser."""
        pass

    def parse_google_results(self, html: str, keyword: str) -> List[DorkResult]:
        """
        Parse Google search results from HTML.

        Args:
            html: Google search results HTML
            keyword: Original search keyword

        Returns:
            List of DorkResult objects
        """
        try:
            from lxml import html as lxml_html
        except ImportError:
            # Fallback if lxml not available
            return []

        results = []

        try:
            tree = lxml_html.fromstring(html)

            # Google results are in <div class="g">... structure
            # Find all result divs
            result_divs = tree.xpath('//div[@class="g"]')

            for div in result_divs:
                # Extract title from <h3><a>
                title_elem = div.xpath('.//h3/a/text()')
                title = title_elem[0] if title_elem else "Unknown"

                # Extract URL from <a href>
                url_elems = div.xpath('.//h3/a/@href')
                if not url_elems:
                    continue
                url = url_elems[0]

                # Skip /url?q=... format, extract actual URL
                if '/url?q=' in url:
                    try:
                        url = url.split('/url?q=')[1].split('&')[0]
                    except IndexError:
                        pass

                # Extract snippet from <div class="VwiC3b">
                snippet_elem = div.xpath('.//div[@class="VwiC3b"]/span/text()')
                snippet = snippet_elem[0] if snippet_elem else ""

                # Clean up title and snippet
                title = title.strip()
                snippet = snippet.strip()

                if url and title:
                    results.append(DorkResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source_site="google",
                        confidence=0.95  # Google results are mostly reliable
                    ))

        except Exception as e:
            print(f"Error parsing Google results: {e}")

        return results

    def parse_archive_results(self, html: str, keyword: str) -> List[DorkResult]:
        """
        Parse archive.org search results.

        Args:
            html: archive.org HTML response
            keyword: Original search keyword

        Returns:
            List of DorkResult objects
        """
        try:
            from lxml import html as lxml_html
        except ImportError:
            return []

        results = []

        try:
            tree = lxml_html.fromstring(html)

            # archive.org results are in <div class="search-result">
            result_divs = tree.xpath('//div[@class="search-result"]')

            for div in result_divs:
                # Extract title/link
                link_elem = div.xpath('.//a[@class="titleline"]/@href')
                if not link_elem:
                    continue
                url = link_elem[0]

                # Extract title
                title_elem = div.xpath('.//a[@class="titleline"]/text()')
                title = title_elem[0] if title_elem else urlparse(url).path.split('/')[-1]

                # Extract file size info as snippet
                size_elem = div.xpath('.//span[@class="filesize"]/text()')
                size_str = size_elem[0] if size_elem else ""

                # Extract date
                date_elem = div.xpath('.//span[@class="date"]/text()')
                date_str = date_elem[0] if date_elem else ""

                snippet = f"Size: {size_str} | Uploaded: {date_str}".strip()

                results.append(DorkResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_site="archive.org",
                    confidence=0.90
                ))

        except Exception as e:
            print(f"Error parsing archive.org results: {e}")

        return results

    def parse_github_results(self, json_response: Dict) -> List[DorkResult]:
        """
        Parse GitHub API search results (JSON).

        Args:
            json_response: GitHub API JSON response

        Returns:
            List of DorkResult objects
        """
        results = []

        try:
            items = json_response.get("items", [])

            for item in items:
                url = item.get("html_url", "")
                title = item.get("name", "") or item.get("full_name", "")
                snippet = item.get("description", "")

                if not url or not title:
                    continue

                results.append(DorkResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_site="github",
                    confidence=0.95
                ))

        except Exception as e:
            print(f"Error parsing GitHub results: {e}")

        return results

    def parse_pastebin_results(self, html: str, keyword: str) -> List[DorkResult]:
        """
        Parse pastebin.com search results.

        Args:
            html: pastebin HTML response
            keyword: Original search keyword

        Returns:
            List of DorkResult objects
        """
        try:
            from lxml import html as lxml_html
        except ImportError:
            return []

        results = []

        try:
            tree = lxml_html.fromstring(html)

            # Pastebin results are usually in <div class="mymain">
            # Each result is a <div class="paste_wrap">
            result_divs = tree.xpath('//div[@class="paste_wrap"]')

            for div in result_divs:
                # Extract pastebin url from <a> tag
                link_elems = div.xpath('.//a[contains(@href, "/")]/@href')
                if not link_elems:
                    continue

                url = f"https://pastebin.com{link_elems[0]}"

                # Extract title
                title_elems = div.xpath('.//a[contains(@href, "/")]/text()')
                title = title_elems[0] if title_elems else "Untitled Paste"

                # Extract metadata (language, date)
                meta_elems = div.xpath('.//span[@class="date"]/text()')
                snippet = meta_elems[0] if meta_elems else ""

                results.append(DorkResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_site="pastebin",
                    confidence=0.80  # Lower confidence for pastebin
                ))

        except Exception as e:
            print(f"Error parsing pastebin results: {e}")

        return results

    def parse_generic_html(self, html: str, selector_config: Dict) -> List[DorkResult]:
        """
        Parse generic HTML results using CSS selectors.

        Args:
            html: HTML response
            selector_config: Dict with selectors for title, url, snippet

        Returns:
            List of DorkResult objects
        """
        try:
            from lxml import html as lxml_html
        except ImportError:
            return []

        results = []

        try:
            tree = lxml_html.fromstring(html)

            # Extract using provided selectors
            title_selector = selector_config.get("title_selector", "//h1")
            url_selector = selector_config.get("url_selector", "//a/@href")
            snippet_selector = selector_config.get("snippet_selector", "//p")

            result_items = tree.xpath(selector_config.get("result_selector", "//div"))

            for item in result_items:
                titles = item.xpath(title_selector + "/text()")
                urls = item.xpath(url_selector)
                snippets = item.xpath(snippet_selector + "/text()")

                if titles and urls:
                    results.append(DorkResult(
                        title=titles[0].strip(),
                        url=urls[0],
                        snippet=snippets[0].strip() if snippets else "",
                        source_site="custom",
                        confidence=0.70
                    ))

        except Exception as e:
            print(f"Error parsing generic HTML: {e}")

        return results

    @staticmethod
    def merge_results(results_by_source: Dict[str, List[DorkResult]]) -> List[DorkResult]:
        """
        Merge results from multiple sources and deduplicate.

        Args:
            results_by_source: Dict mapping source to list of results

        Returns:
            Merged and deduplicated list
        """
        # Merge all results
        all_results = []
        for results in results_by_source.values():
            all_results.extend(results)

        # Deduplicate by URL
        seen_urls = set()
        deduplicated = []

        for result in all_results:
            # Normalize URL
            url_lower = result.url.lower().rstrip('/')

            if url_lower not in seen_urls:
                seen_urls.add(url_lower)
                deduplicated.append(result)

        return deduplicated

    @staticmethod
    def sort_by_confidence(results: List[DorkResult]) -> List[DorkResult]:
        """Sort results by confidence score (highest first)."""
        return sorted(results, key=lambda r: r.confidence, reverse=True)

    @staticmethod
    def filter_by_source(results: List[DorkResult], source: str) -> List[DorkResult]:
        """Filter results by source site."""
        return [r for r in results if r.source_site == source]
