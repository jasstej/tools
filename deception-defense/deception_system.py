#!/usr/bin/env python3
"""
Deception-Based Security System
Deploys honeytokens / decoy files to detect unauthorized access attempts.
Monitors file system events in real time and emits structured alerts.

Usage:
    python deception_system.py --deploy-dir /tmp/honeyfiles
    python deception_system.py --deploy-dir /tmp/honeyfiles --no-monitor
    python deception_system.py --list-decoys
    python deception_system.py --remove-decoys
"""

import argparse
import configparser
import json
import os
import random
import signal
import string
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

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

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    FileSystemEventHandler = object  # Stub for type hints when watchdog absent

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

REGISTRY_FILE   = ".decoy_registry.json"
DEFAULT_LOG_FILE = "decoy_alerts.json"
DEPLOY_DIR       = None   # Set at runtime
WEBHOOK_URL      = None   # Set at runtime
LOG_FILE         = None   # Set at runtime
ALERT_LEVEL      = "LOW"  # Minimum severity to log/alert

_alert_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
_observer     = None  # watchdog Observer


# ---------------------------------------------------------------------------
# Fake credential generators
# ---------------------------------------------------------------------------

def _rand_alphanum(n: int) -> str:
    """Return n random alphanumeric characters (upper + digits)."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _rand_b64like(n: int) -> str:
    """Return n chars from base-64-ish alphabet (for tokens/secrets)."""
    alphabet = string.ascii_letters + string.digits + "+/"
    return "".join(random.choices(alphabet, k=n))


def fake_aws_access_key() -> str:
    """Generate a realistic-looking (but invalid) AWS access key ID."""
    # Real format: AKIA followed by 16 uppercase alphanumeric chars
    return "AKIA" + _rand_alphanum(16)


def fake_aws_secret_key() -> str:
    """Generate a realistic-looking (but invalid) AWS secret access key."""
    # Real format: 40 alphanumeric + some special chars
    return _rand_b64like(40)


def fake_github_token() -> str:
    """Generate a realistic-looking (but invalid) GitHub personal access token."""
    # Modern format: ghp_ + 36 alphanumeric chars
    return "ghp_" + _rand_b64like(36)


def fake_db_password() -> str:
    """Generate a convincing-looking database password."""
    words = ["secure", "prod", "DB", "pass", "2024", "admin", "root", "main"]
    special = random.choice(["!", "@", "#", "$", "%"])
    return "".join(random.choices(words, k=2)) + str(random.randint(10, 99)) + special


def fake_db_connection_string() -> str:
    """Generate a fake database connection string."""
    user = random.choice(["admin", "dbuser", "app_user", "root", "postgres"])
    pwd  = fake_db_password()
    host = f"db-{random.randint(1,5)}.internal.example.com"
    port = random.choice([5432, 3306, 1433])
    db   = random.choice(["production", "main_db", "app_data", "users"])
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


# ---------------------------------------------------------------------------
# Decoy file content builders
# ---------------------------------------------------------------------------

def _build_passwords_txt() -> str:
    entries = [
        f"admin:{fake_db_password()}",
        f"root:{fake_db_password()}",
        f"deploy:{fake_db_password()}",
        f"backup:{fake_db_password()}",
        f"jenkins:{fake_db_password()}",
    ]
    return "# System passwords — DO NOT SHARE\n" + "\n".join(entries) + "\n"


def _build_credentials_json() -> str:
    data = {
        "aws": {
            "access_key_id":     fake_aws_access_key(),
            "secret_access_key": fake_aws_secret_key(),
            "region":            "us-east-1",
        },
        "github": {
            "token":    fake_github_token(),
            "username": "deploy-bot",
        },
        "database": {
            "connection_string": fake_db_connection_string(),
            "password":          fake_db_password(),
        },
    }
    return json.dumps(data, indent=2)


def _build_aws_keys_txt() -> str:
    return (
        "[default]\n"
        f"aws_access_key_id = {fake_aws_access_key()}\n"
        f"aws_secret_access_key = {fake_aws_secret_key()}\n"
        "region = us-east-1\n"
        "\n"
        "[production]\n"
        f"aws_access_key_id = {fake_aws_access_key()}\n"
        f"aws_secret_access_key = {fake_aws_secret_key()}\n"
        "region = us-west-2\n"
    )


def _build_env() -> str:
    return (
        "# Application environment — production\n"
        f"DATABASE_URL={fake_db_connection_string()}\n"
        f"SECRET_KEY={fake_github_token()}\n"
        f"AWS_ACCESS_KEY_ID={fake_aws_access_key()}\n"
        f"AWS_SECRET_ACCESS_KEY={fake_aws_secret_key()}\n"
        f"GITHUB_TOKEN={fake_github_token()}\n"
        f"REDIS_PASSWORD={fake_db_password()}\n"
        "APP_ENV=production\n"
        "DEBUG=false\n"
    )


def _build_id_rsa() -> str:
    # Fake RSA private key header/footer — not a real key
    fake_body = "\n".join(
        "".join(random.choices(string.ascii_letters + string.digits + "+/", k=64))
        for _ in range(26)
    )
    return (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        f"{fake_body}\n"
        "-----END RSA PRIVATE KEY-----\n"
    )


def _build_config_ini() -> str:
    cfg = configparser.ConfigParser()
    cfg["database"] = {
        "host":     "db.internal.example.com",
        "port":     "5432",
        "name":     "production",
        "user":     "app_admin",
        "password": fake_db_password(),
    }
    cfg["smtp"] = {
        "host":     "smtp.example.com",
        "port":     "587",
        "user":     "noreply@example.com",
        "password": fake_db_password(),
    }
    cfg["aws"] = {
        "access_key": fake_aws_access_key(),
        "secret_key": fake_aws_secret_key(),
    }
    import io
    buf = io.StringIO()
    cfg.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Decoy definitions: filename → content builder
# ---------------------------------------------------------------------------

DECOY_DEFINITIONS = {
    "passwords.txt":    _build_passwords_txt,
    "credentials.json": _build_credentials_json,
    "aws_keys.txt":     _build_aws_keys_txt,
    ".env":             _build_env,
    "id_rsa":           _build_id_rsa,
    "config.ini":       _build_config_ini,
}

# Honeypath subdirectories to create inside deploy_dir
HONEYPATH_DIRS = ["backup", "scripts", "private"]


# ---------------------------------------------------------------------------
# Deploy / manage decoys
# ---------------------------------------------------------------------------

def deploy_decoys(deploy_dir: str) -> None:
    """
    Create all decoy files and honeypath subdirectories.
    Writes a .decoy_registry.json manifest for tracking.
    """
    root = Path(deploy_dir)
    root.mkdir(parents=True, exist_ok=True)

    # Create honeypath subdirectories
    for subdir in HONEYPATH_DIRS:
        (root / subdir).mkdir(exist_ok=True)
        cprint(f"  [+] Created honeypath dir: {root / subdir}", Fore.CYAN)

    registry = {
        "deploy_dir": str(root.resolve()),
        "deployed_at": datetime.now().isoformat(),
        "decoys": [],
    }

    for filename, builder in DECOY_DEFINITIONS.items():
        # Write decoy to root and also to backup/ subdirectory for wider coverage
        for dest_dir in [root, root / "backup"]:
            path = dest_dir / filename
            content = builder()
            path.write_text(content, encoding="utf-8")
            # chmod id_rsa to 600 to look authentic
            if filename == "id_rsa":
                path.chmod(0o600)
            registry["decoys"].append({
                "filename": filename,
                "path": str(path.resolve()),
                "deployed_at": datetime.now().isoformat(),
                "trigger_count": 0,
            })
            cprint(f"  [+] Deployed decoy: {path}", Fore.GREEN)

    # Write registry
    registry_path = root / REGISTRY_FILE
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    cprint(f"\n[+] Registry saved: {registry_path}", Fore.GREEN, bright=True)
    cprint(f"[+] {len(registry['decoys'])} decoy files deployed in {root}", Fore.GREEN, bright=True)


def list_decoys() -> None:
    """Print all deployed decoys from the registry."""
    reg = _load_registry()
    if not reg:
        cprint("[!] No registry found. Run --deploy-dir first.", Fore.YELLOW)
        return
    cprint(f"\n[*] Deployed decoys in: {reg['deploy_dir']}", Fore.CYAN, bright=True)
    for d in reg.get("decoys", []):
        exists = "EXISTS" if Path(d["path"]).exists() else "MISSING"
        color  = Fore.GREEN if exists == "EXISTS" else Fore.RED
        cprint(f"  [{exists}] {d['path']}  (triggers: {d['trigger_count']})", color)


def remove_decoys() -> None:
    """Remove all deployed decoy files listed in the registry."""
    reg = _load_registry()
    if not reg:
        cprint("[!] No registry found.", Fore.YELLOW)
        return
    removed = 0
    for d in reg.get("decoys", []):
        p = Path(d["path"])
        if p.exists():
            p.unlink()
            removed += 1
            cprint(f"  [-] Removed: {p}", Fore.YELLOW)
    reg_path = Path(reg["deploy_dir"]) / REGISTRY_FILE
    if reg_path.exists():
        reg_path.unlink()
    cprint(f"\n[+] Removed {removed} decoy files.", Fore.GREEN, bright=True)


def _load_registry() -> dict:
    """Load the decoy registry from cwd or DEPLOY_DIR."""
    candidates = [
        Path(DEPLOY_DIR or ".") / REGISTRY_FILE,
        Path(".") / REGISTRY_FILE,
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------------------
# Alert system
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _severity_passes(severity: str) -> bool:
    """Check whether this severity meets the configured alert level threshold."""
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(ALERT_LEVEL, 1)


def _resolve_pid_info() -> dict:
    """
    Attempt to find the process that recently accessed a file.
    Returns a dict with pid, name, cmdline, user (best-effort).
    """
    if not HAS_PSUTIL:
        return {"pid": None, "name": "unknown", "cmdline": "", "user": "unknown"}
    try:
        # Walk open files of all accessible processes
        for proc in psutil.process_iter(["pid", "name", "username", "cmdline"]):
            try:
                info = proc.info
                return {
                    "pid":     info["pid"],
                    "name":    info["name"],
                    "cmdline": " ".join(info["cmdline"] or []),
                    "user":    info["username"],
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return {"pid": None, "name": "unknown", "cmdline": "", "user": "unknown"}


def emit_alert(event_type: str, filepath: str, severity: str = "HIGH") -> None:
    """
    Emit a structured security alert:
      1. Log to the console with colorama coloring.
      2. Append JSON entry to the log file.
      3. POST to webhook URL if configured.
    """
    if not _severity_passes(severity):
        return

    _alert_counts[severity] = _alert_counts.get(severity, 0) + 1

    timestamp  = datetime.now().isoformat()
    proc_info  = _resolve_pid_info()
    alert_data = {
        "timestamp":  timestamp,
        "severity":   severity,
        "event_type": event_type,
        "filepath":   filepath,
        "process":    proc_info,
    }

    # 1. Console output
    color = (Fore.RED if severity in ("CRITICAL", "HIGH")
             else Fore.YELLOW if severity == "MEDIUM"
             else Fore.CYAN)
    cprint(
        f"[{timestamp}] [{severity}] {event_type} → {filepath}  "
        f"(pid={proc_info['pid']}, user={proc_info['user']})",
        color,
        bright=(severity in ("CRITICAL", "HIGH")),
    )

    # 2. Log file
    log_path = Path(LOG_FILE or DEFAULT_LOG_FILE)
    try:
        existing = []
        if log_path.exists():
            existing = json.loads(log_path.read_text(encoding="utf-8"))
        existing.append(alert_data)
        log_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception as exc:
        cprint(f"[!] Failed to write log: {exc}", Fore.YELLOW)

    # 3. Webhook POST
    if WEBHOOK_URL and HAS_REQUESTS:
        try:
            requests.post(WEBHOOK_URL, json=alert_data, timeout=5)
        except Exception as exc:
            cprint(f"[!] Webhook delivery failed: {exc}", Fore.YELLOW)


# ---------------------------------------------------------------------------
# Filesystem event handler (watchdog)
# ---------------------------------------------------------------------------

class DecoyEventHandler(FileSystemEventHandler if HAS_WATCHDOG else object):
    """
    Watches the deploy directory and fires alerts when decoy files are
    accessed, modified, moved, or deleted.
    """

    def __init__(self, decoy_paths: set):
        if HAS_WATCHDOG:
            super().__init__()
        # Normalize all decoy paths for fast lookup
        self._decoy_paths = {str(Path(p).resolve()) for p in decoy_paths}

    def _is_decoy(self, path: str) -> bool:
        return str(Path(path).resolve()) in self._decoy_paths

    def on_modified(self, event):
        if not event.is_directory and self._is_decoy(event.src_path):
            emit_alert("FILE_MODIFIED", event.src_path, "CRITICAL")

    def on_accessed(self, event):
        if not event.is_directory and self._is_decoy(event.src_path):
            emit_alert("FILE_ACCESSED", event.src_path, "HIGH")

    def on_deleted(self, event):
        if not event.is_directory and self._is_decoy(event.src_path):
            emit_alert("FILE_DELETED", event.src_path, "CRITICAL")

    def on_moved(self, event):
        if not event.is_directory and self._is_decoy(event.src_path):
            emit_alert("FILE_MOVED", event.src_path, "HIGH")

    def on_created(self, event):
        # Alert on new files in honeypath directories — may indicate exfil staging
        if not event.is_directory:
            emit_alert("FILE_CREATED_IN_HONEYPATH", event.src_path, "MEDIUM")


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

def start_monitoring(deploy_dir: str) -> None:
    """
    Start the watchdog observer loop to monitor the deploy directory.
    Blocks until interrupted by SIGINT/SIGTERM.
    """
    global _observer

    if not HAS_WATCHDOG:
        cprint("[!] watchdog is not installed. Run: pip install watchdog", Fore.RED, bright=True)
        sys.exit(1)

    reg = _load_registry()
    decoy_paths = {d["path"] for d in reg.get("decoys", [])}

    if not decoy_paths:
        cprint("[!] No decoys registered. Run --deploy-dir first.", Fore.YELLOW)
        sys.exit(1)

    handler  = DecoyEventHandler(decoy_paths)
    _observer = Observer()
    _observer.schedule(handler, deploy_dir, recursive=True)
    _observer.start()

    cprint(f"\n[*] Monitoring {len(decoy_paths)} decoys in {deploy_dir}", Fore.GREEN, bright=True)
    cprint(f"[*] Alert level: {ALERT_LEVEL}  |  Log: {LOG_FILE or DEFAULT_LOG_FILE}", Fore.CYAN)
    cprint("[*] Press Ctrl+C to stop.\n", Fore.CYAN)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown(None, None)


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

def _shutdown(sig, frame) -> None:
    """Handle SIGINT / SIGTERM — print summary and stop observer."""
    global _observer
    cprint("\n\n[*] Shutting down monitor...", Fore.CYAN, bright=True)
    if _observer:
        _observer.stop()
        _observer.join()
    _print_summary()
    sys.exit(0)


def _print_summary() -> None:
    """Print alert count summary."""
    cprint("\n─────── Alert Summary ───────", Fore.CYAN, bright=True)
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        count = _alert_counts.get(sev, 0)
        color = Fore.RED if sev in ("CRITICAL","HIGH") else Fore.YELLOW if sev == "MEDIUM" else Fore.CYAN
        cprint(f"  {sev:<10}: {count}", color)
    total = sum(_alert_counts.values())
    cprint(f"  {'TOTAL':<10}: {total}", Fore.WHITE, bright=True)
    cprint("─────────────────────────────\n", Fore.CYAN)


def cprint(msg: str, color: str = "", bright: bool = False) -> None:
    """Colorized print helper."""
    prefix = (Style.BRIGHT if bright else "") + color if HAS_COLOR else ""
    print(f"{prefix}{msg}{Style.RESET_ALL if HAS_COLOR else ''}")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deception-Based Security System — deploy and monitor honeytokens",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deception_system.py --deploy-dir /tmp/honeyfiles
  python deception_system.py --deploy-dir /tmp/honeyfiles --webhook-url https://hooks.example.com/alert
  python deception_system.py --deploy-dir /tmp/honeyfiles --no-monitor
  python deception_system.py --list-decoys
  python deception_system.py --remove-decoys
        """,
    )
    parser.add_argument("--deploy-dir",   "-d", help="Directory to deploy decoy files into")
    parser.add_argument("--webhook-url",  "-w", help="HTTP POST endpoint for alert notifications")
    parser.add_argument("--log-file",     "-l", default=DEFAULT_LOG_FILE, help=f"JSON log file path (default: {DEFAULT_LOG_FILE})")
    parser.add_argument("--alert-level",  "-a", choices=["CRITICAL","HIGH","MEDIUM","LOW"], default="LOW", help="Minimum severity to log (default: LOW)")
    parser.add_argument("--list-decoys",  action="store_true", help="List all registered decoy files and exit")
    parser.add_argument("--remove-decoys",action="store_true", help="Remove all registered decoy files and exit")
    parser.add_argument("--no-monitor",   action="store_true", help="Deploy decoys but do not start monitoring")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global DEPLOY_DIR, WEBHOOK_URL, LOG_FILE, ALERT_LEVEL

    args = parse_args()

    WEBHOOK_URL  = args.webhook_url
    LOG_FILE     = args.log_file
    ALERT_LEVEL  = args.alert_level

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── List decoys ──
    if args.list_decoys:
        list_decoys()
        return

    # ── Remove decoys ──
    if args.remove_decoys:
        remove_decoys()
        return

    # ── Deploy + monitor ──
    if not args.deploy_dir:
        cprint("[!] --deploy-dir is required (or use --list-decoys / --remove-decoys).", Fore.RED, bright=True)
        sys.exit(1)

    DEPLOY_DIR = args.deploy_dir

    cprint("\n╔══════════════════════════════════════╗", Fore.CYAN, bright=True)
    cprint("║  Deception-Based Security System     ║", Fore.CYAN, bright=True)
    cprint("╚══════════════════════════════════════╝\n", Fore.CYAN, bright=True)
    cprint(f"[*] Deploy dir  : {DEPLOY_DIR}", Fore.WHITE)
    cprint(f"[*] Alert level : {ALERT_LEVEL}", Fore.WHITE)
    cprint(f"[*] Log file    : {LOG_FILE}", Fore.WHITE)
    if WEBHOOK_URL:
        cprint(f"[*] Webhook     : {WEBHOOK_URL}", Fore.WHITE)
    cprint(f"[!] Legal reminder: deploy only on systems you own or are authorized to test.\n", Fore.YELLOW)

    # Deploy decoys
    deploy_decoys(DEPLOY_DIR)

    if args.no_monitor:
        cprint("\n[*] --no-monitor set. Deployment complete. Exiting.", Fore.CYAN)
        return

    # Start monitoring
    start_monitoring(DEPLOY_DIR)


if __name__ == "__main__":
    main()
