#!/usr/bin/env python3
"""
SOAR-Lite: Security Orchestration, Automation and Response Engine
Provides alert ingestion, correlation, deduplication, playbook execution,
metrics reporting, and a simple HTTP server for receiving alerts.
"""

import argparse
import hashlib
import json
import logging
import random
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLOR = True
except ImportError:
    COLOR = False

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("soar-lite")

# ─── Color helpers ────────────────────────────────────────────────────────────

def _c(text: str, color_code: str) -> str:
    if not COLOR:
        return text
    return f"{color_code}{text}{Style.RESET_ALL}"

def red(t):    return _c(t, Fore.RED)
def yellow(t): return _c(t, Fore.YELLOW)
def green(t):  return _c(t, Fore.GREEN)
def cyan(t):   return _c(t, Fore.CYAN)
def magenta(t):return _c(t, Fore.MAGENTA)
def bold(t):   return _c(t, Style.BRIGHT)

SEVERITY_COLORS = {
    "CRITICAL": red,
    "HIGH":     yellow,
    "MEDIUM":   cyan,
    "LOW":      green,
    "INFO":     lambda t: t,
}

# ─── Alert Ingestion ──────────────────────────────────────────────────────────

REQUIRED_ALERT_FIELDS = {"id", "timestamp", "type", "severity", "source_ip", "affected_asset"}

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}

VALID_ALERT_TYPES = {
    "SSH Brute Force", "RDP Brute Force", "Malware Detection",
    "C2 Communication", "Privilege Escalation", "Data Exfiltration",
    "SQL Injection", "Port Scan", "Credential Dump",
    "Ransomware Indicator", "Insider Threat", "Phishing",
    "Web Application Brute Force", "Account Lockout", "Unknown",
}


def load_alerts_from_file(json_file: str) -> list[dict]:
    """Load and parse alerts from a JSON file (array format)."""
    path = Path(json_file)
    if not path.exists():
        log.error("Alert file not found: %s", json_file)
        sys.exit(1)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = [raw]
    log.info("Loaded %d raw alerts from %s", len(raw), json_file)
    return raw


def normalize_alert(raw_alert: dict) -> dict:
    """Standardize alert fields to a canonical schema."""
    alert = dict(raw_alert)
    # Normalize severity to uppercase
    alert["severity"] = str(alert.get("severity", "MEDIUM")).upper()
    if alert["severity"] not in VALID_SEVERITIES:
        alert["severity"] = "MEDIUM"
    # Normalize type
    alert.setdefault("type", "Unknown")
    # Ensure timestamp is present
    if "timestamp" not in alert:
        alert["timestamp"] = datetime.now(timezone.utc).isoformat()
    # Ensure status
    alert.setdefault("status", "NEW")
    # Ensure details is a dict
    if "details" not in alert or not isinstance(alert["details"], dict):
        alert["details"] = {}
    # Generate normalized id if missing
    if "id" not in alert:
        h = hashlib.md5(json.dumps(alert, sort_keys=True).encode()).hexdigest()[:8]
        alert["id"] = f"ALERT-{h.upper()}"
    # Ensure source_ip and affected_asset
    alert.setdefault("source_ip", "0.0.0.0")
    alert.setdefault("affected_asset", "UNKNOWN")
    alert.setdefault("assigned_playbook", None)
    return alert


def validate_alert(alert: dict) -> tuple[bool, list[str]]:
    """Validate normalized alert. Returns (is_valid, list_of_errors)."""
    errors = []
    for field in REQUIRED_ALERT_FIELDS:
        if field not in alert:
            errors.append(f"Missing required field: {field}")
    if alert.get("severity") not in VALID_SEVERITIES:
        errors.append(f"Invalid severity: {alert.get('severity')}")
    # Validate timestamp format
    ts = alert.get("timestamp", "")
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(f"Invalid timestamp format: {ts}")
    return len(errors) == 0, errors


# ─── Alert Correlation ────────────────────────────────────────────────────────

def _parse_ts(ts: str) -> datetime:
    """Parse ISO8601 timestamp to datetime (UTC)."""
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def correlate_by_source_ip(alerts: list[dict], window_minutes: int = 5) -> dict[str, list[dict]]:
    """Group alerts by source IP within a sliding time window."""
    groups: dict[str, list[dict]] = {}
    sorted_alerts = sorted(alerts, key=lambda a: a["timestamp"])
    for alert in sorted_alerts:
        ip = alert.get("source_ip", "unknown")
        if ip not in groups:
            groups[ip] = []
        ts = _parse_ts(alert["timestamp"])
        # Remove alerts outside the window
        window = timedelta(minutes=window_minutes)
        groups[ip] = [a for a in groups[ip] if ts - _parse_ts(a["timestamp"]) <= window]
        groups[ip].append(alert)
    # Return only IPs with more than one alert (actual correlations)
    return {ip: alerts for ip, alerts in groups.items() if len(alerts) > 1}


