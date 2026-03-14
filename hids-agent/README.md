# Host-Based Intrusion Detection System (HIDS)

Rule-based HIDS starter for Linux endpoints.

## Features

- File integrity baseline/check
- Regex log scanning
- Alert output for SOC workflows

## Usage

```bash
python main.py baseline --path /etc --db baseline.json
python main.py check --path /etc --db baseline.json
python main.py scan-log --log /var/log/auth.log --pattern "failed|sudo"
```
