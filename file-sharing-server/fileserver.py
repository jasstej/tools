#!/usr/bin/env python3
"""
Enhanced File Manager Server - Full Featured
A comprehensive Python-based file manager with directory navigation,
file operations, previews, multi-select, and batch operations.
"""

import os
import sys
import json
import socket
import hashlib
import mimetypes
import shutil
import zipfile
import io
import time
import re
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, quote, parse_qs, urlparse
from html import escape

# Try to import optional dependencies
try:
    import qrcode
except ImportError:
    qrcode = None
    print("Note: qrcode module not installed. QR code generation disabled.")

try:
    from PIL import Image
except ImportError:
    Image = None
    print("Note: PIL/Pillow not installed. Thumbnail generation disabled.")

# ============================================================================
# CONFIGURATION
# ============================================================================

PORT = 8080
ROOT_FOLDER = os.path.expanduser("~/Documents")  # Default root - configurable
THUMBNAIL_SIZE = (128, 128)
MAX_PREVIEW_SIZE = 10 * 1024 * 1024  # 10MB max for text preview
CHUNK_SIZE = 8192

# Thread-safe data structures
lock = threading.Lock()
transfer_logs = []
active_connections = {}
device_history = {}
user_names = {}
connection_stats = {
    "total_downloads": 0,
    "total_uploads": 0,
    "total_bytes_transferred": 0
}

# ============================================================================
# FILE TYPE DETECTION
# ============================================================================

FILE_CATEGORIES = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.heic'],
    'video': ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg'],
    'audio': ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.opus'],
    'document': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp'],
    'archive': ['.zip', '.tar', '.gz', '.rar', '.7z', '.bz2', '.xz', '.tar.gz', '.tgz'],
    'code': ['.py', '.js', '.ts', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bash',
             '.c', '.cpp', '.h', '.hpp', '.java', '.go', '.rs', '.rb', '.php', '.sql', '.md', '.txt',
             '.ini', '.conf', '.cfg', '.toml', '.env', '.gitignore', '.dockerfile'],
    'executable': ['.exe', '.msi', '.dmg', '.app', '.deb', '.rpm', '.appimage', '.bin', '.run']
}

CODE_EXTENSIONS = ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.json', '.xml', '.yaml',
                   '.yml', '.sh', '.bash', '.c', '.cpp', '.h', '.hpp', '.java', '.go', '.rs', '.rb',
                   '.php', '.sql', '.md', '.txt', '.ini', '.conf', '.cfg', '.toml', '.env', '.log',
                   '.gitignore', '.dockerfile', '.makefile']

def get_file_type(filename):
    """Determine file category based on extension"""
    ext = os.path.splitext(filename)[1].lower()
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return 'file'

def get_mime_type(filepath):
    """Get MIME type for a file"""
    mime_type, _ = mimetypes.guess_type(filepath)
    return mime_type or 'application/octet-stream'

def format_size(size):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != 'B' else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def is_text_file(filepath):
    """Check if file is likely text/code that can be previewed"""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in CODE_EXTENSIONS

def safe_path_join(base, *paths):
    """Safely join paths preventing directory traversal"""
    final_path = os.path.normpath(os.path.join(base, *paths))
    if not final_path.startswith(os.path.normpath(base)):
        raise ValueError("Path traversal detected")
    return final_path

# ============================================================================
# THUMBNAIL GENERATION
# ============================================================================

THUMBNAIL_DIR = None

def init_thumbnails(root_folder):
    """Initialize thumbnail directory"""
    global THUMBNAIL_DIR
    THUMBNAIL_DIR = os.path.join(root_folder, '.thumbnails')
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)

def get_thumbnail_path(filepath):
    """Get thumbnail path for a file"""
    if not THUMBNAIL_DIR:
        return None
    file_hash = hashlib.md5(filepath.encode()).hexdigest()
    return os.path.join(THUMBNAIL_DIR, f"{file_hash}.png")

def generate_thumbnail(filepath):
    """Generate thumbnail for image files"""
    if Image is None:
        return None

    file_type = get_file_type(filepath)
    if file_type != 'image':
        return None

    thumb_path = get_thumbnail_path(filepath)
    if not thumb_path:
        return None

    # Return existing thumbnail if valid
    if os.path.exists(thumb_path):
        if os.path.getmtime(thumb_path) >= os.path.getmtime(filepath):
            return os.path.basename(thumb_path)

    try:
        with Image.open(filepath) as img:
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(thumb_path, 'JPEG', quality=85)
        return os.path.basename(thumb_path)
    except Exception:
        return None

# ============================================================================
# TRANSFER MONITORING
# ============================================================================

class MonitoredFileHandler:
    def __init__(self, filepath, client_ip, operation, filename):
        self.filepath = filepath
        self.client_ip = client_ip
        self.operation = operation
        self.filename = filename
        self.bytes_transferred = 0
        self.total_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        self.start_time = time.time()

    def update_progress(self, bytes_count):
        self.bytes_transferred += bytes_count

    def set_total_size(self, size):
        self.total_size = size

    def get_speed(self):
        elapsed = time.time() - self.start_time
        return self.bytes_transferred / elapsed if elapsed > 0 else 0

    def get_progress(self):
        return (self.bytes_transferred / self.total_size * 100) if self.total_size > 0 else 0

# ============================================================================
# HTTP REQUEST HANDLER
# ============================================================================

