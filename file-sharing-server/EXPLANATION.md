# File Sharing Server — Complete Developer Explanation

> **Purpose of this document:** Give you a deep, step-by-step understanding of every part of this project so you can recreate it from scratch with confidence.

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Project Structure Explained](#3-project-structure-explained)
4. [Tech Stack & Why It Was Chosen](#4-tech-stack--why-it-was-chosen)
5. [Module-by-Module Breakdown](#5-module-by-module-breakdown)
   - [auth.py — Token Management](#authpy--token-management)
   - [utils.py — Safety Utilities](#utilspy--safety-utilities)
   - [file_manager.py — Share & File Logic](#file_managerpy--share--file-logic)
   - [logger.py — Activity Logging](#loggerpy--activity-logging)
   - [server.py — HTTP Server](#serverpy--http-server)
   - [main.py — CLI Entry Point](#mainpy--cli-entry-point)
   - [ui/index.html — Web Frontend](#uiindexhtml--web-frontend)
   - [fileserver.py — Standalone Enhanced Server](#fileserverpy--standalone-enhanced-server)
6. [Data Storage Design](#6-data-storage-design)
7. [Request Flow (End-to-End)](#7-request-flow-end-to-end)
8. [Security Design](#8-security-design)
9. [API Reference](#9-api-reference)
10. [Step-by-Step: Rebuild From Scratch](#10-step-by-step-rebuild-from-scratch)
11. [Common Patterns Used](#11-common-patterns-used)
12. [Extending the Project](#12-extending-the-project)

---

## 1. What Is This Project?

This is a **LAN (Local Area Network) file sharing server** written entirely in Python. It lets you:

- **Share a folder** on your machine over the local network
- **Browse that folder** from any browser on the same network (no client installation needed)
- **Upload files** via drag-and-drop or file picker
- **Download files** with a single click
- **Control access** using unique per-share tokens (like a one-time URL)
- **Audit activity** via a structured JSON activity log
- **Administer shares** via a master-token-protected admin dashboard

The project contains **two implementations** that can be used independently:

| Component | File | Description |
|---|---|---|
| **Modular Package** | `file_sharing_server/` | Clean, importable Python package with separated concerns |
| **Standalone Server** | `fileserver.py` | All-in-one enhanced server with more advanced features |

Both achieve the same core goal but differ in design philosophy. The package is better for extensibility; the standalone file is better for quick, single-file deployment.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                           │
│                                                                 │
│   http://192.168.1.100:8000/?token=<UUID>                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP GET / POST
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FileShareServer                              │
│  (Python stdlib HTTPServer on 0.0.0.0:8000)                     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               FileShareHandler                           │   │
│  │  (BaseHTTPRequestHandler subclass)                       │   │
│  │                                                          │   │
│  │  Routes:                                                 │   │
│  │   GET  /              → serve ui/index.html              │   │
│  │   GET  /admin         → serve admin dashboard HTML       │   │
│  │   GET  /api/list      → list active shares               │   │
│  │   GET  /api/explore   → browse directory                 │   │
│  │   GET  /download/...  → stream file to browser           │   │
│  │   POST /api/upload    → receive multipart upload         │   │
│  │   POST /api/create_folder → create folder                │   │
│  │   GET  /api/admin     → admin data (master token)        │   │
│  └──────────────┬──────────────┬──────────────┬─────────────┘   │
│                 │              │              │                  │
│         ┌───────▼──────┐ ┌────▼────┐ ┌───────▼───────┐         │
│         │ ShareManager │ │  Auth   │ │ActivityLogger │         │
│         │(file_manager)│ │(auth.py)│ │ (logger.py)   │         │
│         └───────┬──────┘ └─────────┘ └───────────────┘         │
│                 │                                               │
│         ┌───────▼──────┐                                        │
│         │   utils.py   │                                        │
│         │(path safety) │                                        │
│         └──────────────┘                                        │
└────────────────────────────────────────┬────────────────────────┘
                                         │ reads/writes
                                         ▼
                              ┌──────────────────────┐
                              │      data/           │
                              │  ├── shares.json     │
                              │  ├── activity.log    │
                              │  ├── master_token.txt│
                              │  └── uploads/        │
                              │      └── {share_id}/ │
                              │          └── {token}/│
                              └──────────────────────┘
```

---

## 3. Project Structure Explained

```
file-sharing-server/
│
├── file_sharing_server/          ← The importable Python package
│   ├── __init__.py               ← Package metadata (version, author)
│   ├── __main__.py               ← Allows `python -m file_sharing_server`
│   ├── main.py                   ← CLI argument parsing + command dispatch
│   ├── server.py                 ← HTTP server + all request handlers
│   ├── file_manager.py           ← Share creation, file read/write logic
│   ├── auth.py                   ← UUID token generation & validation
│   ├── logger.py                 ← JSON activity log writer/reader
│   └── utils.py                  ← Path safety, file extension validation
│
├── ui/
│   └── index.html                ← Complete web UI (pure HTML + CSS + JS)
│
├── fileserver.py                 ← Standalone all-in-one enhanced server
├── filebrowser/                  ← Future filebrowser component (see filebrowser/README.md)
├── setup.py                      ← pip-installable package config
├── requirements.txt              ← Runtime dependencies (only colorama)
├── README.md                     ← User-facing documentation
├── QUICKSTART.md                 ← Getting-started guide
└── EXPLANATION.md                ← This file (developer deep-dive)
```

---

## 4. Tech Stack & Why It Was Chosen

| Layer | Technology | Why |
|---|---|---|
| **Server runtime** | Python 3.9+ stdlib only | Zero external deps; runs anywhere Python is installed |
| **HTTP server** | `http.server.HTTPServer` + `BaseHTTPRequestHandler` | Built into Python, no framework needed for this use case |
| **Data storage** | JSON files | Simple, human-readable, no database to install |
| **Token system** | `uuid.uuid4()` | Cryptographically random 128-bit tokens; easy to generate |
| **Frontend** | Vanilla HTML/CSS/JS | No build step, no Node.js needed, runs from a single file |
| **Optional color** | `colorama` | Makes CLI output colorful on all platforms |

**Key design decision:** Use **only Python stdlib** so the server can be run on any machine that has Python 3.9+, with no `pip install` required except for the optional `colorama`.

---

## 5. Module-by-Module Breakdown

### `auth.py` — Token Management

**What it does:** Generates and validates UUID tokens used for access control.

```python
# Two classes:

class TokenManager:
    # Static methods only — no state
    generate_token()          # → str (new UUID4 e.g. "a1b2c3d4-e5f6-...")
    validate_token(token)     # → bool (checks if string is a valid UUID)
    generate_master_token()   # → str (same as generate_token, alias for clarity)

class MasterTokenManager:
    # Has state: knows where the master_token.txt file is
    __init__(token_file)      # path to file storing the single master token
    get_or_create()           # reads token from file; creates new one if missing
    validate(token)           # reads file and compares token == stored_token
```

**Key points:**
- Tokens are **UUIDs (version 4)** — 32 hex digits with dashes, e.g. `a1b2c3d4-e5f6-47a8-9b0c-1d2e3f4a5b6c`
- The master token is stored in a plain-text file with `chmod 600` (owner read-only)
- Validation is done by comparing the token string directly — no hashing needed since UUIDs are already random enough for a trusted-network tool
- `uuid.UUID(token)` raises `ValueError` if the string is not a valid UUID, so validation wraps it in try/except

**How to reimplement:**
```python
import uuid
token = str(uuid.uuid4())           # generates token
uuid.UUID(token)                    # validates (raises ValueError if invalid)
```

---

### `utils.py` — Safety Utilities

**What it does:** Provides security-critical helper functions, especially for preventing **path traversal attacks**.

```python
safe_join_path(base, *parts)          # safely join paths, raises ValueError if result escapes base
validate_file_extension(name, exts)   # check if file extension is in allowed list
validate_directory_path(path)         # check if a directory exists, is readable
get_human_readable_size(bytes)        # "1.5MB", "200KB", etc.
validate_token_format(token)          # check UUID format without uuid module
```

**The most important function — `safe_join_path`:**

```python
def safe_join_path(base: Path, *parts: str) -> Path:
    # Step 1: reject absolute paths in parts (e.g., "/etc/passwd")
    for part in parts:
        if os.path.isabs(part):
            raise ValueError(f"Absolute paths not allowed: {part}")
        if ".." in part:
            # Extra explicit check for traversal sequences;
            # the resolve()+startswith() check below is the real safety net
            raise ValueError(f"Directory traversal not allowed: {part}")

    # Step 2: resolve to absolute path (resolves symlinks, normalizes ..)
    base = Path(base).resolve()
    result = (base / Path(*parts)).resolve()

    # Step 3: CRITICAL — ensure resolved path is still inside base
    if not str(result).startswith(str(base)):
        raise ValueError(f"Path escapes base directory: {result}")

    return result
```

**Why this matters:** Without this check, a malicious user could request `/download/share-id/../../etc/passwd` and read arbitrary files. The `resolve()` + `startswith()` check prevents this.

---

### `file_manager.py` — Share & File Logic

**What it does:** The "business logic" layer — creates/deletes shares, lists directories, handles file uploads and downloads.

**Two classes:**

#### `Share` (dataclass)
Represents one shared directory with all its settings:

```python
@dataclass
class Share:
    id: str                        # UUID identifying this share
    path: str                      # Absolute path to shared directory
    token: str                     # Access token for this share
    created: str                   # ISO timestamp
    expires: Optional[str]         # ISO timestamp or None
    max_file_size_mb: int          # Upload size limit
    allowed_extensions: List[str]  # e.g. ["exe", "deb"] or []
    description: str               # Human label
    webhook_url: Optional[str]     # Future: notify on events
```

`is_expired()` compares `datetime.utcnow()` against the `expires` field.

#### `ShareManager`
Manages the collection of shares, backed by `data/shares.json`:

```
ShareManager.__init__(data_dir)
  └── Creates data/ directory
  └── Loads shares.json into self.shares dict {share_id: Share}

Key methods:
  add_share(path, ...)     → generates UUID id+token, creates Share, saves JSON
  get_share(id)            → returns Share if found and not expired
  remove_share(id)         → deletes from dict, saves JSON, removes upload dir
  list_shares()            → returns list of non-expired share dicts
  explore_directory(id, path) → lists files/folders using Path.iterdir()
  upload_file(...)         → validates, writes to data/uploads/{id}/{token[:8]}/
  download_file(id, path)  → uses safe_join_path, returns file bytes
  create_folder(...)       → mkdir with safe_join_path
  cleanup_expired()        → removes all expired shares
```

**Upload path structure:**
```
data/uploads/
  └── {share_id}/
      └── {user_token[:8]}/    ← first 8 chars of token = user identifier
          └── {rel_path}/
              └── uploaded_file.txt
```

Using the first 8 characters of the token as the directory name isolates each user's uploads while keeping the directory name short.

---

### `logger.py` — Activity Logging

**What it does:** Writes structured JSON log entries to `data/activity.log`, one JSON object per line (JSONL format).

```python
class ActivityLogger:
    log(action, user_token, source_ip, file, status, details)  # generic log
    download(...)   # calls log() with action="download"
    upload(...)     # calls log() with action="upload"
    list_dir(...)   # calls log() with action="list_dir"
    auth_fail(...)  # calls log() with status="FAIL"
    create_folder(...)
    get_logs(limit) # reads last N lines from file, parses JSON
```

**Log entry format:**
```json
{
  "timestamp": "2025-03-23T12:00:00Z",
  "action": "download",
  "user_token": "a1b2c3d4...",
  "source_ip": "192.168.1.100",
  "file": "document.pdf",
  "status": "SUCCESS",
  "details": {"size_bytes": 1024}
}
```

**Important:** The user token is truncated to 8 chars + `"..."` in logs for privacy — enough to identify a session without exposing the full token.

---

### `server.py` — HTTP Server

**What it does:** The HTTP layer. Subclasses Python's `BaseHTTPRequestHandler` to handle all HTTP routes.

**Class hierarchy:**
```
http.server.BaseHTTPRequestHandler
  └── FileShareHandler           (handles individual requests)

http.server.HTTPServer
  └── FileShareServer            (manages the server lifecycle)
```

**`FileShareHandler` — request routing:**

```
do_GET(path):
  "/"           → _serve_ui()           read ui/index.html and send it
  "/admin"      → _serve_admin_ui()     generate admin HTML with embedded token
  "/api/..."    → _handle_api()         check token, route to specific API method
  "/download/." → _handle_download()    validate token, stream file bytes

do_POST(path):
  "/api/..."    → _handle_api_post()    check token, route to upload/create_folder
```

**Token validation flow (every protected request):**
```
1. Extract ?token= from query string
2. TokenManager.validate_token(token)  → check UUID format
3. share_manager.get_share(share_id)   → check share exists and not expired
4. share.token == token                → check token matches THIS share
5. If all pass → serve request
6. If any fail → log auth failure + return 401/403
```

**Multipart upload parsing:**
The server implements a simplified multipart form data parser (`_parse_multipart`) without any external library. It:
1. Splits the request body on the `boundary` string
2. Finds the part with `filename="..."` header to extract the file
3. Finds the part with `name="path"` to extract the optional upload directory

**`FileShareServer`:**
```python
class FileShareServer:
    def __init__(host, port, data_dir, ui_file):
        # Creates ShareManager, ActivityLogger, MasterTokenManager
        # Sets them as CLASS VARIABLES on FileShareHandler
        # (allows the handler to access them without passing through constructor)

    def run():
        server = HTTPServer((host, port), FileShareHandler)
        server.serve_forever()  # blocks until Ctrl+C
```

Note: Class variables are used on `FileShareHandler` because `BaseHTTPRequestHandler` instances are created per-request and you can't inject dependencies through the constructor.

---

### `main.py` — CLI Entry Point

**What it does:** Parses command-line arguments and maps them to actions.

**CLI commands implemented:**

| Command | What it does |
|---|---|
| `share <path> [options]` | Create share + start server |
| `list` | Print all active shares |
| `remove <id>` | Delete a share |
| `config <id> [options]` | Update share settings |
| `status` | Show data directory info |

**Pattern used: argparse subcommands**
```python
parser = argparse.ArgumentParser(...)
subparsers = parser.add_subparsers(dest="command")

share_parser = subparsers.add_parser("share")
share_parser.add_argument("path")
share_parser.add_argument("--port", type=int, default=8000)
# ... etc

args = parser.parse_args()
if args.command == "share":
    cli.cmd_share(args.path, args.port, ...)
```

**`FileShareCLI` class:**
- Wraps `ShareManager` and `MasterTokenManager`
- Each `cmd_*` method corresponds to one CLI command
- The `share` command is the only one that actually starts the server — all others just manipulate `data/shares.json`

---

### `ui/index.html` — Web Frontend

**What it does:** A single-file web application (HTML + CSS + JS) that serves as the entire client-side interface.

**Structure:**
```
HTML:
  ├── <style>             ← All CSS inline (dark GitHub-style theme)
  ├── .sidebar            ← List of available shares (left panel)
  ├── .header             ← Title + token display + "New Folder" button
  ├── .breadcrumb         ← Navigation trail (Root / folder / subfolder)
  ├── .file-list          ← Grid of file/folder cards
  ├── .upload-zone        ← Drag-and-drop upload area
  ├── #newFolderModal     ← Modal dialog for creating folders
  └── <script>            ← All JavaScript inline
```

**JavaScript class `FileShareApp`:**
```
constructor()
  ├── this.token = URL ?token= param
  ├── init() → loadShares() → loadDirectory()

loadShares()         → GET /api/list?token=...
                         → renders sidebar
                         → calls loadDirectory()

loadDirectory()      → GET /api/explore?share_id=...&path=...&token=...
                         → calls renderFileList()

renderFileList(items)→ builds HTML grid of file/folder cards

navigate(path)       → sets this.currentPath, calls loadDirectory()

uploadFile(file)     → POST /api/upload?share_id=...&token=...
                         with FormData (multipart)

downloadFile(path)   → window.location.href = /download/share_id/path?token=...

createFolder()       → POST /api/create_folder?share_id=...&token=...
                         with JSON body {path: "folder/name"}
```

**Drag-and-drop upload:**
```javascript
uploadZone.addEventListener('dragover', e => e.preventDefault());
uploadZone.addEventListener('drop', e => {
    this.handleFiles(e.dataTransfer.files);  // FileList from drop event
});
```

**Theme:** Dark mode using CSS custom properties (`--bg0`, `--bg1`, `--blue`, etc.) matching GitHub's dark theme colors.

---

### `fileserver.py` — Standalone Enhanced Server

**What it does:** A more feature-rich, single-file server that doesn't require the package structure. Think of it as the "power user" version.

**Additional features vs. the package:**

| Feature | Package | Standalone |
|---|---|---|
| File browsing & download | ✅ | ✅ |
| File upload | ✅ | ✅ |
| Token auth | ✅ | ❌ (open access) |
| Activity logging | ✅ | ✅ |
| File thumbnails | ❌ | ✅ (Pillow) |
| File preview (text/code) | ❌ | ✅ |
| QR code for URL | ❌ | ✅ (qrcode lib) |
| File operations (rename/delete/move) | ❌ | ✅ |
| Zip download of folders | ❌ | ✅ |
| Connection tracking | ❌ | ✅ |
| File type icons | Basic | ✅ (categorized) |

**Key file categories used for icons/sorting:**
```python
FILE_CATEGORIES = {
    'image': ['.jpg', '.png', '.gif', ...],
    'video': ['.mp4', '.mkv', ...],
    'audio': ['.mp3', '.wav', ...],
    'document': ['.pdf', '.doc', ...],
    'archive': ['.zip', '.tar', ...],
    'code': ['.py', '.js', '.html', ...],
    'executable': ['.exe', '.deb', ...]
}
```

**Running it:**
```bash
python fileserver.py          # serves ~/Documents on :8080
PORT=9000 python fileserver.py
```

---

## 6. Data Storage Design

All persistent data lives in the `data/` directory (created automatically on first run):

```
data/
├── shares.json           ← All share configurations
├── activity.log          ← Append-only JSON log (one entry per line)
├── master_token.txt      ← Single master token (chmod 600)
└── uploads/
    └── {share_id}/
        └── {token[:8]}/  ← Per-user upload isolation
            ├── file.txt
            └── subfolder/
                └── file2.txt
```

### `shares.json` Schema

```json
{
  "shares": [
    {
      "id": "3f6c2b1a-8d4e-4f7a-b9c0-2e5d1a3f8b7c",
      "path": "/home/user/documents",
      "token": "7a2e9b4c-1d6f-4e8a-b3c5-0f2d7a9e4b1c",
      "created": "2025-03-23T12:00:00Z",
      "expires": null,
      "max_file_size_mb": 500,
      "allowed_extensions": [],
      "description": "My Documents",
      "webhook_url": null
    }
  ],
  "updated": "2025-03-23T12:00:00Z"
}
```

### `activity.log` Schema (JSONL — one JSON per line)

```json
{"timestamp": "2025-03-23T12:00:00Z", "action": "download", "user_token": "a1b2c3d...", "source_ip": "192.168.1.5", "file": "report.pdf", "status": "SUCCESS", "details": {"size_bytes": 204800}}
{"timestamp": "2025-03-23T12:01:00Z", "action": "upload", "user_token": "a1b2c3d...", "source_ip": "192.168.1.5", "file": "notes.txt", "status": "SUCCESS", "details": {"size_bytes": 512}}
{"timestamp": "2025-03-23T12:02:00Z", "action": "auth", "user_token": "unknown", "source_ip": "192.168.1.99", "file": null, "status": "FAIL", "details": {"reason": "Invalid token"}}
```

---

## 7. Request Flow (End-to-End)

### Example: User Downloads a File

```
1. Browser sends:
   GET /download/a1b2c3d4.../documents/report.pdf?token=xyz789ab...
   Host: 192.168.1.100:8000

2. FileShareHandler.do_GET() is called
   └── path starts with "/download/" → _handle_download()

3. _handle_download():
   a. Parse path: share_id = "a1b2c3d4...", file_path = "documents/report.pdf"
   b. Validate token format (uuid.UUID check)
   c. share = share_manager.get_share("a1b2c3d4...")
   d. Check: share.token == "xyz789ab..."  (token matches this share)
   e. share_manager.download_file("a1b2c3d4...", "documents/report.pdf")
      └── safe_join_path("/home/user/documents", "documents/report.pdf")
          → resolves to "/home/user/documents/documents/report.pdf"
          → checks it starts with "/home/user/documents"  ✓
      └── read_bytes() → returns file content
   f. Send HTTP 200 with Content-Type, Content-Disposition headers
   g. Write file bytes to socket
   h. activity_logger.download(token, ip, file_path, file_size)
      └── appends JSON line to data/activity.log

4. Browser receives file
```

### Example: User Uploads a File

```
1. Browser sends:
   POST /api/upload?share_id=a1b2c3d4...&token=xyz789ab...
   Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...
   
   [multipart body with file data]

2. FileShareHandler.do_POST() → _handle_api_post() → _api_upload()

3. _api_upload():
   a. Validate token + share access (same as download)
   b. Read Content-Length bytes from socket into body bytes
   c. _parse_multipart(body, boundary):
      → splits on boundary
      → finds part with 'filename="..."'
      → extracts filename and file_content bytes
      → finds part with 'name="path"' for optional subdirectory
   d. share_manager.upload_file(share_id, token, filename, content, rel_path)
      → check file size ≤ max_file_size_mb
      → check extension in allowed_extensions (if set)
      → user_dir = data/uploads/{share_id}/{token[:8]}/{rel_path}
      → safe_join_path(user_dir, filename)
      → write_bytes(content)
   e. activity_logger.upload(...)
   f. Send JSON {"message": "File uploaded: filename.txt"}
```

---

## 8. Security Design

### Path Traversal Prevention

**Attack:** Request `/download/share/../../etc/passwd`

**Defense (in `utils.py::safe_join_path`):**
```python
# Step 1: Reject obvious traversal patterns
if ".." in part:
    raise ValueError("Directory traversal not allowed")

# Step 2: Resolve all symlinks and ".." before checking
result = (base / part).resolve()

# Step 3: Ensure resolved path is inside base
if not str(result).startswith(str(base)):
    raise ValueError("Path escapes base directory")
```

### Token-Based Access

- Each share has its own **unique UUID token**
- Token is passed in the URL query string: `?token=UUID`
- Server validates: (1) is it a valid UUID format? (2) does it match the specific share?
- Master token is a separate UUID stored in `data/master_token.txt`

### Per-User Upload Isolation

- Uploaded files go to `data/uploads/{share_id}/{token[:8]}/` — not into the original shared directory
- Users cannot overwrite each other's uploads (different subdirectories)
- Users cannot overwrite the shared read-only files

### File Type Restrictions

- If `allowed_extensions` is set on a share, uploads with other extensions are rejected:
```python
if share.allowed_extensions:
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in share.allowed_extensions:
        return False, "File type not allowed"
```

### File Size Limits

- Each share has a `max_file_size_mb` limit (default 500MB)
- Checked before writing: `if len(file_content) > max_mb * 1024 * 1024`

### What This Server Does NOT Provide

- ❌ HTTPS/TLS (use nginx as a reverse proxy for public networks)
- ❌ Rate limiting
- ❌ Password authentication (tokens only)
- ❌ Virus scanning
- ❌ Multi-user login system

---

## 9. API Reference

All API endpoints require `?token=UUID` (or `?token=MASTER_UUID` for admin).

### `GET /`
Returns the web UI HTML file.

### `GET /admin?token=MASTER_TOKEN`
Returns the admin dashboard HTML (server-rendered with embedded token).

### `GET /api/list?token=TOKEN`
Returns all shares accessible with this token.

**Response:**
```json
{
  "shares": [
    {
      "id": "...",
      "path": "/path",
      "token": "...",
      "created": "2025-03-23T12:00:00Z",
      "expires": null,
      "max_file_size_mb": 500,
      "allowed_extensions": [],
      "description": ""
    }
  ]
}
```

### `GET /api/explore?share_id=ID&path=RELATIVE_PATH&token=TOKEN`
Lists the contents of a directory within a share.

**Response:**
```json
{
  "path": "subfolder",
  "items": [
    {"name": "file.txt", "type": "file", "size": 1024, "path": "subfolder/file.txt"},
    {"name": "docs", "type": "dir", "size": null, "path": "subfolder/docs"}
  ]
}
```

### `GET /download/SHARE_ID/FILE_PATH?token=TOKEN`
Streams file content. Response includes `Content-Disposition: attachment` header.

### `POST /api/upload?share_id=ID&token=TOKEN`
Upload a file. Body must be `multipart/form-data` with a `file` field and optional `path` field for subdirectory.

**Response:**
```json
{"message": "File uploaded: report.pdf"}
```

### `POST /api/create_folder?share_id=ID&token=TOKEN`
Create a folder within the user's upload area.

**Request body (JSON):**
```json
{"path": "projects/myproject"}
```

**Response:**
```json
{"message": "Folder created: projects/myproject"}
```

### `GET /api/admin?token=MASTER_TOKEN`
Returns admin dashboard data (all shares + last 100 activity log entries).

**Response:**
```json
{
  "shares": [...],
  "logs": [...],
  "total_shares": 3
}
```

---

## 10. Step-by-Step: Rebuild From Scratch

Here is how you would build this project from zero:

### Step 1: Create the package skeleton

```
mkdir file-sharing-server
cd file-sharing-server
mkdir -p file_sharing_server ui data
touch file_sharing_server/__init__.py
touch file_sharing_server/__main__.py
```

`__init__.py`:
```python
"""File Sharing Server."""
__version__ = "1.0.0"
```

`__main__.py` (allows `python -m file_sharing_server`):
```python
from .main import main
import sys
sys.exit(main())
```

### Step 2: Build the token system (`auth.py`)

```python
import uuid
from pathlib import Path

class TokenManager:
    @staticmethod
    def generate_token():
        return str(uuid.uuid4())

    @staticmethod
    def validate_token(token):
        try:
            uuid.UUID(token)
            return True
        except (ValueError, TypeError):
            return False

class MasterTokenManager:
    def __init__(self, token_file):
        self.token_file = Path(token_file)

    def get_or_create(self):
        if self.token_file.exists():
            return self.token_file.read_text().strip()
        token = str(uuid.uuid4())
        self.token_file.write_text(token)
        self.token_file.chmod(0o600)
        return token

    def validate(self, token):
        if not self.token_file.exists():
            return False
        return token == self.token_file.read_text().strip()
```

### Step 3: Build path safety utilities (`utils.py`)

```python
import os
from pathlib import Path

def safe_join_path(base, *parts):
    for part in parts:
        if os.path.isabs(part) or ".." in part:
            raise ValueError(f"Invalid path component: {part}")
    base = Path(base).resolve()
    result = (base / Path(*parts)).resolve()
    if not str(result).startswith(str(base)):
        raise ValueError("Path traversal detected")
    return result

def validate_file_extension(filename, allowed):
    if not allowed:
        return True
    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in [e.lower() for e in allowed]

def validate_directory_path(path):
    try:
        p = Path(path).resolve()
        if not p.exists():
            return False, f"Does not exist: {path}"
        if not p.is_dir():
            return False, f"Not a directory: {path}"
        if not os.access(p, os.R_OK):
            return False, f"Not readable: {path}"
        return True, ""
    except Exception as e:
        return False, str(e)
```

### Step 4: Build the activity logger (`logger.py`)

```python
import json
from datetime import datetime
from pathlib import Path

class ActivityLogger:
    def __init__(self, log_file):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, action, user_token, source_ip, file=None, status="SUCCESS", details=None):
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "user_token": (user_token[:8] + "...") if user_token else "unknown",
            "source_ip": source_ip,
            "file": file,
            "status": status,
            "details": details or {}
        }
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def get_logs(self, limit=100):
        if not self.log_file.exists():
            return []
        try:
            lines = self.log_file.read_text().splitlines()
            return [json.loads(l) for l in lines[-limit:] if l]
        except Exception:
            return []
```

### Step 5: Build the share manager (`file_manager.py`)

```python
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List

@dataclass
class Share:
    id: str
    path: str
    token: str
    created: str
    expires: Optional[str] = None
    max_file_size_mb: int = 500
    allowed_extensions: List[str] = None
    description: str = ""

    def is_expired(self):
        if not self.expires:
            return False
        expiry = datetime.fromisoformat(self.expires.replace("Z", ""))
        return datetime.utcnow() > expiry

class ShareManager:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.shares_file = self.data_dir / "shares.json"
        self.uploads_dir = self.data_dir / "uploads"
        self.uploads_dir.mkdir(exist_ok=True)
        self._load()

    def _load(self):
        self.shares = {}
        if not self.shares_file.exists():
            return
        data = json.loads(self.shares_file.read_text())
        for s in data.get("shares", []):
            share = Share(**s)
            self.shares[share.id] = share

    def _save(self):
        data = {"shares": [asdict(s) for s in self.shares.values()]}
        self.shares_file.write_text(json.dumps(data, indent=2))

    def add_share(self, path, **kwargs):
        from .auth import TokenManager
        share_id = TokenManager.generate_token()
        token = TokenManager.generate_token()
        share = Share(id=share_id, path=path, token=token,
                      created=datetime.utcnow().isoformat() + "Z", **kwargs)
        self.shares[share_id] = share
        self._save()
        return True, f"Share created: {share_id}", token

    def get_share(self, share_id):
        share = self.shares.get(share_id)
        if share and not share.is_expired():
            return share
        return None
    
    # ... (explore_directory, upload_file, download_file, create_folder as described above)
```

### Step 6: Build the HTTP server (`server.py`)

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, mimetypes, urllib.parse
from pathlib import Path

class FileShareHandler(BaseHTTPRequestHandler):
    # Class vars injected by FileShareServer:
    share_manager = None
    activity_logger = None
    master_token_manager = None
    ui_file = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        ip = self.client_address[0]

        if path in ("/", "/index.html"):
            return self._serve_ui()
        if path.startswith("/download/"):
            return self._handle_download(path, token, ip)
        if path.startswith("/api/"):
            return self._handle_api(path, params, token, ip)
        self._send_error(404, "Not found")

    def _serve_ui(self):
        content = self.ui_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # suppress default access log

class FileShareServer:
    def __init__(self, host="0.0.0.0", port=8000, data_dir=None, ui_file=None):
        # import managers
        from .file_manager import ShareManager
        from .logger import ActivityLogger
        from .auth import MasterTokenManager
        self.share_manager = ShareManager(data_dir or "./data")
        self.activity_logger = ActivityLogger(Path(data_dir or "./data") / "activity.log")
        self.master_token_manager = MasterTokenManager(Path(data_dir or "./data") / "master_token.txt")
        # inject into handler class
        FileShareHandler.share_manager = self.share_manager
        FileShareHandler.activity_logger = self.activity_logger
        FileShareHandler.master_token_manager = self.master_token_manager
        FileShareHandler.ui_file = Path(ui_file) if ui_file else None
        self.host = host
        self.port = port

    def run(self):
        server = HTTPServer((self.host, self.port), FileShareHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
```

### Step 7: Build the CLI (`main.py`)

```python
import argparse, sys
from pathlib import Path
from .server import FileShareServer
from .file_manager import ShareManager
from .auth import MasterTokenManager

def main():
    parser = argparse.ArgumentParser(description="File Sharing Server")
    subs = parser.add_subparsers(dest="command")

    # "share" subcommand
    sp = subs.add_parser("share")
    sp.add_argument("path")
    sp.add_argument("--port", type=int, default=8000)
    sp.add_argument("--host", default="0.0.0.0")
    sp.add_argument("--max-size", type=int, default=500)
    sp.add_argument("--expires-in", type=int)

    args = parser.parse_args()
    data_dir = Path("./data")
    share_mgr = ShareManager(data_dir)
    master_mgr = MasterTokenManager(data_dir / "master_token.txt")

    if args.command == "share":
        ok, msg, token = share_mgr.add_share(
            args.path, max_file_size_mb=args.max_size,
            expires_in_hours=args.expires_in
        )
        if not ok:
            print(f"Error: {msg}", file=sys.stderr)
            return 1
        master = master_mgr.get_or_create()
        print(f"Share token: {token}")
        print(f"Master token: {master}")
        print(f"URL: http://{args.host}:{args.port}/?token={token}")
        ui = Path(__file__).parent.parent / "ui" / "index.html"
        server = FileShareServer(args.host, args.port, data_dir, ui)
        server.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Step 8: Build the web UI (`ui/index.html`)

The UI is a single HTML file with:
1. **CSS** at the top (dark theme using CSS variables)
2. **HTML structure** in the middle (sidebar, header, file grid, upload zone, modal)
3. **JavaScript class** at the bottom (`FileShareApp`)

The JS class pattern to follow:
```javascript
class FileShareApp {
    constructor() {
        this.token = new URLSearchParams(window.location.search).get('token');
        this.currentShare = null;
        this.currentPath = '';
        this.init();
    }

    async init() {
        await this.loadShares();     // GET /api/list
    }

    async loadShares() {
        const res = await fetch(`/api/list?token=${this.token}`);
        const data = await res.json();
        this.currentShare = data.shares[0];
        await this.loadDirectory();
    }

    async loadDirectory() {
        const res = await fetch(
            `/api/explore?share_id=${this.currentShare.id}&path=${this.currentPath}&token=${this.token}`
        );
        const data = await res.json();
        this.renderFileList(data.items);
    }

    // ... navigate, uploadFile, downloadFile, createFolder
}
const app = new FileShareApp();
```

### Step 9: Create `setup.py`

```python
from setuptools import setup, find_packages
setup(
    name="file-sharing-server",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=["colorama>=0.4.4"],
    entry_points={
        "console_scripts": ["file-sharing-server=file_sharing_server.main:main"]
    }
)
```

### Step 10: Test it

```bash
# Create test directory
mkdir -p /tmp/test_share
echo "Hello World" > /tmp/test_share/test.txt

# Start the server
python -m file_sharing_server share /tmp/test_share

# The output will show:
# Share token: <UUID>
# URL: http://0.0.0.0:8000/?token=<UUID>

# In another terminal, test with curl:
curl "http://localhost:8000/?token=<UUID>"
curl "http://localhost:8000/api/list?token=<UUID>"
curl "http://localhost:8000/api/explore?share_id=<SHARE_ID>&path=&token=<UUID>"
curl "http://localhost:8000/download/<SHARE_ID>/test.txt?token=<UUID>"
```

---

## 11. Common Patterns Used

### 1. Dataclass for Data Models
```python
from dataclasses import dataclass, asdict

@dataclass
class Share:
    id: str
    path: str
    # ... fields

share.to_dict()  # or asdict(share) for JSON serialization
```

### 2. Class Variables for Dependency Injection in HTTP Handlers
Since `BaseHTTPRequestHandler` creates a new instance per request, dependencies are set as class variables:
```python
FileShareHandler.share_manager = ShareManager(...)
# Now every handler instance can access self.share_manager
```

### 3. Tuple Returns for Result + Error
Instead of exceptions for expected failures:
```python
def add_share(...) -> tuple[bool, str, Optional[str]]:
    if error:
        return False, "Error message", None
    return True, "Success message", token
```

### 4. Append-only JSON Log (JSONL)
```python
with open(log_file, "a") as f:
    f.write(json.dumps(entry) + "\n")
```

### 5. Resolve + StartsWith for Path Safety
```python
base = Path(base_dir).resolve()
result = (base / user_input).resolve()
assert str(result).startswith(str(base))  # prevent escaping
```

### 6. argparse Subcommands
```python
parser = argparse.ArgumentParser()
subs = parser.add_subparsers(dest="command")
share_cmd = subs.add_parser("share")
list_cmd = subs.add_parser("list")
```

---

## 12. Extending the Project

### Add HTTPS Support
Wrap the `HTTPServer` with an SSL context:
```python
import ssl
server = HTTPServer((host, port), FileShareHandler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("cert.pem", "key.pem")
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
```

### Add Upload Progress Tracking
Use chunked reading instead of reading the entire body at once, and emit server-sent events (SSE) for progress updates.

### Add Webhook on File Events
In `ShareManager.upload_file()`, after saving the file, make an HTTP POST to `share.webhook_url` with the event details.

### Add Password Authentication
Replace UUID tokens with `hmac.new(secret, username+timestamp).hexdigest()` tokens, or use HTTP Basic Auth headers.

### Add Multi-Share Support (Multiple Folders)
The `ShareManager` already supports multiple shares — just call `add_share()` multiple times. The CLI starts the server once but all shares are accessible through it.

### Add File Deletion
Add a `DELETE /api/file?share_id=...&path=...&token=...` endpoint that calls `Path.unlink()` after path validation.

---

*This document covers the full internal design of the file-sharing-server. With this knowledge, you should be able to recreate the entire project from scratch and extend it with new features.*
