#!/usr/bin/env python3
"""
HIDS Agent - Host-Based Intrusion Detection System
Educational security monitoring tool for detecting suspicious activity
on Linux/Unix systems using file integrity monitoring, log analysis,
and process monitoring.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import datetime
import stat
import signal
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[WARNING] psutil not installed. Process monitoring disabled.")

try:
    from colorama import Fore, Back, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = RESET = ""
    class Style:
        BRIGHT = RESET_ALL = DIM = ""
    class Back:
        RED = GREEN = YELLOW = BLACK = RESET = ""

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
VERSION = "1.0.0"
BANNER = f"""
{Fore.GREEN}{Style.BRIGHT}
 ██╗  ██╗██╗██████╗ ███████╗
 ██║  ██║██║██╔══██╗██╔════╝
 ███████║██║██║  ██║███████╗
 ██╔══██║██║██║  ██║╚════██║
 ██║  ██║██║██████╔╝███████║
 ╚═╝  ╚═╝╚═╝╚═════╝ ╚══════╝
{Style.RESET_ALL}
 Host-Based Intrusion Detection System  v{VERSION}
 For authorized use on systems you own or have permission to monitor.
"""

SEVERITY_COLORS = {
    "CRITICAL": Fore.RED + Style.BRIGHT,
    "HIGH":     Fore.YELLOW + Style.BRIGHT,
    "MEDIUM":   Fore.CYAN,
    "LOW":      Fore.WHITE,
    "INFO":     Fore.BLUE,
}

DEFAULT_MONITOR_DIRS = [
    "/etc",
    "/bin",
    "/usr/bin",
    "/usr/sbin",
    "/sbin",
]

DEFAULT_LOG_FILES = [
    "/var/log/auth.log",
    "/var/log/syslog",
    "/var/log/messages",
    "/var/log/secure",
]

DEFAULT_BASELINE_FILE = "hids_baseline.json"
DEFAULT_ALERT_LOG     = "hids_alerts.jsonl"
DEFAULT_RULES_FILE    = "rules.json"
DEFAULT_INTERVAL      = 60

# ─────────────────────────────────────────────
#  FILE INTEGRITY MONITORING
# ─────────────────────────────────────────────

def hash_file(path: str) -> Optional[Dict[str, str]]:
    """Compute SHA-256 and SHA-512 hashes of a file."""
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                sha256.update(chunk)
                sha512.update(chunk)
        return {
            "sha256": sha256.hexdigest(),
            "sha512": sha512.hexdigest(),
        }
    except (OSError, PermissionError):
        return None


def get_file_metadata(path: str) -> Optional[Dict[str, Any]]:
    """Collect metadata for a single file path."""
    try:
        st = os.stat(path)
        hashes = hash_file(path)
        if hashes is None:
            return None
        return {
            "sha256":      hashes["sha256"],
            "sha512":      hashes["sha512"],
            "size":        st.st_size,
            "mtime":       st.st_mtime,
            "permissions": oct(stat.S_IMODE(st.st_mode)),
        }
    except (OSError, PermissionError):
        return None


def walk_directory(directory: str) -> List[str]:
    """Recursively collect all regular file paths under a directory."""
    file_paths = []
    try:
        for root, _, files in os.walk(directory, followlinks=False):
            for name in files:
                full = os.path.join(root, name)
                try:
                    if os.path.isfile(full) and not os.path.islink(full):
                        file_paths.append(full)
                except OSError:
                    pass
    except (OSError, PermissionError):
        pass
    return file_paths


def create_baseline(dirs: List[str], baseline_file: str = DEFAULT_BASELINE_FILE) -> Dict[str, Any]:
    """
    Walk each directory in `dirs`, hash every regular file, and persist
    the baseline to `baseline_file` as JSON.
    Returns the baseline dict.
    """
    baseline: Dict[str, Any] = {
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "hostname":   platform.node(),
        "dirs":       dirs,
        "files":      {},
    }

    total = 0
    skipped = 0
    print(f"{Fore.CYAN}[*] Building FIM baseline for {len(dirs)} director(y/ies)...{Style.RESET_ALL}")

    for d in dirs:
        if not os.path.isdir(d):
            print(f"{Fore.YELLOW}[!] Directory not found, skipping: {d}{Style.RESET_ALL}")
            continue
        paths = walk_directory(d)
        print(f"    {d}  ({len(paths)} files)")
        for path in paths:
            meta = get_file_metadata(path)
            if meta:
                baseline["files"][path] = meta
                total += 1
            else:
                skipped += 1

    try:
        with open(baseline_file, "w") as fh:
            json.dump(baseline, fh, indent=2)
        print(f"{Fore.GREEN}[+] Baseline saved: {baseline_file}  ({total} files hashed, {skipped} skipped){Style.RESET_ALL}")
    except OSError as exc:
        print(f"{Fore.RED}[-] Could not write baseline file: {exc}{Style.RESET_ALL}")

    return baseline


def load_baseline(baseline_file: str) -> Optional[Dict[str, Any]]:
    """Load a previously saved baseline from JSON."""
    try:
        with open(baseline_file, "r") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"{Fore.RED}[-] Baseline file not found: {baseline_file}{Style.RESET_ALL}")
        return None
    except json.JSONDecodeError as exc:
        print(f"{Fore.RED}[-] Corrupt baseline file: {exc}{Style.RESET_ALL}")
        return None


def check_integrity(baseline_file: str, dirs: List[str]) -> Dict[str, List[Any]]:
    """
    Compare the current state of `dirs` against `baseline_file`.
    Returns a dict with keys:
      - added    : list of new file paths
      - modified : list of dicts {path, field, old, new}
      - deleted  : list of file paths no longer present
    """
    baseline = load_baseline(baseline_file)
    if baseline is None:
        return {"added": [], "modified": [], "deleted": []}

    old_files: Dict[str, Any] = baseline.get("files", {})

    print(f"{Fore.CYAN}[*] Scanning {len(dirs)} director(y/ies) for changes...{Style.RESET_ALL}")
    current_files: Dict[str, Any] = {}
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for path in walk_directory(d):
            meta = get_file_metadata(path)
            if meta:
                current_files[path] = meta

    added    = [p for p in current_files if p not in old_files]
    deleted  = [p for p in old_files     if p not in current_files]
    modified = []

    for path, new_meta in current_files.items():
        if path not in old_files:
            continue
        old_meta = old_files[path]
        for field in ("sha256", "sha512", "size", "permissions"):
            if new_meta.get(field) != old_meta.get(field):
                modified.append({
                    "path":  path,
                    "field": field,
                    "old":   old_meta.get(field),
                    "new":   new_meta.get(field),
                })
                break  # report once per file

    return {"added": added, "modified": modified, "deleted": deleted}


# ─────────────────────────────────────────────
#  LOG ANALYSIS
# ─────────────────────────────────────────────

def load_rules(rules_file: str = DEFAULT_RULES_FILE) -> List[Dict[str, Any]]:
    """Load detection rules from a JSON file."""
    try:
        with open(rules_file, "r") as fh:
            rules = json.load(fh)
        # Pre-compile regex patterns
        for rule in rules:
            try:
                rule["_pattern"] = re.compile(rule["pattern"], re.IGNORECASE)
            except re.error as exc:
                print(f"{Fore.YELLOW}[!] Invalid regex in rule {rule.get('id', '?')}: {exc}{Style.RESET_ALL}")
                rule["_pattern"] = None
        print(f"{Fore.GREEN}[+] Loaded {len(rules)} detection rules from {rules_file}{Style.RESET_ALL}")
        return rules
    except FileNotFoundError:
        print(f"{Fore.RED}[-] Rules file not found: {rules_file}{Style.RESET_ALL}")
        return []
    except json.JSONDecodeError as exc:
        print(f"{Fore.RED}[-] Corrupt rules file: {exc}{Style.RESET_ALL}")
        return []


def analyze_log(log_file: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse `log_file` line-by-line against each rule's compiled regex.
    Returns list of match dicts: {time, rule_id, rule_name, severity, line, description, mitre_technique}.
    """
    findings = []
    if not os.path.isfile(log_file):
        return findings

    try:
        with open(log_file, "r", errors="replace") as fh:
            lines = fh.readlines()
    except (OSError, PermissionError):
        return findings

    # Simple timestamp extraction (syslog format)
    ts_pattern = re.compile(
        r"^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})"
    )

    for lineno, line in enumerate(lines, start=1):
        line = line.rstrip("\n")
        ts_match = ts_pattern.match(line)
        timestamp = ts_match.group(1) if ts_match else f"line:{lineno}"

        for rule in rules:
            regex = rule.get("_pattern")
            if regex is None:
                continue
            if regex.search(line):
                findings.append({
                    "time":            timestamp,
                    "rule_id":         rule.get("id", ""),
                    "rule_name":       rule.get("name", ""),
                    "severity":        rule.get("severity", "LOW"),
                    "line":            line[:300],
                    "description":     rule.get("description", ""),
                    "mitre_technique": rule.get("mitre_technique", ""),
                    "log_file":        log_file,
                })

    return findings


