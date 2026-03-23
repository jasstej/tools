# File Sharing Server - Quick Start Guide

## Installation & First Share

### 1. Clone/Setup
```bash
cd /path/to/file-sharing-server
python3 -m file_sharing_server status
```

### 2. Share Your First Folder
```bash
python3 -m file_sharing_server share ~/Documents
```

You'll see:
```
✓ Share created: a1b2c3d4-e5f6-...
├─ Share token: xyz789012-abcd-...

Starting server on http://0.0.0.0:8000

Access share:
  http://localhost:8000/?token=xyz789012-abcd-...

Admin panel:
  http://localhost:8000/admin?token=master789012-...
```

### 3. Share with Others

#### On Local Network
```bash
# Replace 192.168.1.100 with your IP
curl http://192.168.1.100:8000 -I  # Test connectivity

# Share the URL
http://192.168.1.100:8000/?token=xyz789012-abcd-...
```

#### Find Your IP
```bash
# Linux/Mac
hostname -I
ifconfig | grep inet

# Windows
ipconfig
```

### 4. Use the Web UI
- Open the token URL in browser
- Drag files to upload zone
- Click folders to navigate
- Click "Download" to get files
- Use "+ New Folder" to organize

### 5. Admin Access
- Open: `http://localhost:8000/admin?token=MASTER_TOKEN`
- See all active shares
- View activity log (who downloaded what, when)
- Monitor file sizes

## Common Use Cases

### Share Downloads Folder with Time Limit
```bash
python3 -m file_sharing_server share ~/Downloads \
  --description "Temp downloads" \
  --expires-in 1
```
Share auto-removes after 1 hour.

### Restrict File Types (Security)
```bash
python3 -m file_sharing_server share ~/installers \
  --allowed-types exe,deb,iso \
  --max-size 1000
```
Only .exe, .deb, .iso files allowed. Max 1GB per file.

### Custom Port (Multiple Shares)
```bash
# Terminal 1
python3 -m file_sharing_server share ~/folder1 --port 8000

# Terminal 2
python3 -m file_sharing_server share ~/folder2 --port 8001
```

### Using on Air-Gapped Network
```bash
# Same commands work - no internet required
# Files shared over local network interfaces only
python3 -m file_sharing_server share ~/secure_folder
```

## Tips & Tricks

### Get Token From Running Share
```bash
python3 -m file_sharing_server list
```
Shows all active shares with their tokens.

### Change Share Settings
```bash
# After share is running, modify it
python3 -m file_sharing_server config SHARE_ID \
  --max-size 2000 \
  --allowed-types pdf,txt
```

### Stop a Share
```bash
python3 -m file_sharing_server remove SHARE_ID
```
Or just Ctrl+C the running server.

### Nested Folder Organization
Users can:
1. Click "+ New Folder" button
2. Upload files to organized structure
3. Share creates: `data/uploads/{share_id}/{user_token}/my_folder/`

### Monitor Activity
```bash
tail -f data/activity.log | jq .
```
Real-time JSON activity stream.

## Troubleshooting

### "Port already in use"
```bash
# Use different port
python3 -m file_sharing_server share ~/folder --port 9000

# Or find process using 8000
lsof -i :8000
kill -9 <PID>
```

### "Permission denied" on folder
```bash
chmod 755 /path/to/folder
chmod 644 /path/to/folder/*
```

### Lost master token
```bash
# It's in plain text for trusted networks
cat data/master_token.txt
```

### Large files not working
```bash
# Increase max size
python3 -m file_sharing_server share ~/folder \
  --max-size 5000  # 5GB
```

## Security Notes

✅ **For Trusted Networks:**
- No HTTPS needed
- Simple UUID tokens (128-bit)
- IP logging for audit trail
- Path traversal protection

⚠️ **For Public/Untrusted Networks:**
- Use reverse proxy with HTTPS (nginx)
- Consider adding authentication
- Implement rate limiting
- Use ClamAV upload scanning

## Performance

Tested with:
- 10+ concurrent users
- 1GB+ individual files
- 1000+ files per directory
- Typical speed: 100-500 MB/s (LAN)

## Next Steps

1. **Read full README:** `README.md`
2. **Check API docs:** See README API Reference section
3. **Monitor logs:** `tail -f data/activity.log`
4. **Auto-tunnel:** Add `--tunnel auto` flag for public access via cloudflared

---

Happy file sharing! 🚀
