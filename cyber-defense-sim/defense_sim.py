#!/usr/bin/env python3
"""
Enterprise Cyber Defense Simulation Engine
Simulates adversary kill chain progression against configurable security controls.
Produces risk scores, SIEM events, detection analysis, and executive/technical reports.
"""

import argparse
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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

# ─── Kill Chain Model ─────────────────────────────────────────────────────────

KILL_CHAIN = [
    {
        "phase": "Reconnaissance",
        "index": 0,
        "description": "Attacker gathers intelligence on the target — employees, technologies, exposed services.",
        "typical_ttps": ["T1589 - Gather Victim Identity Info", "T1596 - Search Open Technical Databases", "T1593 - Search Open Websites/Domains"],
        "detection_opportunities": ["Honeypot canary tokens triggered", "Shodan/Censys scans in firewall logs", "LinkedIn scraping from suspicious IPs"],
    },
    {
        "phase": "Weaponization",
        "index": 1,
        "description": "Attacker builds or stages malware, exploits, and tooling for the campaign.",
        "typical_ttps": ["T1587.001 - Develop Malware", "T1608.001 - Upload Malware", "T1566.001 - Spearphishing Attachment"],
        "detection_opportunities": ["Threat intel IOC matching on staged infrastructure", "Domain reputation scoring on newly registered C2 domains"],
    },
    {
        "phase": "Delivery",
        "index": 2,
        "description": "Malicious content is transmitted to the target — phishing, drive-by download, supply chain.",
        "typical_ttps": ["T1566 - Phishing", "T1195 - Supply Chain Compromise", "T1190 - Exploit Public-Facing Application"],
        "detection_opportunities": ["Email gateway sandboxing", "URL rewriting and click-time analysis", "WAF alerts on exploit attempts"],
    },
    {
        "phase": "Exploitation",
        "index": 3,
        "description": "Vulnerability or user action triggers malicious code execution on the target system.",
        "typical_ttps": ["T1059.001 - PowerShell", "T1203 - Client Execution Exploit", "T1189 - Drive-by Compromise"],
        "detection_opportunities": ["EDR behavioral analysis", "Script block logging", "Memory-based detections for shellcode"],
    },
    {
        "phase": "Installation",
        "index": 4,
        "description": "Attacker establishes persistence mechanisms to survive reboots and maintain access.",
        "typical_ttps": ["T1547.001 - Registry Run Keys", "T1053.005 - Scheduled Task", "T1543.003 - Windows Service"],
        "detection_opportunities": ["Registry modification alerts", "Scheduled task creation logging", "EDR persistence detection modules"],
    },
    {
        "phase": "Command & Control",
        "index": 5,
        "description": "Malware beacons to attacker infrastructure to receive commands and exfiltrate data.",
        "typical_ttps": ["T1071.001 - HTTPS C2", "T1573 - Encrypted Channel", "T1090 - Proxy"],
        "detection_opportunities": ["Anomalous outbound HTTPS to new domains", "DNS query anomalies", "JA3/JARM TLS fingerprinting"],
    },
    {
        "phase": "Actions on Objectives",
        "index": 6,
        "description": "Attacker achieves goals: data theft, ransomware, sabotage, persistence expansion.",
        "typical_ttps": ["T1003.001 - LSASS Dump", "T1021 - Lateral Movement", "T1041 - Exfiltration over C2", "T1486 - Ransomware"],
        "detection_opportunities": ["LSASS access alerts", "Abnormal SMB traffic patterns", "Large outbound data transfers", "DLP triggers"],
    },
]

# ─── Security Controls ────────────────────────────────────────────────────────