def analyze_all_logs(log_files: List[str], rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run log analysis across multiple log files."""
    all_findings = []
    for log_file in log_files:
        findings = analyze_log(log_file, rules)
        if findings:
            print(f"    {log_file}  -> {len(findings)} hit(s)")
        all_findings.extend(findings)
    return all_findings


# ─────────────────────────────────────────────
#  PROCESS MONITOR
# ─────────────────────────────────────────────

def get_processes() -> List[Dict[str, Any]]:
    """Return a list of running process snapshots via psutil."""
    if not HAS_PSUTIL:
        return []
    procs = []
    for proc in psutil.process_iter(
        attrs=["pid", "name", "cmdline", "username", "cpu_percent", "memory_percent"]
    ):
        try:
            info = proc.info
            procs.append({
                "pid":     info["pid"],
                "name":    info["name"] or "",
                "cmdline": " ".join(info["cmdline"] or []),
                "user":    info["username"] or "unknown",
                "cpu":     round(info["cpu_percent"] or 0.0, 2),
                "memory":  round(info["memory_percent"] or 0.0, 2),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return procs


def save_process_baseline(output_file: str = "hids_procs_baseline.json") -> List[Dict[str, Any]]:
    """Snapshot current processes and save to file."""
    procs = get_processes()
    with open(output_file, "w") as fh:
        json.dump({"created_at": datetime.datetime.utcnow().isoformat() + "Z", "processes": procs}, fh, indent=2)
    print(f"{Fore.GREEN}[+] Process baseline saved: {output_file} ({len(procs)} processes){Style.RESET_ALL}")
    return procs


def compare_processes(
    baseline_procs: List[Dict[str, Any]],
    current_procs:  List[Dict[str, Any]],
) -> Dict[str, List[Any]]:
    """
    Compare two process snapshots.
    Returns:
      - new_procs  : processes in current but not in baseline (by PID + name)
      - gone_procs : processes in baseline but not in current
    """
    baseline_set = {(p["pid"], p["name"]) for p in baseline_procs}
    current_set  = {(p["pid"], p["name"]) for p in current_procs}

    new_pid_names  = current_set  - baseline_set
    gone_pid_names = baseline_set - current_set

    current_map  = {(p["pid"], p["name"]): p for p in current_procs}
    baseline_map = {(p["pid"], p["name"]): p for p in baseline_procs}

    return {
        "new_procs":  [current_map[k]  for k in new_pid_names],
        "gone_procs": [baseline_map[k] for k in gone_pid_names],
    }


# Suspicious patterns for process cmdlines
SUSPICIOUS_PROC_PATTERNS = [
    (re.compile(r"nc\s+.*-[el]",            re.I), "Netcat listener/reverse shell",     "CRITICAL"),
    (re.compile(r"bash\s+-i.*>&.*/dev/tcp", re.I), "Bash TCP reverse shell",            "CRITICAL"),
    (re.compile(r"python.*-c.*socket",      re.I), "Python socket shell",               "HIGH"),
    (re.compile(r"wget\s+http",             re.I), "Wget file download",                "MEDIUM"),
    (re.compile(r"curl\s+.*-[oO]",         re.I), "Curl file download",                "MEDIUM"),
    (re.compile(r"chmod\s+[+]s",           re.I), "SUID bit modification",             "HIGH"),
    (re.compile(r"/etc/shadow",             re.I), "Shadow file access",                "CRITICAL"),
    (re.compile(r"base64\s+--decode",       re.I), "Base64 decode (possible payload)",  "MEDIUM"),
    (re.compile(r"msfconsole|meterpreter",  re.I), "Metasploit component detected",     "CRITICAL"),
    (re.compile(r"mimikatz",               re.I), "Mimikatz credential dumper",         "CRITICAL"),
]


def flag_suspicious_processes(procs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flag processes whose cmdline matches known suspicious patterns."""
    flagged = []
    for proc in procs:
        cmdline = proc.get("cmdline", "")
        for pattern, reason, severity in SUSPICIOUS_PROC_PATTERNS:
            if pattern.search(cmdline):
                flagged.append({**proc, "reason": reason, "severity": severity})
                break
    return flagged


# ─────────────────────────────────────────────
#  ALERT SYSTEM
# ─────────────────────────────────────────────

_alert_log_file: Optional[str] = None


def set_alert_log(path: str) -> None:
    global _alert_log_file
    _alert_log_file = path


def emit_alert(
    severity: str,
    source:   str,
    message:  str,
    details:  Optional[Dict[str, Any]] = None,
) -> None:
    """
    Print a colored alert to stdout and append a JSON Lines entry to the alert log.
    """
    color  = SEVERITY_COLORS.get(severity, Fore.WHITE)
    ts     = datetime.datetime.utcnow().isoformat() + "Z"
    badge  = f"[{severity}]"
    prefix = f"{Fore.WHITE}{Style.DIM}{ts}{Style.RESET_ALL}"

    print(
        f"{prefix}  {color}{badge:<12}{Style.RESET_ALL}  "
        f"{Fore.CYAN}[{source}]{Style.RESET_ALL}  {message}"
    )
    if details:
        for k, v in details.items():
            print(f"             {Style.DIM}{k}: {v}{Style.RESET_ALL}")

    # JSON Lines log
    if _alert_log_file:
        record = {
            "timestamp": ts,
            "severity":  severity,
            "source":    source,
            "message":   message,
            "details":   details or {},
        }
        try:
            with open(_alert_log_file, "a") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError:
            pass


# ─────────────────────────────────────────────
#  CONFIG LOADER
# ─────────────────────────────────────────────

def load_config(config_file: str) -> Dict[str, Any]:
    """Load a JSON or YAML configuration file."""
    if not os.path.isfile(config_file):
        return {}
    try:
        with open(config_file, "r") as fh:
            content = fh.read()
        if config_file.endswith(".yaml") or config_file.endswith(".yml"):
            if HAS_YAML:
                return yaml.safe_load(content) or {}
            else:
                print(f"{Fore.YELLOW}[!] PyYAML not installed; cannot parse YAML config.{Style.RESET_ALL}")
                return {}
        else:
            return json.loads(content)
    except Exception as exc:
        print(f"{Fore.RED}[-] Failed to load config {config_file}: {exc}{Style.RESET_ALL}")
        return {}


# ─────────────────────────────────────────────
#  HIDS MODES
# ─────────────────────────────────────────────

def mode_baseline(config: Dict[str, Any]) -> None:
    """Create a File Integrity Monitoring baseline."""
    dirs          = config.get("monitor_dirs", DEFAULT_MONITOR_DIRS)
    baseline_file = config.get("baseline_file", DEFAULT_BASELINE_FILE)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}=== BASELINE MODE ==={Style.RESET_ALL}\n")
    create_baseline(dirs, baseline_file)

    # Also snapshot processes
    proc_baseline = config.get("process_baseline_file", "hids_procs_baseline.json")
    if HAS_PSUTIL:
        save_process_baseline(proc_baseline)

    emit_alert("INFO", "HIDS", "Baseline created successfully", {
        "baseline_file": baseline_file,
        "dirs": str(dirs),
    })