class FileManagerHandler(SimpleHTTPRequestHandler):

    def log_message(self, format, *args):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.client_address[0]} - {format % args}")

    def send_json(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_error_json(self, message, status=400):
        """Send error as JSON"""
        self.send_json({"success": False, "error": message}, status)

    def get_current_path(self):
        """Parse and validate the current path from query string"""
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        rel_path = query.get('path', [''])[0]
        rel_path = unquote(rel_path).strip('/')

        try:
            full_path = safe_path_join(ROOT_FOLDER, rel_path)
            if os.path.isdir(full_path):
                return rel_path, full_path
        except ValueError:
            pass
        return '', ROOT_FOLDER

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        client_ip = self.client_address[0]
        user_agent = self.headers.get('User-Agent', 'Unknown')
        parsed = urlparse(self.path)
        path = parsed.path

        # Track device
        if not path.startswith('/api/'):
            track_device(client_ip, user_agent, f"GET {path}")

        # Route requests
        if path == "/":
            self.serve_main_page()
        elif path == "/api/files":
            self.api_list_files()
        elif path == "/api/stats":
            self.api_stats()
        elif path == "/api/user-info":
            self.api_user_info()
        elif path.startswith("/api/preview/"):
            self.api_preview_file()
        elif path.startswith("/download/"):
            self.serve_download()
        elif path.startswith("/stream/"):
            self.serve_stream()
        elif path.startswith("/thumbnail/"):
            self.serve_thumbnail()
        elif path.startswith("/api/zip"):
            self.api_download_zip()
        elif path == "/monitor":
            self.serve_monitor_page()
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        client_ip = self.client_address[0]
        user_agent = self.headers.get('User-Agent', 'Unknown')
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")

        track_device(client_ip, user_agent, f"POST {path}")

        if path == "/api/upload":
            self.api_upload()
        elif path == "/api/create-folder":
            self.api_create_folder()
        elif path == "/api/rename":
            self.api_rename()
        elif path == "/api/delete":
            self.api_delete()
        elif path == "/api/move":
            self.api_move()
        elif path == "/api/copy":
            self.api_copy()
        elif path == "/api/set-name":
            self.api_set_user_name()
        elif "multipart/form-data" in content_type:
            # Legacy upload support
            self.handle_legacy_upload()
        else:
            self.send_error_json("Unknown endpoint", 404)

    # ========================================================================
    # API ENDPOINTS
    # ========================================================================

    def api_list_files(self):
        """List files and directories in current path"""
        rel_path, full_path = self.get_current_path()

        if not os.path.isdir(full_path):
            return self.send_error_json("Directory not found", 404)

        items = []
        try:
            for name in os.listdir(full_path):
                if name.startswith('.'):
                    continue

                item_path = os.path.join(full_path, name)
                is_dir = os.path.isdir(item_path)

                try:
                    stat = os.stat(item_path)
                    size = 0 if is_dir else stat.st_size
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    size = 0
                    modified = "Unknown"

                item = {
                    "name": name,
                    "is_dir": is_dir,
                    "size": size,
                    "size_str": format_size(size) if not is_dir else "-",
                    "modified": modified,
                    "type": "folder" if is_dir else get_file_type(name),
                    "path": f"{rel_path}/{name}" if rel_path else name
                }

                # Add thumbnail for images
                if not is_dir and item["type"] == "image":
                    thumb = generate_thumbnail(item_path)
                    if thumb:
                        item["thumbnail"] = thumb

                items.append(item)

            # Sort: folders first, then by name
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

            # Build breadcrumb
            breadcrumb = [{"name": "Home", "path": ""}]
            if rel_path:
                parts = rel_path.split('/')
                for i, part in enumerate(parts):
                    breadcrumb.append({
                        "name": part,
                        "path": '/'.join(parts[:i+1])
                    })

            self.send_json({
                "success": True,
                "path": rel_path,
                "breadcrumb": breadcrumb,
                "items": items,
                "total": len(items)
            })

        except PermissionError:
            self.send_error_json("Permission denied", 403)
        except Exception as e:
            self.send_error_json(str(e), 500)

    def api_preview_file(self):
        """Preview file content (for text/code files)"""
        rel_path = unquote(self.path[len("/api/preview/"):])

        try:
            full_path = safe_path_join(ROOT_FOLDER, rel_path)
        except ValueError:
            return self.send_error_json("Invalid path", 400)

        if not os.path.isfile(full_path):
            return self.send_error_json("File not found", 404)

        file_size = os.path.getsize(full_path)
        file_type = get_file_type(full_path)
        mime = get_mime_type(full_path)

        # For text/code files, read content
        if is_text_file(full_path) and file_size <= MAX_PREVIEW_SIZE:
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                self.send_json({
                    "success": True,
                    "type": "text",
                    "mime": mime,
                    "content": content,
                    "size": file_size,
                    "size_str": format_size(file_size)
                })
            except Exception as e:
                self.send_error_json(f"Could not read file: {e}", 500)
        else:
            # For binary files, just return metadata
            self.send_json({
                "success": True,
                "type": file_type,
                "mime": mime,
                "size": file_size,
                "size_str": format_size(file_size),
                "streamable": file_type in ['video', 'audio', 'image']
            })

    def api_upload(self):
        """Handle file upload with progress"""
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))

        if "multipart/form-data" not in content_type:
            return self.send_error_json("Invalid content type", 400)

        # Parse query for target path
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        target_path = query.get('path', [''])[0]

        try:
            target_dir = safe_path_join(ROOT_FOLDER, target_path)
        except ValueError:
            return self.send_error_json("Invalid path", 400)

        if not os.path.isdir(target_dir):
            return self.send_error_json("Target directory not found", 404)

        boundary = content_type.split("boundary=")[1].encode()
        data = self.rfile.read(content_length)

        uploaded_files = []
        for part in data.split(b"--" + boundary):
            if b"Content-Disposition" not in part or b"filename=" not in part:
                continue

            headers_end = part.find(b"\r\n\r\n")
            if headers_end == -1:
                continue

            headers = part[:headers_end].decode()
            file_data = part[headers_end + 4:].rstrip(b"\r\n--")

            # Extract filename
            fname_match = re.search(r'filename="([^"]+)"', headers)
            if not fname_match:
                continue

            filename = os.path.basename(fname_match.group(1))
            if not filename:
                continue

            # Save file
            file_path = os.path.join(target_dir, filename)
            with open(file_path, "wb") as f:
                f.write(file_data)

            uploaded_files.append(filename)

            with lock:
                connection_stats["total_uploads"] += 1
                connection_stats["total_bytes_transferred"] += len(file_data)

        if uploaded_files:
            self.send_json({
                "success": True,
                "files": uploaded_files,
                "message": f"Uploaded {len(uploaded_files)} file(s)"
            })
        else:
            self.send_error_json("No files uploaded", 400)

    def api_create_folder(self):
        """Create a new folder"""
        content_length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_length).decode())

        parent_path = data.get("path", "")
        folder_name = data.get("name", "").strip()

        if not folder_name:
            return self.send_error_json("Folder name required", 400)

        # Validate folder name
        if any(c in folder_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            return self.send_error_json("Invalid folder name", 400)

        try:
            parent_dir = safe_path_join(ROOT_FOLDER, parent_path)
            new_folder = os.path.join(parent_dir, folder_name)

            if os.path.exists(new_folder):
                return self.send_error_json("Folder already exists", 400)

            os.makedirs(new_folder)
            self.send_json({"success": True, "message": f"Created folder: {folder_name}"})

        except ValueError:
            self.send_error_json("Invalid path", 400)
        except PermissionError:
            self.send_error_json("Permission denied", 403)
        except Exception as e:
            self.send_error_json(str(e), 500)

    def api_rename(self):
        """Rename a file or folder"""
        content_length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_length).decode())

        old_path = data.get("path", "")
        new_name = data.get("name", "").strip()

        if not new_name:
            return self.send_error_json("New name required", 400)

        if any(c in new_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            return self.send_error_json("Invalid name", 400)

        try:
            full_old = safe_path_join(ROOT_FOLDER, old_path)
            parent_dir = os.path.dirname(full_old)
            full_new = os.path.join(parent_dir, new_name)

            if not os.path.exists(full_old):
                return self.send_error_json("Item not found", 404)

            if os.path.exists(full_new):
                return self.send_error_json("Name already exists", 400)

            os.rename(full_old, full_new)
            self.send_json({"success": True, "message": f"Renamed to: {new_name}"})

        except ValueError:
            self.send_error_json("Invalid path", 400)
        except PermissionError:
            self.send_error_json("Permission denied", 403)
        except Exception as e:
            self.send_error_json(str(e), 500)

    def api_delete(self):
        """Delete files or folders"""
        content_length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_length).decode())

        paths = data.get("paths", [])
        if not paths:
            return self.send_error_json("No items specified", 400)

        deleted = []
        errors = []

        for rel_path in paths:
            try:
                full_path = safe_path_join(ROOT_FOLDER, rel_path)

                if not os.path.exists(full_path):
                    errors.append(f"Not found: {rel_path}")
                    continue

                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)

                deleted.append(rel_path)

            except ValueError:
                errors.append(f"Invalid path: {rel_path}")
            except PermissionError:
                errors.append(f"Permission denied: {rel_path}")
            except Exception as e:
                errors.append(f"Error: {rel_path} - {e}")

        self.send_json({
            "success": len(deleted) > 0,
            "deleted": deleted,
            "errors": errors,
            "message": f"Deleted {len(deleted)} item(s)"
        })

    def api_move(self):
        """Move files/folders to another location"""
        content_length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_length).decode())

        paths = data.get("paths", [])
        destination = data.get("destination", "")

        if not paths:
            return self.send_error_json("No items specified", 400)

        try:
            dest_dir = safe_path_join(ROOT_FOLDER, destination)
            if not os.path.isdir(dest_dir):
                return self.send_error_json("Destination not found", 404)
        except ValueError:
            return self.send_error_json("Invalid destination", 400)

        moved = []
        errors = []

        for rel_path in paths:
            try:
                full_path = safe_path_join(ROOT_FOLDER, rel_path)
                name = os.path.basename(full_path)
                new_path = os.path.join(dest_dir, name)

                if os.path.exists(new_path):
                    errors.append(f"Already exists in destination: {name}")
                    continue

                shutil.move(full_path, new_path)
                moved.append(rel_path)

            except Exception as e:
                errors.append(f"Error moving {rel_path}: {e}")

        self.send_json({
            "success": len(moved) > 0,
            "moved": moved,
            "errors": errors,
            "message": f"Moved {len(moved)} item(s)"
        })

    def api_copy(self):
        """Copy files/folders to another location"""
        content_length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_length).decode())

        paths = data.get("paths", [])
        destination = data.get("destination", "")

        if not paths:
            return self.send_error_json("No items specified", 400)

        try:
            dest_dir = safe_path_join(ROOT_FOLDER, destination)
            if not os.path.isdir(dest_dir):
                return self.send_error_json("Destination not found", 404)
        except ValueError:
            return self.send_error_json("Invalid destination", 400)

        copied = []
        errors = []

        for rel_path in paths:
            try:
                full_path = safe_path_join(ROOT_FOLDER, rel_path)
                name = os.path.basename(full_path)
                new_path = os.path.join(dest_dir, name)

                # Handle name collision
                if os.path.exists(new_path):
                    base, ext = os.path.splitext(name)
                    counter = 1
                    while os.path.exists(new_path):
                        name = f"{base} ({counter}){ext}"
                        new_path = os.path.join(dest_dir, name)
                        counter += 1

                if os.path.isdir(full_path):
                    shutil.copytree(full_path, new_path)
                else:
                    shutil.copy2(full_path, new_path)

                copied.append(rel_path)

            except Exception as e:
                errors.append(f"Error copying {rel_path}: {e}")

        self.send_json({
            "success": len(copied) > 0,
            "copied": copied,
            "errors": errors,
            "message": f"Copied {len(copied)} item(s)"
        })

    def api_download_zip(self):
        """Download multiple files as ZIP"""
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        paths = query.get('paths', [''])[0]

        if not paths:
            return self.send_error_json("No files specified", 400)

        file_paths = paths.split(',')

        # Create ZIP in memory
        zip_buffer = io.BytesIO()

        try:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for rel_path in file_paths:
                    rel_path = unquote(rel_path)
                    full_path = safe_path_join(ROOT_FOLDER, rel_path)

                    if os.path.isfile(full_path):
                        zf.write(full_path, os.path.basename(full_path))
                    elif os.path.isdir(full_path):
                        base_name = os.path.basename(full_path)
                        for root, dirs, files in os.walk(full_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arc_name = os.path.join(base_name, os.path.relpath(file_path, full_path))
                                zf.write(file_path, arc_name)

            zip_buffer.seek(0)
            zip_data = zip_buffer.read()

            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(zip_data)))
            self.send_header("Content-Disposition", 'attachment; filename="download.zip"')
            self.end_headers()
            self.wfile.write(zip_data)

        except Exception as e:
            self.send_error_json(str(e), 500)

    def api_stats(self):
        """Get server statistics"""
        with lock:
            device_list = []
            for ip, info in device_history.items():
                user_name = user_names.get(ip, "")
                device_list.append({
                    "ip": ip,
                    "user_name": user_name,
                    "display_name": f"{ip} - {user_name}" if user_name else ip,
                    "hostname": info.get("hostname", "Unknown"),
                    "first_seen": info.get("first_seen", ""),
                    "last_seen": info.get("last_seen", ""),
                    "total_transfers": info.get("total_transfers", 0),
                    "last_action": info.get("last_action", "")
                })

            device_list.sort(key=lambda x: x.get("last_seen", ""), reverse=True)

            stats = {
                "active_connections": len(active_connections),
                "total_downloads": connection_stats["total_downloads"],
                "total_uploads": connection_stats["total_uploads"],
                "total_bytes": connection_stats["total_bytes_transferred"],
                "recent_logs": transfer_logs[-20:],
                "device_history": device_list,
                "active_transfers": []
            }

        self.send_json(stats)

    def api_user_info(self):
        """Get current user info"""
        client_ip = self.client_address[0]
        user_name = user_names.get(client_ip, "")
        hostname = device_history.get(client_ip, {}).get("hostname", "Unknown")

        self.send_json({
            "ip": client_ip,
            "name": user_name,
            "hostname": hostname,
            "display_name": f"{client_ip} - {user_name}" if user_name else client_ip
        })

    def api_set_user_name(self):
        """Set user display name"""
        content_length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_length).decode())

        name = data.get("name", "").strip()
        client_ip = self.client_address[0]

        if name:
            if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name) or len(name) > 30:
                return self.send_error_json("Invalid name format", 400)
            with lock:
                user_names[client_ip] = name
        else:
            with lock:
                user_names.pop(client_ip, None)

        self.send_json({"success": True, "message": f"Name {'set to: ' + name if name else 'cleared'}"})

    # ========================================================================
    # FILE SERVING
    # ========================================================================

    def serve_download(self):
        """Serve file download"""
        rel_path = unquote(self.path[len("/download/"):])

        try:
            full_path = safe_path_join(ROOT_FOLDER, rel_path)
        except ValueError:
            return self.send_error(400, "Invalid path")

        if not os.path.isfile(full_path):
            return self.send_error(404, "File not found")

        file_size = os.path.getsize(full_path)
        filename = os.path.basename(full_path)

        with lock:
            connection_stats["total_downloads"] += 1

        self.send_response(200)
        self.send_header("Content-Type", get_mime_type(full_path))
        self.send_header("Content-Length", str(file_size))
        self.send_header("Content-Disposition", f'attachment; filename="{quote(filename)}"')
        self.end_headers()

        with open(full_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                self.wfile.write(chunk)
                with lock:
                    connection_stats["total_bytes_transferred"] += len(chunk)

    def serve_stream(self):
        """Stream media files with range support"""
        rel_path = unquote(self.path[len("/stream/"):])

        try:
            full_path = safe_path_join(ROOT_FOLDER, rel_path)
        except ValueError:
            return self.send_error(400, "Invalid path")

        if not os.path.isfile(full_path):
            return self.send_error(404, "File not found")

        file_size = os.path.getsize(full_path)
        mime_type = get_mime_type(full_path)

        # Handle range requests
        range_header = self.headers.get('Range')
        if range_header:
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

                if start >= file_size:
                    self.send_error(416, "Range Not Satisfiable")
                    return

                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(full_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk_size = min(CHUNK_SIZE, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return

        # Full file
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        with open(full_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def serve_thumbnail(self):
        """Serve thumbnail images"""
        thumb_name = unquote(self.path[len("/thumbnail/"):])
        thumb_path = os.path.join(THUMBNAIL_DIR, thumb_name)

        if os.path.isfile(thumb_path):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "max-age=86400")
            self.end_headers()
            with open(thumb_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "Thumbnail not found")

    def handle_legacy_upload(self):
        """Handle legacy multipart upload"""
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))

        boundary = content_type.split("boundary=")[1].encode()
        data = self.rfile.read(content_length)

        for part in data.split(b"--" + boundary):
            if b"Content-Disposition" in part and b"filename=" in part:
                headers_end = part.find(b"\r\n\r\n")
                if headers_end == -1:
                    continue
                headers = part[:headers_end].decode()
                file_data = part[headers_end + 4:-2]

                fname_match = re.search(r'filename="([^"]+)"', headers)
                if fname_match:
                    filename = os.path.basename(fname_match.group(1))
                    file_path = os.path.join(ROOT_FOLDER, filename)

                    with open(file_path, "wb") as f:
                        f.write(file_data)

                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(f"Uploaded: {filename}".encode())
                    return

        self.send_response(400)
        self.end_headers()
        self.wfile.write(b"Bad upload format")

    # ========================================================================
    # HTML PAGES
    # ========================================================================

    def serve_main_page(self):
        """Serve the main file manager page"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(self.generate_main_html().encode())

    def serve_monitor_page(self):
        """Serve the monitoring page"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(self.generate_monitor_html().encode())

    def generate_main_html(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Manager</title>
    <style>
        :root {
            --bg-primary: #0d0d0d;
            --bg-secondary: #1a1a1a;
            --bg-tertiary: #2a2a2a;
            --accent: #00ff99;
            --accent-dim: #00cc7a;
            --accent-secondary: #00ffff;
            --text-primary: #e0e0e0;
            --text-secondary: #888;
            --border: #333;
            --danger: #ff4757;
            --warning: #ffa502;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        /* Header */
        .header {
            background: var(--bg-secondary);
            padding: 15px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }

        .logo {
            font-size: 1.4em;
            font-weight: bold;
            color: var(--accent);
        }

        .nav-links {
            display: flex;
            gap: 10px;
        }

        .nav-links a {
            padding: 8px 16px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--accent-secondary);
            text-decoration: none;
            border-radius: 4px;
            transition: all 0.2s;
        }

        .nav-links a:hover {
            border-color: var(--accent);
            background: var(--bg-primary);
        }

        .search-box {
            flex: 1;
            max-width: 400px;
            margin-left: auto;
        }

        .search-box input {
            width: 100%;
            padding: 10px 15px;
            background: var(--bg-primary);
            border: 1px solid var(--border);
            color: var(--text-primary);
            border-radius: 4px;
            font-size: 14px;
        }

        .search-box input:focus {
            outline: none;
            border-color: var(--accent);
        }

        /* Toolbar */
        .toolbar {
            background: var(--bg-secondary);
            padding: 10px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }

        .breadcrumb {
            display: flex;
            align-items: center;
            gap: 5px;
            flex-wrap: wrap;
        }

        .breadcrumb a {
            color: var(--accent-secondary);
            text-decoration: none;
            padding: 4px 8px;
            border-radius: 3px;
        }

        .breadcrumb a:hover {
            background: var(--bg-tertiary);
        }

        .breadcrumb span { color: var(--text-secondary); }

        .toolbar-actions {
            display: flex;
            gap: 8px;
            margin-left: auto;
        }

        .btn {
            padding: 8px 16px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-primary);
            cursor: pointer;
            border-radius: 4px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }

        .btn:hover {
            border-color: var(--accent);
            background: var(--bg-secondary);
        }

        .btn-primary {
            background: var(--accent);
            color: #000;
            border-color: var(--accent);
        }

        .btn-primary:hover {
            background: var(--accent-dim);
        }

        .btn-danger {
            border-color: var(--danger);
            color: var(--danger);
        }

        .btn-danger:hover {
            background: var(--danger);
            color: #fff;
        }

        /* View Options */
        .view-options {
            display: flex;
            gap: 5px;
        }

        .view-btn {
            padding: 6px 10px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            cursor: pointer;
            border-radius: 3px;
            font-size: 16px;
        }

        .view-btn.active {
            background: var(--accent);
            color: #000;
            border-color: var(--accent);
        }

        /* Selection bar */
        .selection-bar {
            background: var(--accent);
            color: #000;
            padding: 10px 20px;
            display: none;
            align-items: center;
            gap: 15px;
        }

        .selection-bar.visible { display: flex; }

        .selection-bar .btn {
            background: rgba(0,0,0,0.2);
            border-color: rgba(0,0,0,0.3);
            color: #000;
        }

        /* Main content */
        .main-content {
            padding: 20px;
        }

        /* Drop zone */
        .drop-zone {
            border: 2px dashed var(--border);
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            margin-bottom: 20px;
            transition: all 0.3s;
            cursor: pointer;
        }

        .drop-zone:hover, .drop-zone.dragover {
            border-color: var(--accent);
            background: rgba(0, 255, 153, 0.05);
        }

        .drop-zone h3 { color: var(--accent); margin-bottom: 10px; }
        .drop-zone p { color: var(--text-secondary); }

        /* File grid */
        .file-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
        }

        .file-grid.list {
            grid-template-columns: 1fr;
            gap: 2px;
        }

        /* File item */
        .file-item {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }

        .file-item:hover {
            border-color: var(--accent);
            transform: translateY(-2px);
        }

        .file-item.selected {
            border-color: var(--accent);
            background: rgba(0, 255, 153, 0.1);
        }

        .file-item .checkbox {
            position: absolute;
            top: 8px;
            left: 8px;
            width: 20px;
            height: 20px;
            border: 2px solid var(--border);
            border-radius: 4px;
            background: var(--bg-primary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.2s;
        }

        .file-item:hover .checkbox, .file-item.selected .checkbox {
            opacity: 1;
        }

        .file-item.selected .checkbox {
            background: var(--accent);
            border-color: var(--accent);
        }

        .file-item.selected .checkbox::after {
            content: "\\2714";
            color: #000;
            font-size: 12px;
        }

        .file-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }

        .file-thumbnail {
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 4px;
            margin-bottom: 10px;
        }

        .file-name {
            color: var(--accent-secondary);
            font-size: 13px;
            word-break: break-word;
            margin-bottom: 5px;
        }

        .file-info {
            color: var(--text-secondary);
            font-size: 11px;
        }

        /* List view */
        .file-grid.list .file-item {
            display: flex;
            align-items: center;
            padding: 10px 15px;
            text-align: left;
            border-radius: 0;
        }

        .file-grid.list .file-icon {
            font-size: 24px;
            margin: 0 15px 0 30px;
        }

        .file-grid.list .file-thumbnail {
            width: 40px;
            height: 40px;
            margin: 0 15px 0 30px;
        }

        .file-grid.list .file-name {
            flex: 1;
            margin: 0;
        }

        .file-grid.list .file-info {
            width: 150px;
            text-align: right;
        }

        .file-grid.list .checkbox {
            position: static;
            opacity: 1;
        }

        /* Context menu */
        .context-menu {
            position: fixed;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 5px 0;
            min-width: 180px;
            z-index: 1000;
            box-shadow: 0 5px 20px rgba(0,0,0,0.5);
            display: none;
        }

        .context-menu.visible { display: block; }

        .context-menu-item {
            padding: 10px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .context-menu-item:hover {
            background: var(--bg-tertiary);
        }

        .context-menu-item.danger { color: var(--danger); }
        .context-menu-divider {
            height: 1px;
            background: var(--border);
            margin: 5px 0;
        }

        /* Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .modal-overlay.visible { display: flex; }

        .modal {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            max-width: 90vw;
            max-height: 90vh;
            overflow: auto;
        }

        .modal-header {
            padding: 15px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .modal-header h3 { color: var(--accent); }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 24px;
            cursor: pointer;
        }

        .modal-close:hover { color: var(--text-primary); }

        .modal-body {
            padding: 20px;
        }

        .modal-footer {
            padding: 15px 20px;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }

        /* Preview modal */
        .preview-modal .modal {
            width: 90vw;
            height: 90vh;
        }

        .preview-modal .modal-body {
            height: calc(100% - 120px);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0;
        }

        .preview-modal img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }

        .preview-modal video, .preview-modal audio {
            max-width: 100%;
            max-height: 100%;
        }

        .preview-modal pre {
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 20px;
            overflow: auto;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'Fira Code', monospace;
            font-size: 13px;
            line-height: 1.5;
        }

        /* Input modal */
        .input-modal .modal {
            width: 400px;
        }

        .input-modal input {
            width: 100%;
            padding: 12px;
            background: var(--bg-primary);
            border: 1px solid var(--border);
            color: var(--text-primary);
            border-radius: 4px;
            font-size: 14px;
        }

        .input-modal input:focus {
            outline: none;
            border-color: var(--accent);
        }

        /* Upload progress */
        .upload-progress {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            min-width: 300px;
            z-index: 100;
        }

        .upload-item {
            margin-bottom: 10px;
        }

        .upload-item:last-child { margin-bottom: 0; }

        .upload-item .name {
            font-size: 13px;
            margin-bottom: 5px;
            color: var(--accent-secondary);
        }

        .progress-bar {
            height: 6px;
            background: var(--bg-primary);
            border-radius: 3px;
            overflow: hidden;
        }

        .progress-bar .fill {
            height: 100%;
            background: var(--accent);
            transition: width 0.3s;
        }

        /* Toast messages */
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1001;
        }

        .toast {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 20px;
            margin-bottom: 10px;
            animation: slideIn 0.3s ease;
        }

        .toast.success { border-color: var(--accent); }
        .toast.error { border-color: var(--danger); }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* Folder picker modal */
        .folder-picker {
            max-height: 400px;
            overflow-y: auto;
        }

        .folder-picker-item {
            padding: 10px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            border-radius: 4px;
        }

        .folder-picker-item:hover {
            background: var(--bg-tertiary);
        }

        .folder-picker-item.selected {
            background: var(--accent);
            color: #000;
        }

        /* Stats footer */
        .stats-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
            padding: 8px 20px;
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            gap: 20px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .header { padding: 10px; gap: 10px; }
            .search-box { max-width: 100%; order: 3; flex-basis: 100%; }
            .toolbar { padding: 10px; }
            .toolbar-actions { flex-wrap: wrap; }
            .file-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
            .main-content { padding: 10px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">File Manager</div>
        <div class="nav-links">
            <a href="/">Home</a>
            <a href="/monitor">Monitor</a>
        </div>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search files..." oninput="filterFiles()">
        </div>
    </div>

    <div class="toolbar">
        <div class="breadcrumb" id="breadcrumb"></div>
        <div class="view-options">
            <button class="view-btn active" data-view="grid" onclick="setView('grid')">&#9638;</button>
            <button class="view-btn" data-view="list" onclick="setView('list')">&#9776;</button>
        </div>
        <div class="toolbar-actions">
            <button class="btn" onclick="createFolder()">+ New Folder</button>
            <button class="btn btn-primary" onclick="document.getElementById('fileInput').click()">Upload</button>
            <input type="file" id="fileInput" multiple style="display:none" onchange="uploadFiles(this.files)">
        </div>
    </div>

    <div class="selection-bar" id="selectionBar">
        <span id="selectionCount">0 selected</span>
        <button class="btn" onclick="downloadSelected()">Download</button>
        <button class="btn" onclick="moveSelected()">Move</button>
        <button class="btn" onclick="copySelected()">Copy</button>
        <button class="btn btn-danger" onclick="deleteSelected()">Delete</button>
        <button class="btn" onclick="clearSelection()">Cancel</button>
    </div>

    <div class="main-content">
        <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
            <h3>Drop files here to upload</h3>
            <p>or click to browse</p>
        </div>

        <div class="file-grid" id="fileGrid"></div>
    </div>

    <div class="stats-footer">
        <span id="itemCount">0 items</span>
        <span id="connectionInfo"></span>
    </div>

    <!-- Context Menu -->
    <div class="context-menu" id="contextMenu">
        <div class="context-menu-item" onclick="openFile()"><span>Open</span></div>
        <div class="context-menu-item" onclick="downloadContextItem()"><span>Download</span></div>
        <div class="context-menu-divider"></div>
        <div class="context-menu-item" onclick="renameItem()"><span>Rename</span></div>
        <div class="context-menu-item" onclick="copyItem()"><span>Copy</span></div>
        <div class="context-menu-item" onclick="moveItem()"><span>Move to...</span></div>
        <div class="context-menu-divider"></div>
        <div class="context-menu-item danger" onclick="deleteItem()"><span>Delete</span></div>
    </div>

    <!-- Preview Modal -->
    <div class="modal-overlay preview-modal" id="previewModal">
        <div class="modal">
            <div class="modal-header">
                <h3 id="previewTitle">Preview</h3>
                <button class="modal-close" onclick="closePreview()">&times;</button>
            </div>
            <div class="modal-body" id="previewBody"></div>
            <div class="modal-footer">
                <span id="previewInfo" style="margin-right:auto;color:var(--text-secondary)"></span>
                <button class="btn" onclick="downloadPreviewFile()">Download</button>
                <button class="btn" onclick="closePreview()">Close</button>
            </div>
        </div>
    </div>

    <!-- Input Modal (for rename/create folder) -->
    <div class="modal-overlay input-modal" id="inputModal">
        <div class="modal">
            <div class="modal-header">
                <h3 id="inputModalTitle">Input</h3>
                <button class="modal-close" onclick="closeInputModal()">&times;</button>
            </div>
            <div class="modal-body">
                <input type="text" id="inputModalField" placeholder="">
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeInputModal()">Cancel</button>
                <button class="btn btn-primary" id="inputModalSubmit">Submit</button>
            </div>
        </div>
    </div>

    <!-- Folder Picker Modal -->
    <div class="modal-overlay" id="folderPickerModal">
        <div class="modal" style="width:400px">
            <div class="modal-header">
                <h3 id="folderPickerTitle">Select Destination</h3>
                <button class="modal-close" onclick="closeFolderPicker()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="folder-picker" id="folderPickerList"></div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeFolderPicker()">Cancel</button>
                <button class="btn btn-primary" id="folderPickerSubmit">Select</button>
            </div>
        </div>
    </div>

    <!-- Toast container -->
    <div class="toast-container" id="toastContainer"></div>

    <!-- Upload progress -->
    <div class="upload-progress" id="uploadProgress" style="display:none"></div>

    <script>
        // State
        let currentPath = '';
        let files = [];
        let selectedItems = new Set();
        let currentView = 'grid';
        let contextTarget = null;
        let previewFilePath = null;

        // File icons
        const FILE_ICONS = {
            folder: '&#128193;',
            image: '&#128444;',
            video: '&#127916;',
            audio: '&#127925;',
            document: '&#128196;',
            archive: '&#128230;',
            code: '&#128187;',
            executable: '&#9881;',
            file: '&#128196;'
        };

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadFiles();
            setupDragDrop();
            setupKeyboard();
            document.addEventListener('click', hideContextMenu);
        });

        // API calls
        async function api(endpoint, options = {}) {
            try {
                const response = await fetch(endpoint, options);
                return await response.json();
            } catch (e) {
                console.error('API error:', e);
                return { success: false, error: e.message };
            }
        }

        // Load files
        async function loadFiles() {
            const data = await api(`/api/files?path=${encodeURIComponent(currentPath)}`);
            if (data.success) {
                files = data.items;
                renderBreadcrumb(data.breadcrumb);
                renderFiles();
                document.getElementById('itemCount').textContent = `${data.total} items`;
            } else {
                showToast(data.error || 'Failed to load files', 'error');
            }
        }

        // Render breadcrumb
        function renderBreadcrumb(breadcrumb) {
            const el = document.getElementById('breadcrumb');
            el.innerHTML = breadcrumb.map((item, i) => {
                if (i === breadcrumb.length - 1) {
                    return `<span>${item.name}</span>`;
                }
                return `<a href="#" onclick="navigateTo('${item.path}')">${item.name}</a><span>/</span>`;
            }).join('');
        }

        // Render files
        function renderFiles() {
            const grid = document.getElementById('fileGrid');
            const search = document.getElementById('searchInput').value.toLowerCase();

            let filtered = files;
            if (search) {
                filtered = files.filter(f => f.name.toLowerCase().includes(search));
            }

            if (filtered.length === 0) {
                grid.innerHTML = '<p style="color:var(--text-secondary);padding:40px;text-align:center">No files found</p>';
                return;
            }

            grid.innerHTML = filtered.map(file => {
                const isSelected = selectedItems.has(file.path);
                const icon = FILE_ICONS[file.type] || FILE_ICONS.file;
                const thumbnail = file.thumbnail ?
                    `<img class="file-thumbnail" src="/thumbnail/${encodeURIComponent(file.thumbnail)}" onerror="this.style.display='none';this.nextElementSibling.style.display='block'"><div class="file-icon" style="display:none">${icon}</div>` :
                    `<div class="file-icon">${icon}</div>`;

                return `
                    <div class="file-item ${isSelected ? 'selected' : ''}"
                         data-path="${file.path}"
                         data-isdir="${file.is_dir}"
                         onclick="handleItemClick(event, '${file.path}')"
                         ondblclick="handleItemDblClick('${file.path}', ${file.is_dir})"
                         oncontextmenu="showContextMenu(event, '${file.path}', ${file.is_dir})">
                        <div class="checkbox" onclick="toggleSelect(event, '${file.path}')"></div>
                        ${thumbnail}
                        <div class="file-name">${escapeHtml(file.name)}</div>
                        <div class="file-info">${file.is_dir ? 'Folder' : file.size_str}</div>
                    </div>
                `;
            }).join('');

            grid.className = `file-grid ${currentView}`;
        }

        // Navigation
        function navigateTo(path) {
            currentPath = path;
            selectedItems.clear();
            updateSelectionBar();
            loadFiles();
        }

        // Handle clicks
        function handleItemClick(event, path) {
            if (event.target.classList.contains('checkbox')) return;

            if (event.ctrlKey || event.metaKey) {
                toggleSelect(event, path);
            } else if (event.shiftKey && selectedItems.size > 0) {
                // Range select
                const items = Array.from(document.querySelectorAll('.file-item'));
                const paths = items.map(el => el.dataset.path);
                const lastSelected = Array.from(selectedItems).pop();
                const startIdx = paths.indexOf(lastSelected);
                const endIdx = paths.indexOf(path);
                const [from, to] = startIdx < endIdx ? [startIdx, endIdx] : [endIdx, startIdx];
                for (let i = from; i <= to; i++) {
                    selectedItems.add(paths[i]);
                }
                updateSelectionBar();
                renderFiles();
            }
        }

        function handleItemDblClick(path, isDir) {
            if (isDir) {
                navigateTo(path);
            } else {
                previewFile(path);
            }
        }

        function toggleSelect(event, path) {
            event.stopPropagation();
            if (selectedItems.has(path)) {
                selectedItems.delete(path);
            } else {
                selectedItems.add(path);
            }
            updateSelectionBar();
            renderFiles();
        }

        function selectAll() {
            files.forEach(f => selectedItems.add(f.path));
            updateSelectionBar();
            renderFiles();
        }

        function clearSelection() {
            selectedItems.clear();
            updateSelectionBar();
            renderFiles();
        }

        function updateSelectionBar() {
            const bar = document.getElementById('selectionBar');
            const count = selectedItems.size;
            if (count > 0) {
                bar.classList.add('visible');
                document.getElementById('selectionCount').textContent = `${count} selected`;
            } else {
                bar.classList.remove('visible');
            }
        }

        // View modes
        function setView(view) {
            currentView = view;
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.view === view);
            });
            renderFiles();
        }

        function filterFiles() {
            renderFiles();
        }

        // Context menu
        function showContextMenu(event, path, isDir) {
            event.preventDefault();
            event.stopPropagation();
            contextTarget = { path, isDir };

            const menu = document.getElementById('contextMenu');
            menu.style.left = event.clientX + 'px';
            menu.style.top = event.clientY + 'px';
            menu.classList.add('visible');
        }

        function hideContextMenu() {
            document.getElementById('contextMenu').classList.remove('visible');
        }

        // Context menu actions
        function openFile() {
            hideContextMenu();
            if (contextTarget.isDir) {
                navigateTo(contextTarget.path);
            } else {
                previewFile(contextTarget.path);
            }
        }

        function downloadContextItem() {
            hideContextMenu();
            window.location.href = `/download/${encodeURIComponent(contextTarget.path)}`;
        }

        function renameItem() {
            hideContextMenu();
            const name = contextTarget.path.split('/').pop();
            showInputModal('Rename', name, async (newName) => {
                const result = await api('/api/rename', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: contextTarget.path, name: newName })
                });
                if (result.success) {
                    showToast('Renamed successfully');
                    loadFiles();
                } else {
                    showToast(result.error, 'error');
                }
            });
        }

        function deleteItem() {
            hideContextMenu();
            if (confirm(`Delete "${contextTarget.path.split('/').pop()}"?`)) {
                deleteFiles([contextTarget.path]);
            }
        }

        function copyItem() {
            hideContextMenu();
            showFolderPicker('Copy to', async (dest) => {
                const result = await api('/api/copy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paths: [contextTarget.path], destination: dest })
                });
                if (result.success) {
                    showToast(result.message);
                    loadFiles();
                } else {
                    showToast(result.error, 'error');
                }
            });
        }

        function moveItem() {
            hideContextMenu();
            showFolderPicker('Move to', async (dest) => {
                const result = await api('/api/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paths: [contextTarget.path], destination: dest })
                });
                if (result.success) {
                    showToast(result.message);
                    loadFiles();
                } else {
                    showToast(result.error, 'error');
                }
            });
        }

        // Batch operations
        function downloadSelected() {
            if (selectedItems.size === 0) return;
            const paths = Array.from(selectedItems).map(p => encodeURIComponent(p)).join(',');
            window.location.href = `/api/zip?paths=${paths}`;
        }

        function deleteSelected() {
            if (selectedItems.size === 0) return;
            if (confirm(`Delete ${selectedItems.size} item(s)?`)) {
                deleteFiles(Array.from(selectedItems));
            }
        }

        async function deleteFiles(paths) {
            const result = await api('/api/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paths })
            });
            if (result.success) {
                showToast(result.message);
                selectedItems.clear();
                updateSelectionBar();
                loadFiles();
            } else {
                showToast(result.errors?.join(', ') || result.error, 'error');
            }
        }

        function moveSelected() {
            if (selectedItems.size === 0) return;
            showFolderPicker('Move to', async (dest) => {
                const result = await api('/api/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paths: Array.from(selectedItems), destination: dest })
                });
                if (result.success) {
                    showToast(result.message);
                    selectedItems.clear();
                    updateSelectionBar();
                    loadFiles();
                } else {
                    showToast(result.error, 'error');
                }
            });
        }

        function copySelected() {
            if (selectedItems.size === 0) return;
            showFolderPicker('Copy to', async (dest) => {
                const result = await api('/api/copy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paths: Array.from(selectedItems), destination: dest })
                });
                if (result.success) {
                    showToast(result.message);
                    loadFiles();
                } else {
                    showToast(result.error, 'error');
                }
            });
        }

        // Create folder
        function createFolder() {
            showInputModal('New Folder', '', async (name) => {
                const result = await api('/api/create-folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: currentPath, name })
                });
                if (result.success) {
                    showToast(result.message);
                    loadFiles();
                } else {
                    showToast(result.error, 'error');
                }
            });
        }

        // Preview
        async function previewFile(path) {
            previewFilePath = path;
            const data = await api(`/api/preview/${encodeURIComponent(path)}`);

            const modal = document.getElementById('previewModal');
            const body = document.getElementById('previewBody');
            const title = document.getElementById('previewTitle');
            const info = document.getElementById('previewInfo');

            title.textContent = path.split('/').pop();
            info.textContent = data.size_str || '';

            if (data.type === 'text' && data.content !== undefined) {
                body.innerHTML = `<pre>${escapeHtml(data.content)}</pre>`;
            } else if (data.type === 'image' || data.mime?.startsWith('image/')) {
                body.innerHTML = `<img src="/stream/${encodeURIComponent(path)}">`;
            } else if (data.type === 'video' || data.mime?.startsWith('video/')) {
                body.innerHTML = `<video controls autoplay><source src="/stream/${encodeURIComponent(path)}" type="${data.mime}"></video>`;
            } else if (data.type === 'audio' || data.mime?.startsWith('audio/')) {
                body.innerHTML = `<audio controls autoplay><source src="/stream/${encodeURIComponent(path)}" type="${data.mime}"></audio>`;
            } else {
                body.innerHTML = `<div style="padding:40px;text-align:center">
                    <div style="font-size:64px;margin-bottom:20px">${FILE_ICONS[data.type] || FILE_ICONS.file}</div>
                    <p>Preview not available</p>
                    <p style="color:var(--text-secondary)">${data.mime || 'Unknown type'} - ${data.size_str}</p>
                </div>`;
            }

            modal.classList.add('visible');
        }

        function closePreview() {
            document.getElementById('previewModal').classList.remove('visible');
            document.getElementById('previewBody').innerHTML = '';
        }

        function downloadPreviewFile() {
            if (previewFilePath) {
                window.location.href = `/download/${encodeURIComponent(previewFilePath)}`;
            }
        }

        // Input modal
        let inputModalCallback = null;

        function showInputModal(title, value, callback) {
            inputModalCallback = callback;
            document.getElementById('inputModalTitle').textContent = title;
            const field = document.getElementById('inputModalField');
            field.value = value;
            document.getElementById('inputModal').classList.add('visible');
            field.focus();
            field.select();
        }

        function closeInputModal() {
            document.getElementById('inputModal').classList.remove('visible');
            inputModalCallback = null;
        }

        document.getElementById('inputModalSubmit').addEventListener('click', () => {
            const value = document.getElementById('inputModalField').value.trim();
            if (value && inputModalCallback) {
                inputModalCallback(value);
            }
            closeInputModal();
        });

        document.getElementById('inputModalField').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.getElementById('inputModalSubmit').click();
            }
        });

        // Folder picker
        let folderPickerCallback = null;
        let folderPickerPath = '';

        async function showFolderPicker(title, callback) {
            folderPickerCallback = callback;
            folderPickerPath = '';
            document.getElementById('folderPickerTitle').textContent = title;
            await loadFolderPickerItems('');
            document.getElementById('folderPickerModal').classList.add('visible');
        }

        async function loadFolderPickerItems(path) {
            folderPickerPath = path;
            const data = await api(`/api/files?path=${encodeURIComponent(path)}`);
            const list = document.getElementById('folderPickerList');

            let html = '';
            if (path) {
                const parent = path.split('/').slice(0, -1).join('/');
                html += `<div class="folder-picker-item" onclick="loadFolderPickerItems('${parent}')">&#128193; ..</div>`;
            }
            html += `<div class="folder-picker-item selected" onclick="selectFolderPickerItem(this, '${path}')">&#128193; (Current folder)</div>`;

            if (data.items) {
                data.items.filter(f => f.is_dir).forEach(folder => {
                    html += `<div class="folder-picker-item" ondblclick="loadFolderPickerItems('${folder.path}')" onclick="selectFolderPickerItem(this, '${folder.path}')">&#128193; ${escapeHtml(folder.name)}</div>`;
                });
            }

            list.innerHTML = html;
        }

        function selectFolderPickerItem(el, path) {
            document.querySelectorAll('.folder-picker-item').forEach(i => i.classList.remove('selected'));
            el.classList.add('selected');
            folderPickerPath = path;
        }

        function closeFolderPicker() {
            document.getElementById('folderPickerModal').classList.remove('visible');
            folderPickerCallback = null;
        }

        document.getElementById('folderPickerSubmit').addEventListener('click', () => {
            if (folderPickerCallback) {
                folderPickerCallback(folderPickerPath);
            }
            closeFolderPicker();
        });

        // Upload
        function setupDragDrop() {
            const dropZone = document.getElementById('dropZone');

            ['dragenter', 'dragover'].forEach(event => {
                document.addEventListener(event, (e) => {
                    e.preventDefault();
                    dropZone.classList.add('dragover');
                });
            });

            ['dragleave', 'drop'].forEach(event => {
                document.addEventListener(event, (e) => {
                    e.preventDefault();
                    dropZone.classList.remove('dragover');
                });
            });

            document.addEventListener('drop', (e) => {
                if (e.dataTransfer.files.length > 0) {
                    uploadFiles(e.dataTransfer.files);
                }
            });
        }

        async function uploadFiles(fileList) {
            const progressContainer = document.getElementById('uploadProgress');
            progressContainer.style.display = 'block';
            progressContainer.innerHTML = '';

            for (const file of fileList) {
                const itemEl = document.createElement('div');
                itemEl.className = 'upload-item';
                itemEl.innerHTML = `
                    <div class="name">${escapeHtml(file.name)}</div>
                    <div class="progress-bar"><div class="fill" style="width:0%"></div></div>
                `;
                progressContainer.appendChild(itemEl);

                const formData = new FormData();
                formData.append('file', file);

                try {
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', `/api/upload?path=${encodeURIComponent(currentPath)}`);

                    xhr.upload.onprogress = (e) => {
                        if (e.lengthComputable) {
                            const pct = (e.loaded / e.total * 100).toFixed(0);
                            itemEl.querySelector('.fill').style.width = pct + '%';
                        }
                    };

                    await new Promise((resolve, reject) => {
                        xhr.onload = () => {
                            if (xhr.status === 200) {
                                itemEl.querySelector('.fill').style.width = '100%';
                                resolve();
                            } else {
                                reject(new Error('Upload failed'));
                            }
                        };
                        xhr.onerror = reject;
                        xhr.send(formData);
                    });
                } catch (e) {
                    itemEl.querySelector('.name').style.color = 'var(--danger)';
                }
            }

            setTimeout(() => {
                progressContainer.style.display = 'none';
                loadFiles();
            }, 1000);
        }

        // Keyboard shortcuts
        function setupKeyboard() {
            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT') return;

                if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    selectAll();
                } else if (e.key === 'Escape') {
                    clearSelection();
                    closePreview();
                    closeInputModal();
                    closeFolderPicker();
                } else if (e.key === 'Delete') {
                    if (selectedItems.size > 0) {
                        deleteSelected();
                    }
                } else if (e.key === 'Backspace' && currentPath) {
                    const parent = currentPath.split('/').slice(0, -1).join('/');
                    navigateTo(parent);
                }
            });
        }

        // Toast notifications
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);

            setTimeout(() => toast.remove(), 3000);
        }

        // Utilities
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Load stats periodically
        setInterval(async () => {
            const stats = await api('/api/stats');
            if (stats) {
                document.getElementById('connectionInfo').textContent =
                    `Downloads: ${stats.total_downloads} | Uploads: ${stats.total_uploads}`;
            }
        }, 5000);
    </script>
