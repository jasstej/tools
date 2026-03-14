#!/usr/bin/env python3
"""
Network Reconnaissance Scanner
A TCP port scanner with service banner grabbing, subdomain enumeration,
OS fingerprinting hints, and JSON/HTML report generation.

Usage:
    python scanner.py --target example.com --ports 1-1024 --threads 100
    python scanner.py --demo
"""

import argparse
import json
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import escape
from typing import Optional

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        RED = YELLOW = GREEN = CYAN = BLUE = MAGENTA = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = DIM = ""

# ---------------------------------------------------------------------------
# Port → service name mapping
# ---------------------------------------------------------------------------
PORT_SERVICE_MAP = {
    21:    "FTP",
    22:    "SSH",
    23:    "Telnet",
    25:    "SMTP",
    53:    "DNS",
    80:    "HTTP",
    110:   "POP3",
    111:   "RPC",
    135:   "MSRPC",
    139:   "NetBIOS",
    143:   "IMAP",
    443:   "HTTPS",
    445:   "SMB",
    465:   "SMTPS",
    587:   "SMTP Submission",
    993:   "IMAPS",
    995:   "POP3S",
    1433:  "MSSQL",
    2375:  "Docker",
    3000:  "Dev Server",
    3306:  "MySQL",
    3389:  "RDP",
    4444:  "Shell",
    5432:  "PostgreSQL",
    5900:  "VNC",
    6379:  "Redis",
    8080:  "HTTP Alt",
    8443:  "HTTPS Alt",
    8888:  "Jupyter",
    9200:  "Elasticsearch",
    27017: "MongoDB",
}

# Ports considered high-risk due to common exploitation / exposure issues
HIGH_RISK_PORTS = {23, 21, 3389, 445, 3306, 27017, 4444, 2375, 9200, 6379, 5900}

# Subdomains to probe during enumeration
SUBDOMAIN_WORDLIST = [
    "www", "mail", "ftp", "api", "dev", "staging", "admin",
    "vpn", "remote", "cdn", "static", "assets", "blog", "shop",
    "app", "portal", "dashboard", "auth", "docs", "git",
]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def cprint(msg: str, color: str = "", bright: bool = False) -> None:
    """Print a message with optional colorama color."""
    prefix = (Style.BRIGHT if bright else "") + color if HAS_COLOR else ""
    print(f"{prefix}{msg}{Style.RESET_ALL}")


def banner_line(title: str) -> None:
    """Print a section banner."""
    width = 60
    cprint("\n" + "=" * width, Fore.CYAN, bright=True)
    cprint(f"  {title}", Fore.CYAN, bright=True)
    cprint("=" * width, Fore.CYAN, bright=True)


def resolve_target(target: str) -> Optional[str]:
    """Resolve a hostname to an IP address. Returns None on failure."""
    try:
        return socket.gethostbyname(target)
    except socket.gaierror:
        return None


# ---------------------------------------------------------------------------
# Port scanning
# ---------------------------------------------------------------------------

def scan_port(host: str, port: int, timeout: float) -> dict:
    """
    Attempt a TCP connect to host:port.
    Returns a result dict with state, service name, and optional banner.
    """
    result = {
        "port": port,
        "state": "closed",
        "service": PORT_SERVICE_MAP.get(port, "unknown"),
        "banner": "",
        "risk": "LOW",
    }

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            result["state"] = "open"
            result["risk"] = "HIGH" if port in HIGH_RISK_PORTS else "MEDIUM" if port < 1024 else "LOW"
            result["banner"] = grab_banner(sock, port, host, timeout)
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass  # Port closed or filtered — leave state as "closed"

    return result


def grab_banner(sock: socket.socket, port: int, host: str, timeout: float) -> str:
    """
    Attempt to grab a service banner.
    Sends an HTTP HEAD probe for web ports; reads raw bytes for others.
    """
    try:
        sock.settimeout(timeout)
        # HTTP-family ports: send a HEAD request
        if port in (80, 8080, 8443, 3000, 8888):
            probe = f"HEAD / HTTP/1.0\r\nHost: {host}\r\n\r\n".encode()
            sock.sendall(probe)
        # For other ports just read whatever the service sends
        raw = sock.recv(120)
        return raw.decode("utf-8", errors="replace").strip()[:120]
    except Exception:
        return ""


