# Deception-Based Security System

A Python honeypot / honeytoken framework for blue teams. Deploys convincing fake credential files and private keys across a monitored directory tree, then watches for any access or modification using real-time filesystem events. Triggers structured alerts to the console, a JSON log, and an optional webhook endpoint.

---

## Overview

Modern attackers who gain initial foothold on a system immediately hunt for credentials — SSH keys, database passwords, `.env` files, and cloud API keys. This tool exploits that behavior by planting realistic decoy files containing fake-but-convincing credentials and monitoring those files 24/7. Any touch to a decoy file produces an instant high-fidelity alert with timestamp, process info, and severity classification.

---

## Blue Team Use Cases

- **Insider threat detection** — catch employees accessing sensitive-looking files they shouldn't
- **Post-breach detection** — identify attacker credential harvesting after initial compromise
- **Lateral movement detection** — honeypots in network shares catch pivoting attackers
- **SOC alerting enrichment** — webhook integration delivers structured JSON to SIEM / Slack / PagerDuty
- **Red team exercises** — validate that your monitoring catches credential access

---

## Features

- **6 Decoy Types**: `passwords.txt`, `credentials.json`, `aws_keys.txt`, `.env`, `id_rsa`, `config.ini`
- **Fake Credential Generators**: AWS access keys (AKIA prefix), AWS secret keys (40-char), GitHub tokens (ghp_ prefix), DB passwords, DB connection strings
- **Honeypath Subdirectories**: Creates `backup/`, `scripts/`, `private/` subdirectories — each also containing decoys
- **Real-Time File Monitoring**: Uses `watchdog` to detect access, modification, deletion, and moves
- **Process Identification**: Uses `psutil` to capture the PID, process name, user, and command line of the accessing process
- **Severity Classification**: CRITICAL / HIGH / MEDIUM / LOW with configurable minimum threshold
- **JSON Alert Logging**: All alerts appended to a structured JSON log file
- **Webhook Integration**: HTTP POST of alert JSON to any endpoint (Slack, PagerDuty, custom SIEM)
- **Graceful Shutdown**: SIGINT/SIGTERM handlers print an alert summary on exit
- **Registry Tracking**: `.decoy_registry.json` tracks all deployed decoys and trigger counts
- **List & Remove**: `--list-decoys` and `--remove-decoys` flags for lifecycle management

---

## Installation

```bash
git clone <repo-url>
cd deception-defense
pip install -r requirements.txt
```

**requirements.txt**
```
watchdog
requests
psutil
colorama
```

---

## Usage

```bash
python deception_system.py [OPTIONS]
```

### CLI Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--deploy-dir` | `-d` | — | Directory to deploy decoy files into |
| `--webhook-url` | `-w` | — | HTTP POST endpoint for alert delivery |
| `--log-file` | `-l` | `decoy_alerts.json` | Path to JSON alert log |
| `--alert-level` | `-a` | `LOW` | Minimum severity: CRITICAL/HIGH/MEDIUM/LOW |
| `--list-decoys` | — | off | Print all registered decoys and exit |
| `--remove-decoys` | — | off | Delete all registered decoys and exit |
| `--no-monitor` | — | off | Deploy decoys without starting monitoring |

### Examples

```bash
# Deploy decoys and start monitoring
python deception_system.py --deploy-dir /opt/honeyfiles

# Deploy with webhook alerts (e.g. Slack incoming webhook)
python deception_system.py --deploy-dir /opt/honeyfiles --webhook-url https://hooks.slack.com/services/xxx

# High-severity alerts only
python deception_system.py --deploy-dir /opt/honeyfiles --alert-level HIGH

# Deploy only, no monitoring (useful for manual watchdog setup)
python deception_system.py --deploy-dir /opt/honeyfiles --no-monitor

# List all deployed decoys
python deception_system.py --list-decoys

# Remove all decoys
python deception_system.py --remove-decoys
```

---

## Decoy File Details

| Filename | Type | Content |
|----------|------|---------|
| `passwords.txt` | Credential list | Username/password pairs |
| `credentials.json` | JSON secrets | AWS keys, GitHub token, DB connection |
| `aws_keys.txt` | AWS config | INI format, two profiles |
| `.env` | Env file | DATABASE_URL, SECRET_KEY, AWS keys, GitHub token |
| `id_rsa` | Private key | RSA key header/footer with fake body |
| `config.ini` | App config | DB, SMTP, and AWS credentials |

All decoys are deployed in both the root deploy directory and the `backup/` subdirectory.

---

## Alert JSON Format

Each alert written to the log file has this structure:

```json
{
  "timestamp": "2024-03-14T10:25:33.712841",
  "severity": "CRITICAL",
  "event_type": "FILE_MODIFIED",
  "filepath": "/opt/honeyfiles/credentials.json",
  "process": {
    "pid": 14392,
    "name": "python3",
    "cmdline": "python3 harvest.py",
    "user": "attacker"
  }
}
```

### Event Types

| Event | Severity | Meaning |
|-------|----------|---------|
| `FILE_MODIFIED` | CRITICAL | Decoy file contents changed |
| `FILE_ACCESSED` | HIGH | Decoy file was read |
| `FILE_DELETED` | CRITICAL | Decoy file was removed |
| `FILE_MOVED` | HIGH | Decoy file was renamed/moved |
| `FILE_CREATED_IN_HONEYPATH` | MEDIUM | New file created in honeypath dir |

---

## Webhook Integration

Set `--webhook-url` to any HTTP endpoint that accepts POST with a JSON body. Compatible with:

- **Slack** — create an Incoming Webhook app and pass the URL
- **PagerDuty** — use the Events API v2 endpoint
- **Microsoft Teams** — use Incoming Webhook connector URL
- **Custom SIEM** — any endpoint accepting JSON POST

The alert JSON payload is sent as `Content-Type: application/json` with a 5-second timeout.

---

## Architecture

```
deception_system.py
├── Credential generators    (fake_aws_access_key, fake_github_token, …)
├── Decoy builders           (DECOY_DEFINITIONS dict → content functions)
├── deploy_decoys()          (creates files + registry)
├── DecoyEventHandler        (watchdog FileSystemEventHandler subclass)
├── emit_alert()             (console + JSON log + webhook)
├── start_monitoring()       (Observer loop)
└── Signal handlers          (graceful shutdown + summary)
```

---

## Legal Disclaimer

This tool is designed for **authorized** defensive security use only:

- Deploy decoys **exclusively** on systems you own or manage
- Obtain written authorization before deploying in enterprise environments
- Be aware of local privacy laws before monitoring employee file access
- This tool **does not** intrude on external systems — it is purely defensive

The authors accept no liability for unauthorized or illegal use.

---

## License

MIT — see LICENSE for details.