def mode_scan(config: Dict[str, Any]) -> None:
    """One-shot FIM + log analysis + process check."""
    dirs          = config.get("monitor_dirs", DEFAULT_MONITOR_DIRS)
    baseline_file = config.get("baseline_file", DEFAULT_BASELINE_FILE)
    rules_file    = config.get("rules_file",    DEFAULT_RULES_FILE)
    log_files     = config.get("log_files",     DEFAULT_LOG_FILES)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}=== SCAN MODE ==={Style.RESET_ALL}\n")

    # ── FIM ──
    print(f"{Fore.CYAN}[*] File Integrity Check{Style.RESET_ALL}")
    if not os.path.isfile(baseline_file):
        print(f"{Fore.YELLOW}[!] No baseline found at '{baseline_file}'. Run with --mode baseline first.{Style.RESET_ALL}")
    else:
        changes = check_integrity(baseline_file, dirs)
        added    = changes["added"]
        modified = changes["modified"]
        deleted  = changes["deleted"]

        print(f"    Added:    {len(added)}")
        print(f"    Modified: {len(modified)}")
        print(f"    Deleted:  {len(deleted)}")

        for path in added:
            emit_alert("MEDIUM", "FIM", f"New file detected: {path}")
        for item in modified:
            emit_alert("HIGH", "FIM", f"File modified: {item['path']}",
                       {"field": item["field"], "old": item["old"], "new": item["new"]})
        for path in deleted:
            emit_alert("HIGH", "FIM", f"File deleted: {path}")

    # ── Log Analysis ──
    print(f"\n{Fore.CYAN}[*] Log Analysis{Style.RESET_ALL}")
    rules    = load_rules(rules_file)
    findings = analyze_all_logs(log_files, rules)
    print(f"    Total findings: {len(findings)}")
    for f in findings:
        emit_alert(f["severity"], f"LOG:{os.path.basename(f['log_file'])}", f["rule_name"],
                   {"description": f["description"], "mitre": f["mitre_technique"],
                    "line": f["line"][:120]})

    # ── Process Monitor ──
    print(f"\n{Fore.CYAN}[*] Process Monitor{Style.RESET_ALL}")
    if HAS_PSUTIL:
        procs   = get_processes()
        flagged = flag_suspicious_processes(procs)
        print(f"    Running processes: {len(procs)}")
        print(f"    Suspicious:        {len(flagged)}")
        for p in flagged:
            emit_alert(p["severity"], "PROCESS", p["reason"],
                       {"pid": p["pid"], "name": p["name"], "cmdline": p["cmdline"][:120]})
    else:
        print(f"    {Fore.YELLOW}psutil unavailable; skipping process scan.{Style.RESET_ALL}")

    print(f"\n{Fore.GREEN}[+] Scan complete.{Style.RESET_ALL}")