def scan_ports(host: str, port_range: tuple, threads: int, timeout: float) -> list:
    """
    Run a threaded TCP connect scan across the specified port range.
    Returns a list of open-port result dicts, sorted by port number.
    """
    start_port, end_port = port_range
    ports = list(range(start_port, end_port + 1))
    open_ports = []

    cprint(f"\n[*] Scanning {len(ports)} ports on {host} with {threads} threads...", Fore.BLUE)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(scan_port, host, p, timeout): p for p in ports}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            if result["state"] == "open":
                open_ports.append(result)
                risk_color = Fore.RED if result["risk"] == "HIGH" else Fore.YELLOW if result["risk"] == "MEDIUM" else Fore.GREEN
                cprint(
                    f"  [+] Port {result['port']:5d}/tcp  OPEN  {result['service']:<22} [{result['risk']}]",
                    risk_color,
                )
            # Simple inline progress indicator every 100 ports
            if completed % 100 == 0 or completed == len(ports):
                sys.stdout.write(f"\r    Progress: {completed}/{len(ports)} ports checked")
                sys.stdout.flush()

    print()  # newline after progress bar
    return sorted(open_ports, key=lambda x: x["port"])


# ---------------------------------------------------------------------------
# Subdomain enumeration
# ---------------------------------------------------------------------------

def enumerate_subdomains(domain: str) -> list:
    """
    Probe common subdomains for the given domain using DNS resolution.
    Returns a list of dicts with subdomain, ip, and status.
    """
    results = []
    cprint(f"\n[*] Enumerating subdomains for {domain}...", Fore.BLUE)

    for prefix in SUBDOMAIN_WORDLIST:
        fqdn = f"{prefix}.{domain}"
        try:
            # getaddrinfo returns a list of tuples; take the first IP
            info = socket.getaddrinfo(fqdn, None, socket.AF_INET)
            ip = info[0][4][0]
            results.append({"subdomain": fqdn, "ip": ip, "status": "resolved"})
            cprint(f"  [+] {fqdn:<40} -> {ip}", Fore.GREEN)
        except socket.gaierror:
            pass  # Subdomain does not exist or doesn't resolve

    if not results:
        cprint("  [-] No subdomains resolved.", Fore.YELLOW)

    return results


# ---------------------------------------------------------------------------
# OS fingerprinting (heuristic, non-intrusive)
# ---------------------------------------------------------------------------

def fingerprint_os(open_ports: list) -> str:
    """
    Derive a rough OS fingerprint hint from the open port pattern.
    This is purely heuristic — not authoritative.
    """
    ports = {r["port"] for r in open_ports}

    if {135, 139, 445}.intersection(ports):
        return "Windows (SMB/MSRPC detected)"
    if 22 in ports and not ports.intersection({135, 139, 445}):
        if 80 in ports or 443 in ports:
            return "Linux / Unix (SSH + web stack)"
        return "Linux / Unix (SSH detected)"
    if {2375}.intersection(ports):
        return "Linux with Docker daemon exposed"
    if {9200}.intersection(ports):
        return "Linux / Elasticsearch node"
    if {3306, 5432, 27017}.intersection(ports):
        return "Database server (Linux likely)"
    if {3389}.intersection(ports):
        return "Windows (RDP detected)"
    if ports:
        return "Unknown OS — insufficient port pattern"
    return "No open ports — OS undetermined"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_json_report(scan_data: dict, output_path: str) -> None:
    """Write scan results to a JSON file."""
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(scan_data, fh, indent=2, default=str)
    cprint(f"\n[+] JSON report saved: {output_path}", Fore.GREEN, bright=True)


