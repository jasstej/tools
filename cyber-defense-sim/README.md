# Enterprise Cyber Defense Simulation

**Purple Team Attack Simulation & Defense Effectiveness Platform**

This tool simulates adversary kill chain campaigns against configurable enterprise security control sets. It is designed for purple team exercises, security control validation, risk quantification, and SOC analyst training.

---

## Table of Contents

1. [Purple Team Concepts](#purple-team-concepts)
2. [Kill Chain Model](#kill-chain-model)
3. [Simulation Methodology](#simulation-methodology)
4. [Risk Scoring Explanation](#risk-scoring-explanation)
5. [Security Controls](#security-controls)
6. [Scenario Configuration](#scenario-configuration)
7. [Usage](#usage)
8. [Output Format](#output-format)
9. [Use Cases](#use-cases)
10. [File Structure](#file-structure)

---

## Purple Team Concepts

**Purple teaming** is the collaborative practice of combining offensive (red team) adversary simulation with defensive (blue team) detection and response capability validation. Unlike traditional red team engagements, purple team exercises are conducted transparently with defenders aware of and participating in attack simulations.

### Red Team vs. Blue Team vs. Purple Team

| Approach | Goal | Transparency | Output |
|---|---|---|---|
| Red Team | Test defenses by simulating real attackers | Low — defenders unaware | Findings report |
| Blue Team | Detect and respond to actual/simulated attacks | High | Incident reports |
| Purple Team | Collaboratively test and improve detection coverage | Full | Control improvement roadmap |

### Key Questions Purple Team Answers

- Which kill chain phases have adequate detection coverage?
- What is the probability of an APT reaching its objectives given current controls?
- Where should security investment be prioritized?
- How does control maturity affect overall risk?
- What is the residual risk after all controls are applied?

---

## Kill Chain Model

This simulation uses a 7-phase kill chain model based on Lockheed Martin's Cyber Kill Chain and MITRE ATT&CK framework:

| Phase | Index | Description | Key Detection Opportunity |
|---|---|---|---|
| Reconnaissance | 0 | Attacker gathers OSINT on the target | Honeypots, threat intel feeds |
| Weaponization | 1 | Building malware and attack infrastructure | Threat intel on new C2 domains |
| Delivery | 2 | Transmitting malicious content to target | Email gateway, WAF |
| Exploitation | 3 | Triggering code execution on target system | EDR behavioral detection |
| Installation | 4 | Establishing persistence mechanisms | Registry/task monitoring |
| Command & Control | 5 | Malware beaconing to attacker infrastructure | DNS filtering, firewall |
| Actions on Objectives | 6 | Data theft, ransomware, lateral movement | DLP, SIEM correlation |

### MITRE ATT&CK Mapping

Each technique in simulation scenarios maps to MITRE ATT&CK technique IDs (e.g., `T1566.001`). This enables direct comparison with ATT&CK Navigator layers and threat intelligence reports.

---

## Simulation Methodology

### Detection Calculation

For each technique executed in a kill chain phase, the detection engine:

1. Retrieves the **base effectiveness** of each enabled control for that phase (0.0–1.0)
2. Applies a **maturity multiplier**: `0.5 + (maturity/5) × 0.7` (range: 0.5 at maturity 1, 1.2 at maturity 5)
3. Adds Gaussian noise (σ=0.05) to simulate real-world detection variability
4. Determines detection using probabilistic draw: `random() < final_confidence`

### Phase Detection Rate (Ensemble)

The overall detection probability for a phase uses an ensemble model:

```
P(detected) = 1 - ∏(1 - P_i)  for all enabled controls i
```

This means multiple imperfect controls combine to increase overall detection probability.

### Attack Success Model

A phase succeeds (attacker advances) if:
- The phase was NOT detected, **OR**
- The attacker's evasion check succeeds (APT-level: 35% evasion probability even when detected)

The simulation stops advancing the kill chain if a phase fails (attacker is fully stopped).

---

## Risk Scoring Explanation

### Three-Factor Risk Model

**Likelihood** = Probability of attack success based on control coverage
Calculated as `1 - (average_detection_rate × 0.85)`, bounded between 0.05 and 0.95.

**Impact** = Potential damage based on asset criticality
Calculated as `(max_criticality × 0.6 + avg_criticality × 0.4) / 10`.

**Risk Score** = `Likelihood × Impact × 100` (expressed as 0–100)

**Residual Risk** = Post-simulation risk based on actual phases that succeeded, accounting for control effectiveness observed during the run.

### Risk Interpretation

| Score | Rating | Action |
|---|---|---|
| 0–20 | Low | Controls adequate; maintain current posture |
| 21–40 | Moderate | Monitor; address identified gaps |
| 41–60 | High | Priority investment needed in weak phases |
| 61–80 | Critical | Immediate remediation required |
| 81–100 | Severe | Major security program overhaul needed |

---

## Security Controls

The simulation models 10 enterprise security controls, each with effectiveness values per kill chain phase:

| Control | Type | Strongest Phase | Primary Detection |
|---|---|---|---|
| Firewall | Network | C2 (50%), Actions (40%) | C2 beaconing, blocked exploits |
| EDR | Endpoint | Install (90%), Actions (85%) | Malicious processes, LSASS access |
| SIEM | Monitoring | Actions (70%), C2 (65%) | Correlation rules, UBA |
| MFA | Identity | Actions (35%), C2 (30%) | MFA bypass attempts |
| PAM | Identity | Actions (55%), C2 (40%) | Privileged access anomalies |
| WAF | Network | Delivery (60%), Exploit (55%) | SQLi, XSS, web shells |
| IDS/IPS | Network | C2 (60%), Exploit (55%) | Signature-based detection |
| Email Gateway | Email | Delivery (80%) | Malicious attachments, phishing |
| DLP | Data | Actions (75%), Install (30%) | Bulk data transfers |
| DNS Filter | Network | C2 (70%), Recon (20%) | C2 domains, DGA |

### Control Maturity Scale (1–5)

| Level | Description | Detection Multiplier |
|---|---|---|
| 1 | Initial/Ad-hoc | 0.64× |
| 2 | Developing | 0.78× |
| 3 | Defined | 0.92× |
| 4 | Managed | 1.06× |
| 5 | Optimizing | 1.20× |

---

## Scenario Configuration

Scenarios are defined as JSON files. See `scenarios/enterprise_scenario.json` for a complete example.

### Schema

```json
{
  "name": "string — scenario name",
  "description": "string",
  "target_environment": {
    "org_size": "small|medium|large|enterprise",
    "industry": "string",
    "assets": [
      {
        "name": "string — asset hostname",
        "type": "string — asset type",
        "criticality": "integer 1-10",
        "ip": "string — IP address"
      }
    ]
  },
  "attack_vector": "string — initial access method",
  "attacker_profile": {
    "type": "APT|Ransomware|Insider|Script Kiddie",
    "skill": "low|medium|high|nation-state",
    "motivation": "string"
  },
  "security_controls": [
    {
      "name": "string — must match CONTROLS dict key",
      "maturity": "integer 1-5",
      "enabled": "boolean"
    }
  ],
  "attack_phases": [
    {
      "phase": "string — must match KILL_CHAIN phase name",
      "techniques": [
        { "id": "string — MITRE ATT&CK ID", "name": "string", "description": "string" }
      ],
      "success_probability": "float 0.0-1.0"
    }
  ]
}
```

---

## Usage

### Basic Simulation

```bash
# Single run with console output + JSON export
python defense_sim.py --scenario scenarios/enterprise_scenario.json

# 10-iteration Monte Carlo for statistical results
python defense_sim.py --scenario scenarios/enterprise_scenario.json --iterations 10

# JSON-only output
python defense_sim.py --scenario scenarios/enterprise_scenario.json --format json --output report.json

# Text-only output (no file export)
python defense_sim.py --scenario scenarios/enterprise_scenario.json --format text
```

### Custom Controls

Override scenario controls with a separate controls JSON file:

```json
[
  { "name": "EDR",  "maturity": 5, "enabled": true },
  { "name": "SIEM", "maturity": 4, "enabled": true },
  { "name": "MFA",  "maturity": 3, "enabled": true }
]
```

```bash
python defense_sim.py --scenario scenarios/enterprise_scenario.json \
  --controls custom_controls.json --iterations 5
```

---

## Output Format

### Console Output

1. **Kill Chain Simulation**: Phase-by-phase results showing DETECTED/BYPASSED per technique
2. **Executive Summary**: Risk scores, outcome verdict, top 3 recommendations
3. **Technical Report**: Detailed per-phase table, control assessment, coverage gaps

### JSON Report Structure

```json
{
  "report_type": "cyber_defense_simulation",
  "generated_at": "ISO8601 timestamp",
  "simulation_results": {
    "scenario": "string",
    "attack_stopped": "boolean",
    "stopped_at_phase": "string|null",
    "detected_phases": "integer",
    "total_impact": "float",
    "phase_results": [...]
  },
  "risk_scoring": {
    "likelihood": "float 0.0-1.0",
    "impact": "float 0.0-1.0",
    "risk_score": "float 0-100",
    "residual_risk": "float 0-100"
  },
  "control_assessment": [...],
  "coverage_gaps": [...],
  "siem_events": [...]
}
```

### SIEM Events (CEF Format)

Each technique execution generates a CEF-format event:

```json
{
  "cef_version": "CEF:0",
  "device_vendor": "DefSimEngine",
  "signature_id": "T1566_001",
  "name": "Spearphishing Attachment",
  "severity": 7,
  "phase": "Delivery",
  "detected": true,
  "timestamp": "2025-11-20T09:14:22Z",
  "src_ip": "198.51.100.42",
  "dst_host": "WORKSTATION-07",
  "outcome": "detected"
}
```

---

## Use Cases

### Security Control Validation (Purple Team)

Run the simulation before and after implementing a new control to quantify the risk reduction:

```bash
# Baseline: current controls
python defense_sim.py --scenario scenarios/enterprise_scenario.json \
  --output baseline.json --format json

# After deploying EDR at maturity 5
python defense_sim.py --scenario scenarios/enterprise_scenario.json \
  --controls edr_improved.json --output improved.json --format json

# Compare risk scores between baseline.json and improved.json
```

### CISO Risk Reporting

Run 50 iterations to generate statistically robust breach probability:

```bash
python defense_sim.py --scenario scenarios/enterprise_scenario.json \
  --iterations 50 --format json --output risk_report.json
```

The `breach_rate` from multi-run output provides a defensible probability metric for board-level risk reporting.

### SOC Analyst Training

Use the SIEM events output to populate training SIEM environments with realistic attack data, teaching analysts to recognize kill chain progression patterns.

### Compliance Gap Analysis

Map coverage gaps to regulatory requirements:
- NIST CSF: Identify, Protect, Detect, Respond, Recover
- ISO 27001 Annex A controls
- PCI-DSS Requirements 10, 11, 12

---

## File Structure

```
cyber-defense-sim/
├── defense_sim.py                    # Main simulation engine (~550 lines)
├── requirements.txt                  # Python dependencies
├── README.md                         # This file
├── index.html                        # Web-based simulation platform UI
└── scenarios/
    └── enterprise_scenario.json      # APT intrusion scenario (financial sector)
```