</body>
</html>'''

    def generate_monitor_html(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Monitor</title>
    <style>
        :root {
            --bg-primary: #0d0d0d;
            --bg-secondary: #1a1a1a;
            --accent: #00ff99;
            --accent-secondary: #00ffff;
            --text-primary: #e0e0e0;
            --text-secondary: #888;
            --border: #333;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Fira Code', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 20px;
        }

        .header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 20px;
        }

        .header h1 { color: var(--accent); }

        .header a {
            padding: 8px 16px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            color: var(--accent-secondary);
            text-decoration: none;
            border-radius: 4px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-box {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }

        .stat-box h3 {
            color: var(--text-secondary);
            font-size: 12px;
            margin-bottom: 10px;
        }

        .stat-box .value {
            font-size: 32px;
            color: var(--accent);
        }

        .section {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .section h2 {
            color: var(--accent);
            margin-bottom: 15px;
            font-size: 16px;
        }

        .device-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 10px;
        }

        .device-item {
            background: var(--bg-primary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 15px;
        }

        .device-ip {
            color: var(--accent-secondary);
            font-weight: bold;
            margin-bottom: 5px;
        }

        .device-info {
            color: var(--text-secondary);
            font-size: 12px;
            line-height: 1.6;
        }

        .log-container {
            max-height: 400px;
            overflow-y: auto;
        }

        .log-entry {
            padding: 10px;
            border-left: 3px solid var(--border);
            margin-bottom: 5px;
            background: var(--bg-primary);
        }

        .log-entry.download { border-left-color: var(--accent); }
        .log-entry.upload { border-left-color: #ffa502; }

        .log-time {
            color: var(--text-secondary);
            font-size: 11px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Server Monitor</h1>
        <a href="/">Back to Files</a>
    </div>

    <div class="stats-grid">
        <div class="stat-box">
            <h3>ACTIVE CONNECTIONS</h3>
            <div class="value" id="activeConnections">0</div>
        </div>
        <div class="stat-box">
            <h3>TOTAL DOWNLOADS</h3>
            <div class="value" id="totalDownloads">0</div>
        </div>
        <div class="stat-box">
            <h3>TOTAL UPLOADS</h3>
            <div class="value" id="totalUploads">0</div>
        </div>
        <div class="stat-box">
            <h3>DATA TRANSFERRED</h3>
            <div class="value" id="totalBytes">0 MB</div>
        </div>
    </div>

    <div class="section">
        <h2>Connected Devices</h2>
        <div class="device-grid" id="deviceGrid"></div>
    </div>

    <div class="section">
        <h2>Activity Log</h2>
        <div class="log-container" id="logContainer"></div>
    </div>

    <script>
        async function updateStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();

                document.getElementById('activeConnections').textContent = data.active_connections;
                document.getElementById('totalDownloads').textContent = data.total_downloads;
                document.getElementById('totalUploads').textContent = data.total_uploads;
                document.getElementById('totalBytes').textContent = (data.total_bytes / 1024 / 1024).toFixed(2) + ' MB';

                // Devices
                const deviceGrid = document.getElementById('deviceGrid');
                if (data.device_history.length === 0) {
                    deviceGrid.innerHTML = '<p style="color:var(--text-secondary)">No devices connected yet</p>';
                } else {
                    deviceGrid.innerHTML = data.device_history.map(d => `
                        <div class="device-item">
                            <div class="device-ip">${d.display_name}</div>
                            <div class="device-info">
                                Hostname: ${d.hostname}<br>
                                First seen: ${d.first_seen}<br>
                                Last seen: ${d.last_seen}<br>
                                Transfers: ${d.total_transfers}<br>
                                Last action: ${d.last_action}
                            </div>
                        </div>
                    `).join('');
                }

                // Logs
                const logContainer = document.getElementById('logContainer');
                if (data.recent_logs.length === 0) {
                    logContainer.innerHTML = '<p style="color:var(--text-secondary)">No activity yet</p>';
                } else {
                    logContainer.innerHTML = data.recent_logs.slice().reverse().map(log => {
                        const type = log.action?.includes('DOWNLOAD') ? 'download' : 'upload';
                        return `
                            <div class="log-entry ${type}">
                                <div class="log-time">${log.timestamp}</div>
                                <strong>${log.ip}</strong> - ${log.action}<br>
                                ${log.filename}
                                ${log.details ? '<br><small>' + log.details + '</small>' : ''}
                            </div>
                        `;
                    }).join('');
                }
            } catch (e) {
                console.error('Failed to update stats:', e);
            }
        }

        updateStats();
        setInterval(updateStats, 2000);
    </script>
</body>
</html>'''


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_local_ip():
    """Get local IP address"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def get_hostname_from_ip(ip):
    """Resolve hostname from IP"""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return None

def track_device(ip, user_agent, action):
    """Track device connection history"""
    with lock:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if ip not in device_history:
            device_history[ip] = {
                "first_seen": current_time,
                "last_seen": current_time,
                "hostname": get_hostname_from_ip(ip),
                "total_transfers": 1,
                "user_agents": {user_agent},
                "last_action": action
            }
        else:
            device_history[ip]["last_seen"] = current_time
            device_history[ip]["total_transfers"] += 1
            device_history[ip]["user_agents"].add(user_agent)
            device_history[ip]["last_action"] = action

def show_qr_code(url):
    """Display QR code for URL"""
    if qrcode is None:
        print(f"QR code unavailable. Access: {url}")
        return

    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.make_image().show()
        print("QR code displayed!")
    except Exception as e:
        print(f"QR error: {e}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    global ROOT_FOLDER, PORT

    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced File Manager Server')
    parser.add_argument('folder', nargs='?', default=os.path.expanduser('~/Documents'),
                        help='Root folder to serve (default: ~/Documents)')
    parser.add_argument('-p', '--port', type=int, default=8080, help='Port (default: 8080)')
    parser.add_argument('--no-qr', action='store_true', help='Disable QR code')
    args = parser.parse_args()

    ROOT_FOLDER = os.path.abspath(args.folder)
    PORT = args.port

    if not os.path.isdir(ROOT_FOLDER):
        print(f"Error: {ROOT_FOLDER} is not a directory")
        sys.exit(1)

    init_thumbnails(ROOT_FOLDER)

    ip = get_local_ip()
    url = f"http://{ip}:{PORT}"

    print(f"\n{'='*60}")
    print(f"  Enhanced File Manager Server")
    print(f"{'='*60}")
    print(f"  URL:     {url}")
    print(f"  Monitor: {url}/monitor")
    print(f"  Root:    {ROOT_FOLDER}")
    print(f"{'='*60}")
    print(f"  Features:")
    print(f"    - Directory navigation with breadcrumb")
    print(f"    - File operations (rename, delete, move, copy)")
    print(f"    - File preview (images, video, audio, code)")
    print(f"    - Multi-select with batch operations")
    print(f"    - Download as ZIP")
    print(f"    - Drag & drop upload")
    print(f"    - Real-time monitoring")
    print(f"{'='*60}\n")

    if not args.no_qr:
        show_qr_code(url)

    try:
        server = ThreadingHTTPServer(("0.0.0.0", PORT), FileManagerHandler)
        print("Server running. Press Ctrl+C to stop.\n")
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n\nServer stopped.")
        print(f"Downloads: {connection_stats['total_downloads']}")
        print(f"Uploads: {connection_stats['total_uploads']}")
        print(f"Data: {connection_stats['total_bytes_transferred']/1024/1024:.2f} MB")

if __name__ == "__main__":
    main()
