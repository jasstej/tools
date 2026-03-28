"""
Database module for FilePursuit.

Handles SQLite database operations, schema management, and full-text search.
"""

import sqlite3
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


@dataclass
class FileEntry:
    """Represents a file discovered during crawling."""
    url: str
    filename: str
    extension: str
    file_type: str
    size_bytes: int
    modified_date: str
    crawl_source_id: int
    hash_md5: Optional[str] = None
    discovered_at: Optional[str] = None
    relevance_score: float = 0.0

    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.utcnow().isoformat() + "Z"


@dataclass
class CrawlTarget:
    """Represents a crawl target (directory to index)."""
    target_id: str
    url: str
    type: str  # 'apache' or 'nginx'
    created_at: str
    last_crawl_at: Optional[str] = None
    next_crawl_at: Optional[str] = None
    status: str = "idle"  # 'idle', 'crawling', 'error', 'paused'
    error_message: Optional[str] = None
    file_count: int = 0
    id: Optional[int] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + "Z"


@dataclass
class DorkSource:
    """Represents a dork source (saved dork searches)."""
    source_id: str  # UUID
    keyword: str
    category: str  # 'video', 'audio', 'image', 'book', 'ebook', 'iso', 'document', 'source', 'archive'
    dork_queries: str  # JSON array of dork queries
    search_engine: str  # 'google', 'archive.org', 'github', 'pastebin'
    created_at: str
    results_count: int = 0
    id: Optional[int] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + "Z"


@dataclass
class SearchResult:
    """Result of a search query."""
    filename: str
    url: str
    size_bytes: int
    extension: str
    file_type: str
    modified_date: str
    relevance_score: float


@dataclass
class DorkSearchResult:
    """Result from a dork search."""
    title: str
    url: str
    snippet: str
    source_site: str  # 'google', 'archive.org', 'github', 'pastebin'
    found_at: str
    dork_template_id: Optional[int] = None
    bookmarked: bool = False
    id: Optional[int] = None