def generate_html_report(scan_data: dict, output_path: str) -> None:
    """Generate a self-contained HTML report from scan results."""
    target = escape(scan_data.get("target", ""))
    ip = escape(scan_data.get("resolved_ip", ""))
    scan_time = escape(str(scan_data.get("scan_time_seconds", "")))
    os_hint = escape(scan_data.get("os_fingerprint", ""))
    open_ports = scan_data.get("open_ports", [])
    subdomains = scan_data.get("subdomains", [])
    timestamp = escape(scan_data.get("timestamp", ""))

    # Build port rows
    port_rows = ""
    for r in open_ports:
        risk = escape(r.get("risk", "LOW"))
        color = "#f85149" if risk == "HIGH" else "#e3b341" if risk == "MEDIUM" else "#40c463"
        banner = escape(r.get("banner", "") or "—")[:80]
        port_rows += (
            f"<tr>"
            f"<td>{r['port']}</td>"
            f"<td style='color:{color};font-weight:bold'>{risk}</td>"
            f"<td>{escape(r.get('service',''))}</td>"
            f"<td style='font-size:0.82em;color:#aaa'>{banner}</td>"
            f"</tr>\n"
        )

    # Build subdomain rows
    sub_rows = ""
    for s in subdomains:
        sub_rows += (
            f"<tr><td>{escape(s['subdomain'])}</td>"
            f"<td>{escape(s['ip'])}</td>"
            f"<td style='color:#40c463'>Resolved</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Scan Report — {target}</title>
<style>
  body{{font-family:'Courier New',monospace;background:#0f1117;color:#c9d1d9;margin:0;padding:2rem}}
  h1{{color:#58a6ff}} h2{{color:#40c463;border-bottom:1px solid #30363d;padding-bottom:.3rem}}
  table{{width:100%;border-collapse:collapse;margin:1rem 0}}
  th{{background:#161b22;color:#58a6ff;padding:.5rem;text-align:left}}
  td{{padding:.4rem .5rem;border-bottom:1px solid #21262d}}
  .meta span{{color:#58a6ff;font-weight:bold}} .meta p{{margin:.2rem 0}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:3px;font-size:.8em}}
</style>
</head>
<body>
<h1>Network Scan Report</h1>
<div class="meta">
  <p>Target: <span>{target}</span> &nbsp; IP: <span>{ip}</span></p>
  <p>Scan time: <span>{scan_time}s</span> &nbsp; Generated: <span>{timestamp}</span></p>
  <p>OS Hint: <span>{os_hint}</span></p>
</div>
<h2>Open Ports ({len(open_ports)})</h2>
<table><tr><th>Port</th><th>Risk</th><th>Service</th><th>Banner</th></tr>
{port_rows if port_rows else '<tr><td colspan="4">No open ports found</td></tr>'}
</table>
<h2>Subdomains ({len(subdomains)})</h2>
<table><tr><th>Subdomain</th><th>IP</th><th>Status</th></tr>
{sub_rows if sub_rows else '<tr><td colspan="3">No subdomains resolved</td></tr>'}
</table>
</body></html>"""

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    cprint(f"[+] HTML report saved: {output_path}", Fore.GREEN, bright=True)


# ---------------------------------------------------------------------------
# Demo / sample scan
# ---------------------------------------------------------------------------

def sample_scan() -> None:
    """
    Run a quick demo scan against localhost to showcase tool output.
    Useful for CI/CD pipelines or local feature demonstrations.
    """
    banner_line("DEMO MODE — scanning localhost")
    cprint("[i] Scanning 127.0.0.1 ports 1-1024 with 50 threads (timeout=0.5s)", Fore.YELLOW)

    start = time.time()
    ip = "127.0.0.1"
    open_ports = scan_ports(ip, (1, 1024), threads=50, timeout=0.5)
    elapsed = round(time.time() - start, 2)

    os_hint = fingerprint_os(open_ports)
    high_risk = [p for p in open_ports if p["port"] in HIGH_RISK_PORTS]

    banner_line("Demo Results")
    cprint(f"  Open ports : {len(open_ports)}", Fore.CYAN)
    cprint(f"  High-risk  : {len(high_risk)}", Fore.RED if high_risk else Fore.GREEN)
    cprint(f"  OS hint    : {os_hint}", Fore.MAGENTA)
    cprint(f"  Scan time  : {elapsed}s", Fore.BLUE)

    scan_data = {
        "target": "localhost",
        "resolved_ip": ip,
        "scan_time_seconds": elapsed,
        "timestamp": datetime.now().isoformat(),
        "os_fingerprint": os_hint,
        "open_ports": open_ports,
        "subdomains": [],
    }
    generate_json_report(scan_data, "demo_scan.json")
    generate_html_report(scan_data, "demo_scan.html")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Network Reconnaissance Scanner — TCP port scan, banner grab, subdomain enum",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scanner.py --target 192.168.1.1 --ports 1-1024
  python scanner.py --target example.com --ports 1-65535 --threads 200 --subdomains
  python scanner.py --target example.com --output both
  python scanner.py --demo
        """,
    )
    parser.add_argument("--target", "-t", help="Target hostname or IP address")
    parser.add_argument(
        "--ports", "-p", default="1-1024",
        help="Port range to scan, e.g. 1-1024 or 80-443 (default: 1-1024)",
    )
    parser.add_argument("--threads", "-T", type=int, default=100, help="Concurrent threads (default: 100)")
    parser.add_argument("--timeout", "-W", type=float, default=1.0, help="Socket timeout in seconds (default: 1.0)")
    parser.add_argument("--subdomains", "-s", action="store_true", help="Enumerate common subdomains")
    parser.add_argument(
        "--output", "-o", choices=["json", "html", "both"], default=None,
        help="Save report as json, html, or both",
    )
    parser.add_argument("--demo", action="store_true", help="Run a demo scan against localhost and exit")
    return parser.parse_args()


def parse_port_range(port_str: str) -> tuple:
    """Parse '1-1024' into (1, 1024). Raises ValueError on bad input."""
    parts = port_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid port range: '{port_str}'. Expected format: START-END")
    start, end = int(parts[0]), int(parts[1])
    if not (1 <= start <= 65535 and 1 <= end <= 65535 and start <= end):
        raise ValueError(f"Port range {start}-{end} is invalid.")
    return start, end


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # ---- Demo mode ----
    if args.demo:
        sample_scan()
        return

    # ---- Target required for real scan ----
    if not args.target:
        cprint("[!] --target is required unless --demo is set.", Fore.RED, bright=True)
        sys.exit(1)

    # ---- Print banner ----
    banner_line("Network Reconnaissance Scanner")
    cprint(f"  Target   : {args.target}", Fore.WHITE, bright=True)

    # ---- Resolve hostname ----
    ip = resolve_target(args.target)
    if not ip:
        cprint(f"[!] Cannot resolve target '{args.target}'. Check spelling or connectivity.", Fore.RED, bright=True)
        sys.exit(1)
    cprint(f"  Resolved : {ip}", Fore.CYAN)

    # ---- Parse port range ----
    try:
        port_range = parse_port_range(args.ports)
    except ValueError as exc:
        cprint(f"[!] {exc}", Fore.RED, bright=True)
        sys.exit(1)

    cprint(f"  Ports    : {port_range[0]}–{port_range[1]}", Fore.WHITE)
    cprint(f"  Threads  : {args.threads}", Fore.WHITE)
    cprint(f"  Timeout  : {args.timeout}s", Fore.WHITE)

    # ---- Ethical use reminder ----
    cprint("\n[!] Scan only hosts you own or have explicit written permission to test.", Fore.YELLOW)

    # ---- Port scan ----
    start_ts = time.time()
    open_ports = scan_ports(ip, port_range, args.threads, args.timeout)
    elapsed = round(time.time() - start_ts, 2)

    # ---- Subdomain enumeration ----
    subdomains = []
    if args.subdomains:
        # Only enumerate subdomains if target looks like a domain (not raw IP)
        if not args.target.replace(".", "").isdigit():
            subdomains = enumerate_subdomains(args.target)
        else:
            cprint("[!] Subdomain enumeration skipped — target appears to be an IP.", Fore.YELLOW)

    # ---- OS fingerprinting ----
    os_hint = fingerprint_os(open_ports)
    high_risk = [p for p in open_ports if p["port"] in HIGH_RISK_PORTS]

    # ---- Summary ----
    banner_line("Scan Summary")
    cprint(f"  Open ports  : {len(open_ports)}", Fore.CYAN, bright=True)
    cprint(f"  High-risk   : {len(high_risk)}", Fore.RED if high_risk else Fore.GREEN, bright=True)
    cprint(f"  Subdomains  : {len(subdomains)}", Fore.CYAN)
    cprint(f"  OS hint     : {os_hint}", Fore.MAGENTA)
    cprint(f"  Scan time   : {elapsed}s", Fore.BLUE)

    if high_risk:
        cprint("\n  High-risk open ports detected:", Fore.RED, bright=True)
        for p in high_risk:
            cprint(f"    - Port {p['port']} ({p['service']})", Fore.RED)

    # ---- Build scan data dict ----
    scan_data = {
        "target": args.target,
        "resolved_ip": ip,
        "port_range": args.ports,
        "threads": args.threads,
        "timeout": args.timeout,
        "scan_time_seconds": elapsed,
        "timestamp": datetime.now().isoformat(),
        "os_fingerprint": os_hint,
        "open_ports": open_ports,
        "subdomains": subdomains,
        "high_risk_open": [p["port"] for p in high_risk],
    }

    # ---- Reports ----
    if args.output in ("json", "both"):
        safe = args.target.replace("/", "_").replace(":", "_")
        generate_json_report(scan_data, f"scan_{safe}.json")
    if args.output in ("html", "both"):
        safe = args.target.replace("/", "_").replace(":", "_")
        generate_html_report(scan_data, f"scan_{safe}.html")

    cprint("\n[*] Scan complete.\n", Fore.CYAN, bright=True)


if __name__ == "__main__":
    main()