# Effectiveness per control per kill chain phase (0.0 = no detection, 1.0 = perfect detection)
# Phases: Recon, Weapon, Delivery, Exploit, Install, C2, Actions
CONTROLS: dict[str, dict] = {
    "Firewall": {
        "type": "network",
        "phase_effectiveness": [0.35, 0.10, 0.30, 0.20, 0.15, 0.50, 0.40],
        "description": "Network perimeter control blocking unauthorized traffic",
        "typical_detections": ["Outbound C2 beaconing", "Port scans", "Blocked inbound exploits"],
    },
    "EDR": {
        "type": "endpoint",
        "phase_effectiveness": [0.05, 0.10, 0.40, 0.85, 0.90, 0.80, 0.85],
        "description": "Endpoint Detection & Response — behavioral and signature-based endpoint protection",
        "typical_detections": ["Malicious process execution", "LSASS access", "Persistence mechanisms", "Shellcode injection"],
    },
    "SIEM": {
        "type": "monitoring",
        "phase_effectiveness": [0.20, 0.10, 0.35, 0.50, 0.55, 0.65, 0.70],
        "description": "Security Information and Event Management — log aggregation and correlation",
        "typical_detections": ["Failed login correlations", "Lateral movement patterns", "Anomalous privilege use"],
    },
    "MFA": {
        "type": "identity",
        "phase_effectiveness": [0.05, 0.05, 0.10, 0.30, 0.20, 0.30, 0.35],
        "description": "Multi-Factor Authentication reducing credential-based access",
        "typical_detections": ["MFA bypass attempts", "Impossible travel alerts"],
    },
    "PAM": {
        "type": "identity",
        "phase_effectiveness": [0.05, 0.05, 0.10, 0.25, 0.35, 0.40, 0.55],
        "description": "Privileged Access Management controlling admin credential access",
        "typical_detections": ["Unauthorized privileged access", "Credential vault access anomalies"],
    },
    "WAF": {
        "type": "network",
        "phase_effectiveness": [0.15, 0.10, 0.60, 0.55, 0.20, 0.25, 0.30],
        "description": "Web Application Firewall blocking web-based exploitation",
        "typical_detections": ["SQL injection", "XSS attempts", "Web shell uploads", "CVE exploitation"],
    },
    "IDS/IPS": {
        "type": "network",
        "phase_effectiveness": [0.30, 0.10, 0.45, 0.55, 0.35, 0.60, 0.55],
        "description": "Intrusion Detection/Prevention System with signature and anomaly detection",
        "typical_detections": ["Known exploit signatures", "Port scanning", "C2 traffic patterns"],
    },
    "Email Gateway": {
        "type": "email",
        "phase_effectiveness": [0.05, 0.15, 0.80, 0.20, 0.10, 0.05, 0.05],
        "description": "Email security gateway with sandboxing, URL rewriting, and malware analysis",
        "typical_detections": ["Malicious attachments", "Phishing URLs", "BEC patterns"],
    },
    "DLP": {
        "type": "data",
        "phase_effectiveness": [0.10, 0.05, 0.15, 0.20, 0.30, 0.30, 0.75],
        "description": "Data Loss Prevention monitoring and blocking sensitive data exfiltration",
        "typical_detections": ["Bulk data transfers", "Sensitive file access", "USB/cloud uploads"],
    },
    "DNS Filter": {
        "type": "network",
        "phase_effectiveness": [0.20, 0.10, 0.35, 0.25, 0.20, 0.70, 0.45],
        "description": "DNS-layer security blocking malicious domains and C2 communications",
        "typical_detections": ["C2 domain lookups", "DGA domain patterns", "Newly registered domains"],
    },
}

# ─── Color helpers ────────────────────────────────────────────────────────────

def _c(t, code): return f"{code}{t}{Style.RESET_ALL}" if COLOR else t
def red(t):     return _c(t, Fore.RED)
def yellow(t):  return _c(t, Fore.YELLOW)
def green(t):   return _c(t, Fore.GREEN)
def cyan(t):    return _c(t, Fore.CYAN)
def magenta(t): return _c(t, Fore.MAGENTA)
def bold(t):    return _c(t, Style.BRIGHT)
def dim(t):     return _c(t, Style.DIM)

# ─── Detection Engine ─────────────────────────────────────────────────────────

