# File Sharing Server

Simple, secure file sharing server for local networks. Share files with a web UI, no installation required on client side.

## Features

✨ **Core Features:**
- 📁 Browse directories and files via web UI
- 📤 Drag-and-drop file upload
- 📥 Download individual files
- 🔐 Token-based access control
- 🔗 Per-share unique URLs
- 📊 Activity logging (IP, file, timestamp)
- 🚫 Path traversal protection
- 🌐 Works on air-gapped networks (no internet required)

🔧 **Advanced Features:**
- 📂 Nested folder creation with full isolation
- 👤 Per-user upload directories
- ⏰ Auto-expiring shares
- 📝 File type restrictions
- 📚 Admin dashboard with activity log
- 🎯 Master token for admin access
- 💾 Persistent shares (survive restarts)
- 📏 File size limits per share

## Installation

### From Source

```bash
# Clone and enter directory
git clone <repo>
cd file-sharing-server

# Install with pip
pip install -e .

# Or run directly
python -m file_sharing_server share /path/to/folder
```

### Requirements
- Python 3.9+
- No external dependencies required (colorama optional for colored output)

## Quick Start

### 1. Share a Folder

```bash
python -m file_sharing_server share /home/user/documents
```

Output:
```
✓ Share created: a1b2c3d4-e5f6-47a8-9b0c-1d2e3f4a5b6c
├─ Share token: xyz789012-abcd-efgh-ijkl-mnopqrstuvwx
├─ Master token (admin access): master789012-abcd-efgh-ijkl-mnopqr

Starting server on http://0.0.0.0:8000

Access share:
  http://localhost:8000/?token=xyz789012-abcd-efgh-ijkl-mnopqrstuvwx

Admin panel:
  http://localhost:8000/admin?token=master789012-abcd-efgh-ijkl-mnopqr

Press Ctrl+C to stop server
```

### 2. Open in Browser

Share the token-based URL with others:
```
http://your-ip:8000/?token=xyz789012-abcd-efgh-ijkl-mnopqrstuvwx
```

### 3. Use the Interface

- **Browse**: Click folders to navigate
- **Upload**: Drag files onto the upload zone or click to select
- **Download**: Click "Download" button on any file
- **Create Folders**: Use "New Folder" button to organize uploads
- **Admin**: Access master token URL to see all shares and activity

## Command Reference

### Share a Folder

```bash
python -m file_sharing_server share /path/to/share [OPTIONS]
```

**Options:**
- `--host HOST` - Bind address (default: 0.0.0.0)
- `--port PORT` - Port number (default: 8000)
- `--description DESC` - Share description
- `--max-size MB` - Max file size in MB (default: 500)
- `--allowed-types TYPES` - Comma-separated file types (e.g., `exe,deb,txt`)
- `--expires-in HOURS` - Auto-expire share after N hours
- `--ui-file PATH` - Custom UI HTML file

**Examples:**

```bash
# Basic share
python -m file_sharing_server share ~/Downloads

# With size limit and type restrictions
python -m file_sharing_server share ~/files \
  --max-size 1000 \
  --allowed-types exe,deb,iso \
  --description "Installation files"

# Auto-expire after 2 hours
python -m file_sharing_server share ~/temp --expires-in 2

# Custom host/port
python -m file_sharing_server share ~/folder \
  --host 192.168.1.100 \
  --port 9000
```

### List Active Shares

```bash
python -m file_sharing_server list
```

### Remove a Share

```bash
python -m file_sharing_server remove <share_id>
```

### Configure a Share

```bash
python -m file_sharing_server config <share_id> \
  --max-size 1000 \
  --allowed-types pdf,txt
```

### Server Status

```bash
python -m file_sharing_server status
```

## API Reference

### GET /

Serves the web UI.

### GET /api/list

List all active shares for the current token.

**Request:**
```
GET /api/list?token=YOUR_TOKEN
```

**Response:**
```json
{
  "shares": [
    {
      "id": "share-id",
      "path": "/path/to/folder",
      "token": "access-token",
      "created": "2025-03-23T12:00:00Z",
      "expires": null,
      "max_file_size_mb": 500,
      "allowed_extensions": [],
      "description": "My share"
    }
  ]
}
```

### GET /api/explore

Explore directory contents.

**Request:**
```
GET /api/explore?share_id=SHARE_ID&path=RELATIVE_PATH&token=TOKEN
```

**Response:**
```json
{
  "path": "current/path",
  "items": [
    {
      "name": "filename.txt",
      "type": "file",
      "size": 1024,
      "path": "current/path/filename.txt"
    },
    {
      "name": "subfolder",
      "type": "dir",
      "size": null,
      "path": "current/path/subfolder"
    }
  ]
}
```

### GET /download/SHARE_ID/FILE_PATH

Download a file from the shared directory.

**Request:**
```
GET /download/share-id/path/to/file.txt?token=TOKEN
```

**Response:** File contents with appropriate MIME type.

### POST /api/upload

Upload a file to the share.

**Request:**
```
POST /api/upload?share_id=SHARE_ID&token=TOKEN
Content-Type: multipart/form-data

file=<binary_data>
path=optional/relative/path  # Optional nested path
```

**Response:**
```json
{
  "message": "File uploaded: filename.txt"
}
```