def correlate_by_asset(alerts: list[dict]) -> dict[str, list[dict]]:
    """Group all alerts by affected asset."""
    groups: dict[str, list[dict]] = {}
    for alert in alerts:
        asset = alert.get("affected_asset", "UNKNOWN")
        groups.setdefault(asset, []).append(alert)
    return {asset: als for asset, als in groups.items() if len(als) > 1}


ATTACK_PATTERNS = [
    {
        "name": "Ransomware Kill Chain",
        "sequence": ["Malware Detection", "Credential Dump", "Ransomware Indicator"],
        "description": "Classic ransomware execution pattern: initial compromise, credential harvesting, encryption.",
    },
    {
        "name": "Brute Force to Compromise",
        "sequence": ["SSH Brute Force", "Privilege Escalation"],
        "description": "Credential attack followed by privilege escalation — likely successful login.",
    },
    {
        "name": "Exfiltration After C2",
        "sequence": ["C2 Communication", "Data Exfiltration"],
        "description": "C2 beaconing followed by data exfiltration — active APT behavior.",
    },
    {
        "name": "Recon to Exploitation",
        "sequence": ["Port Scan", "SQL Injection"],
        "description": "Network reconnaissance followed by web application exploitation.",
    },
]


def detect_attack_pattern(correlated_alerts: dict) -> list[dict]:
    """Detect multi-step attack sequences across correlated alert groups."""
    detected = []
    for group_key, alerts in correlated_alerts.items():
        alert_types = [a["type"] for a in alerts]
        for pattern in ATTACK_PATTERNS:
            seq = pattern["sequence"]
            if all(t in alert_types for t in seq):
                detected.append({
                    "pattern": pattern["name"],
                    "description": pattern["description"],
                    "group": group_key,
                    "matching_alerts": [a["id"] for a in alerts if a["type"] in seq],
                    "confidence": round(len(seq) / len(ATTACK_PATTERNS) * 100, 1),
                })
    return detected


ASSET_CRITICALITY = {
    "DOMAIN-CONTROLLER": 10,
    "PROD-SERVER":       9,
    "FILE-SERVER":       8,
    "HR-DATABASE-SERVER":8,
    "WEB-APP-SERVER":    7,
    "DEV-LAPTOP":        4,
    "WORKSTATION":       3,
    "DMZ":               6,
}


def calculate_priority(alert: dict, correlation_count: int = 1, asset_criticality: int = 5) -> int:
    """
    Calculate a 1-100 priority score for an alert.
    Factors: severity, correlation count, asset criticality.
    """
    severity_weights = {"CRITICAL": 40, "HIGH": 30, "MEDIUM": 20, "LOW": 10, "INFO": 5}
    base = severity_weights.get(alert.get("severity", "MEDIUM"), 20)
    corr_bonus = min(correlation_count * 5, 20)
    crit_bonus = min(asset_criticality * 2, 20)
    noise_penalty = 0 if alert.get("status") == "NEW" else 5
    return min(100, base + corr_bonus + crit_bonus - noise_penalty)


# ─── Deduplication ────────────────────────────────────────────────────────────

def _alert_fingerprint(alert: dict) -> str:
    key = f"{alert.get('type')}|{alert.get('source_ip')}|{alert.get('affected_asset')}"
    return hashlib.md5(key.encode()).hexdigest()


def deduplicate_alerts(alerts: list[dict], window_seconds: int = 300) -> list[dict]:
    """Remove duplicate alerts (same type/IP/asset) within window_seconds."""
    seen: dict[str, datetime] = {}
    unique: list[dict] = []
    for alert in sorted(alerts, key=lambda a: a["timestamp"]):
        fp = _alert_fingerprint(alert)
        ts = _parse_ts(alert["timestamp"])
        if fp in seen:
            if (ts - seen[fp]).total_seconds() < window_seconds:
                log.debug("Deduped alert %s (fingerprint %s)", alert["id"], fp[:8])
                continue
        seen[fp] = ts
        unique.append(alert)
    removed = len(alerts) - len(unique)
    if removed:
        log.info("Deduplication removed %d duplicate alert(s).", removed)
    return unique


