# DFIR Toolkit — Digital Forensics & Incident Response

A command-line toolkit for rapid artifact collection, timeline reconstruction, evidence integrity verification, and forensic report generation during security incidents.

---

## Table of Contents

1. [DFIR Methodology](#dfir-methodology)
2. [Artifact Types](#artifact-types)
3. [Toolkit Modules](#toolkit-modules)
4. [Evidence Handling Best Practices](#evidence-handling-best-practices)
5. [Chain of Custody](#chain-of-custody)
6. [Installation](#installation)
7. [Usage](#usage)
8. [Integration Tips](#integration-tips)

---

## DFIR Methodology

Digital Forensics and Incident Response (DFIR) is the discipline of investigating security incidents, collecting evidence, and reconstructing attack timelines. The overarching goal is to answer six core questions:

| Question | What to Look For |
|---|---|
| What happened? | Attack type, malware family, TTPs |
| When did it happen? | First compromise, lateral movement, exfiltration timestamps |
| Who did it? | Attribution indicators, accounts used |
| How did they get in? | Initial access vector: phishing, exploit, credential abuse |
| What did they access? | Files read, databases queried, credentials harvested |
| Have they been removed? | Persistence mechanisms, backdoors, dormant implants |

### The PICERL Lifecycle

This toolkit supports all phases of the PICERL incident response lifecycle:

```
Preparation -> Identification -> Containment -> Eradication -> Recovery -> Lessons Learned
```

See `ir_playbook.md` for detailed checklists for each phase.

---

## Artifact Types

### Volatile Artifacts (collect first — lost on reboot)

| Artifact | Location / Method | Volatility |
|---|---|---|
| Running processes | psutil / /proc | Very High |
| Network connections | psutil / ss / netstat | Very High |
| Loaded kernel modules | /proc/modules | High |
| ARP cache | ip neigh | High |
| Routing table | ip route | Medium |
| Active user sessions | who, w | High |
| Open file handles | lsof | High |
| Clipboard contents | xclip, xdotool | Very High |

### Non-Volatile Artifacts

| Artifact | Location | Value |
|---|---|---|
| Authentication logs | /var/log/auth.log | Login history, brute force |
| Bash/shell history | ~/.bash_history | Commands executed |
| System logs | /var/log/syslog | System events |
| Crontabs | /etc/cron*, /var/spool/cron | Persistence |
| SSH authorized_keys | ~/.ssh/authorized_keys | Backdoor access |
| Systemd units | /etc/systemd/system/ | Persistence |
| /tmp and /dev/shm | filesystem | Malware staging area |
| Web server logs | /var/log/apache2/, /var/log/nginx/ | Web shell activity |

### Memory Artifacts

For deep malware analysis, capture RAM with:
- Linux: LiME (Linux Memory Extractor) kernel module
- Windows: WinPmem, Magnet RAM Capture
- Analysis: Volatility 3, Rekall

---

## Toolkit Modules

### 1. Artifact Collection (collect_* functions)

```python
from dfir import collect_processes, collect_network, collect_recent_files

procs = collect_processes("/evidence/IR-001")
conns = collect_network("/evidence/IR-001")
files = collect_recent_files("/evidence/IR-001", hours=48)
```

Each function saves a JSON file and returns the data as a Python list/dict.

### 2. Evidence Integrity (hash_file, create_manifest)

All collected artifacts are SHA-256 hashed and recorded in manifest.json:

```python
from dfir import hash_file, create_manifest

digest = hash_file("/evidence/IR-001/processes.json")
manifest = create_manifest("/evidence/IR-001")
```

### 3. Chain of Custody (chain_of_custody)

Every significant action is logged with analyst name, timestamp, and platform details:

```python
from dfir import chain_of_custody

chain_of_custody("IR-2024-001", "jsmith", "/evidence/IR-001",
                 action="EVIDENCE_TRANSFERRED",
                 notes="Transferred to forensic workstation via encrypted USB")
```

### 4. Timeline Reconstruction

```python
from dfir import parse_auth_log, parse_bash_history, merge_timeline

auth_events = parse_auth_log("/var/log/auth.log")
bash_cmds = parse_bash_history("alice")
timeline = merge_timeline([auth_events, bash_cmds])
```

### 5. Case Management (init_case)

Creates a structured directory tree and case metadata:

```
IR-2024-001/
  case_metadata.json    # Case info, timestamps
  coc_log.json          # Chain of custody log
  manifest.json         # Evidence hashes
  processes.json
  network_connections.json
  users.json
  scheduled_tasks.json
  recent_files.json
  loaded_modules.json
  timeline.json
  forensic_report_IR-2024-001.html
```

### 6. Report Generation

Generates a self-contained dark-themed HTML report with:
- Summary statistics with suspicious item counts
- Full process table (suspicious rows highlighted in red)
- Network connections table
- Recently modified files
- Forensic timeline

---

## Evidence Handling Best Practices

### Order of Volatility

Always collect in this order to preserve the most volatile evidence first:

1. CPU registers and cache (requires hardware tools — beyond this toolkit's scope)
2. Running processes — collect immediately
3. Network connections — collect immediately
4. Kernel modules — collect before any reboot
5. Open file handles
6. Recently modified files — collect before any cleanup
7. Auth logs and bash history — relatively stable
8. Disk image (full forensic copy) — time-consuming, do last

### Write Blockers

When capturing disk images, always use a hardware write blocker to prevent accidental modification of the source drive. This toolkit does not perform disk imaging — use FTK Imager, dc3dd, or Guymager for disk acquisition.

### Hash Everything

Every artifact must be hashed (SHA-256) at collection time. The create_manifest() function does this automatically. Retain original hashes to prove evidence integrity if required in legal proceedings.

### Least Privilege

Run this toolkit with the minimum privileges required. For process and network collection, standard user privileges are usually sufficient. Only /proc/modules and some log files may require elevated access.

### Isolation

Before collecting artifacts from a suspected compromised system:
1. Do NOT run the toolkit from the suspect system's shell if possible
2. Boot from trusted read-only media (forensic boot USB)
3. Mount the toolkit from a clean USB or network share

---

## Chain of Custody

Chain of custody (CoC) is the chronological documentation proving that evidence has been handled properly and has not been tampered with.

### What Gets Logged

Every chain_of_custody() call records:

```json
{
  "case_id": "IR-2024-001",
  "analyst": "jsmith",
  "timestamp": "2024-01-15T03:14:22+00:00",
  "action": "EVIDENCE_COLLECTED",
  "platform": "forensic-workstation-01",
  "os": "Linux-5.15.0-x86_64",
  "notes": "Collected from live host 10.0.1.99",
  "output_dir": "/evidence/IR-2024-001"
}
```

### Standard CoC Actions

| Action | When to Use |
|---|---|
| CASE_OPENED | init_case() — automatic |
| EVIDENCE_COLLECTED | After each artifact collection |
| COLLECTION_COMPLETE | After all artifacts gathered |
| EVIDENCE_TRANSFERRED | When moving evidence to another location |
| EVIDENCE_REVIEWED | When analyst examines evidence |
| CASE_CLOSED | When incident is resolved |

### Legal Admissibility

For evidence to be admissible, the CoC log must demonstrate:
1. Evidence was collected without modification (hash verification)
2. All access to evidence was logged
3. Storage was secure at all times
4. Evidence was not commingled with other cases

---

## Installation

```bash
# Navigate to the toolkit directory
cd dfir-toolkit

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose |
|---|---|
| psutil | Process and network artifact collection |
| colorama | Coloured terminal output |
| tabulate | Formatted table output |

All other functionality uses Python standard library only (json, hashlib, os, subprocess, re, datetime).

---

## Usage

### Full Collection

```bash
python dfir.py --collect all --case-id IR-2024-001 --analyst jsmith
```

### Selective Collection

```bash
# Processes and network only
python dfir.py --collect processes,network --case-id IR-2024-001 --analyst jsmith

# Files modified in last 48 hours
python dfir.py --collect files --hours 48 --output-dir /evidence/IR-001

# Timeline reconstruction (requires previous file collection)
python dfir.py --collect timeline --output-dir /evidence/IR-001
```

### Report Generation

```bash
# HTML report only
python dfir.py --collect all --case-id IR-001 --analyst jsmith --format html

# JSON report only
python dfir.py --collect all --case-id IR-001 --analyst jsmith --format json

# Both formats (default)
python dfir.py --collect all --case-id IR-001 --analyst jsmith --format both
```

### Full CLI Reference

```
usage: dfir.py [-h] [--collect COLLECT] [--output-dir OUTPUT_DIR]
               [--case-id CASE_ID] [--analyst ANALYST]
               [--format {json,html,both}] [--hours HOURS]

Options:
  --collect         Comma-separated: all,processes,network,users,tasks,
                    files,modules,timeline (default: all)
  --output-dir, -o  Output directory (default: ./dfir_output_<timestamp>)
  --case-id         Case identifier (default: auto-generated)
  --analyst         Analyst name (default: current user)
  --format, -f      Report format: json, html, or both (default: both)
  --hours           Lookback hours for file collection (default: 24)
```

---

## Integration Tips

### Velociraptor Integration

Export collected artifacts to Velociraptor hunt for fleet-wide comparison:

```bash
python dfir.py --collect processes --format json --output-dir /tmp/hunt
# Upload processes.json to Velociraptor as custom artifact data
```

### Splunk / SIEM Ingestion

Point Splunk Universal Forwarder at the output directory:

```
[monitor:///evidence/]
index = dfir
sourcetype = dfir_artifact
```

### Automated Triage Script

```bash
#!/bin/bash
CASE="IR-$(date +%Y%m%d-%H%M%S)"
OUTPUT="/mnt/evidence-share/$CASE"
python3 /opt/dfir-toolkit/dfir.py \
  --collect all \
  --case-id "$CASE" \
  --analyst "$1" \
  --output-dir "$OUTPUT" \
  --format both
echo "Evidence collected at $OUTPUT"
```

### Yara Integration

After collection, scan recently modified files with YARA rules:

```bash
yara -r /opt/yara-rules/malware.yar \
  $(python3 -c "import json; [print(f['path']) for f in json.load(open('/evidence/IR-001/recent_files.json'))]")
```

---

## MITRE ATT&CK Mapping

The toolkit collects evidence relevant to these MITRE ATT&CK techniques:

| Technique ID | Name | Artifact Collected |
|---|---|---|
| T1059 | Command and Scripting Interpreter | Bash history, process cmdlines |
| T1053 | Scheduled Task/Job | Crontabs, systemd timers |
| T1078 | Valid Accounts | /etc/passwd, auth logs |
| T1021 | Remote Services | SSH connections, auth logs |
| T1571 | Non-Standard Port | Network connections |
| T1036 | Masquerading | Process names vs cmdlines |
| T1014 | Rootkit | Loaded kernel modules |
| T1070 | Indicator Removal | Recently modified log files |

---

## License

MIT License. See LICENSE file for details.

## References

- NIST SP 800-86: Guide to Integrating Forensic Techniques into Incident Response
- RFC 3227: Guidelines for Evidence Collection and Archiving
- SANS FOR508: Advanced Incident Response, Threat Hunting, and Digital Forensics
