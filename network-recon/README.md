# Network Reconnaissance Scanner

A Python-based CLI network reconnaissance tool for authorized security assessments. Performs TCP port scanning, service banner grabbing, subdomain enumeration, and OS fingerprinting with JSON and HTML report generation.

---

## Features

- **TCP Connect Port Scanning** — multithreaded via `ThreadPoolExecutor`; configurable thread count and socket timeout
- **Service Banner Grabbing** — sends HTTP HEAD probes to web ports and reads raw service banners up to 120 characters
- **31-port Service Map** — maps well-known ports to service names (FTP, SSH, HTTP, MySQL, Redis, and more)
- **High-Risk Port Flagging** — instantly highlights dangerous open ports such as Telnet, RDP, SMB, Docker API, MongoDB, Redis, and VNC
- **Subdomain Enumeration** — resolves 20 common subdomains (`www`, `api`, `admin`, `staging`, `git`, etc.) via DNS
- **OS Fingerprinting Hints** — infers probable OS from open port patterns (Windows SMB, Linux SSH, Docker exposure)
- **JSON Report** — machine-readable full scan output with all metadata
- **HTML Report** — self-contained dark-theme report viewable in any browser
- **Demo Mode** — `--demo` flag scans localhost without any target argument
- **Colorized Output** — risk-coded terminal output via `colorama`

---

## Installation

```bash
git clone <repo-url>
cd network-recon
pip install -r requirements.txt
```

**requirements.txt**
```
colorama
dnspython
python-nmap
```

---

## Usage

```bash
python scanner.py [OPTIONS]
```

### CLI Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--target` | `-t` | — | Target hostname or IP address |
| `--ports` | `-p` | `1-1024` | Port range, e.g. `1-65535` or `80-443` |
| `--threads` | `-T` | `100` | Number of concurrent threads |
| `--timeout` | `-W` | `1.0` | Socket connect timeout (seconds) |
| `--subdomains` | `-s` | off | Enumerate common subdomains |
| `--output` | `-o` | — | Save report: `json`, `html`, or `both` |
| `--demo` | — | off | Demo scan against localhost |

### Examples

```bash
# Basic scan of top 1024 ports
python scanner.py --target 192.168.1.1

# Full scan with subdomain enum and HTML report
python scanner.py --target example.com --ports 1-65535 --threads 200 --subdomains --output both

# Web ports only with JSON output
python scanner.py --target 10.0.0.5 --ports 80-443 --timeout 0.5 --output json

# Quick demo against localhost
python scanner.py --demo
```

---

## Sample Output

```
============================================================
  Network Reconnaissance Scanner
============================================================
  Target   : example.com
  Resolved : 93.184.216.34
  Ports    : 1–1024
  Threads  : 100
  Timeout  : 1.0s

[!] Scan only hosts you own or have explicit written permission to test.

[*] Scanning 1024 ports on 93.184.216.34 with 100 threads...
  [+] Port    80/tcp  OPEN  HTTP                   [MEDIUM]
  [+] Port   443/tcp  OPEN  HTTPS                  [MEDIUM]
    Progress: 1024/1024 ports checked

============================================================
  Scan Summary
============================================================
  Open ports  : 2
  High-risk   : 0
  Subdomains  : 3
  OS hint     : Linux / Unix (SSH + web stack)
  Scan time   : 4.21s
```

---

## Report Files

| File | Description |
|------|-------------|
| `scan_<target>.json` | Full machine-readable results |
| `scan_<target>.html` | Self-contained dark-theme browser report |
| `demo_scan.json` | Output from `--demo` run |
| `demo_scan.html` | HTML report from `--demo` run |

---

## High-Risk Ports

The following ports are flagged `HIGH` risk when found open:

| Port | Service | Risk Reason |
|------|---------|-------------|
| 21 | FTP | Cleartext credentials |
| 23 | Telnet | Unencrypted remote access |
| 445 | SMB | Common ransomware vector |
| 3389 | RDP | Brute-force / exploit target |
| 3306 | MySQL | Direct DB exposure |
| 27017 | MongoDB | Unauthenticated by default |
| 4444 | Shell | Common reverse shell port |
| 2375 | Docker | Unauthenticated Docker API |
| 9200 | Elasticsearch | Unauthenticated data exposure |
| 6379 | Redis | No auth by default |
| 5900 | VNC | Weak authentication |

---

## Ethical Use Disclaimer

This tool is intended **exclusively** for:

- Scanning infrastructure you own
- Authorized penetration testing engagements with written permission
- Controlled lab environments and CTF competitions
- Security research on dedicated test networks

**Unauthorized port scanning may violate the Computer Fraud and Abuse Act (CFAA), the Computer Misuse Act (UK), and equivalent laws worldwide. The authors accept no responsibility for misuse.**

---

## License

MIT — see LICENSE for details.