# ─── Playbook Engine ──────────────────────────────────────────────────────────

def load_playbook(json_file: str) -> dict:
    """Load a SOAR playbook from a JSON file."""
    path = Path(json_file)
    if not path.exists():
        log.error("Playbook not found: %s", json_file)
        sys.exit(1)
    pb = json.loads(path.read_text(encoding="utf-8"))
    log.info("Loaded playbook: %s (%d steps)", pb.get("name"), len(pb.get("steps", [])))
    return pb


def evaluate_trigger(playbook: dict, alert: dict) -> tuple[bool, str]:
    """
    Check whether an alert satisfies playbook trigger conditions.
    Returns (triggered: bool, reason: str).
    """
    conds = playbook.get("trigger_conditions", {})
    alert_type = alert.get("type", "")
    severity = alert.get("severity", "")

    # Check alert type
    allowed_types = conds.get("alert_types", [])
    if allowed_types and alert_type not in allowed_types:
        return False, f"Alert type '{alert_type}' not in trigger list {allowed_types}"

    # Check severity
    allowed_severities = conds.get("severity", [])
    if allowed_severities and severity not in allowed_severities:
        return False, f"Severity '{severity}' not in trigger list {allowed_severities}"

    # Check keywords in details
    keywords = conds.get("keywords", [])
    if keywords:
        details_str = json.dumps(alert.get("details", {})).lower()
        if not any(kw.lower() in details_str for kw in keywords):
            return False, f"No trigger keywords found in alert details"

    return True, "All trigger conditions met"


# ─── Step Actions (all logged; execution gated by dry_run flag) ───────────────

def _log_action(dry_run: bool, action: str, params: dict, context: dict) -> dict:
    prefix = "[DRY RUN] " if dry_run else "[EXECUTE] "
    log.info("%s%s | params=%s | incident=%s", prefix, action.upper(),
             json.dumps(params, default=str)[:120], context.get("incident_id", "N/A"))
    return {
        "action": action,
        "dry_run": dry_run,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "params": params,
        "result": "simulated" if dry_run else "executed",
    }


def block_ip(params: dict, context: dict, dry_run: bool) -> dict:
    ip = context.get("source_ip", params.get("target_ip", "N/A"))
    log.info("%s block_ip %s at [%s]",
             "[DRY RUN]" if dry_run else "[EXECUTE]",
             ip, ", ".join(params.get("block_at", ["firewall"])))
    return _log_action(dry_run, "block_ip", {"ip": ip, **params}, context)


def isolate_host(params: dict, context: dict, dry_run: bool) -> dict:
    host = context.get("affected_asset", "UNKNOWN")
    log.info("%s isolate_host %s via %s",
             "[DRY RUN]" if dry_run else "[EXECUTE]",
             host, params.get("method", "network_isolation"))
    return _log_action(dry_run, "isolate_host", {"host": host, **params}, context)


def disable_user(params: dict, context: dict, dry_run: bool) -> dict:
    log.info("%s disable_user on asset %s",
             "[DRY RUN]" if dry_run else "[EXECUTE]",
             context.get("affected_asset", "UNKNOWN"))
    return _log_action(dry_run, "disable_user", params, context)


def kill_process(params: dict, context: dict, dry_run: bool) -> dict:
    proc = params.get("process_name", "unknown_process")
    log.info("%s kill_process %s on %s",
             "[DRY RUN]" if dry_run else "[EXECUTE]",
             proc, context.get("affected_asset", "UNKNOWN"))
    return _log_action(dry_run, "kill_process", params, context)


def create_ticket(params: dict, context: dict, dry_run: bool) -> dict:
    system = params.get("ticket_system", "jira")
    priority = params.get("priority", "High")
    log.info("%s create_ticket in %s with priority %s",
             "[DRY RUN]" if dry_run else "[EXECUTE]", system, priority)
    fake_ticket_id = f"INC-{random.randint(10000, 99999)}"
    result = _log_action(dry_run, "create_ticket", params, context)
    result["ticket_id"] = fake_ticket_id
    return result


def notify_team(params: dict, context: dict, dry_run: bool) -> dict:
    channels = params.get("channels", ["email"])
    log.info("%s notify_team via %s",
             "[DRY RUN]" if dry_run else "[EXECUTE]", channels)
    return _log_action(dry_run, "notify_team", params, context)