def detect_technique(technique: dict, active_controls: dict, control_maturity: dict) -> tuple[bool, float]:
    """
    Determine whether a technique is detected by active controls.
    Returns (detected: bool, confidence: float 0.0-1.0).
    """
    phase_index = technique.get("_phase_index", 0)
    max_confidence = 0.0

    for ctrl_name, ctrl_data in active_controls.items():
        if not ctrl_data.get("enabled", True):
            continue
        base_eff = CONTROLS[ctrl_name]["phase_effectiveness"][phase_index]
        maturity = control_maturity.get(ctrl_name, 3)  # 1-5 scale
        maturity_multiplier = 0.5 + (maturity / 5) * 0.7  # range: 0.5 (maturity=1) to 1.2 (maturity=5)
        adjusted = min(1.0, base_eff * maturity_multiplier)
        max_confidence = max(max_confidence, adjusted)

    # Add some randomness to simulate real-world noise
    noise = random.gauss(0, 0.05)
    final_confidence = max(0.0, min(1.0, max_confidence + noise))
    detected = random.random() < final_confidence

    return detected, round(final_confidence, 3)


def calc_detection_rate(phase_index: int, active_controls: dict, control_maturity: dict) -> float:
    """Calculate overall detection probability for a kill chain phase."""
    confidences = []
    for ctrl_name, ctrl_data in active_controls.items():
        if not ctrl_data.get("enabled", True):
            continue
        base_eff = CONTROLS[ctrl_name]["phase_effectiveness"][phase_index]
        maturity = control_maturity.get(ctrl_name, 3)
        mat_mult = 0.5 + (maturity / 5) * 0.7
        confidences.append(min(1.0, base_eff * mat_mult))

    if not confidences:
        return 0.0
    # Ensemble detection: P(detected) = 1 - prod(1 - P_i)
    combined = 1.0 - math.prod(1.0 - c for c in confidences)
    return round(combined, 3)


# ─── Attack Simulation ────────────────────────────────────────────────────────

def simulate_phase(phase: dict, active_controls: dict, control_maturity: dict,
                   target: dict) -> dict:
    """
    Simulate a single kill chain phase. Returns detection results and events.
    """
    phase_index = phase["index"]
    detection_rate = calc_detection_rate(phase_index, active_controls, control_maturity)

    events = []
    detected_techniques = []
    missed_techniques = []

    for tech in phase.get("techniques", []):
        tech_copy = dict(tech)
        tech_copy["_phase_index"] = phase_index
        detected, confidence = detect_technique(tech_copy, active_controls, control_maturity)
        siem_event = generate_siem_event(tech, phase["phase"], detected, target)
        events.append(siem_event)
        if detected:
            detected_techniques.append(tech["id"])
        else:
            missed_techniques.append(tech["id"])

    # Phase succeeds if attacker is NOT detected (or if detected but can evade)
    phase_detected = len(detected_techniques) > 0
    # Attacker evasion probability based on skill
    evasion_prob = 0.35  # APT-level evasion
    phase_succeeded = not phase_detected or (random.random() < evasion_prob)

    # Impact calculation: severity based on phase position and asset criticality
    max_criticality = max((a.get("criticality", 5) for a in target.get("assets", [])), default=5)
    impact = round((phase_index + 1) / 7 * max_criticality / 10 * (1 if phase_succeeded else 0.3), 3)

    return {
        "phase":               phase["phase"],
        "phase_index":         phase_index,
        "detection_rate":      detection_rate,
        "phase_detected":      phase_detected,
        "phase_succeeded":     phase_succeeded,
        "detected_techniques": detected_techniques,
        "missed_techniques":   missed_techniques,
        "impact":              impact,
        "siem_events":         events,
    }


