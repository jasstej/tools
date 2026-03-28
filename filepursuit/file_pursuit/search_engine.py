"""
Search engine module for FilePursuit.

Handles full-text search with relevance ranking and filtering.
"""

import time
from typing import List, Dict, Any, Tuple, Optional
from .database import Database, SearchResult


class SearchEngine:
    """Full-text search engine with relevance ranking."""

    def __init__(self, database: Database):
        """Initialize search engine."""
        self.database = database

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None,
               sort_by: str = "relevance", limit: int = 50, offset: int = 0) -> Tuple[List[SearchResult], int, float]:
        """
        Search the index.

        Args:
            query: Search query
            filters: Filter dict with keys: file_type, extension, min_size, max_size, after_date
            sort_by: Sort order (relevance, size, date)
            limit: Results per page
            offset: Pagination offset

        Returns:
            (results, total_count, execution_time_ms)
        """
        start_time = time.time()

        if filters is None:
            filters = {}

        # Normalize query
        query = query.strip()
        if not query:
            return [], 0, 0.0

        # Tokenize query for better matching
        query_tokens = query.split()

        # Search with improved query (quote for exact phrases)
        # FTS5 queries: Use AND, OR, NOT operators
        fts_query = " AND ".join(query_tokens) if query_tokens else query

        try:
            results, total = self.database.search(
                fts_query,
                filters=filters,
                sort_by=sort_by,
                limit=limit,
                offset=offset
            )

            # Compute relevance scores
            for result in results:
                result.relevance_score = self._compute_relevance_score(
                    result.filename,
                    query,
                    result.size_bytes
                )

            # Re-sort if by relevance
            if sort_by == "relevance":
                results.sort(key=lambda r: r.relevance_score, reverse=True)

            execution_time = (time.time() - start_time) * 1000  # ms

            return results, total, execution_time

        except Exception as e:
            print(f"Search error: {e}")
            return [], 0, 0.0

    def _compute_relevance_score(self, filename: str, query: str, size_bytes: int) -> float:
        """
        Compute relevance score for a file.

        Scoring criteria:
        - Exact filename match: +100
        - Query words at start: +50 each
        -Query word substring: +20 each
        - Filename length penalty: prefer shorter names
        - Size preference: prefer smaller files
        """
        score = 0.0
        filename_lower = filename.lower()
        query_lower = query.lower()

        # Exact match (full filename)
        if filename_lower == query_lower:
            score += 100

        # Query matches at start of filename
        query_words = query_lower.split()
        for word in query_words:
            if filename_lower.startswith(word):
                score += 50
            elif word in filename_lower:
                # Count occurrences
                count = filename_lower.count(word)
                score += 20 * count

        # Filename length bonus (prefer shorter, more specific names)
        # Penalty: -0.1 per character over 20
        if len(filename) > 20:
            score -= (len(filename) - 20) * 0.1

        # Size bonus (prefer smaller files for high relevance)
        # Bonus: 10 * (1 - log(size) / log(1GB))
        max_size = 1024 ** 3  # 1GB reference
        if size_bytes > 0:
            size_score = 10 * max(0, 1 - (size_bytes / max_size))
            score += size_score

        return max(0, score)

    def suggest_corrections(self, query: str, max_suggestions: int = 5) -> List[str]:
        """
        Suggest corrections/alternatives for a query.

        (Placeholder for Phase 2 - semantic search)
        """
        # For MVP, just return empty
        return []

    def get_popular_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular search queries."""
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT query, COUNT(*) as count, AVG(result_count) as avg_results
                FROM search_queries
                WHERE searched_at > datetime('now', '-30 days')
                GROUP BY query
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [
                {
                    "query": row[0],
                    "search_count": row[1],
                    "avg_results": int(row[2])
                }
                for row in rows
            ]
        except Exception:
            return []

    def get_trending_extensions(self, days: int = 7) -> Dict[str, int]:
        """Get trending file types in recent searches."""
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.extension, COUNT(*) as count
                FROM search_queries sq
                JOIN files f ON 1=1
                WHERE sq.searched_at > datetime('now', ? || ' days')
                GROUP BY f.extension
                ORDER BY count DESC
                LIMIT 20
            """, (f"-{days}",))

            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows} if rows else {}
        except Exception:
            return {}