def run_script(params: dict, context: dict, dry_run: bool) -> dict:
    script = params.get("script", "unknown_script.sh")
    log.info("%s run_script %s",
             "[DRY RUN]" if dry_run else "[EXECUTE]", script)
    return _log_action(dry_run, "run_script", params, context)


def enrich_ip(params: dict, context: dict, dry_run: bool) -> dict:
    """Mock IP enrichment with whois/geo lookup data."""
    ip = context.get("source_ip", "0.0.0.0")
    mock_enrichment = {
        "ip": ip,
        "country": random.choice(["Russia", "China", "Netherlands", "Brazil", "Ukraine"]),
        "asn": f"AS{random.randint(1000, 65000)}",
        "is_tor_exit": random.choice([True, False]),
        "is_vpn": random.choice([True, False]),
        "abuse_confidence_score": random.randint(60, 100),
        "threat_intel_hits": random.randint(0, 15),
        "isp": random.choice(["Choopa LLC", "DigitalOcean", "M247 Ltd", "Hetzner"]),
    }
    log.info("%s enrich_ip %s -> country=%s, abuse_score=%d",
             "[DRY RUN]" if dry_run else "[EXECUTE]",
             ip, mock_enrichment["country"], mock_enrichment["abuse_confidence_score"])
    result = _log_action(dry_run, "enrich_ip", params, context)
    result["enrichment"] = mock_enrichment
    return result


ACTION_HANDLERS = {
    "block_ip":     block_ip,
    "isolate_host": isolate_host,
    "disable_user": disable_user,
    "kill_process": kill_process,
    "create_ticket":create_ticket,
    "notify_team":  notify_team,
    "run_script":   run_script,
    "enrich_ip":    enrich_ip,
}


def execute_step(step: dict, context: dict, dry_run: bool = True) -> dict:
    """Execute a single playbook step. Context carries alert fields."""
    action_name = step.get("action", "unknown")
    params = step.get("params", {})
    handler = ACTION_HANDLERS.get(action_name)
    if handler is None:
        log.warning("Unknown action '%s' in step '%s' — skipping.", action_name, step.get("name"))
        return {"action": action_name, "result": "SKIPPED", "reason": "unknown action"}
    try:
        result = handler(params, context, dry_run)
        result["status"] = "COMPLETED"
        result["step_id"] = step.get("id")
        result["step_name"] = step.get("name")
        return result
    except Exception as exc:
        log.error("Step '%s' failed: %s", step.get("name"), exc)
        return {"step_id": step.get("id"), "step_name": step.get("name"),
                "status": "FAILED", "error": str(exc)}


def execute_playbook(playbook: dict, alert: dict, dry_run: bool = True) -> dict:
    """Execute all steps in a playbook for the given alert."""
    context = {
        "incident_id":    alert.get("id"),
        "source_ip":      alert.get("source_ip"),
        "affected_asset": alert.get("affected_asset"),
        "severity":       alert.get("severity"),
        "alert_type":     alert.get("type"),
        "timestamp":      alert.get("timestamp"),
        "details":        alert.get("details", {}),
    }

    print(bold(f"\n{'='*60}"))
    print(bold(f"  PLAYBOOK: {playbook.get('name')}"))
    print(bold(f"  ALERT:    {alert.get('id')} | {alert.get('type')} | {alert.get('severity')}"))
    mode_label = "DRY RUN — no actions will be executed" if dry_run else "EXECUTE MODE — actions are LIVE"
    color_fn = yellow if dry_run else red
    print(color_fn(f"  MODE:     {mode_label}"))
    print(bold(f"{'='*60}\n"))

    steps = playbook.get("steps", [])
    step_index = {s["id"]: s for s in steps}
    execution_log = []
    current_id = steps[0]["id"] if steps else None
    step_num = 0

    while current_id and current_id in step_index:
        step = step_index[current_id]
        step_num += 1
        print(f"  [{step_num:02d}] {cyan(step.get('name', current_id))} — {step.get('description', '')[:70]}")
        result = execute_step(step, context, dry_run)
        status_color = green if result.get("status") == "COMPLETED" else red
        print(f"       Status: {status_color(result.get('status', 'UNKNOWN'))}\n")
        execution_log.append(result)

        if result.get("status") == "COMPLETED":
            current_id = step.get("on_success")
        else:
            current_id = step.get("on_failure")

    completion_time = datetime.now(timezone.utc).isoformat()
    failed = sum(1 for r in execution_log if r.get("status") == "FAILED")
    print(bold(f"\n{'='*60}"))
    print(green(f"  PLAYBOOK COMPLETE | {len(execution_log)} steps | {failed} failures"))
    print(bold(f"{'='*60}\n"))

    return {
        "playbook_name": playbook.get("name"),
        "alert_id":      alert.get("id"),
        "dry_run":       dry_run,
        "started_at":    context["timestamp"],
        "completed_at":  completion_time,
        "steps_executed":len(execution_log),
        "steps_failed":  failed,
        "execution_log": execution_log,
    }


