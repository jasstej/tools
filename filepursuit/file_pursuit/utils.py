"""
Utility functions for FilePursuit.
"""

import os
import re
from urllib.parse import urljoin, urlparse
from typing import Optional
from pathlib import Path


def sanitize_path(path: str) -> str:
    """Sanitize path to prevent directory traversal attacks."""
    # Remove null bytes
    if "\x00" in path:
        path = path.replace("\x00", "")

    # Normalize path
    path = os.path.normpath(path)

    # Remove leading slashes and parent directory references
    while path.startswith(".."):
        path = path[2:]
        if path.startswith("/"):
            path = path[1:]

    return path


def parse_size(size_str: str) -> int:
    """Parse size string (e.g., '1.5M', '2G') to bytes."""
    size_str = size_str.strip().upper()

    # Handle plain bytes
    try:
        return int(size_str)
    except ValueError:
        pass

    # Parse with units
    units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}

    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                return int(float(size_str[:-1]) * multiplier)
            except ValueError:
                return 0

    return 0


def is_valid_url(url: str) -> bool:
    """Validate URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme in ["http", "https"], result.netloc])
    except Exception:
        return False


def join_urls(base: str, relative: str) -> str:
    """Join base URL with relative URL."""
    return urljoin(base, relative)


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


def extract_extension(filename: str) -> str:
    """Extract file extension."""
    if not filename:
        return ""
    name = filename.lower()
    # Remove URL parameters
    if "?" in name:
        name = name.split("?")[0]
    # Remove fragments
    if "#" in name:
        name = name.split("#")[0]

    # Extract extension
    if "." in name:
        ext = name.rsplit(".", 1)[-1]
        # Validate extension (max 10 chars, alphanumeric only)
        if len(ext) <= 10 and ext.isalnum():
            return f".{ext}"

    return ""


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def truncate_string(s: str, max_len: int = 50) -> str:
    """Truncate string to max length with ellipsis."""
    if len(s) <= max_len:
        return s
    return s[:max_len-3] + "..."


def is_file_url(url: str) -> bool:
    """Check if URL looks like a file (has extension)."""
    # Remove query params and fragments
    clean_url = url.split("?")[0].split("#")[0]
    return "." in clean_url.split("/")[-1]


def is_directory_url(url: str) -> bool:
    """Check if URL looks like a directory."""
    clean_url = url.rstrip("/")
    # Directory if no extension in last part, or ends with /
    return not is_file_url(clean_url) or url.endswith("/")


def parse_http_date(date_str: str) -> Optional[str]:
    """Parse HTTP date format to ISO format."""
    if not date_str or date_str == "-":
        return None

    # Common formats: "28-Mar-2026 14:30:00 UTC" or "2026-03-28T14:30:00Z"
    try:
        from datetime import datetime
        # Try ISO format first
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            # Try Apache/Nginx format
            import email.utils
            dt = email.utils.parsedate_to_datetime(date_str)

        return dt.isoformat() if dt else None
    except Exception:
        return None


def normalize_filename(filename: str) -> str:
    """Normalize filename."""
    # Decode URL encoding if present
    try:
        from urllib.parse import unquote
        filename = unquote(filename)
    except Exception:
        pass

    # Remove trailing slashes
    filename = filename.rstrip("/")

    return filename