class Database:
    """SQLite database wrapper with FTS5 support."""

    FILE_TYPES = {
        'document': ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.ppt', '.pptx'],
        'archive': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso'],
        'media': ['.mp3', '.mp4', '.mkv', '.avi', '.jpg', '.png', '.gif', '.flv', '.mov'],
        'source': ['.py', '.js', '.cpp', '.java', '.go', '.rs', '.c', '.h', '.html'],
        'executable': ['.exe', '.msi', '.elf', '.bin', '.app', '.apk'],
        'other': ['*']
    }

    def __init__(self, db_path: str = "data/index.db"):
        """Initialize database connection."""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.connection = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create crawl_targets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id TEXT UNIQUE NOT NULL,
                url TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_crawl_at TEXT,
                next_crawl_at TEXT,
                status TEXT DEFAULT 'idle',
                error_message TEXT,
                file_count INTEGER DEFAULT 0
            )
        """)

        # Create files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                extension TEXT,
                file_type TEXT,
                size_bytes INTEGER,
                modified_date TEXT,
                hash_md5 TEXT UNIQUE,
                crawl_source_id INTEGER NOT NULL,
                discovered_at TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                relevance_score REAL DEFAULT 0.0,
                FOREIGN KEY(crawl_source_id) REFERENCES crawl_targets(id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_filename
            ON files(filename)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_extension
            ON files(extension)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_file_type
            ON files(file_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_size_bytes
            ON files(size_bytes)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_modified_date
            ON files(modified_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_crawl_source
            ON files(crawl_source_id)
        """)

        # Create FTS5 virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                filename,
                extension,
                file_type,
                content='files',
                content_rowid='id'
            )
        """)

        # Create search_queries table for analytics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                filters TEXT,
                result_count INTEGER,
                execution_ms REAL,
                searched_at TEXT NOT NULL,
                source_ip TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_search_queries_searched_at
            ON search_queries(searched_at)
        """)

        # Create dork_templates table (for saved dork searches)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dork_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT UNIQUE NOT NULL,
                keyword TEXT NOT NULL,
                category TEXT NOT NULL,
                dork_queries TEXT NOT NULL,  -- JSON array
                search_engine TEXT,
                created_at TEXT NOT NULL,
                results_count INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dork_templates_keyword
            ON dork_templates(keyword)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dork_templates_category
            ON dork_templates(category)
        """)

        # Create dork_search_results table (for storing results from dorks)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dork_search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                snippet TEXT,
                source_site TEXT NOT NULL,  -- 'google', 'archive.org', 'github', 'pastebin'
                dork_template_id INTEGER,
                found_at TEXT NOT NULL,
                bookmarked BOOLEAN DEFAULT 0,
                FOREIGN KEY(dork_template_id) REFERENCES dork_templates(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dork_search_results_url
            ON dork_search_results(url)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dork_search_results_source
            ON dork_search_results(source_site)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dork_search_results_found_at
            ON dork_search_results(found_at)
        """)

        conn.commit()

    def add_crawl_target(self, target: CrawlTarget) -> CrawlTarget:
        """Add a new crawl target."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO crawl_targets
            (target_id, url, type, created_at, status)
            VALUES (?, ?, ?, ?, ?)
        """, (target.target_id, target.url, target.type, target.created_at, target.status))

        target_id = cursor.lastrowid
        target.id = target_id
        conn.commit()
        return target

    def get_crawl_target(self, target_id: str) -> Optional[CrawlTarget]:
        """Get a crawl target by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM crawl_targets WHERE target_id = ?
        """, (target_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_crawl_target(row)

    def list_crawl_targets(self) -> List[CrawlTarget]:
        """List all crawl targets."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM crawl_targets ORDER BY created_at DESC")
        rows = cursor.fetchall()

        return [self._row_to_crawl_target(row) for row in rows]

    def remove_crawl_target(self, target_id: str) -> bool:
        """Remove a crawl target."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM crawl_targets WHERE target_id = ?", (target_id,))
        conn.commit()

        return cursor.rowcount > 0

    def update_crawl_target_status(self, target_id: str, status: str,
                                  error_message: Optional[str] = None):
        """Update crawl target status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE crawl_targets
            SET status = ?, error_message = ?, last_crawl_at = ?
            WHERE target_id = ?
        """, (status, error_message, datetime.utcnow().isoformat() + "Z", target_id))

        conn.commit()

    def insert_files(self, files: List[FileEntry], crawl_source_id: int) -> int:
        """Insert multiple files into database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        indexed_count = 0
        now = datetime.utcnow().isoformat() + "Z"

        for file_entry in files:
            try:
                # Skip duplicates
                cursor.execute("SELECT id FROM files WHERE url = ?", (file_entry.url,))
                if cursor.fetchone():
                    continue

                # Detect file type if not provided
                if not file_entry.file_type:
                    file_entry.file_type = self._detect_file_type(file_entry.extension)

                cursor.execute("""
                    INSERT INTO files
                    (url, filename, extension, file_type, size_bytes, modified_date,
                     crawl_source_id, discovered_at, indexed_at, relevance_score, hash_md5)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_entry.url,
                    file_entry.filename,
                    file_entry.extension,
                    file_entry.file_type,
                    file_entry.size_bytes,
                    file_entry.modified_date,
                    crawl_source_id,
                    file_entry.discovered_at,
                    now,
                    file_entry.relevance_score,
                    file_entry.hash_md5
                ))

                # Insert into FTS5 index
                file_id = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO files_fts(rowid, filename, extension, file_type)
                    VALUES (?, ?, ?, ?)
                """, (file_id, file_entry.filename, file_entry.extension, file_entry.file_type))

                indexed_count += 1
            except sqlite3.IntegrityError:
                # Duplicate or constraint violation, skip
                continue

        conn.commit()
        return indexed_count

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None,
               sort_by: str = "relevance", limit: int = 50, offset: int = 0) -> Tuple[List[SearchResult], int]:
        """Search files with FTS5."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if filters is None:
            filters = {}

        # Build WHERE clause from filters
        where_clauses = []
        params = []

        if filters.get("file_type"):
            where_clauses.append("file_type = ?")
            params.append(filters["file_type"])

        if filters.get("extension"):
            where_clauses.append("extension = ?")
            params.append(filters["extension"])

        if filters.get("min_size") is not None:
            where_clauses.append("size_bytes >= ?")
            params.append(filters["min_size"])

        if filters.get("max_size") is not None:
            where_clauses.append("size_bytes <= ?")
            params.append(filters["max_size"])

        if filters.get("after_date"):
            where_clauses.append("modified_date >= ?")
            params.append(filters["after_date"])

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = " AND " + where_sql

        # Build order by
        if sort_by == "size":
            order_sql = "ORDER BY size_bytes DESC"
        elif sort_by == "date":
            order_sql = "ORDER BY modified_date DESC"
        else:  # relevance
            order_sql = "ORDER BY relevance_score DESC, filename"

        # FTS5 search
        sql = f"""
            SELECT f.id, f.filename, f.url, f.size_bytes, f.extension,
                   f.file_type, f.modified_date, f.relevance_score
            FROM files f
            WHERE f.id IN (
                SELECT rowid FROM files_fts WHERE files_fts MATCH ?
            ){where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
        """

        # Get count first
        count_sql = f"""
            SELECT COUNT(*) FROM files f
            WHERE f.id IN (
                SELECT rowid FROM files_fts WHERE files_fts MATCH ?
            ){where_sql}
        """

        params_with_query = [query] + params
        cursor.execute(count_sql, params_with_query)
        total = cursor.fetchone()[0]

        # Get results
        cursor.execute(sql, params_with_query + [limit, offset])
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append(SearchResult(
                filename=row[1],
                url=row[2],
                size_bytes=row[3],
                extension=row[4],
                file_type=row[5],
                modified_date=row[6],
                relevance_score=row[7]
            ))

        return results, total

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM files")
        total_files = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM crawl_targets")
        targets_count = cursor.fetchone()[0]

        # Type distribution
        cursor.execute("""
            SELECT file_type, COUNT(*) as count
            FROM files
            GROUP BY file_type
            ORDER BY count DESC
        """)
        type_dist = {row[0]: row[1] for row in cursor.fetchall()}

        # Size distribution
        cursor.execute("""
            SELECT
                CASE
                    WHEN size_bytes < 1048576 THEN 'small_<1mb'
                    WHEN size_bytes < 104857600 THEN 'medium_1-100mb'
                    ELSE 'large_>100mb'
                END as size_category,
                COUNT(*) as count
            FROM files
            GROUP BY size_category
        """)
        size_dist = {row[0]: row[1] for row in cursor.fetchall()}

        # Last crawl time
        cursor.execute("""
            SELECT MAX(last_crawl_at) FROM crawl_targets
        """)
        last_crawl = cursor.fetchone()[0]

        return {
            "total_files": total_files,
            "targets_count": targets_count,
            "type_distribution": type_dist,
            "size_distribution": size_dist,
            "last_crawl": last_crawl
        }

    def add_dork_template(self, source: DorkSource) -> DorkSource:
        """Add a new dork template."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO dork_templates
            (source_id, keyword, category, dork_queries, search_engine, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source.source_id, source.keyword, source.category, source.dork_queries,
              source.search_engine, source.created_at))

        source.id = cursor.lastrowid
        conn.commit()
        return source

    def list_dork_templates(self) -> List[DorkSource]:
        """List all dork templates."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM dork_templates ORDER BY created_at DESC")
        rows = cursor.fetchall()

        return [self._row_to_dork_source(row) for row in rows]

    def get_dork_template(self, source_id: str) -> Optional[DorkSource]:
        """Get a dork template by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM dork_templates WHERE source_id = ?", (source_id,))
        row = cursor.fetchone()

        return self._row_to_dork_source(row) if row else None

    def insert_dork_results(self, results: List['DorkSearchResult'], dork_template_id: int) -> int:
        """Insert dork search results."""
        conn = self._get_connection()
        cursor = conn.cursor()

        inserted_count = 0

        for result in results:
            try:
                # Skip duplicates (URL already exists)
                cursor.execute("SELECT id FROM dork_search_results WHERE url = ?", (result.url,))
                if cursor.fetchone():
                    continue

                cursor.execute("""
                    INSERT INTO dork_search_results
                    (url, title, snippet, source_site, dork_template_id, found_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (result.url, result.title, result.snippet, result.source_site,
                      dork_template_id, result.found_at))

                inserted_count += 1
            except sqlite3.IntegrityError:
                # Duplicate, skip
                continue

        # Update result count in template
        cursor.execute("""
            UPDATE dork_templates
            SET results_count = (SELECT COUNT(*) FROM dork_search_results WHERE dork_template_id = ?)
            WHERE id = ?
        """, (dork_template_id, dork_template_id))

        conn.commit()
        return inserted_count

    def search_dork_results(self, query: str, source_site: Optional[str] = None,
                          limit: int = 50, offset: int = 0) -> Tuple[List['DorkSearchResult'], int]:
        """Search dork results by keyword."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build query
        where_clauses = ["(title LIKE ? OR snippet LIKE ?)"]
        params = [f"%{query}%", f"%{query}%"]

        if source_site:
            where_clauses.append("source_site = ?")
            params.append(source_site)

        where_sql = " AND ".join(where_clauses)

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM dork_search_results WHERE {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        # Get results
        results_sql = f"""
            SELECT * FROM dork_search_results
            WHERE {where_sql}
            ORDER BY found_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(results_sql, params + [limit, offset])
        rows = cursor.fetchall()

        results = [self._row_to_dork_result(row) for row in rows]
        return results, total

    def get_bookmarks(self, limit: int = 100) -> List['DorkSearchResult']:
        """Get bookmarked dork results."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM dork_search_results
            WHERE bookmarked = 1
            ORDER BY found_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        return [self._row_to_dork_result(row) for row in rows]

    def toggle_bookmark(self, result_id: int, bookmarked: bool):
        """Toggle bookmark status for a result."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE dork_search_results
            SET bookmarked = ?
            WHERE id = ?
        """, (1 if bookmarked else 0, result_id))

        conn.commit()

    @staticmethod
    def _row_to_dork_source(row) -> DorkSource:
        """Convert database row to DorkSource dataclass."""
        return DorkSource(
            id=row[0],
            source_id=row[1],
            keyword=row[2],
            category=row[3],
            dork_queries=row[4],
            search_engine=row[5],
            created_at=row[6],
            results_count=row[7]
        )

    @staticmethod
    def _row_to_dork_result(row) -> 'DorkSearchResult':
        """Convert database row to DorkSearchResult dataclass."""
        return DorkSearchResult(
            id=row[0],
            url=row[1],
            title=row[2],
            snippet=row[3],
            source_site=row[4],
            dork_template_id=row[5],
            found_at=row[6],
            bookmarked=bool(row[7])
        )

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    @staticmethod
    def _detect_file_type(extension: str) -> str:
        """Detect file type from extension."""
        ext = extension.lower()
        for file_type, extensions in Database.FILE_TYPES.items():
            if ext in extensions:
                return file_type
        return "other"

    @staticmethod
    def _row_to_crawl_target(row) -> CrawlTarget:
        """Convert database row to CrawlTarget dataclass."""
        return CrawlTarget(
            id=row[0],
            target_id=row[1],
            url=row[2],
            type=row[3],
            created_at=row[4],
            last_crawl_at=row[5],
            next_crawl_at=row[6],
            status=row[7],
            error_message=row[8],
            file_count=row[9]
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