def mode_monitor(config: Dict[str, Any]) -> None:
    """Continuous monitoring loop."""
    interval = config.get("interval", DEFAULT_INTERVAL)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}=== MONITOR MODE ==={Style.RESET_ALL}")
    print(f"    Scan interval: {interval}s  |  Press Ctrl-C to stop\n")

    run = True

    def _stop(sig, frame):  # noqa: ANN001
        nonlocal run
        run = False
        print(f"\n{Fore.YELLOW}[*] Stopping HIDS monitor...{Style.RESET_ALL}")

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    cycle = 0
    while run:
        cycle += 1
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{Fore.CYAN}{'─'*60}")
        print(f"  Scan cycle #{cycle}  |  {ts}")
        print(f"{'─'*60}{Style.RESET_ALL}")
        mode_scan(config)
        if run:
            for _ in range(interval):
                if not run:
                    break
                time.sleep(1)

    emit_alert("INFO", "HIDS", "Monitor stopped", {"cycles": cycle})


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hids_agent",
        description="Host-Based Intrusion Detection System Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hids_agent.py --mode baseline --monitor-dir /etc /bin /usr/bin
  python hids_agent.py --mode scan
  python hids_agent.py --mode monitor --interval 120
  python hids_agent.py --mode scan --config hids_config.yaml
        """,
    )
    parser.add_argument(
        "--mode", choices=["baseline", "scan", "monitor"], required=True,
        help="Operating mode: baseline | scan | monitor",
    )
    parser.add_argument(
        "--config", default=None, metavar="FILE",
        help="Path to JSON or YAML configuration file",
    )
    parser.add_argument(
        "--monitor-dir", nargs="+", dest="monitor_dir", metavar="DIR",
        help="Directory/directories to monitor (overrides config)",
    )
    parser.add_argument(
        "--baseline-file", default=DEFAULT_BASELINE_FILE, metavar="FILE",
        help=f"FIM baseline JSON file (default: {DEFAULT_BASELINE_FILE})",
    )
    parser.add_argument(
        "--log-output", default=DEFAULT_ALERT_LOG, metavar="FILE",
        help=f"Alert output file in JSON Lines format (default: {DEFAULT_ALERT_LOG})",
    )
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL, metavar="SECONDS",
        help=f"Scan interval for monitor mode (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--rules", default=DEFAULT_RULES_FILE, metavar="FILE",
        help=f"Detection rules JSON file (default: {DEFAULT_RULES_FILE})",
    )
    parser.add_argument(
        "--log-files", nargs="+", dest="log_files", metavar="FILE",
        help="Log files to analyse (overrides config)",
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colored terminal output",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Merge file config, argparse defaults, and CLI overrides into one dict."""
    config: Dict[str, Any] = {
        "monitor_dirs":  DEFAULT_MONITOR_DIRS,
        "baseline_file": args.baseline_file,
        "log_files":     DEFAULT_LOG_FILES,
        "rules_file":    args.rules,
        "interval":      args.interval,
        "log_output":    args.log_output,
    }

    # Load file config if provided
    if args.config:
        file_cfg = load_config(args.config)
        config.update({k: v for k, v in file_cfg.items() if v is not None})

    # CLI overrides
    if args.monitor_dir:
        config["monitor_dirs"] = args.monitor_dir
    if args.log_files:
        config["log_files"] = args.log_files

    return config


def main() -> None:
    print(BANNER)
    args   = parse_args()
    config = build_config(args)

    # Set up alert log
    set_alert_log(config.get("log_output", DEFAULT_ALERT_LOG))

    emit_alert("INFO", "HIDS", f"Agent started  mode={args.mode}", {
        "version":  VERSION,
        "hostname": platform.node(),
        "python":   sys.version.split()[0],
    })

    if   args.mode == "baseline": mode_baseline(config)
    elif args.mode == "scan":     mode_scan(config)
    elif args.mode == "monitor":  mode_monitor(config)


if __name__ == "__main__":
    main()