### POST /api/create_folder

Create a folder in the shared directory.

**Request:**
```
POST /api/create_folder?share_id=SHARE_ID&token=TOKEN
Content-Type: application/json

{
  "path": "path/to/new/folder"
}
```

**Response:**
```json
{
  "message": "Folder created: path/to/new/folder"
}
```

### GET /api/admin

Get admin dashboard (requires master token).

**Request:**
```
GET /api/admin?token=MASTER_TOKEN
```

**Response:**
```json
{
  "shares": [/* list of shares */],
  "logs": [/* activity logs */],
  "total_shares": 5
}
```

## Security Features

### Path Traversal Protection
- All paths are validated against directory traversal attacks (`../`, absolute paths)
- Uploads are restricted to designated user directories
- Download paths are normalized and verified to be within share directory

### Token-Based Access
- Each share has a unique UUID token
- Master token for admin access (stored in `master_token.txt`)
- No password required on trusted networks
- Tokens are simple UUIDs (128-bit entropy)

### Activity Logging
- All actions logged to `data/activity.log`
- Logs include: timestamp, action, user token, IP, file, status
- JSON format for easy parsing

### Per-User Isolation
- Uploaded files stored in `data/uploads/{share_id}/{user_token}/`
- Users can only access their own uploads folder
- Shared files are read-only from the original share

## Data Storage

```
data/
├── shares.json           # Share metadata and settings
├── activity.log          # JSON activity log (append-only)
├── master_token.txt      # Master token (chmod 600)
└── uploads/
    └── {share_id}/
        └── {user_token}/
            └── [user's uploaded files]
```

### shares.json Format

```json
{
  "shares": [
    {
      "id": "unique-share-id",
      "path": "/absolute/path/to/folder",
      "token": "access-token",
      "created": "2025-03-23T12:00:00Z",
      "expires": "2025-03-25T12:00:00Z",
      "max_file_size_mb": 500,
      "allowed_extensions": ["exe", "deb"],
      "description": "Installation files",
      "webhook_url": null
    }
  ],
  "updated": "2025-03-23T12:00:00Z"
}
```

### activity.log Format

Each line is a JSON object:

```json
{"timestamp": "2025-03-23T12:00:00Z", "action": "download", "user_token": "xyz789...", "source_ip": "192.168.1.100", "file": "document.pdf", "status": "SUCCESS", "details": {"size_bytes": 1024}}
```

## Network Setup

### Local Network (LAN)

1. **Find your IP:**
   ```bash
   hostname -I  # Linux/Mac
   ipconfig     # Windows
   ```

2. **Share and access:**
   ```bash
   # On server machine
   python -m file_sharing_server share ~/files

   # On client machine (another device on same network)
   # Open browser: http://192.168.1.100:8000/?token=YOUR_TOKEN
   ```

### Air-Gapped Networks

- No internet required - works over any network interface
- Peer-to-peer sharing on isolated networks
- Useful for secure document transfer without external connectivity

### Behind Router

1. Find server's local IP: `hostname -I`
2. Configure port forwarding on router (if external access needed)
3. Use local IP for internal access

## Performance

- Handles concurrent uploads/downloads
- Efficient streaming for large files
- JSON-based metadata (no database)
- Single Python process

**Tested with:**
- Files up to 1GB+
- 10+ concurrent users
- Thousands of files in directory

## Troubleshooting

### Port Already in Use

```bash
# Use different port
python -m file_sharing_server share ~/folder --port 9000
```

### Permission Denied

```bash
# Check directory permissions
ls -la /path/to/folder

# Fix if needed
chmod 755 /path/to/folder
```

### Token Issues

If you lose the token, use `list` command:

```bash
python -m file_sharing_server list
```

Tokens are also printed to console when share is created.

### Activity Log Issues

Activity log is optional - if it can't be written, server continues working.
Check log file location: `data/activity.log`

## Development

### Project Structure

```
file-sharing-server/
├── file_sharing_server/
│   ├── __init__.py        # Package info
│   ├── main.py            # CLI entry point
│   ├── server.py          # HTTP server + handlers
│   ├── file_manager.py    # Share + file operations
│   ├── auth.py            # Token management
│   ├── logger.py          # Activity logging
│   └── utils.py           # Utility functions
├── ui/
│   └── index.html         # Web UI (vanilla JS)
├── setup.py               # Package setup
└── requirements.txt       # Dependencies
```

### Running Tests

```bash
# Manual testing
python -m file_sharing_server share /tmp/test_files

# In another terminal
curl http://localhost:8000/?token=...
```

## License

MIT License - See LICENSE file

## Contributing

Contributions welcome! Please ensure:
- Code follows existing patterns
- New files validated for security (path traversal, injection)
- Backwards compatible with existing shares.json format
- Tested on Python 3.9+

## Future Features

- [ ] HTTPS support
- [ ] Upload progress tracking
- [ ] Quota per share
- [ ] User authentication (passwords, LDAP)
- [ ] Webhooks on file events
- [ ] S3 backend support
- [ ] Mobile app
- [ ] CLI download utility

## Support

Issues and feature requests: GitHub Issues
Questions: GitHub Discussions

---

Made with ❤️ for secure file sharing on trusted networks.