# ─── Metrics ──────────────────────────────────────────────────────────────────

def calculate_mttr(incidents: list[dict]) -> float:
    """Mean time to resolve in minutes."""
    times = []
    for inc in incidents:
        start = inc.get("started_at")
        end = inc.get("completed_at")
        if start and end:
            try:
                delta = _parse_ts(end) - _parse_ts(start)
                times.append(delta.total_seconds() / 60)
            except Exception:
                pass
    return round(sum(times) / len(times), 2) if times else 0.0


def count_by_severity(incidents: list[dict]) -> dict[str, int]:
    """Count incidents/alerts by severity."""
    counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for inc in incidents:
        sev = inc.get("severity", "INFO").upper()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def playbook_stats(executions: list[dict]) -> dict:
    """Aggregate stats across multiple playbook executions."""
    total = len(executions)
    if total == 0:
        return {"total_executions": 0}
    success = sum(1 for e in executions if e.get("steps_failed", 0) == 0)
    total_steps = sum(e.get("steps_executed", 0) for e in executions)
    failed_steps = sum(e.get("steps_failed", 0) for e in executions)
    return {
        "total_executions": total,
        "successful_runs":  success,
        "failed_runs":      total - success,
        "success_rate_pct": round(success / total * 100, 1),
        "total_steps_run":  total_steps,
        "failed_steps":     failed_steps,
        "mttr_minutes":     calculate_mttr(executions),
    }


def print_metrics(alerts: list[dict], executions: list[dict]) -> None:
    severity_counts = count_by_severity(alerts)
    stats = playbook_stats(executions)
    print(bold("\n  SOAR-Lite Metrics Report"))
    print("  " + "─" * 40)
    headers = ["Severity", "Count"]
    rows = [[SEVERITY_COLORS.get(k, lambda t: t)(k), v] for k, v in severity_counts.items() if v > 0]
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        for row in rows:
            print(f"  {row[0]:<12} {row[1]}")
    print()
    for k, v in stats.items():
        print(f"  {k:<25} {v}")
    print()


# ─── Simple HTTP Alert Receiver ───────────────────────────────────────────────

_received_alerts: list[dict] = []


class AlertHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info("HTTP %s", fmt % args)

    def do_POST(self):
        if self.path != "/alerts":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            raw = json.loads(body)
            alert = normalize_alert(raw)
            valid, errors = validate_alert(alert)
            if not valid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"errors": errors}).encode())
                return
            _received_alerts.append(alert)
            log.info("Received alert %s via HTTP | severity=%s", alert["id"], alert["severity"])
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "accepted", "id": alert["id"]}).encode())
        except json.JSONDecodeError as exc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def do_GET(self):
        if self.path == "/alerts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(_received_alerts, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    server = HTTPServer((host, port), AlertHandler)
    log.info("SOAR-Lite HTTP server listening on %s:%d", host, port)
    log.info("POST JSON alerts to http://%s:%d/alerts", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Server stopped.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SOAR-Lite: Security Orchestration, Automation & Response Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  ingest        Load, normalize and validate alerts from --input JSON file
  correlate     Run correlation analysis on loaded alerts
  run-playbook  Execute a playbook against alerts from --input (requires --playbook)
  metrics       Display metrics for a list of execution results (--input)
  server        Start HTTP server to receive POST /alerts (requires no --input)

Examples:
  python soar_engine.py --mode ingest --input sample_alerts.json
  python soar_engine.py --mode correlate --input sample_alerts.json
  python soar_engine.py --mode run-playbook --input sample_alerts.json --playbook playbooks/ransomware_response.json
  python soar_engine.py --mode run-playbook --input sample_alerts.json --playbook playbooks/brute_force_response.json --execute
  python soar_engine.py --mode metrics --input executions.json
  python soar_engine.py --mode server
        """,
    )
    parser.add_argument("--mode", required=True,
                        choices=["ingest", "correlate", "run-playbook", "metrics", "server"],
                        help="Operational mode")
    parser.add_argument("--input",    help="Input JSON file (alerts or execution results)")
    parser.add_argument("--playbook", help="Path to playbook JSON file (run-playbook mode)")
    parser.add_argument("--output",   help="Output JSON file for results", default="soar_output.json")
    parser.add_argument("--dry-run",  action="store_true", default=True,
                        help="Simulate actions without executing (default)")
    parser.add_argument("--execute",  action="store_true", default=False,
                        help="Actually execute actions (overrides --dry-run)")
    parser.add_argument("--port",     type=int, default=8080, help="HTTP server port (server mode)")
    parser.add_argument("--verbose",  action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    dry_run = not args.execute

    if args.mode == "server":
        run_server(port=args.port)
        return

    if args.mode == "ingest":
        if not args.input:
            parser.error("--input is required for 'ingest' mode")
        raw_alerts = load_alerts_from_file(args.input)
        normalized = [normalize_alert(a) for a in raw_alerts]
        results = []
        for alert in normalized:
            valid, errors = validate_alert(alert)
            sev_color = SEVERITY_COLORS.get(alert["severity"], lambda t: t)
            status_str = green("VALID") if valid else red(f"INVALID: {errors}")
            print(f"  {alert['id']:<15} {sev_color(alert['severity']):<12} {alert['type']:<28} {status_str}")
            results.append({"alert": alert, "valid": valid, "errors": errors})
        output = Path(args.output)
        output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        log.info("Ingestion complete. %d alerts processed. Output: %s", len(results), args.output)

    elif args.mode == "correlate":
        if not args.input:
            parser.error("--input is required for 'correlate' mode")
        raw_alerts = load_alerts_from_file(args.input)
        alerts = [normalize_alert(a) for a in raw_alerts]
        alerts = deduplicate_alerts(alerts)

        ip_correlations   = correlate_by_source_ip(alerts)
        asset_correlations = correlate_by_asset(alerts)
        all_correlations   = {**ip_correlations, **asset_correlations}
        patterns = detect_attack_pattern(all_correlations)

        print(bold("\n  IP-Based Correlations:"))
        for ip, group in ip_correlations.items():
            print(f"  {cyan(ip)}: {len(group)} alerts — {', '.join(a['id'] for a in group)}")

        print(bold("\n  Asset-Based Correlations:"))
        for asset, group in asset_correlations.items():
            print(f"  {magenta(asset)}: {len(group)} alerts")

        print(bold("\n  Detected Attack Patterns:"))
        if not patterns:
            print("  None detected.")
        for p in patterns:
            print(f"  {red(p['pattern'])}: {p['description']}")
            print(f"    Group: {p['group']} | Matching: {p['matching_alerts']} | Confidence: {p['confidence']}%")

        output_data = {
            "ip_correlations":    {ip: [a["id"] for a in g] for ip, g in ip_correlations.items()},
            "asset_correlations": {asset: [a["id"] for a in g] for asset, g in asset_correlations.items()},
            "attack_patterns":    patterns,
        }
        Path(args.output).write_text(json.dumps(output_data, indent=2), encoding="utf-8")
        log.info("Correlation complete. Output: %s", args.output)

    elif args.mode == "run-playbook":
        if not args.input:
            parser.error("--input is required for 'run-playbook' mode")
        if not args.playbook:
            parser.error("--playbook is required for 'run-playbook' mode")

        raw_alerts = load_alerts_from_file(args.input)
        alerts = [normalize_alert(a) for a in raw_alerts]
        playbook = load_playbook(args.playbook)
        executions = []

        for alert in alerts:
            triggered, reason = evaluate_trigger(playbook, alert)
            if triggered:
                log.info("Playbook triggered for %s: %s", alert["id"], reason)
                execution = execute_playbook(playbook, alert, dry_run=dry_run)
                executions.append(execution)
            else:
                log.debug("Playbook NOT triggered for %s: %s", alert["id"], reason)

        if not executions:
            print(yellow("No alerts matched the playbook trigger conditions."))
        else:
            print_metrics(alerts, executions)

        Path(args.output).write_text(json.dumps(executions, indent=2, default=str), encoding="utf-8")
        log.info("%d playbook execution(s) complete. Output: %s", len(executions), args.output)

    elif args.mode == "metrics":
        if not args.input:
            parser.error("--input is required for 'metrics' mode")
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        print_metrics(data, data)


if __name__ == "__main__":
    main()
