#!/usr/bin/env python3
"""
DFIR Toolkit — Digital Forensics & Incident Response
=====================================================
Collect artifacts, build timelines, manage cases, and generate
forensic reports from Linux/macOS hosts.

Usage:
    python dfir.py --collect all --case-id IR-2024-001 --analyst jsmith
    python dfir.py --collect processes --output-dir /evidence/IR-001
    python dfir.py --collect timeline --case-id IR-2024-001
"""

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
def _red(t):    return (Fore.RED + str(t) + Style.RESET_ALL) if HAS_COLORAMA else str(t)
def _yellow(t): return (Fore.YELLOW + str(t) + Style.RESET_ALL) if HAS_COLORAMA else str(t)
def _green(t):  return (Fore.GREEN + str(t) + Style.RESET_ALL) if HAS_COLORAMA else str(t)
def _cyan(t):   return (Fore.CYAN + str(t) + Style.RESET_ALL) if HAS_COLORAMA else str(t)
def _bold(t):   return (Style.BRIGHT + str(t) + Style.RESET_ALL) if HAS_COLORAMA else str(t)


def now_utc():
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _write_json(path, data):
    """Write data as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    return path


def _banner(text):
    line = "=" * 60
    print(_bold(_cyan(f"\n{line}\n  {text}\n{line}")))


# ---------------------------------------------------------------------------
# 1. ARTIFACT COLLECTION
# ---------------------------------------------------------------------------

def collect_processes(output_dir):
    """
    Collect running process snapshot using psutil.
    Saves processes.json in output_dir.
    """
    _banner("Collecting Processes")
    if not HAS_PSUTIL:
        print(_red("[ERROR] psutil not installed. Run: pip install psutil"))
        return []

    procs = []
    for proc in psutil.process_iter(
        ["pid", "name", "cmdline", "username", "cpu_percent",
         "memory_percent", "create_time", "ppid", "status"]
    ):
        try:
            info = proc.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "",
                "cmdline": " ".join(info["cmdline"] or []),
                "user": info["username"] or "N/A",
                "cpu_percent": round(info["cpu_percent"] or 0.0, 2),
                "memory_percent": round(info["memory_percent"] or 0.0, 3),
                "create_time": datetime.fromtimestamp(
                    info["create_time"], tz=timezone.utc
                ).isoformat() if info["create_time"] else None,
                "parent_pid": info["ppid"],
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    out_path = os.path.join(output_dir, "processes.json")
    _write_json(out_path, procs)
    print(_green(f"[+] Collected {len(procs)} processes -> {out_path}"))

    # Print summary table
    if HAS_TABULATE:
        top = sorted(procs, key=lambda p: p["cpu_percent"], reverse=True)[:10]
        print(tabulate(
            [[p["pid"], p["name"][:30], p["user"], p["cpu_percent"],
              f"{p['memory_percent']:.2f}%", p["cmdline"][:50]]
             for p in top],
            headers=["PID", "Name", "User", "CPU%", "Mem%", "Cmdline"],
            tablefmt="simple",
        ))
    return procs


def collect_network(output_dir):
    """
    Collect active network connections using psutil.
    Saves network_connections.json in output_dir.
    """
    _banner("Collecting Network Connections")
    if not HAS_PSUTIL:
        print(_red("[ERROR] psutil not installed."))
        return []

    connections = []
    for conn in psutil.net_connections(kind="inet"):
        proc_name = "N/A"
        try:
            if conn.pid:
                proc_name = psutil.Process(conn.pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"

        connections.append({
            "local_addr": laddr,
            "remote_addr": raddr,
            "status": conn.status,
            "pid": conn.pid,
            "process_name": proc_name,
            "family": str(conn.family),
            "type": str(conn.type),
        })

    out_path = os.path.join(output_dir, "network_connections.json")
    _write_json(out_path, connections)
    print(_green(f"[+] Collected {len(connections)} connections -> {out_path}"))

    if HAS_TABULATE:
        print(tabulate(
            [[c["local_addr"], c["remote_addr"], c["status"],
              c["pid"], c["process_name"]] for c in connections[:20]],
            headers=["Local", "Remote", "Status", "PID", "Process"],
            tablefmt="simple",
        ))
    return connections


def collect_users(output_dir):
    """
    Collect user account information from /etc/passwd (Linux).
    Falls back to `id` and `who` on other platforms.
    Saves users.json in output_dir.
    """
    _banner("Collecting User Accounts")
    users = []

    # /etc/passwd parse
    passwd_path = "/etc/passwd"
    if os.path.isfile(passwd_path):
        with open(passwd_path, "r", errors="replace") as fh:
            for line in fh:
                parts = line.strip().split(":")
                if len(parts) >= 7:
                    users.append({
                        "username": parts[0],
                        "uid": parts[2],
                        "gid": parts[3],
                        "comment": parts[4],
                        "home": parts[5],
                        "shell": parts[6],
                        "has_shell": parts[6] not in ("/usr/sbin/nologin", "/bin/false", ""),
                    })
        print(_green(f"[+] Parsed {len(users)} accounts from {passwd_path}"))
    else:
        print(_yellow("[!] /etc/passwd not found — skipping passwd parse"))

    # Last logins via `last` command
    last_logins = []
    try:
        result = subprocess.run(
            ["last", "-n", "50", "-F"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] not in ("wtmp", "btmp", "reboot"):
                last_logins.append({
                    "user": parts[0],
                    "tty": parts[1] if len(parts) > 1 else "",
                    "from": parts[2] if len(parts) > 2 else "",
                    "raw": line,
                })
        print(_green(f"[+] Collected {len(last_logins)} last-login records"))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(_yellow(f"[!] Could not run 'last': {exc}"))

    data = {"accounts": users, "last_logins": last_logins}
    out_path = os.path.join(output_dir, "users.json")
    _write_json(out_path, data)
    print(_green(f"[+] User data saved -> {out_path}"))
    return data


def collect_scheduled_tasks(output_dir):
    """
    Collect crontabs and systemd timers.
    Saves scheduled_tasks.json in output_dir.
    """
    _banner("Collecting Scheduled Tasks")
    tasks = {"crontabs": [], "systemd_timers": [], "at_jobs": []}

    # System crontab
    for cron_path in ["/etc/crontab", "/etc/cron.d", "/var/spool/cron/crontabs"]:
        if os.path.isfile(cron_path):
            try:
                with open(cron_path, "r", errors="replace") as fh:
                    tasks["crontabs"].append({"source": cron_path, "content": fh.read()})
            except PermissionError:
                tasks["crontabs"].append({"source": cron_path, "content": "[Permission Denied]"})
        elif os.path.isdir(cron_path):
            try:
                for fname in os.listdir(cron_path):
                    fpath = os.path.join(cron_path, fname)
                    try:
                        with open(fpath, "r", errors="replace") as fh:
                            tasks["crontabs"].append({"source": fpath, "content": fh.read()})
                    except (PermissionError, IsADirectoryError):
                        pass
            except PermissionError:
                pass

    # Systemd timers
    try:
        result = subprocess.run(
            ["systemctl", "list-timers", "--all", "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
        tasks["systemd_timers"] = result.stdout.splitlines()
        print(_green(f"[+] Found {len(tasks['systemd_timers'])} systemd timer lines"))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(_yellow(f"[!] systemctl not available: {exc}"))

    # at jobs
    try:
        result = subprocess.run(["atq"], capture_output=True, text=True, timeout=5)
        tasks["at_jobs"] = result.stdout.splitlines()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    out_path = os.path.join(output_dir, "scheduled_tasks.json")
    _write_json(out_path, tasks)
    print(_green(f"[+] Scheduled task data saved -> {out_path}"))
    return tasks


def collect_recent_files(output_dir, hours=24):
    """
    Find files modified in the last N hours across key directories.
    Saves recent_files.json in output_dir.
    """
    _banner(f"Collecting Files Modified in Last {hours} Hours")
    search_dirs = ["/etc", "/tmp", "/home", "/var/log", "/var/tmp", "/dev/shm"]
    cutoff = time.time() - (hours * 3600)
    found_files = []

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        try:
            for root, dirs, files in os.walk(search_dir, onerror=lambda e: None):
                # Skip deep proc/sys mounts
                dirs[:] = [d for d in dirs if not d.startswith("proc") and d != "sys"]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        stat = os.stat(fpath)
                        if stat.st_mtime >= cutoff:
                            found_files.append({
                                "path": fpath,
                                "size": stat.st_size,
                                "mtime": datetime.fromtimestamp(
                                    stat.st_mtime, tz=timezone.utc
                                ).isoformat(),
                                "uid": stat.st_uid,
                                "permissions": oct(stat.st_mode),
                            })
                    except (PermissionError, OSError):
                        continue
        except PermissionError:
            continue

    found_files.sort(key=lambda f: f["mtime"], reverse=True)
    out_path = os.path.join(output_dir, "recent_files.json")
    _write_json(out_path, found_files)
    print(_green(f"[+] Found {len(found_files)} recently modified files -> {out_path}"))
    return found_files


def collect_loaded_modules(output_dir):
    """
    Collect loaded kernel modules from /proc/modules or lsmod.
    Saves loaded_modules.json in output_dir.
    """
    _banner("Collecting Loaded Kernel Modules")
    modules = []

    proc_modules = "/proc/modules"
    if os.path.isfile(proc_modules):
        try:
            with open(proc_modules, "r") as fh:
                for line in fh:
                    parts = line.strip().split()
                    if parts:
                        modules.append({
                            "name": parts[0],
                            "size": parts[1] if len(parts) > 1 else "",
                            "use_count": parts[2] if len(parts) > 2 else "",
                            "depends": parts[3] if len(parts) > 3 else "",
                            "state": parts[4] if len(parts) > 4 else "",
                        })
        except PermissionError as exc:
            print(_yellow(f"[!] Cannot read /proc/modules: {exc}"))
    else:
        # fallback: lsmod
        try:
            result = subprocess.run(
                ["lsmod"], capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines()[1:]:
                parts = line.split()
                if parts:
                    modules.append({
                        "name": parts[0],
                        "size": parts[1] if len(parts) > 1 else "",
                        "use_count": parts[2] if len(parts) > 2 else "",
                        "depends": parts[3] if len(parts) > 3 else "",
                        "state": "",
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            print(_yellow(f"[!] lsmod not available: {exc}"))

    out_path = os.path.join(output_dir, "loaded_modules.json")
    _write_json(out_path, modules)
    print(_green(f"[+] Found {len(modules)} loaded modules -> {out_path}"))
    return modules


# ---------------------------------------------------------------------------
# 2. EVIDENCE INTEGRITY
# ---------------------------------------------------------------------------

def hash_file(path, algorithm="sha256"):
    """Compute SHA-256 (or other) hash of a file. Returns hex digest string."""
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError) as exc:
        return f"ERROR: {exc}"


def create_manifest(output_dir, algorithm="sha256"):
    """
    Hash every file in output_dir and write a manifest JSON.
    Returns the manifest dict.
    """
    _banner("Creating Evidence Manifest")
    manifest = {
        "created_at": now_utc(),
        "output_dir": output_dir,
        "algorithm": algorithm,
        "files": [],
    }

    for fname in sorted(os.listdir(output_dir)):
        if fname == "manifest.json":
            continue
        fpath = os.path.join(output_dir, fname)
        if os.path.isfile(fpath):
            file_hash = hash_file(fpath, algorithm)
            size = os.path.getsize(fpath)
            manifest["files"].append({
                "filename": fname,
                "path": fpath,
                algorithm: file_hash,
                "size_bytes": size,
                "collected_at": now_utc(),
            })
            print(f"  {fname:<35} {file_hash[:16]}...  ({size:,} bytes)")

    manifest_path = os.path.join(output_dir, "manifest.json")
    _write_json(manifest_path, manifest)
    print(_green(f"[+] Manifest written -> {manifest_path}"))
    return manifest


def chain_of_custody(case_id, analyst, output_dir, action="EVIDENCE_COLLECTED",
                     notes=""):
    """
    Append a chain-of-custody log entry to coc_log.json in output_dir.
    """
    coc_path = os.path.join(output_dir, "coc_log.json")
    existing = []
    if os.path.isfile(coc_path):
        try:
            with open(coc_path, "r") as fh:
                existing = json.load(fh)
        except json.JSONDecodeError:
            existing = []

    entry = {
        "case_id": case_id,
        "analyst": analyst,
        "timestamp": now_utc(),
        "action": action,
        "platform": platform.node(),
        "os": platform.platform(),
        "notes": notes,
        "output_dir": output_dir,
    }
    existing.append(entry)
    _write_json(coc_path, existing)
    print(_green(f"[+] Chain of custody entry appended -> {coc_path}"))
    return entry


# ---------------------------------------------------------------------------
# 3. TIMELINE RECONSTRUCTION
# ---------------------------------------------------------------------------

def parse_auth_log(log_file="/var/log/auth.log"):
    """
    Parse SSH / PAM authentication events from auth.log.
    Returns list of event dicts with timestamp, user, host, event_type.
    """
    events = []
    patterns = [
        (re.compile(r"(\w+\s+\d+\s+\d+:\d+:\d+).*sshd.*Accepted\s+(\w+)\s+for\s+(\S+)\s+from\s+(\S+)"),
         "SSH_LOGIN_SUCCESS"),
        (re.compile(r"(\w+\s+\d+\s+\d+:\d+:\d+).*sshd.*Failed\s+\w+\s+for\s+(\S+)\s+from\s+(\S+)"),
         "SSH_LOGIN_FAIL"),
        (re.compile(r"(\w+\s+\d+\s+\d+:\d+:\d+).*sudo.*:.*USER=(\S+).*;.*COMMAND=(.+)"),
         "SUDO_COMMAND"),
        (re.compile(r"(\w+\s+\d+\s+\d+:\d+:\d+).*useradd.*new user: name=(\S+)"),
         "USER_CREATED"),
    ]

    if not os.path.isfile(log_file):
        print(_yellow(f"[!] Auth log not found: {log_file}"))
        return events

    try:
        with open(log_file, "r", errors="replace") as fh:
            for line in fh:
                for pattern, event_type in patterns:
                    m = pattern.search(line)
                    if m:
                        events.append({
                            "timestamp_raw": m.group(1),
                            "event_type": event_type,
                            "raw_line": line.strip(),
                            "source": log_file,
                            "groups": list(m.groups()),
                        })
                        break
    except PermissionError as exc:
        print(_yellow(f"[!] Cannot read {log_file}: {exc}"))

    print(_green(f"[+] Parsed {len(events)} auth events from {log_file}"))
    return events


def parse_bash_history(user, home_dir=None):
    """
    Parse .bash_history for a given user.
    Returns list of command strings.
    """
    if home_dir is None:
        home_dir = os.path.expanduser(f"~{user}")

    history_path = os.path.join(home_dir, ".bash_history")
    commands = []

    if not os.path.isfile(history_path):
        print(_yellow(f"[!] No bash history at {history_path}"))
        return commands

    try:
        with open(history_path, "r", errors="replace") as fh:
            for line in fh:
                cmd = line.strip()
                if cmd and not cmd.startswith("#"):
                    commands.append({"user": user, "command": cmd, "source": history_path})
    except PermissionError as exc:
        print(_yellow(f"[!] Cannot read {history_path}: {exc}"))

    print(_green(f"[+] Parsed {len(commands)} commands from {history_path}"))
    return commands


def merge_timeline(sources):
    """
    Merge multiple lists of timeline events, sort by timestamp.
    sources: list of lists of event dicts.
    Returns sorted merged list.
    """
    merged = []
    for source in sources:
        merged.extend(source)

    # Try to sort by ISO timestamp if present, else by raw string
    def sort_key(ev):
        ts = ev.get("timestamp") or ev.get("timestamp_raw") or ev.get("mtime") or ""
        return str(ts)

    merged.sort(key=sort_key)
    return merged


def build_timeline(output_dir, case_id="N/A"):
    """
    Build a forensic timeline by merging auth.log, bash history, and file events.
    """
    _banner("Building Timeline")
    sources = []

    # Auth log
    auth_events = parse_auth_log()
    if auth_events:
        sources.append(auth_events)

    # Bash history for all users with home dirs
    try:
        for entry in os.scandir("/home"):
            if entry.is_dir():
                cmds = parse_bash_history(entry.name, entry.path)
                sources.append(cmds)
    except PermissionError:
        pass

    # Recent file events from previous collection
    recent_files_path = os.path.join(output_dir, "recent_files.json")
    if os.path.isfile(recent_files_path):
        with open(recent_files_path) as fh:
            file_events = json.load(fh)
        for fe in file_events:
            fe["event_type"] = "FILE_MODIFIED"
        sources.append(file_events)

    timeline = merge_timeline(sources)
    out_path = os.path.join(output_dir, "timeline.json")
    _write_json(out_path, timeline)
    print(_green(f"[+] Timeline with {len(timeline)} events -> {out_path}"))
    return timeline


# ---------------------------------------------------------------------------
# 4. CASE MANAGEMENT
# ---------------------------------------------------------------------------

CASE_DIRS = ["processes", "network", "files", "timeline", "reports", "evidence"]


def init_case(case_id, analyst, output_dir):
    """
    Initialise a case directory structure with metadata.
    Creates subdirectories and a case_metadata.json file.
    """
    _banner(f"Initialising Case: {case_id}")

    os.makedirs(output_dir, exist_ok=True)
    for sub in CASE_DIRS:
        os.makedirs(os.path.join(output_dir, sub), exist_ok=True)

    metadata = {
        "case_id": case_id,
        "analyst": analyst,
        "created_at": now_utc(),
        "platform": platform.node(),
        "os": platform.platform(),
        "python_version": sys.version,
        "status": "ACTIVE",
        "artifacts_collected": [],
        "output_dir": output_dir,
    }

    meta_path = os.path.join(output_dir, "case_metadata.json")
    _write_json(meta_path, metadata)
    chain_of_custody(case_id, analyst, output_dir, action="CASE_OPENED",
                     notes=f"Case initialised on {platform.node()}")

    print(_green(f"[+] Case {case_id} initialised at {output_dir}"))
    print(f"    Subdirectories: {', '.join(CASE_DIRS)}")
    return metadata


# ---------------------------------------------------------------------------
# 5. REPORT GENERATION
# ---------------------------------------------------------------------------

def generate_html_report(case_id, analyst, output_dir, artifacts):
    """
    Generate a self-contained HTML forensic report with all findings.
    """
    _banner("Generating Forensic Report")

    procs = artifacts.get("processes", [])
    connections = artifacts.get("network", [])
    recent_files = artifacts.get("files", [])
    timeline = artifacts.get("timeline", [])

    suspicious_procs = [p for p in procs if any(
        kw in (p.get("cmdline") or "").lower()
        for kw in ["nc ", "ncat", "netcat", "/tmp/", "curl|", "wget|",
                   "base64", "python -c", "bash -i", "reverse"]
    )]

    suspicious_conns = [c for c in connections if any(
        port in (c.get("remote_addr") or "")
        for port in [":4444", ":1337", ":6667", ":31337", ":8888"]
    )]

    proc_rows = "".join(
        f"""<tr class="{'suspicious-row' if p in suspicious_procs else ''}">
            <td>{p['pid']}</td><td>{p['name'][:40]}</td><td>{p.get('user','')}</td>
            <td>{p['cpu_percent']}</td><td>{p['memory_percent']:.2f}%</td>
            <td style="font-size:11px;max-width:300px;word-break:break-all;">{(p.get('cmdline') or '')[:100]}</td>
        </tr>"""
        for p in (procs[:50])
    )

    conn_rows = "".join(
        f"""<tr class="{'suspicious-row' if c in suspicious_conns else ''}">
            <td>{c['local_addr']}</td><td>{c['remote_addr']}</td>
            <td>{c['status']}</td><td>{c['pid']}</td><td>{c['process_name']}</td>
        </tr>"""
        for c in connections[:30]
    )

    file_rows = "".join(
        f"""<tr>
            <td style="font-size:11px;">{f['path'][:80]}</td>
            <td>{f.get('size',0):,}</td><td>{f.get('mtime','')[:19]}</td>
        </tr>"""
        for f in recent_files[:30]
    )

    timeline_rows = "".join(
        f"""<tr>
            <td style="font-size:10px;">{ev.get('timestamp_raw') or ev.get('mtime','')[:19]}</td>
            <td><span class="badge-{_ev_badge(ev)}">{ev.get('event_type','EVENT')}</span></td>
            <td style="font-size:11px;">{(ev.get('raw_line') or ev.get('path') or ev.get('command',''))[:100]}</td>
        </tr>"""
        for ev in timeline[:50]
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Forensic Report — {case_id}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e6edf3; margin: 0; padding: 0; }}
  header {{ background: #161b22; border-bottom: 2px solid #e3b341; padding: 20px 32px; }}
  header h1 {{ font-size: 22px; color: #e3b341; margin: 0; }}
  header .meta {{ color: #8b949e; font-size: 13px; margin-top: 6px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 32px; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 16px; color: #e3b341; border-bottom: 1px solid #21262d; padding-bottom: 8px; margin-bottom: 14px; }}
  .stats-row {{ display: flex; gap: 16px; margin-bottom: 24px; }}
  .stat-box {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 14px 18px; flex: 1; }}
  .stat-num {{ font-size: 24px; font-weight: 700; font-family: monospace; }}
  .stat-num.red {{ color: #f85149; }} .stat-num.amber {{ color: #e3b341; }} .stat-num.green {{ color: #40c463; }}
  .stat-label {{ font-size: 11px; color: #8b949e; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ background: #161b22; color: #8b949e; padding: 8px 10px; text-align: left; border-bottom: 1px solid #21262d; font-size: 11px; text-transform: uppercase; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #161b22; color: #c9d1d9; }}
  tr:hover td {{ background: rgba(255,255,255,.03); }}
  .suspicious-row td {{ background: rgba(248,81,73,.08); }}
  .badge-auth {{ background: #1a2d4d; color: #58a6ff; padding: 2px 6px; border-radius: 3px; font-size: 10px; }}
  .badge-file {{ background: #3d2a10; color: #e3b341; padding: 2px 6px; border-radius: 3px; font-size: 10px; }}
  .badge-net {{ background: #1a4731; color: #40c463; padding: 2px 6px; border-radius: 3px; font-size: 10px; }}
  .badge-cmd {{ background: #3d1a1a; color: #f85149; padding: 2px 6px; border-radius: 3px; font-size: 10px; }}
  .badge-EVENT {{ background: #21262d; color: #8b949e; padding: 2px 6px; border-radius: 3px; font-size: 10px; }}
  footer {{ text-align: center; padding: 20px; color: #484f58; font-size: 11px; border-top: 1px solid #21262d; margin-top: 40px; }}
</style>
</head>
<body>
<header>
  <h1>DFIR Forensic Report</h1>
  <div class="meta">
    Case ID: <strong>{case_id}</strong> &nbsp;|&nbsp;
    Analyst: <strong>{analyst}</strong> &nbsp;|&nbsp;
    Generated: <strong>{now_utc()[:19]} UTC</strong> &nbsp;|&nbsp;
    Host: <strong>{platform.node()}</strong>
  </div>
</header>
<div class="container">
  <div class="stats-row">
    <div class="stat-box"><div class="stat-num amber">{len(procs)}</div><div class="stat-label">Processes Collected</div></div>
    <div class="stat-box"><div class="stat-num {'red' if suspicious_procs else 'green'}">{len(suspicious_procs)}</div><div class="stat-label">Suspicious Processes</div></div>
    <div class="stat-box"><div class="stat-num amber">{len(connections)}</div><div class="stat-label">Network Connections</div></div>
    <div class="stat-box"><div class="stat-num {'red' if suspicious_conns else 'green'}">{len(suspicious_conns)}</div><div class="stat-label">Suspicious Connections</div></div>
    <div class="stat-box"><div class="stat-num amber">{len(recent_files)}</div><div class="stat-label">Recent Files</div></div>
    <div class="stat-box"><div class="stat-num amber">{len(timeline)}</div><div class="stat-label">Timeline Events</div></div>
  </div>

  <div class="section">
    <h2>Process List {f'<span style="color:#f85149;">({len(suspicious_procs)} suspicious)</span>' if suspicious_procs else ''}</h2>
    <table><thead><tr><th>PID</th><th>Name</th><th>User</th><th>CPU%</th><th>Mem%</th><th>Command Line</th></tr></thead>
    <tbody>{proc_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>Network Connections {f'<span style="color:#f85149;">({len(suspicious_conns)} suspicious)</span>' if suspicious_conns else ''}</h2>
    <table><thead><tr><th>Local Address</th><th>Remote Address</th><th>Status</th><th>PID</th><th>Process</th></tr></thead>
    <tbody>{conn_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>Recently Modified Files (Last 24h)</h2>
    <table><thead><tr><th>Path</th><th>Size</th><th>Modified</th></tr></thead>
    <tbody>{file_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>Forensic Timeline</h2>
    <table><thead><tr><th>Timestamp</th><th>Event Type</th><th>Details</th></tr></thead>
    <tbody>{timeline_rows}</tbody></table>
  </div>
</div>
<footer>Generated by DFIR Toolkit &mdash; {now_utc()[:19]} UTC &mdash; Case {case_id}</footer>
</body></html>"""

    report_path = os.path.join(output_dir, f"forensic_report_{case_id}.html")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(_green(f"[+] Forensic report generated -> {report_path}"))
    return report_path