def simulate_full_attack(scenario: dict, active_controls: dict, control_maturity: dict) -> dict:
    """
    Run the full kill chain simulation for a scenario.
    Returns complete simulation results with per-phase and aggregate data.
    """
    target = scenario.get("target_environment", {})
    attacker = scenario.get("attacker_profile", {})
    phase_results = []
    attack_stopped = False
    stopped_at = None

    print(bold(f"\n{'='*64}"))
    print(bold(f"  CYBER DEFENSE SIMULATION: {scenario.get('name', 'Unknown')}"))
    print(bold(f"  Attacker: {attacker.get('group', 'APT')} | Skill: {attacker.get('skill', 'high')}"))
    print(bold(f"{'='*64}\n"))

    for kc_phase in KILL_CHAIN:
        phase_name = kc_phase["phase"]
        # Find matching scenario phase (if any) for success probability modifier
        scenario_phase = next((p for p in scenario.get("attack_phases", [])
                               if p["phase"] == phase_name), None)
        success_prob = scenario_phase.get("success_probability", 0.75) if scenario_phase else 0.75

        result = simulate_phase(kc_phase, active_controls, control_maturity, target)

        detect_label = green("DETECTED") if result["phase_detected"] else red("BYPASSED")
        succeed_label = red("SUCCEEDED") if result["phase_succeeded"] else green("STOPPED")
        print(f"  [{kc_phase['index']+1}/7] {bold(phase_name):<28} {detect_label:<20} {succeed_label}")

        if result["phase_detected"] and result["detected_techniques"]:
            for tid in result["detected_techniques"]:
                print(f"        {cyan('✓')} {tid}")
        if result["missed_techniques"]:
            for tid in result["missed_techniques"]:
                print(f"        {red('✗')} {tid}")
        print()

        phase_results.append(result)

        if not result["phase_succeeded"]:
            attack_stopped = True
            stopped_at = phase_name
            break

    print(bold(f"{'='*64}"))
    if attack_stopped:
        print(green(f"  RESULT: ATTACK STOPPED at '{stopped_at}'"))
    else:
        print(red("  RESULT: ATTACKER REACHED OBJECTIVES — Breach confirmed"))
    print(bold(f"{'='*64}\n"))

    total_impact = sum(r["impact"] for r in phase_results)
    detected_phases = sum(1 for r in phase_results if r["phase_detected"])
    succeeded_phases = sum(1 for r in phase_results if r["phase_succeeded"])

    return {
        "scenario":         scenario.get("name"),
        "attacker":         attacker.get("group", "Unknown"),
        "simulated_at":     datetime.now(timezone.utc).isoformat(),
        "attack_stopped":   attack_stopped,
        "stopped_at_phase": stopped_at,
        "total_phases_run": len(phase_results),
        "detected_phases":  detected_phases,
        "succeeded_phases": succeeded_phases,
        "total_impact":     round(total_impact, 3),
        "phase_results":    phase_results,
    }


# ─── SIEM Event Generator ─────────────────────────────────────────────────────

CEF_SEVERITY = {"CRITICAL": 10, "HIGH": 7, "MEDIUM": 5, "LOW": 3, "INFO": 1}

def generate_siem_event(technique: dict, phase: str, detected: bool,
                        target: dict) -> dict:
    """Generate a CEF-format SIEM event for a technique execution."""
    assets = target.get("assets", [{"name": "UNKNOWN", "ip": "10.0.0.1"}])
    asset = random.choice(assets)
    severity = "CRITICAL" if detected and phase in ("Actions on Objectives", "Exploitation") else \
               "HIGH"     if detected else "LOW"

    return {
        "cef_version":    "CEF:0",
        "device_vendor":  "DefSimEngine",
        "device_product": "ThreatSim",
        "device_version": "1.0",
        "signature_id":   technique["id"].replace(".", "_"),
        "name":           technique["name"],
        "severity":       CEF_SEVERITY.get(severity, 5),
        "severity_label": severity,
        "phase":          phase,
        "detected":       detected,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "src_ip":         "198.51.100." + str(random.randint(1,254)),
        "dst_ip":         asset.get("ip", "10.0.0.1"),
        "dst_host":       asset.get("name", "UNKNOWN"),
        "message":        technique.get("description", "Technique execution observed"),
        "outcome":        "detected" if detected else "evaded",
    }


