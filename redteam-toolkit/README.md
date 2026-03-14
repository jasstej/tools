# Red Team Simulation Toolkit

> **EDUCATIONAL USE ONLY** — This toolkit is for security education, CTF
> challenges, and authorized penetration testing lab environments only.
> It performs simulations and reference lookups; it does NOT execute real
> attacks, exploit production systems, or make unauthorized connections.

---

## Legal Disclaimer

**IMPORTANT — READ BEFORE USE**

This software is provided strictly for:

- Security education and awareness training
- Authorized penetration testing (with written consent from the system owner)
- CTF (Capture The Flag) competitions
- Home lab and controlled research environments

Using this tool against any system, network, or service **without explicit
written authorization** from the owner is:

- A violation of the **Computer Fraud and Abuse Act (CFAA)** in the United States
- A violation of the **Computer Misuse Act 1990** in the United Kingdom
- A violation of equivalent computer crime laws in virtually every jurisdiction

The authors assume **no liability** for misuse of this software. By using this
tool, you accept full responsibility for complying with all applicable laws.

---

## Table of Contents

1. [ATT&CK Framework Overview](#attck-framework-overview)
2. [Modules](#modules)
3. [Installation](#installation)
4. [Lab Setup Guide](#lab-setup-guide)
5. [Usage](#usage)
6. [mitre_map.json Format](#mitre_mapjson-format)
7. [Output / Reports](#output--reports)
8. [Contributing](#contributing)

---

## ATT&CK Framework Overview

The **MITRE ATT&CK** (Adversarial Tactics, Techniques, and Common Knowledge)
framework is a globally accessible knowledge base of adversary tactics and
techniques based on real-world observations.

```
Tactics (the "why"):
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Recon        │ Initial      │ Execution    │ Persistence  │ Priv Esc     │
│              │ Access       │              │              │              │
├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Defense      │ Credential   │ Discovery    │ Lateral      │ Exfiltration │
│ Evasion      │ Access       │              │ Movement     │              │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘

Each tactic contains multiple Techniques (T1xxx) and Sub-techniques (T1xxx.001)
that describe HOW adversaries accomplish each goal.
```

This toolkit maps simulation modules directly to ATT&CK technique IDs, enabling
defenders to understand which detections are relevant for each phase.

---

## Modules

### OSINT Module (`--module osint`)

Demonstrates Open Source Intelligence gathering techniques:

| Sub-module               | MITRE Technique | Description                           |
|--------------------------|-----------------|---------------------------------------|
| DNS enumeration          | T1595           | Subdomain discovery via DNS queries   |
| WHOIS lookup             | T1596.002       | Registrar and ownership data          |
| Certificate Transparency | T1596.003       | Subdomain discovery via CT logs       |

Note: DNS A record lookup uses Python's `socket.gethostbyname()` (a standard
DNS query, the same type a browser makes). All subdomain and record data is
**simulated**.

### Simulate Module (`--module simulate`)

Walks through a full attack chain scenario for a target domain, showing:

1. Reconnaissance (OSINT phase)
2. Default credential reference table
3. Persistence technique examples (as string references)
4. Lateral movement technique reference
5. Credential spray walkthrough (SIMULATION ONLY — no real auth attempts)

### MITRE Module (`--module mitre`)

Query the bundled `mitre_map.json` knowledge base:

```bash
# Look up a specific technique by ID
python red_team.py --module mitre --target T1595

# Search by keyword
python red_team.py --module mitre --target phishing

# List all loaded techniques
python red_team.py --module mitre
```

### Report Module (`--module report`)

Generates a structured JSON engagement report from simulation findings,
suitable for use in security awareness training materials.

---

## Installation

### Prerequisites

- Python 3.8 or newer
- pip

### Steps

```bash
cd redteam-toolkit
pip install -r requirements.txt
python red_team.py --module list
```

### requirements.txt

```
dnspython   # DNS queries (optional; socket fallback included)
colorama    # Cross-platform colored terminal output
tabulate    # Formatted table output
```

---

## Lab Setup Guide

For safe and legal use, run this toolkit in one of these environments:

### Option 1: Local Virtual Machine

```
Host OS
  └── VirtualBox / VMware
        ├── Kali Linux VM  (attack VM)
        └── Ubuntu/Metasploitable VM  (target — intentionally vulnerable)

Network: Host-only adapter (isolated, no internet access)
```

### Option 2: Docker Lab

```bash
# Pull an intentionally vulnerable target
docker pull webgoat/goat-and-wolf
docker run -d -p 8080:8080 webgoat/goat-and-wolf

# Run the toolkit against your local container
python red_team.py --module osint --target localhost
```

### Option 3: Cloud Lab (AWS/GCP/Azure)

Create an isolated VPC/VNet with:
- One attack instance (your toolkit)
- One target instance (e.g., Metasploitable, DVWA)
- No public internet access from target
- Security group/NSG restricting access to your IP only

### Recommended Practice Platforms

- **TryHackMe** (tryhackme.com) — guided learning paths
- **HackTheBox** (hackthebox.com) — realistic machine challenges
- **PentesterLab** (pentesterlab.com) — web security focus
- **VulnHub** (vulnhub.com) — downloadable VM targets

---

## Usage

```bash
# Show all modules
python red_team.py --module list

# OSINT on a domain (uses simulated data + real DNS A record)
python red_team.py --module osint --target example.com

# Full simulation walkthrough
python red_team.py --module simulate --target testlab.local --verbose

# ATT&CK technique lookup by ID
python red_team.py --module mitre --target T1595

# ATT&CK keyword search
python red_team.py --module mitre --target "credential dump"

# Generate engagement report
python red_team.py --module simulate --target testlab.local --output report.json
```

---

## mitre_map.json Format

The bundled MITRE map is a JSON object keyed by technique ID. Each entry:

| Field               | Type   | Description                                |
|---------------------|--------|--------------------------------------------|
| `id`                | string | ATT&CK technique ID (e.g., `T1595`)       |
| `name`              | string | Technique display name                     |
| `tactic`            | string | Parent tactic                              |
| `description`       | string | What the technique does                    |
| `procedure_examples`| array  | 2 real-world adversary usage examples      |
| `mitigations`       | array  | 2 recommended defensive mitigations        |
| `detection`         | string | How to detect this technique               |

```json
{
  "T1595": {
    "id": "T1595",
    "name": "Active Scanning",
    "tactic": "Reconnaissance",
    "description": "...",
    "procedure_examples": ["APT28 used...", "Lazarus Group..."],
    "mitigations": ["Network Intrusion Prevention...", "Pre-compromise..."],
    "detection": "Monitor for port scanning activity..."
  }
}
```

---

## Output / Reports

Engagement reports are saved as JSON with the following schema:

```json
{
  "report_type": "Red Team Engagement Simulation",
  "generated_at": "2025-11-15T14:32:07Z",
  "tool_version": "1.0.0",
  "disclaimer": "EDUCATIONAL USE ONLY",
  "engagement_id": "RT-20251115-143207",
  "findings": { ... },
  "executive_summary": {
    "modules_run": ["osint", "simulate"],
    "total_findings": 42
  }
}
```

---

## Contributing

Contributions are welcome for:

- Additional MITRE technique entries in `mitre_map.json`
- New educational simulation modules
- Improved detection guidance
- Lab setup automation scripts

Please ensure all additions remain educational and contain no real exploit code.