def _ev_badge(ev):
    et = ev.get("event_type", "")
    if "SSH" in et or "LOGIN" in et or "USER" in et: return "auth"
    if "FILE" in et: return "file"
    if "NET" in et or "CONN" in et: return "net"
    if "CMD" in et or "SUDO" in et: return "cmd"
    return "EVENT"


# ---------------------------------------------------------------------------
# 6. COMMAND-LINE INTERFACE
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="DFIR Toolkit — Digital Forensics & Incident Response",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full collection with case management
  python dfir.py --collect all --case-id IR-2024-001 --analyst jsmith

  # Collect only processes and network connections
  python dfir.py --collect processes,network --output-dir /tmp/evidence

  # Build timeline from previously collected artifacts
  python dfir.py --collect timeline --output-dir /tmp/evidence --case-id IR-001

  # Generate HTML report
  python dfir.py --collect all --case-id IR-001 --analyst jsmith --format html
""",
    )
    parser.add_argument(
        "--collect", "-c",
        default="all",
        help="Comma-separated list: all,processes,network,users,tasks,files,modules,timeline "
             "(default: all)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory for artifacts (default: ./dfir_output_<timestamp>)"
    )
    parser.add_argument(
        "--case-id",
        default=f"CASE-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        help="Case identifier string (default: auto-generated)"
    )
    parser.add_argument(
        "--analyst",
        default=os.environ.get("USER", "unknown"),
        help="Analyst name (default: current user)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "html", "both"],
        default="both",
        help="Report output format (default: both)"
    )
    parser.add_argument(
        "--hours",
        type=int, default=24,
        help="Hours lookback for recent file collection (default: 24)"
    )

    args = parser.parse_args()

    # Determine output directory
    if args.output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = os.path.join(os.getcwd(), f"dfir_output_{ts}")

    os.makedirs(args.output_dir, exist_ok=True)

    # Initialise case
    init_case(args.case_id, args.analyst, args.output_dir)

    collect_targets = [t.strip().lower() for t in args.collect.split(",")]
    do_all = "all" in collect_targets

    artifacts = {}

    if do_all or "processes" in collect_targets:
        artifacts["processes"] = collect_processes(args.output_dir)

    if do_all or "network" in collect_targets:
        artifacts["network"] = collect_network(args.output_dir)

    if do_all or "users" in collect_targets:
        artifacts["users"] = collect_users(args.output_dir)

    if do_all or "tasks" in collect_targets:
        artifacts["tasks"] = collect_scheduled_tasks(args.output_dir)

    if do_all or "files" in collect_targets:
        artifacts["files"] = collect_recent_files(args.output_dir, hours=args.hours)

    if do_all or "modules" in collect_targets:
        artifacts["modules"] = collect_loaded_modules(args.output_dir)

    if do_all or "timeline" in collect_targets:
        artifacts["timeline"] = build_timeline(args.output_dir, args.case_id)

    # Create evidence manifest
    create_manifest(args.output_dir)

    # Chain of custody entry
    chain_of_custody(
        args.case_id, args.analyst, args.output_dir,
        action="COLLECTION_COMPLETE",
        notes=f"Collected: {args.collect}"
    )

    # Generate report
    if args.format in ("html", "both"):
        generate_html_report(
            args.case_id, args.analyst, args.output_dir, artifacts
        )

    if args.format in ("json", "both"):
        report_path = os.path.join(
            args.output_dir, f"forensic_report_{args.case_id}.json"
        )
        _write_json(report_path, {
            "case_id": args.case_id,
            "analyst": args.analyst,
            "generated_at": now_utc(),
            "artifacts": {
                k: (v if not isinstance(v, list) else len(v))
                for k, v in artifacts.items()
            },
        })
        print(_green(f"[+] JSON report -> {report_path}"))

    _banner("Collection Complete")
    print(f"  Case ID  : {_cyan(args.case_id)}")
    print(f"  Analyst  : {_cyan(args.analyst)}")
    print(f"  Output   : {_cyan(args.output_dir)}")
    print(f"  Artifacts: {_cyan(', '.join(artifacts.keys()))}")


if __name__ == "__main__":
    main()