# ─── Risk Scoring ─────────────────────────────────────────────────────────────

def calc_likelihood(active_controls: dict, control_maturity: dict) -> float:
    """
    Calculate attack success likelihood (0.0-1.0) based on controls.
    Higher detection coverage = lower likelihood.
    """
    phase_rates = [calc_detection_rate(i, active_controls, control_maturity) for i in range(7)]
    avg_detection = sum(phase_rates) / len(phase_rates)
    # Invert: high detection = low likelihood
    likelihood = max(0.05, min(0.95, 1.0 - avg_detection * 0.85))
    return round(likelihood, 3)


def calc_impact(target_assets: list[dict]) -> float:
    """
    Calculate potential impact score (0.0-1.0) based on asset criticality.
    """
    if not target_assets:
        return 0.5
    max_crit = max(a.get("criticality", 5) for a in target_assets)
    avg_crit = sum(a.get("criticality", 5) for a in target_assets) / len(target_assets)
    impact = (max_crit * 0.6 + avg_crit * 0.4) / 10
    return round(impact, 3)


def calc_risk(likelihood: float, impact: float) -> float:
    """Risk = Likelihood × Impact, expressed as 0-100 score."""
    return round(likelihood * impact * 100, 1)


def calc_residual_risk(sim_results: dict) -> float:
    """Calculate residual risk after controls are applied based on simulation results."""
    phase_results = sim_results.get("phase_results", [])
    if not phase_results:
        return 50.0
    succeeded = sum(1 for p in phase_results if p["phase_succeeded"])
    total = len(phase_results)
    base_risk = (succeeded / 7) * 100
    impact_component = sum(p["impact"] for p in phase_results) * 15
    return round(min(100.0, base_risk * 0.6 + impact_component * 0.4), 1)


# ─── Control Assessment ───────────────────────────────────────────────────────

def assess_controls(controls_config: list[dict]) -> list[dict]:
    """Score each security control and produce a maturity assessment."""
    assessments = []
    for ctrl in controls_config:
        name = ctrl.get("name", "Unknown")
        maturity = ctrl.get("maturity", 1)
        enabled = ctrl.get("enabled", True)
        ctrl_data = CONTROLS.get(name, {})
        phase_eff = ctrl_data.get("phase_effectiveness", [0.1]*7)
        avg_eff = sum(phase_eff) / len(phase_eff) if phase_eff else 0
        score = round(avg_eff * (maturity / 5) * 100, 1) if enabled else 0.0
        gap_phases = [KILL_CHAIN[i]["phase"] for i, e in enumerate(phase_eff) if e < 0.3]
        assessments.append({
            "control":       name,
            "enabled":       enabled,
            "maturity":      maturity,
            "avg_effectiveness": round(avg_eff, 3),
            "score":         score,
            "type":          ctrl.get("type", ctrl_data.get("type", "unknown")),
            "gap_phases":    gap_phases,
        })
    return sorted(assessments, key=lambda a: a["score"], reverse=True)


def identify_gaps(assessment: list[dict]) -> list[dict]:
    """Identify coverage gaps in the control landscape."""
    gaps = []
    phase_coverage: dict[int, list[str]] = {i: [] for i in range(7)}

    for ctrl in assessment:
        if not ctrl["enabled"]:
            continue
        ctrl_data = CONTROLS.get(ctrl["control"], {})
        for i, eff in enumerate(ctrl_data.get("phase_effectiveness", [])):
            maturity_adj = eff * (0.5 + ctrl["maturity"] / 5 * 0.7)
            if maturity_adj >= 0.4:
                phase_coverage[i].append(ctrl["control"])

    for i, controllers in phase_coverage.items():
        if len(controllers) < 2:
            gaps.append({
                "phase":     KILL_CHAIN[i]["phase"],
                "phase_idx": i,
                "covered_by": controllers,
                "severity":  "CRITICAL" if i >= 3 else "HIGH",
                "recommendation": f"Increase control coverage for {KILL_CHAIN[i]['phase']} phase — "
                                  f"currently only {len(controllers)} control(s) provide adequate detection.",
            })
    return gaps


