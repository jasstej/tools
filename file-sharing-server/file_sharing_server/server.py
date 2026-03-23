"""HTTP Server for file sharing."""

import json
import mimetypes
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

from .auth import TokenManager, MasterTokenManager
from .file_manager import ShareManager
from .logger import ActivityLogger


class FileShareHandler(BaseHTTPRequestHandler):
    """HTTP request handler for file sharing."""

    # Class variables (set by server)
    share_manager: ShareManager = None
    activity_logger: ActivityLogger = None
    master_token_manager: MasterTokenManager = None
    ui_file: Path = None

    def do_GET(self):
        """Handle GET requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = urllib.parse.parse_qs(parsed_url.query)

        # Extract token from query params
        token = params.get("token", [None])[0]
        client_ip = self.client_address[0]

        # Routes
        if path == "/" or path == "/index.html":
            return self._serve_ui()

        if path == "/admin" or path == "/admin.html":
            return self._serve_admin_ui(params, client_ip)

        if path.startswith("/api/"):
            return self._handle_api(path, params, token, client_ip)

        if path.startswith("/download/"):
            return self._handle_download(path, token, client_ip)

        self._send_error(404, "Not found")

    def do_POST(self):
        """Handle POST requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = urllib.parse.parse_qs(parsed_url.query)

        token = params.get("token", [None])[0]
        client_ip = self.client_address[0]

        if path.startswith("/api/"):
            return self._handle_api_post(path, params, token, client_ip)

        self._send_error(404, "Not found")

    def _serve_ui(self):
        """Serve the web UI."""
        if not self.ui_file or not self.ui_file.exists():
            self._send_error(404, "UI not found")
            return

        try:
            content = self.ui_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self._add_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error(500, str(e))

    def _serve_admin_ui(self, params: dict, client_ip: str):
        """Serve the admin dashboard UI."""
        master_token = params.get("token", [None])[0]

        # Generate HTML with token embedded
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - File Sharing Server</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        :root {{
            --bg0: #0d1117;
            --bg1: #161b22;
            --text: #e6edf3;
            --text-secondary: #8b949e;
            --border: #30363d;
            --blue: #58a6ff;
            --green: #3fb950;
            --red: #f85149;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background-color: var(--bg0);
            color: var(--text);
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: var(--bg1);
            padding: 20px;
            border-radius: 6px;
            border: 1px solid var(--border);
            margin-bottom: 20px;
        }}
        .header h1 {{
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 10px;
        }}
        .status {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .stat {{
            background-color: var(--bg0);
            padding: 15px;
            border-radius: 4px;
            border: 1px solid var(--border);
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: 600;
            color: var(--blue);
        }}
        .stat-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-top: 5px;
        }}
        .section {{
            background-color: var(--bg1);
            padding: 20px;
            border-radius: 6px;
            border: 1px solid var(--border);
            margin-bottom: 20px;
        }}
        .section h2 {{
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
            font-size: 18px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background-color: var(--bg0);
            font-weight: 600;
            color: var(--blue);
        }}
        tr:hover {{
            background-color: rgba(88, 166, 255, 0.05);
        }}
        .empty {{
            text-align: center;
            color: var(--text-secondary);
            padding: 40px 20px;
        }}
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            color: var(--text-secondary);
        }}
        .spinner {{
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .error {{
            background-color: rgba(248, 81, 73, 0.1);
            border-left: 4px solid var(--red);
            color: var(--red);
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }}
        .success {{
            background-color: rgba(63, 185, 80, 0.1);
            border-left: 4px solid var(--green);
            color: var(--green);
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }}
        button {{
            background-color: var(--blue);
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        button:hover {{
            background-color: #79c0ff;
        }}
        .mono {{
            font-family: monospace;
            font-size: 11px;
            background-color: var(--bg0);
            padding: 2px 4px;
            border-radius: 2px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Admin Dashboard</h1>
            <p style="color: var(--text-secondary);">File Sharing Server Administration</p>
            <div class="status">
                <div class="stat">
                    <div class="stat-value" id="shareCount">-</div>
                    <div class="stat-label">Active Shares</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="logCount">-</div>
                    <div class="stat-label">Recent Events</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="statusText">Checking...</div>
                    <div class="stat-label">Status</div>
                </div>
            </div>
        </div>

        <div id="messageContainer"></div>

        <div class="section">
            <h2>📊 Active Shares</h2>
            <table id="sharesTable">
                <thead>
                    <tr>
                        <th>Share ID</th>
                        <th>Path</th>
                        <th>Created</th>
                        <th>Expires</th>
                        <th>Max Size (MB)</th>
                    </tr>
                </thead>
                <tbody id="sharesList">
                    <tr><td colspan="5" class="loading"><span class="spinner"></span>Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>📋 Recent Activity Log</h2>
            <table id="logsTable">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Action</th>
                        <th>User</th>
                        <th>Source IP</th>
                        <th>File</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="logsList">
                    <tr><td colspan="6" class="loading"><span class="spinner"></span>Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        class AdminDashboard {{
            constructor() {{
                this.masterToken = "{master_token}";
                this.init();
            }}

            async init() {{
                if (!this.masterToken) {{
                    this.showError("No master token provided. Use: /admin?token=MASTER_TOKEN");
                    return;
                }}
                await this.loadData();
                // Refresh every 5 seconds
                setInterval(() => this.loadData(), 5000);
            }}

            async loadData() {{
                try {{
                    const response = await fetch(`/api/admin?token=${{this.masterToken}}`);
                    if (!response.ok) {{
                        throw new Error("Failed to load admin data (invalid token?)");
                    }}
                    const data = await response.json();
                    this.render(data);
                }} catch (error) {{
                    this.showError("Error: " + error.message);
                    document.getElementById("statusText").textContent = "Error";
                    document.getElementById("statusText").style.color = "var(--red)";
                }}
            }}

            render(data) {{
                // Update stats
                document.getElementById("shareCount").textContent = data.total_shares || 0;
                document.getElementById("logCount").textContent = (data.logs || []).length;
                document.getElementById("statusText").textContent = "Active";
                document.getElementById("statusText").style.color = "var(--green)";

                // Render shares table
                const sharesList = document.getElementById("sharesList");
                const shares = data.shares || [];
                if (shares.length === 0) {{
                    sharesList.innerHTML = "<tr><td colspan=\"5\" class=\"empty\">No active shares</td></tr>";
                }} else {{
                    sharesList.innerHTML = shares.map(share => `
                        <tr>
                            <td><span class="mono">${{share.id.substring(0, 8)}}...</span></td>
                            <td>${{share.path}}</td>
                            <td>${{share.created ? new Date(share.created).toLocaleString() : '-'}}</td>
                            <td>${{share.expires ? new Date(share.expires).toLocaleString() : 'Never'}}</td>
                            <td>${{share.max_file_size_mb}}</td>
                        </tr>
                    `).join("");
                }}

                // Render logs table
                const logsList = document.getElementById("logsList");
                const logs = data.logs || [];
                if (logs.length === 0) {{
                    logsList.innerHTML = "<tr><td colspan=\"6\" class=\"empty\">No activity yet</td></tr>";
                }} else {{
                    logsList.innerHTML = logs.reverse().map(log => `
                        <tr>
                            <td>${{log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}}</td>
                            <td>${{log.action}}</td>
                            <td><span class="mono">${{log.user_token || '?'}}</span></td>
                            <td>${{log.source_ip}}</td>
                            <td>${{log.file || '-'}}</td>
                            <td style="color: ${{log.status === 'SUCCESS' ? 'var(--green)' : 'var(--red)'}}">${{log.status}}</td>
                        </tr>
                    `).join("");
                }}
            }}

            showError(message) {{
                const container = document.getElementById("messageContainer");
                const div = document.createElement("div");
                div.className = "error";
                div.textContent = message;
                container.innerHTML = "";
                container.appendChild(div);
            }}
        }}

        // Initialize dashboard
        const dashboard = new AdminDashboard();
    </script>
</body>
</html>"""

        content = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(content))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _handle_api(self, path: str, params: dict, token: str, client_ip: str):
        """Handle API GET requests."""
        # Validate token
        if not token or not TokenManager.validate_token(token):
            self.activity_logger.auth_fail(client_ip, "Invalid token")
            self._send_json({"error": "Invalid or missing token"}, 401)
            return

        # Check if user has access to share
        share_id = params.get("share_id", [None])[0]
        if not share_id:
            self._send_json({"error": "share_id required"}, 400)
            return

        share = self.share_manager.get_share(share_id)
        if not share or share.token != token:
            self.activity_logger.log(
                "access_denied", token, client_ip, details={"share_id": share_id}
            )
            self._send_json({"error": "Access denied"}, 403)
            return

        # Route API endpoints
        if path == "/api/list":
            return self._api_list_shares(token, client_ip)

        if path == "/api/explore":
            rel_path = params.get("path", [""])[0]
            return self._api_explore(share_id, rel_path, token, client_ip)

        if path == "/api/admin":
            return self._api_admin(params.get("token", [None])[0], client_ip)

        self._send_json({"error": "Not found"}, 404)

    def _handle_api_post(
        self, path: str, params: dict, token: str, client_ip: str
    ):
        """Handle API POST requests."""
        if not token or not TokenManager.validate_token(token):
            self.activity_logger.auth_fail(client_ip, "Invalid token")
            self._send_json({"error": "Invalid or missing token"}, 401)
            return

        share_id = params.get("share_id", [None])[0]
        if not share_id:
            self._send_json({"error": "share_id required"}, 400)
            return

        share = self.share_manager.get_share(share_id)
        if not share or share.token != token:
            self._send_json({"error": "Access denied"}, 403)
            return

        if path == "/api/upload":
            return self._api_upload(share_id, token, client_ip)

        if path == "/api/create_folder":
            return self._api_create_folder(share_id, token, client_ip)

        self._send_json({"error": "Not found"}, 404)

    def _handle_download(self, path: str, token: str, client_ip: str):
        """Handle file download."""
        # Extract share_id and file_path from /download/<share_id>/<file_path>
        parts = path.split("/")[2:]  # Skip empty string and "download"
        if len(parts) < 2:
            self._send_error(400, "Invalid download path")
            return

        share_id = parts[0]
        file_path = "/".join(parts[1:])

        # Validate token
        if not token or not TokenManager.validate_token(token):
            self.activity_logger.auth_fail(client_ip, "Invalid token")
            self._send_error(401, "Invalid token")
            return

        share = self.share_manager.get_share(share_id)
        if not share or share.token != token:
            self.activity_logger.log(
                "access_denied", token, client_ip, file_path, "FAIL"
            )
            self._send_error(403, "Access denied")
            return

        # Download file
        success, content, message = self.share_manager.download_file(
            share_id, file_path
        )
        if not success:
            self.activity_logger.log(
                "download", token, client_ip, file_path, "FAIL", {"error": message}
            )
            self._send_error(404, message)
            return

        # Send file
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", len(content))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{Path(file_path).name}"',
        )
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(content)

        # Log download
        self.activity_logger.download(token, client_ip, file_path, len(content))

    def _api_list_shares(self, token: str, client_ip: str):
        """API: List active shares."""
        shares = self.share_manager.list_shares()
        self.activity_logger.log("list_shares", token, client_ip, None)
        self._send_json({"shares": shares})

    def _api_explore(self, share_id: str, rel_path: str, token: str, client_ip: str):
        """API: Explore directory."""
        success, data = self.share_manager.explore_directory(share_id, rel_path)
        if success:
            self.activity_logger.log(
                "list_dir", token, client_ip, rel_path or "/"
            )
            self._send_json(data)
        else:
            self._send_json(data, 404)

    def _api_create_folder(
        self, share_id: str, token: str, client_ip: str
    ) -> None:
        """API: Create folder."""
        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        folder_path = data.get("path", "")
        success, message = self.share_manager.create_folder(
            share_id, token, folder_path
        )

        if success:
            self.activity_logger.create_folder(token, client_ip, folder_path)
            self._send_json({"message": message})
        else:
            self._send_json({"error": message}, 400)

    def _api_upload(self, share_id: str, token: str, client_ip: str) -> None:
        """API: Upload file."""
        content_type = self.headers.get("Content-Type", "")
        is_multipart = "multipart/form-data" in content_type

        if not is_multipart:
            self._send_json({"error": "Expected multipart/form-data"}, 400)
            return

        # Parse multipart data (simplified - assumes single file)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Extract boundary from content-type
        boundary_str = content_type.split("boundary=")[1].split(";")[0]
        boundary = boundary_str.encode()

        # Parse multipart (simplified parser)
        try:
            filename, file_content, rel_path = self._parse_multipart(
                body, boundary
            )
            if not filename:
                raise ValueError("No file found in upload")

            success, message = self.share_manager.upload_file(
                share_id, token, filename, file_content, rel_path
            )

            if success:
                self.activity_logger.upload(
                    token, client_ip, filename, len(file_content)
                )
                self._send_json({"message": message})
            else:
                self._send_json({"error": message}, 400)
        except Exception as e:
            self._send_json({"error": str(e)}, 400)

    def _api_admin(self, token: str, client_ip: str):
        """API: Admin dashboard (master token required)."""
        if not token or not self.master_token_manager.validate(token):
            self.activity_logger.auth_fail(client_ip, "Invalid master token")
            self._send_json({"error": "Unauthorized"}, 403)
            return

        shares = self.share_manager.list_shares()
        logs = self.activity_logger.get_logs(limit=100)

        self._send_json(
            {
                "shares": shares,
                "logs": logs,
                "total_shares": len(shares),
            }
        )

    def _parse_multipart(self, body: bytes, boundary: bytes) -> tuple:
        """
        Parse multipart form data (simplified).

        Returns:
            Tuple of (filename, file_content, relative_path)
        """
        parts = body.split(b"--" + boundary)
        filename = None
        file_content = b""
        rel_path = ""

        for part in parts:
            if b"Content-Disposition" not in part:
                continue

            # Extract filename
            if b'filename="' in part:
                start = part.index(b'filename="') + 10
                end = part.index(b'"', start)
                filename = part[start:end].decode()

                # Extract file content (after headers)
                content_start = part.index(b"\r\n\r\n") + 4
                content_end = part.rfind(b"\r\n")
                file_content = part[content_start:content_end]

            # Extract optional "path" field
            if b'name="path"' in part:
                start = part.index(b"\r\n\r\n") + 4
                end = part.rfind(b"\r\n")
                rel_path = part[start:end].decode()

        return filename, file_content, rel_path

    def _send_json(self, data: dict, status_code: int = 200) -> None:
        """Send JSON response."""
        response = json.dumps(data)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response.encode()))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(response.encode())

    def _send_error(self, status_code: int, message: str) -> None:
        """Send error response."""
        response = json.dumps({"error": message})
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response.encode()))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(response.encode())

    def _add_cors_headers(self) -> None:
        """Add CORS headers to response."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        """Suppress verbose HTTP logging."""
        pass


class FileShareServer:
    """File sharing HTTP server."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        data_dir: Path = None,
        ui_file: Path = None,
    ):
        """
        Initialize server.

        Args:
            host: Bind address
            port: Bind port
            data_dir: Data directory for shares and logs
            ui_file: Path to UI HTML file
        """
        self.host = host
        self.port = port
        self.data_dir = Path(data_dir or "./data")
        self.ui_file = Path(ui_file) if ui_file else None

        # Initialize managers
        self.share_manager = ShareManager(self.data_dir)
        self.activity_logger = ActivityLogger(self.data_dir / "activity.log")
        self.master_token_manager = MasterTokenManager(self.data_dir / "master_token.txt")

        # Set class variables for handler
        FileShareHandler.share_manager = self.share_manager
        FileShareHandler.activity_logger = self.activity_logger
        FileShareHandler.master_token_manager = self.master_token_manager
        FileShareHandler.ui_file = self.ui_file

    def run(self) -> None:
        """Start the HTTP server."""
        server = HTTPServer((self.host, self.port), FileShareHandler)
        print(f"Server running on http://{self.host}:{self.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutdown requested")
            server.shutdown()
