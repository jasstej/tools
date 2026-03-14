# SOAR-Lite

**Security Orchestration, Automation and Response Engine**

SOAR-Lite is a command-line SOAR platform that demonstrates core concepts of modern security orchestration: alert ingestion, normalization, correlation, deduplication, playbook-driven response automation, and operational metrics. It is designed as both a learning tool and a functional prototype suitable for SOC analyst training environments.

---

## Table of Contents

1. [What is SOAR?](#what-is-soar)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Playbook Format](#playbook-format)
5. [Alert Ingestion](#alert-ingestion)
6. [Correlation Logic](#correlation-logic)
7. [Playbook Execution](#playbook-execution)
8. [Metrics](#metrics)
9. [HTTP Server API](#http-server-api)
10. [CLI Reference](#cli-reference)
11. [Integration Examples](#integration-examples)
12. [File Structure](#file-structure)

---

## What is SOAR?

**SOAR** (Security Orchestration, Automation and Response) platforms help security teams manage, investigate, and respond to alerts at machine speed. A SOAR system typically provides three capabilities:

- **Orchestration**: Connecting and coordinating multiple security tools (SIEM, firewall, EDR, ticketing systems) through a single workflow engine.
- **Automation**: Executing predefined response actions automatically when specific conditions are met — blocking IPs, isolating hosts, creating tickets — without requiring analyst intervention for every event.
- **Response**: Providing structured playbooks that guide human analysts through complex incident response procedures, ensuring consistency and reducing mean time to respond (MTTR).

### Key Concepts

| Concept | Description |
|---|---|
| Alert | A raw security event from a detection tool (SIEM, EDR, IDS) |
| Incident | One or more correlated alerts representing a single security event |
| Playbook | A JSON-defined workflow of response steps triggered by alert conditions |
| Action | A specific automated task: block IP, isolate host, notify team, create ticket |
| Correlation | Grouping related alerts by source IP, target asset, or attack pattern |
| MTTR | Mean Time to Respond — the primary KPI for measuring SOC efficiency |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SOAR-Lite Engine                     │
│                                                             │
│  ┌──────────────┐   ┌────────────────┐   ┌───────────────┐ │
│  │  Alert       │   │  Correlation   │   │  Playbook     │ │
│  │  Ingestion   │──▶│  Engine        │──▶│  Executor     │ │
│  │              │   │                │   │               │ │
│  │ load_alerts  │   │ correlate_ip   │   │ load_playbook │ │
│  │ normalize    │   │ correlate_asset│   │ eval_trigger  │ │
│  │ validate     │   │ detect_pattern │   │ execute_steps │ │
│  └──────────────┘   └────────────────┘   └───────────────┘ │
│                                                    │        │
│  ┌──────────────┐   ┌────────────────┐            │        │
│  │  HTTP Server │   │  Metrics       │◀───────────┘        │
│  │  POST/alerts │   │  MTTR / Stats  │                     │
│  └──────────────┘   └────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
         ▲
         │  JSON alerts (file or HTTP)
         │
    ┌────┴──────┐
    │  Data     │
    │  Sources  │
    │  SIEM/EDR │
    └───────────┘
```

---

## Installation

```bash
cd soar-lite
pip install -r requirements.txt
```

Requirements: `colorama`, `tabulate` (both optional but recommended for terminal output formatting).

---

## Playbook Format

Playbooks are JSON files that define trigger conditions and a sequence of response steps.

### JSON Schema

```json
{
  "name": "string — human-readable playbook name",
  "version": "string — semver",
  "trigger_conditions": {
    "alert_types": ["string — alert types that trigger this playbook"],
    "severity": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
    "keywords": ["string — keywords searched in alert details"],
    "thresholds": {
      "failed_logins_per_minute": "integer",
      "distinct_accounts_targeted": "integer"
    }
  },
  "description": "string — playbook purpose",
  "metadata": {
    "author": "string",
    "created": "YYYY-MM-DD",
    "last_updated": "YYYY-MM-DD",
    "severity": "CRITICAL|HIGH|MEDIUM|LOW",
    "estimated_duration_minutes": "integer",
    "compliance_frameworks": ["string"]
  },
  "steps": [
    {
      "id": "step_01",
      "name": "string — snake_case step identifier",
      "type": "detection|containment|forensics|notification|investigation|escalation|documentation|remediation",
      "action": "block_ip|isolate_host|disable_user|kill_process|create_ticket|notify_team|run_script|enrich_ip",
      "params": {
        "key": "value — action-specific parameters"
      },
      "on_success": "step_02 — next step ID on success, or null to end",
      "on_failure": "step_03 — next step ID on failure, or null to end",
      "description": "string — what this step does"
    }
  ]
}
```

### Supported Actions

| Action | Description | Key Params |
|---|---|---|
| `block_ip` | Block source IP at firewall/proxy/IDS | `block_at`, `direction`, `duration_hours` |
| `isolate_host` | Network-isolate an endpoint | `method`, `allow_management_traffic` |
| `disable_user` | Disable AD/Azure AD user account | `disable_ad_account`, `revoke_active_sessions` |
| `kill_process` | Terminate a malicious process | `process_name` |
| `create_ticket` | Create IR ticket in Jira/ServiceNow | `ticket_system`, `priority`, `issue_type` |
| `notify_team` | Send alert via Slack/email/PagerDuty | `channels`, `recipients`, `priority` |
| `run_script` | Execute a remediation/forensic script | `script`, `timeout_seconds` |
| `enrich_ip` | Mock threat intel lookup for source IP | `threat_intel_lookup` |

### Step Flow Control

Steps are connected via `on_success` and `on_failure` fields. Set either to `null` to terminate the playbook at that point. This creates conditional branching based on action outcomes.

---

## Alert Ingestion

### Input Format

Alerts should be a JSON array in `sample_alerts.json`:

```json
[
  {
    "id": "ALERT-001",
    "timestamp": "2025-11-20T08:14:32Z",
    "type": "SSH Brute Force",
    "severity": "HIGH",
    "source_ip": "185.220.101.47",
    "affected_asset": "PROD-SERVER-01",
    "details": { ... },
    "status": "NEW"
  }
]
```

### Required Fields

`id`, `timestamp`, `type`, `severity`, `source_ip`, `affected_asset`

### Normalization

The `normalize_alert()` function standardizes every incoming alert:
- Uppercases severity values
- Defaults missing fields (`status: NEW`, `details: {}`)
- Generates an MD5-based ID if `id` is absent
- Converts non-dict `details` fields to empty dict

---

## Correlation Logic

### IP-Based Correlation

`correlate_by_source_ip(alerts, window_minutes=5)` groups alerts by source IP within a sliding 5-minute window. A group with 2+ alerts from the same IP indicates sustained malicious activity.

### Asset-Based Correlation

`correlate_by_asset(alerts)` groups all alerts by the affected asset regardless of time. Multiple alert types against the same host indicate multi-vector targeting.

### Attack Pattern Detection

`detect_attack_pattern(correlated_alerts)` matches alert sequences against known kill chain patterns:

| Pattern | Sequence | Meaning |
|---|---|---|
| Ransomware Kill Chain | Malware Detection → Credential Dump → Ransomware Indicator | Complete ransomware deployment |
| Brute Force to Compromise | SSH Brute Force → Privilege Escalation | Successful credential attack |
| Exfiltration After C2 | C2 Communication → Data Exfiltration | Active APT data theft |
| Recon to Exploitation | Port Scan → SQL Injection | Targeted web application attack |

### Deduplication

`deduplicate_alerts(alerts, window_seconds=300)` removes alerts with identical `type + source_ip + affected_asset` fingerprints occurring within 5 minutes of each other.

---

## Playbook Execution

```bash
# Dry run (default) — logs actions, does not execute
python soar_engine.py --mode run-playbook \
  --input sample_alerts.json \
  --playbook playbooks/ransomware_response.json

# Execute mode — actions are treated as live
python soar_engine.py --mode run-playbook \
  --input sample_alerts.json \
  --playbook playbooks/brute_force_response.json \
  --execute
```

In **dry-run mode** (default), all actions are logged with a `[DRY RUN]` prefix. No actual network changes, ticket creation, or notifications occur. This is safe for testing and demonstrations.

In **execute mode** (`--execute`), actions are logged with `[EXECUTE]` — in a production environment this is where actual API calls to firewall management, EDR platforms, and ticketing systems would be made.

---

## Metrics

```bash
python soar_engine.py --mode metrics --input executions.json
```

Displays:
- Alert count by severity
- Total playbook executions
- Success/failure rate
- Mean Time to Respond (MTTR) in minutes
- Total steps executed and failed

---

## HTTP Server API

```bash
# Start server
python soar_engine.py --mode server --port 8080
```

### POST /alerts

Submit a new alert for processing:

```bash
curl -X POST http://localhost:8080/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "type": "SSH Brute Force",
    "severity": "HIGH",
    "source_ip": "1.2.3.4",
    "affected_asset": "PROD-SERVER-01"
  }'
```

**Response (201)**:
```json
{"status": "accepted", "id": "ALERT-A1B2C3D4"}
```

### GET /alerts

Retrieve all received alerts:
```bash
curl http://localhost:8080/alerts
```

---

## CLI Reference

```
usage: soar_engine.py [--mode MODE] [--input INPUT] [--playbook PLAYBOOK]
                      [--output OUTPUT] [--dry-run] [--execute] [--port PORT] [--verbose]

Options:
  --mode          ingest | correlate | run-playbook | metrics | server
  --input         Path to JSON alerts file or execution results file
  --playbook      Path to playbook JSON file (run-playbook mode only)
  --output        Output file path (default: soar_output.json)
  --dry-run       Simulate actions without executing (default: True)
  --execute       Actually execute actions (overrides --dry-run)
  --port          HTTP server port (default: 8080)
  --verbose       Enable debug-level logging
```

---

## Integration Examples

### SIEM Integration (Splunk)

```python
import requests, json

# Export alerts from Splunk saved search via REST API
# Then feed to SOAR-Lite HTTP endpoint
alerts = fetch_splunk_alerts()
for alert in alerts:
    requests.post("http://soar-lite:8080/alerts", json=alert)
```

### EDR Integration (CrowdStrike)

```python
# Map Falcon detection to SOAR-Lite alert schema
def map_falcon_detection(detection: dict) -> dict:
    return {
        "type": "Malware Detection",
        "severity": detection["max_severity"].upper(),
        "source_ip": detection["device"]["local_ip"],
        "affected_asset": detection["device"]["hostname"],
        "details": {
            "malware_family": detection["behaviors"][0]["technique"],
            "file_path": detection["behaviors"][0]["filepath"],
        }
    }
```

### Custom Playbook

```json
{
  "name": "Phishing Email Response",
  "trigger_conditions": {
    "alert_types": ["Phishing"],
    "severity": ["HIGH", "CRITICAL"]
  },
  "steps": [
    {
      "id": "step_01",
      "name": "quarantine_email",
      "type": "containment",
      "action": "run_script",
      "params": { "script": "quarantine_email.py" },
      "on_success": "step_02",
      "on_failure": "step_02"
    },
    {
      "id": "step_02",
      "name": "notify_user",
      "type": "notification",
      "action": "notify_team",
      "params": { "channels": ["email"], "recipients_type": "affected_users" },
      "on_success": null,
      "on_failure": null
    }
  ]
}
```

---

## File Structure

```
soar-lite/
├── soar_engine.py              # Main SOAR engine (~500 lines)
├── sample_alerts.json          # 10 realistic sample security alerts
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── index.html                  # Web-based SOC dashboard UI
└── playbooks/
    ├── ransomware_response.json # Ransomware incident response playbook
    └── brute_force_response.json# Brute force attack response playbook
```