# ─── Reporting ────────────────────────────────────────────────────────────────

def executive_summary(sim_results: dict, likelihood: float, impact: float,
                      risk_score: float, gaps: list[dict]) -> None:
    """Print executive summary to console."""
    print(bold("\n  EXECUTIVE SUMMARY"))
    print("  " + "─" * 50)
    print(f"  Scenario:          {sim_results.get('scenario')}")
    print(f"  Attacker Group:    {sim_results.get('attacker')}")
    print(f"  Simulation Date:   {sim_results.get('simulated_at', '')[:10]}")
    print()
    outcome = green("ATTACK CONTAINED") if sim_results.get("attack_stopped") else red("BREACH OCCURRED")
    print(f"  Outcome:           {outcome}")
    print(f"  Attack Stopped At: {sim_results.get('stopped_at_phase', 'N/A')}")
    print(f"  Phases Detected:   {sim_results.get('detected_phases', 0)} / {sim_results.get('total_phases_run', 7)}")
    print()

    risk_color = green if risk_score < 30 else yellow if risk_score < 60 else red
    print(f"  Risk Score:        {risk_color(f'{risk_score}/100')}")
    print(f"  Likelihood:        {round(likelihood*100,1)}%")
    print(f"  Impact:            {round(impact*100,1)}%")
    print()

    if gaps:
        print(bold("  Top Recommendations:"))
        for i, gap in enumerate(gaps[:3], 1):
            print(f"  {i}. [{gap['severity']}] {gap['recommendation']}")
    print()


def technical_report(sim_results: dict, assessment: list[dict],
                     gaps: list[dict]) -> None:
    """Print detailed technical report to console."""
    print(bold("\n  TECHNICAL REPORT — Phase-by-Phase Analysis"))
    print("  " + "─" * 50)
    rows = []
    for r in sim_results.get("phase_results", []):
        detected_str = green("YES") if r["phase_detected"] else red("NO")
        succeeded_str = red("YES") if r["phase_succeeded"] else green("NO")
        rows.append([r["phase"], f"{r['detection_rate']*100:.0f}%", detected_str, succeeded_str,
                     ", ".join(r["detected_techniques"][:2]) or "—"])
    if HAS_TABULATE:
        print(tabulate(rows, headers=["Phase","Det. Rate","Detected","Succeeded","Key Detections"],
                       tablefmt="simple"))
    else:
        for row in rows:
            print(f"  {row[0]:<28} {row[1]:<12} {row[2]:<12} {row[3]:<12} {row[4]}")

    print(bold("\n  Control Assessment:"))
    ctrl_rows = [[a["control"], str(a["maturity"])+"/5",
                  f"{a['avg_effectiveness']*100:.0f}%", f"{a['score']:.1f}",
                  "YES" if a["enabled"] else "NO"] for a in assessment]
    if HAS_TABULATE:
        print(tabulate(ctrl_rows, headers=["Control","Maturity","Avg Eff.","Score","Enabled"],
                       tablefmt="simple"))
    else:
        for row in ctrl_rows:
            print(f"  {row[0]:<18} {row[1]:<10} {row[2]:<12} {row[3]:<8} {row[4]}")

    print(bold("\n  Coverage Gaps:"))
    if not gaps:
        print(green("  No critical gaps identified."))
    for gap in gaps:
        print(f"  {red(gap['severity']):<15} {gap['phase']:<28} Covered by: {', '.join(gap['covered_by']) or 'NONE'}")
    print()


