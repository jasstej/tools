# HIDS - Host-Based Intrusion Detection System

A Python-based Host-Based Intrusion Detection System (HIDS) that provides File
Integrity Monitoring (FIM), log analysis, and process monitoring for Linux/Unix
systems.

---

## Table of Contents

1. [What is a HIDS?](#what-is-a-hids)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [rules.json Format](#rulesjson-format-spec)
7. [Usage Examples](#usage-examples)
8. [Alert Format](#alert-format)
9. [Disclaimer](#disclaimer)

---

## What is a HIDS?

A **Host-Based Intrusion Detection System** monitors the internals of a single
host for signs of attack, policy violation, or unauthorized change. Unlike a
network IDS (NIDS) that inspects packets on the wire, a HIDS sits on the
endpoint itself and watches:

- **File Integrity** — detects unauthorized modification of critical system
  binaries and configuration files.
- **Log Events** — parses authentication and system logs for patterns associated
  with known attack techniques.
- **Process Activity** — snapshots the running process list and flags command
  lines that match malicious signatures.

HIDS is a core component of any endpoint security stack and directly supports
detection of techniques catalogued in the MITRE ATT&CK framework.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        HIDS Agent                               │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  File Integrity  │  │   Log Analysis   │  │   Process    │  │
│  │   Monitor (FIM)  │  │     Engine       │  │   Monitor    │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
│           │                     │                    │          │
│           │  SHA-256/512        │  Regex rules       │  psutil  │
│           │  metadata diff      │  (rules.json)      │  cmdline │
│           │                     │                    │  patterns│
│           └──────────┬──────────┘────────────────────┘          │
│                      │                                          │
│              ┌───────▼────────┐                                 │
│              │  Alert System  │                                 │
│              │  colorama TTY  │                                 │
│              │  JSON Lines    │                                 │
│              └───────┬────────┘                                 │
│                      │                                          │
│              ┌───────▼────────┐                                 │
│              │  hids_alerts   │                                 │
│              │   .jsonl       │                                 │
│              └────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘

Modes
-----
  baseline  ──>  Walk dirs, hash files, snapshot processes
  scan      ──>  Compare hashes, parse logs, flag processes (one-shot)
  monitor   ──>  Repeat scan every N seconds (continuous)
```

---

## Features

| Feature                       | Description                                                          |
|-------------------------------|----------------------------------------------------------------------|
| SHA-256 + SHA-512 hashing     | Dual-hash FIM for collision resistance                               |
| File metadata tracking        | Tracks size, mtime, and permissions alongside hashes                 |
| Incremental diff              | Reports added, modified, and deleted files against baseline          |
| Regex-based log parsing       | 12 built-in rules covering common Linux attack patterns              |
| MITRE ATT&CK mapping          | Every rule is tagged with a technique ID                             |
| Process inspection            | Flags running processes with suspicious cmdline signatures            |
| Continuous monitor mode       | Configurable scan interval with graceful SIGINT/SIGTERM handling     |
| JSON / YAML config support    | File-based configuration with CLI override capability                |
| JSON Lines alert log          | Machine-readable alert stream for SIEM ingestion                     |
| Colorized terminal output     | Severity-coded output for easy human triage                          |

---

## Installation

### Prerequisites

- Python 3.8 or newer
- pip

### Steps

```bash
# Clone or download the project
cd hids

# Install Python dependencies
pip install -r requirements.txt

# Verify
python hids_agent.py --help
```

### requirements.txt

```
psutil      # Process enumeration
colorama    # Cross-platform colored output
watchdog    # (optional) filesystem event hooks
PyYAML      # YAML configuration file support
```

---

## Configuration

The agent can be configured via a JSON or YAML file passed with `--config`, or
entirely through CLI flags. CLI flags always override file config values.

### Sample hids_config.yaml

```yaml
monitor_dirs:
  - /etc
  - /bin
  - /usr/bin
  - /sbin
  - /usr/sbin

baseline_file: hids_baseline.json
process_baseline_file: hids_procs_baseline.json

log_files:
  - /var/log/auth.log
  - /var/log/syslog

rules_file: rules.json
log_output: hids_alerts.jsonl

interval: 120        # seconds between monitor-mode scans
```

### Sample hids_config.json

```json
{
  "monitor_dirs": ["/etc", "/bin", "/usr/bin"],
  "baseline_file": "hids_baseline.json",
  "log_files": ["/var/log/auth.log"],
  "rules_file": "rules.json",
  "log_output": "hids_alerts.jsonl",
  "interval": 60
}
```

---

## rules.json Format Spec

The rules file is a JSON array. Each rule object must contain:

| Field             | Type   | Required | Description                                            |
|-------------------|--------|----------|--------------------------------------------------------|
| `id`              | string | yes      | Unique rule identifier (e.g. `RULE-001`)               |
| `name`            | string | yes      | Short human-readable rule name                         |
| `pattern`         | string | yes      | Python-compatible regex applied to each log line        |
| `log_source`      | string | yes      | Hint: `auth`, `syslog`, or `process`                   |
| `severity`        | string | yes      | `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`                 |
| `description`     | string | yes      | Explanation of what the rule detects                   |
| `mitre_technique` | string | yes      | MITRE ATT&CK technique ID and name                     |

### Example Rule Object

```json
{
  "id": "RULE-001",
  "name": "SSH Brute Force Attempt",
  "pattern": "Failed password for .* from .* port \\d+ ssh",
  "log_source": "auth",
  "severity": "HIGH",
  "description": "Multiple failed SSH authentication attempts detected.",
  "mitre_technique": "T1110.001 - Brute Force: Password Guessing"
}
```

---

## Usage Examples

### 1. Create a baseline

```bash
# Baseline default dirs (/etc, /bin, /usr/bin, /sbin, /usr/sbin)
python hids_agent.py --mode baseline

# Baseline specific directories
python hids_agent.py --mode baseline --monitor-dir /etc /bin /usr/bin

# Use a config file
python hids_agent.py --mode baseline --config hids_config.yaml
```

The baseline is saved to `hids_baseline.json` (or the file named by
`--baseline-file`).

### 2. One-shot scan

```bash
# Scan with defaults (requires an existing baseline)
python hids_agent.py --mode scan

# Scan with custom log files
python hids_agent.py --mode scan --log-files /var/log/auth.log /var/log/syslog

# Send alerts to a custom output file
python hids_agent.py --mode scan --log-output /var/log/hids_alerts.jsonl
```

### 3. Continuous monitoring

```bash
# Monitor every 60 seconds (default)
python hids_agent.py --mode monitor

# Monitor every 5 minutes
python hids_agent.py --mode monitor --interval 300

# Full config-driven monitor
python hids_agent.py --mode monitor --config hids_config.yaml
```

Press `Ctrl-C` to stop the monitoring loop gracefully.

### 4. Custom rules

```bash
python hids_agent.py --mode scan --rules /path/to/my_rules.json
```

---

## Alert Format

Alerts are written as **JSON Lines** (one JSON object per line) to the output
file (`hids_alerts.jsonl` by default).

### Alert record schema

```json
{
  "timestamp": "2025-11-15T14:32:07Z",
  "severity":  "HIGH",
  "source":    "FIM",
  "message":   "File modified: /etc/passwd",
  "details": {
    "field": "sha256",
    "old":   "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "new":   "a948904f2f0f479b8f9564e9d4b8a3a4b5f04d9a6b7c1e2d3f4a5b6c7d8e9f0a"
  }
}
```

### Severity levels

| Level    | Color        | Meaning                                                  |
|----------|--------------|----------------------------------------------------------|
| CRITICAL | Red (bright) | Immediate action required; active compromise suspected   |
| HIGH     | Yellow       | Serious anomaly; investigate promptly                    |
| MEDIUM   | Cyan         | Suspicious activity; review when possible                |
| LOW      | White        | Informational; low confidence signal                     |
| INFO     | Blue         | Agent lifecycle events (start, stop, baseline)           |

### Ingesting into a SIEM

The JSON Lines format is compatible with most log shippers:

```bash
# Filebeat
filebeat -e -c filebeat.yml   # configure input.path: hids_alerts.jsonl

# Logstash
logstash -e 'input { file { path => "/path/to/hids_alerts.jsonl" codec => json } }'

# Simple tail for debugging
tail -f hids_alerts.jsonl | python -m json.tool
```

---

## Disclaimer

This tool is designed for **authorized security monitoring only**. Always ensure
you have explicit written permission before monitoring any system you do not own.
Unauthorized monitoring may violate computer crime laws in your jurisdiction.
