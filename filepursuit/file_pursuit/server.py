"""
HTTP Server module for FilePursuit.

Provides REST API and serves the web UI.
"""

import json
import os
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, urljoin
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from .database import Database
from .search_engine import SearchEngine
from .crawler import run_crawl_sync, ConcurrentCrawler
from .auth import MasterTokenManager
from .logger import ActivityLogger


class FilePursuitHandler(BaseHTTPRequestHandler):
    """HTTP request handler for FilePursuit API."""

    # Class variables (shared across instances)
    database: Optional[Database] = None
    search_engine: Optional[SearchEngine] = None
    logger: Optional[ActivityLogger] = None
    token_manager: Optional[MasterTokenManager] = None
    ui_path: Optional[str] = None

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_string = parsed_url.query
        params = parse_qs(query_string)

        # Parse single-value parameters
        def get_param(key, default=""):
            return params.get(key, [default])[0]

        try:
            # API Routes
            if path == "/api/search":
                self._handle_search(get_param)

            elif path == "/api/stats":
                self._handle_stats()

            elif path == "/api/targets":
                self._handle_get_targets()

            elif path == "/api/crawl/status":
                self._handle_crawl_status(get_param)

            elif path == "/admin":
                self._handle_admin_page()

            elif path == "/":
                self._handle_index()

            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            print(f"Error handling {path}: {e}")
            self._send_error(500, "Internal Server Error")

    def do_POST(self):
        """Handle POST requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            # API Routes
            if path == "/api/targets":
                self._handle_add_target(data)

            elif path == "/api/crawl":
                self._handle_crawl_trigger(data)

            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            print(f"Error handling POST {path}: {e}")
            self._send_error(500, "Internal Server Error")

    def do_DELETE(self):
        """Handle DELETE requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        try:
            if path.startswith("/api/targets/"):
                target_id = path.split("/")[-1]
                self._handle_delete_target(target_id)
            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            print(f"Error handling DELETE {path}: {e}")
            self._send_error(500, "Internal Server Error")

    # Handler methods

    def _handle_search(self, get_param):
        """Handle search API requests."""
        query = get_param("q", "")
        file_type = get_param("type", "")
        min_size = get_param("min_size", "")
        max_size = get_param("max_size", "")
        sort_by = get_param("sort", "relevance")
        limit_str = get_param("limit", "50")
        offset_str = get_param("offset", "0")

        try:
            limit = int(limit_str)
            offset = int(offset_str)
        except ValueError:
            limit = 50
            offset = 0

        # Build filters
        filters = {}
        if file_type:
            filters["file_type"] = file_type
        if min_size:
            try:
                filters["min_size"] = int(min_size)
            except ValueError:
                pass
        if max_size:
            try:
                filters["max_size"] = int(max_size)
            except ValueError:
                pass

        # Search
        results, total, exec_time = self.search_engine.search(
            query,
            filters=filters,
            sort_by=sort_by,
            limit=limit,
            offset=offset
        )

        # Log search
        self.logger.log_search(
            query,
            filters,
            len(results),
            exec_time,
            self.client_address[0]
        )

        # Format response
        response = {
            "query": query,
            "results": [
                {
                    "filename": r.filename,
                    "url": r.url,
                    "size_bytes": r.size_bytes,
                    "extension": r.extension,
                    "file_type": r.file_type,
                    "modified_date": r.modified_date,
                    "relevance_score": round(r.relevance_score, 2)
                }
                for r in results
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
            "query_time_ms": round(exec_time, 2)
        }

        self._send_json(200, response)

    def _handle_stats(self):
        """Handle stats API request."""
        stats = self.database.get_stats()
        self._send_json(200, stats)

    def _handle_get_targets(self):
        """Handle get targets API request."""
        if not self._check_auth():
            self._send_error(401, "Unauthorized")
            return

        targets = self.database.list_crawl_targets()
        response = [
            {
                "target_id": t.target_id,
                "url": t.url,
                "type": t.type,
                "status": t.status,
                "file_count": t.file_count,
                "created_at": t.created_at,
                "last_crawl_at": t.last_crawl_at
            }
            for t in targets
        ]

        self._send_json(200, response)

    def _handle_add_target(self, data):
        """Handle add target API request."""
        if not self._check_auth():
            self._send_error(401, "Unauthorized")
            return

        url = data.get("url", "").strip()
        target_type = data.get("type", "apache")

        if not url:
            self._send_error(400, "Missing URL")
            return

        if target_type not in ["apache", "nginx"]:
            self._send_error(400, "Invalid type")
            return

        try:
            from .database import CrawlTarget
            import uuid

            target = CrawlTarget(
                target_id=str(uuid.uuid4()),
                url=url,
                type=target_type,
                created_at=datetime.utcnow().isoformat() + "Z"
            )

            target = self.database.add_crawl_target(target)

            response = {
                "target_id": target.target_id,
                "url": target.url,
                "type": target.type,
                "created_at": target.created_at,
                "status": "added"
            }

            self._send_json(201, response)
        except Exception as e:
            self._send_error(400, str(e))

    def _handle_delete_target(self, target_id):
        """Handle delete target API request."""
        if not self._check_auth():
            self._send_error(401, "Unauthorized")
            return

        if self.database.remove_crawl_target(target_id):
            self._send_json(200, {"status": "removed"})
        else:
            self._send_error(404, "Target not found")

    def _handle_crawl_trigger(self, data):
        """Handle crawl trigger API request."""
        if not self._check_auth():
            self._send_error(401, "Unauthorized")
            return

        target_id = data.get("target_id", "")
        concurrent = data.get("concurrent_workers", 4)

        try:
            import uuid
            crawl_id = str(uuid.uuid4())

            # Trigger crawl in background
            def run_crawl():
                if target_id:
                    target = self.database.get_crawl_target(target_id)
                    if target:
                        run_crawl_sync(
                            self.database,
                            self.logger,
                            [target],
                            concurrent
                        )
                else:
                    run_crawl_sync(
                        self.database,
                        self.logger,
                        None,
                        concurrent
                    )

            thread = threading.Thread(target=run_crawl, daemon=True)
            thread.start()

            response = {
                "crawl_id": crawl_id,
                "status": "started",
                "target_id": target_id or "all"
            }

            self._send_json(202, response)
        except Exception as e:
            self._send_error(400, str(e))

    def _handle_crawl_status(self, get_param):
        """Handle crawl status API request."""
        crawl_id = get_param("crawl_id", "")
        if not crawl_id:
            self._send_error(400, "Missing crawl_id")
            return

        # For MVP, return generic status
        response = {
            "crawl_id": crawl_id,
            "status": "completed",
            "progress": 1.0,
            "files_indexed": 0,
            "errors": 0
        }

        self._send_json(200, response)

    def _handle_index(self):
        """Serve index.html."""
        if not self.ui_path or not os.path.exists(self.ui_path):
            self._send_error(404, "UI not found")
            return

        with open(self.ui_path, "r") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def _handle_admin_page(self):
        """Serve admin dashboard."""
        if not self._check_auth():
            self._send_error(401, "Unauthorized")
            return

        # Return simple admin HTML
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>FilePursuit Admin</title></head>
        <body>
            <h1>FilePursuit Admin Dashboard</h1>
            <p>Admin panel coming soon...</p>
        </body>
        </html>
        """

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    # Utility methods

    def _check_auth(self) -> bool:
        """Check admin token from Authorization header."""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False

        token = auth_header[7:]  # Remove "Bearer "
        return self.token_manager.validate_token(token)

    def _send_json(self, status: int, data: Dict) -> None:
        """Send JSON response."""
        response = json.dumps(data)
        response_bytes = response.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(response_bytes))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_bytes)

    def _send_error(self, status: int, message: str) -> None:
        """Send error response."""
        self._send_json(status, {"error": message})


class FilePursuitServer:
    """FilePursuit HTTP Server."""

    def __init__(self, database: Database, search_engine: SearchEngine,
                 logger: ActivityLogger, token_manager: MasterTokenManager,
                 ui_path: str = None, host: str = "0.0.0.0", port: int = 8080):
        """Initialize server."""
        self.database = database
        self.search_engine = search_engine
        self.logger = logger
        self.token_manager = token_manager
        self.ui_path = ui_path
        self.host = host
        self.port = port
        self.server = None

    def start(self):
        """Start the HTTP server."""
        # Set class variables
        FilePursuitHandler.database = self.database
        FilePursuitHandler.search_engine = self.search_engine
        FilePursuitHandler.logger = self.logger
        FilePursuitHandler.token_manager = self.token_manager
        FilePursuitHandler.ui_path = self.ui_path

        self.server = HTTPServer((self.host, self.port), FilePursuitHandler)
        print(f"FilePursuit server running at http://{self.host}:{self.port}")
        print(f"API: http://{self.host}:{self.port}/api/search?q=...")
        print(f"Admin: http://{self.host}:{self.port}/admin (token: {self.token_manager.get_token()})")

        self.server.serve_forever()

    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