def export_json(sim_results: dict, assessment: list[dict], gaps: list[dict],
                likelihood: float, impact: float, risk_score: float,
                output_file: str) -> None:
    """Export full simulation report to JSON."""
    report = {
        "report_type":        "cyber_defense_simulation",
        "generated_at":       datetime.now(timezone.utc).isoformat(),
        "simulation_results": sim_results,
        "risk_scoring": {
            "likelihood":     likelihood,
            "impact":         impact,
            "risk_score":     risk_score,
            "residual_risk":  calc_residual_risk(sim_results),
        },
        "control_assessment": assessment,
        "coverage_gaps":      gaps,
        "siem_events": [
            evt
            for phase in sim_results.get("phase_results", [])
            for evt in phase.get("siem_events", [])
        ],
    }
    Path(output_file).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(green(f"  Report exported to: {output_file}"))


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enterprise Cyber Defense Simulation Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python defense_sim.py --scenario scenarios/enterprise_scenario.json
  python defense_sim.py --scenario scenarios/enterprise_scenario.json --iterations 5
  python defense_sim.py --scenario scenarios/enterprise_scenario.json --output report.json --format json
        """,
    )
    parser.add_argument("--scenario",   required=True, help="Path to scenario JSON file")
    parser.add_argument("--controls",   help="Optional custom controls JSON (overrides scenario controls)")
    parser.add_argument("--iterations", type=int, default=1, help="Number of simulation runs (default: 1)")
    parser.add_argument("--output",     default="sim_report.json", help="Output file (default: sim_report.json)")
    parser.add_argument("--format",     choices=["json","text","both"], default="both",
                        help="Output format (default: both)")
    parser.add_argument("--verbose",    action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    # Load scenario
    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        print(red(f"Scenario file not found: {args.scenario}"))
        sys.exit(1)
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    print(green(f"Loaded scenario: {scenario.get('name')}"))

    # Load controls
    if args.controls:
        controls_path = Path(args.controls)
        if not controls_path.exists():
            print(red(f"Controls file not found: {args.controls}"))
            sys.exit(1)
        controls_config = json.loads(controls_path.read_text(encoding="utf-8"))
    else:
        controls_config = scenario.get("security_controls", [])

    # Build active controls dict and maturity map
    active_controls = {
        ctrl["name"]: {"enabled": ctrl.get("enabled", True)}
        for ctrl in controls_config
        if ctrl["name"] in CONTROLS
    }
    control_maturity = {
        ctrl["name"]: ctrl.get("maturity", 3)
        for ctrl in controls_config
        if ctrl["name"] in CONTROLS
    }

    target = scenario.get("target_environment", {})
    assets = target.get("assets", [])

    # Run simulation(s)
    all_results = []
    for run in range(args.iterations):
        if args.iterations > 1:
            print(bold(f"\n  --- Run {run+1}/{args.iterations} ---"))
        result = simulate_full_attack(scenario, active_controls, control_maturity)
        all_results.append(result)

    # Use last run for reporting (aggregate in future versions)
    sim_results = all_results[-1]

    # Risk scoring
    likelihood  = calc_likelihood(active_controls, control_maturity)
    impact      = calc_impact(assets)
    risk_score  = calc_risk(likelihood, impact)

    # Control assessment
    assessment = assess_controls(controls_config)
    gaps = identify_gaps(assessment)

    if args.format in ("text", "both"):
        executive_summary(sim_results, likelihood, impact, risk_score, gaps)
        technical_report(sim_results, assessment, gaps)

    if args.format in ("json", "both"):
        export_json(sim_results, assessment, gaps, likelihood, impact, risk_score, args.output)

    if args.iterations > 1:
        breach_count = sum(1 for r in all_results if not r["attack_stopped"])
        print(bold(f"\n  Multi-Run Summary ({args.iterations} iterations):"))
        print(f"  Breach Rate:   {red(str(round(breach_count/args.iterations*100,1))+'%')}")
        print(f"  Containment:   {green(str(round((1-breach_count/args.iterations)*100,1))+'%')}")
        avg_detections = sum(r["detected_phases"] for r in all_results) / args.iterations
        print(f"  Avg Phases Detected: {avg_detections:.1f} / 7")
        print()


if __name__ == "__main__":
    main()
