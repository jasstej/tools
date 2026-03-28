"""
FilePursuit - Distributed file search engine for public file indexes.

Crawls Apache/Nginx directory listings, FTP servers, and indexes files
for fast keyword search with type and size filtering.
"""

__version__ = "1.0.0"
__author__ = "FilePursuit Contributors"
__license__ = "MIT"

from .database import Database, FileEntry, CrawlTarget
from .logger import ActivityLogger
from .auth import MasterTokenManager
from .search_engine import SearchEngine
from .crawler import Crawler, CrawlResult

__all__ = [
    "Database",
    "FileEntry",
    "CrawlTarget",
    "ActivityLogger",
    "MasterTokenManager",
    "SearchEngine",
    "Crawler",
    "CrawlResult",
]
