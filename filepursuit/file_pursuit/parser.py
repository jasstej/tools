"""
Directory listing parser for FilePursuit.

Parses Apache/Nginx directory listing HTML pages to extract file metadata.
"""

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from lxml import html
from .database import FileEntry
from .utils import normalize_filename, parse_http_date, extract_extension


class DirectoryParser:
    """Parse Apache/Nginx directory listings."""

    # Apache directory listing signature patterns
    APACHE_SIGNATURES = [
        r"<h1>Index of",
        r"<title>Index of",
        r"Apache Server at",
    ]

    # Nginx directory listing signature patterns
    NGINX_SIGNATURES = [
        r"<h1>.*directory listing",
        r"nginx",
        r"<title>\[directory\]",
    ]

    def __init__(self):
        """Initialize parser."""
        pass

    def parse_directory_listing(self, content: str, base_url: str) -> tuple:
        """
        Parse directory listing HTML.

        Returns:
            (files, directories, detected_server_type)
        """
        if not content:
            return [], [], "unknown"

        try:
            tree = html.fromstring(content)
        except Exception:
            return [], [], "unknown"

        # Detect server type
        server_type = self._detect_server_type(content)

        # Parse based on server type
        if "nginx" in server_type.lower():
            return self._parse_nginx_listing(tree, base_url, content)
        elif "apache" in server_type.lower():
            return self._parse_apache_listing(tree, base_url, content)
        else:
            # Try both parsers
            files, dirs = self._parse_apache_listing(tree, base_url, content)[:2]
            if not files and not dirs:
                files, dirs = self._parse_nginx_listing(tree, base_url, content)[:2]
            return files, dirs, server_type

    def _detect_server_type(self, content: str) -> str:
        """Detect if Apache or Nginx directory listing."""
        content_lower = content.lower()

        for sig in self.APACHE_SIGNATURES:
            if re.search(sig, content, re.IGNORECASE):
                return "apache"

        for sig in self.NGINX_SIGNATURES:
            if re.search(sig, content, re.IGNORECASE):
                return "nginx"

        # Heuristic: Check for typical Apache/Nginx response headers in HTML
        if "apache" in content_lower:
            return "apache"
        if "nginx" in content_lower:
            return "nginx"

        return "unknown"

    def _parse_apache_listing(self, tree, base_url: str, content: str) -> tuple:
        """Parse Apache mod_autoindex directory listing."""
        files = []
        directories = []

        try:
            # Look for the file listing table
            rows = tree.xpath("//tr")

            for row in rows[1:]:  # Skip header row
                cells = row.xpath("td")
                if len(cells) < 4:
                    continue

                # Extract filename (from link)
                link = cells[0].xpath("a/@href")
                if not link:
                    continue

                link_text = cells[0].xpath("a/text()")
                if not link_text:
                    continue

                href = link[0]
                filename = link_text[0].strip()

                # Skip parent directory link
                if filename in ["..", "Parent Directory"]:
                    continue

                # Extract size
                size_text = cells[1].xpath("text()")
                size_bytes = self._parse_size(size_text[0] if size_text else "")

                # Extract modified date
                date_text = cells[2].xpath("string()")
                modified_date = parse_http_date(date_text)

                # Extract description (if present)
                desc_text = cells[3].xpath("text()")

                # Determine if file or directory
                is_dir = href.endswith("/") or "[DIR]" in desc_text[0] if desc_text else False

                # Normalize filename
                filename_clean = normalize_filename(filename)
                full_url = urljoin(base_url, href)

                if is_dir:
                    directories.append({
                        "name": filename_clean,
                        "url": full_url,
                        "type": "directory"
                    })
                else:
                    ext = extract_extension(filename_clean)
                    files.append(FileEntry(
                        url=full_url,
                        filename=filename_clean,
                        extension=ext,
                        file_type="",
                        size_bytes=size_bytes,
                        modified_date=modified_date or datetime.utcnow().isoformat() + "Z",
                        crawl_source_id=0,  # Will be set during insertion
                    ))

        except Exception as e:
            print(f"Error parsing Apache listing: {e}")

        return files, directories, "apache"

    def _parse_nginx_listing(self, tree, base_url: str, content: str) -> tuple:
        """Parse Nginx directory listing (simpler format)."""
        files = []
        directories = []

        try:
            # Nginx listings typically use <pre> or tables
            # Look for links in pre blocks or tables

            # Try table format first
            rows = tree.xpath("//table//tr")
            if rows:
                for row in rows[1:]:  # Skip header
                    cells = row.xpath("td|th")
                    if len(cells) < 3:
                        continue

                    # Extract link
                    links = cells[0].xpath("a/@href")
                    if not links:
                        continue

                    link_text = cells[0].xpath("a/text()")
                    if not link_text:
                        continue

                    href = links[0]
                    filename = link_text[0].strip()

                    # Skip parent directory
                    if filename in ["..", "Parent Directory"]:
                        continue

                    # Extract size
                    size_text = cells[1].xpath("text()")
                    size_bytes = self._parse_size(size_text[0] if size_text else "")

                    # Extract date
                    date_text = cells[2].xpath("text()")
                    modified_date = parse_http_date("".join(date_text) if date_text else "")

                    # Determine if directory
                    is_dir = href.endswith("/")

                    filename_clean = normalize_filename(filename)
                    full_url = urljoin(base_url, href)

                    if is_dir:
                        directories.append({
                            "name": filename_clean,
                            "url": full_url,
                            "type": "directory"
                        })
                    else:
                        ext = extract_extension(filename_clean)
                        files.append(FileEntry(
                            url=full_url,
                            filename=filename_clean,
                            extension=ext,
                            file_type="",
                            size_bytes=size_bytes,
                            modified_date=modified_date or datetime.utcnow().isoformat() + "Z",
                            crawl_source_id=0,
                        ))

            # Try pre format (fallback)
            if not rows:
                pre_text = tree.xpath("//pre/text()")
                if pre_text:
                    content_text = "".join(pre_text)
                    # Parse nginx pre format: "filename           size     date"
                    for line in content_text.split("\n"):
                        line = line.strip()
                        if not line or line.startswith("..") or line.startswith("total"):
                            continue

                        # Regex: filename (with optional / for directories), size, date
                        match = re.match(r"^(.+?)\s+(\d+|-)\s+(\w+.*)", line)
                        if not match:
                            continue

                        filename = match.group(1).strip()
                        size_str = match.group(2)
                        date_str = match.group(3)

                        # Skip if not a valid entry
                        if not filename:
                            continue

                        is_dir = filename.endswith("/")
                        filename_clean = normalize_filename(filename)

                        full_url = urljoin(base_url, filename)

                        if is_dir:
                            directories.append({
                                "name": filename_clean,
                                "url": full_url,
                                "type": "directory"
                            })
                        else:
                            size_bytes = self._parse_size(size_str)
                            ext = extract_extension(filename_clean)
                            modified_date = parse_http_date(date_str)

                            files.append(FileEntry(
                                url=full_url,
                                filename=filename_clean,
                                extension=ext,
                                file_type="",
                                size_bytes=size_bytes,
                                modified_date=modified_date or datetime.utcnow().isoformat() + "Z",
                                crawl_source_id=0,
                            ))

        except Exception as e:
            print(f"Error parsing Nginx listing: {e}")

        return files, directories, "nginx"

    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes."""
        if not size_str or size_str == "-":
            return 0

        size_str = size_str.strip().upper()

        # Try to parse as plain bytes
        try:
            return int(size_str)
        except ValueError:
            pass

        # Parse with units
        units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}

        for unit, multiplier in units.items():
            if unit in size_str:
                try:
                    num = float(size_str.replace(unit, "").strip())
                    return int(num * multiplier)
                except ValueError:
                    continue

        return 0
