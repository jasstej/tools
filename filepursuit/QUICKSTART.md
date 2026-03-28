# FilePursuit Quick Start Guide

Get **FilePursuit** running in 5 minutes!

## Step 1: Install

```bash
# Clone repository
git clone https://github.com/yourusername/filepursuit.git
cd filepursuit

# Install dependencies (Python 3.8+)
pip install -r requirements.txt
```

## Step 2: Add a Crawl Target

```bash
# Start with a demo server (Apache directory listing)
python -m file_pursuit add-target https://httpbin.org/ --type apache

# Or any public directory listing:
python -m file_pursuit add-target https://example.com/files/ --type apache
```

List your targets:
```bash
python -m file_pursuit list-targets
```

## Step 3: Crawl and Index

```bash
# Crawl all targets
python -m file_pursuit crawl --concurrent 4

# Watch the progress...
# Files discovered: 150
# Files indexed: 145
# Errors: 5
```

Check statistics:
```bash
python -m file_pursuit status
```

## Step 4: Search

```bash
# Search the index
python -m file_pursuit search "python" --type document --limit 10

# With filters:
python -m file_pursuit search "tutorial" --max-size 10  # 10 MB files only
```

## Step 5: Start Web Server

```bash
# Start HTTP server
python -m file_pursuit serve --host 0.0.0.0 --port 8080

# Output:
# FilePursuit server running at http://0.0.0.0:8080
# API: http://0.0.0.0:8080/api/search?q=...
# Admin: http://0.0.0.0:8080/admin (token: abc123...)
```

Open browser: **http://localhost:8080**

## Common Commands

```bash
# Add more targets
python -m file_pursuit add-target https://example2.com/downloads/ --type nginx

# Remove a target
python -m file_pursuit remove-target <target-id>

# Search API
curl "http://localhost:8080/api/search?q=python"

# Get admin token
python -m file_pursuit admin-token

# Regenerate admin token
python -m file_pursuit admin-token --regenerate

# Add target via API
curl -X POST http://localhost:8080/api/targets \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/", "type": "apache"}'
```

## Usage Patterns

### Pattern 1: Search via Web UI
1. Open http://localhost:8080
2. Type search query
3. Filter by type/size
4. Click download link

### Pattern 2: Programmatic Search
```bash
# Get JSON results
curl "http://localhost:8080/api/search?q=tutorial&type=document" | jq .

# Parse with Python
python -c "
import urllib.request, json
response = urllib.request.urlopen('http://localhost:8080/api/search?q=python')
data = json.load(response)
for result in data['results']:
    print(result['filename'], result['url'])
"
```

### Pattern 3: Automated Crawling
```bash
#!/bin/bash
# daily-crawl.sh

# Crawl all targets
python -m file_pursuit crawl --concurrent 4

# Get statistics
python -m file_pursuit status

# Log results
python -m file_pursuit log >> crawl-history.log
```

### Pattern 4: Custom Configuration
```bash
# Create targets file (data/targets.json)
{
  "targets": [
    {
      "url": "https://example.com/files/",
      "type": "apache",
      "max_depth": 5,
      "concurrent_workers": 3
    }
  ]
}
```

## Troubleshooting

**Q: No files found after crawling**
```bash
# Check target URL manually
curl https://example.com/files/

# Try a different target (Apache index)
python -m file_pursuit add-target https://www.kernel.org/ --type apache
python -m file_pursuit crawl
```

**Q: How do I get the admin token?**
```bash
python -m file_pursuit admin-token
```

**Q: Search is slow**
- Increase results limit to cache more
- Use more specific queries
- Add type filters to narrow down

**Q: Can't connect to server**
- Check port 8080 isn't in use: `lsof -i :8080`
- Use different port: `python -m file_pursuit serve --port 9000`
- Check firewall rules

## Next Steps

- 📚 Read [README.md](README.md) for full documentation
- 🔧 Configure crawler settings in `crawler.py`
- 🤝 Add more crawl targets for better coverage
- 📊 Monitor statistics: `python -m file_pursuit status`
- 🚀 Deploy on server for production use

## Example Use Cases

### 1. Research Database
```bash
# Index multiple research repositories
python -m file_pursuit add-target https://arxiv.org/papers
python -m file_pursuit add-target https://github.com/papers-pdf
python -m file_pursuit crawl

# Search for papers
python -m file_pursuit search "machine learning" --type document
```

### 2. Software Distribution
```bash
# Index software packages
python -m file_pursuit add-target https://releases.example.com
python -m file_pursuit crawl

# Find specific versions
python -m file_pursuit search "python-3.9" --type archive
```

### 3. Documentation Searcher
```bash
# Create personal documentation index
python -m file_pursuit add-target https://docs.example.com
python -m file_pursuit crawl

# Quick research
python -m file_pursuit search "API reference" --type document
```

## Tips & Tricks

💡 **Faster crawling:**
```bash
python -m file_pursuit crawl --concurrent 8  # Increase workers
```

💡 **Scheduled crawls:* (using cron)
```bash
# Add to crontab
0 3 * * * cd /path/to/filepursuit && python -m file_pursuit crawl
```

💡 **Backup index:**
```bash
cp -r data/ data-backup-$(date +%Y%m%d)/
```

💡 **Export search results:**
```bash
# Via API
curl "http://localhost:8080/api/search?q=test&limit=1000" > results.json
```

## Performance Tips

- Start with `--concurrent 4` and increase if needed
- Use `--max-size` filter to exclude huge files
- Add `--type` filter to search faster
- Monitor system resources during crawls

Enjoy searching! 🚀
