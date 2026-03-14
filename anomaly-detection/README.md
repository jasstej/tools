# AI-Driven Anomaly Detection System

A machine-learning powered network anomaly detection tool that uses **Isolation Forest** and **statistical Z-score baselines** to identify suspicious activity in network logs.

---

## Table of Contents

1. [Concepts](#concepts)
2. [How Isolation Forest Works](#how-isolation-forest-works)
3. [Feature Engineering](#feature-engineering)
4. [Installation](#installation)
5. [Usage Modes](#usage-modes)
6. [Score Interpretation](#score-interpretation)
7. [Dashboard (index.html)](#dashboard)
8. [SOC Integration Guide](#soc-integration-guide)

---

## Concepts

Anomaly detection in cybersecurity focuses on identifying events that deviate from an established **baseline of normal behaviour**. Rather than relying on signature databases (which miss zero-day attacks), machine learning models learn the statistical fingerprint of normal traffic and flag statistical outliers.

Key approaches used in this tool:

| Method | Description | Best For |
|---|---|---|
| Isolation Forest | Ensemble tree-based unsupervised ML | Multivariate anomalies |
| Z-score Baseline | Statistical deviation from mean | Single-feature spikes |
| Feature Engineering | Transform raw data into signals | Reducing noise |

---

## How Isolation Forest Works

Isolation Forest (Liu et al., 2008) is an unsupervised anomaly detection algorithm built on a simple insight: **anomalies are few and different**, so they are easier to isolate.

### Algorithm Steps

1. **Random sub-sampling**: Draw a random subset of the training data.
2. **Random partitioning**: Recursively partition the feature space by randomly selecting a feature and a random split point within the feature's min-max range.
3. **Path length**: Count how many splits it takes to isolate a single point. Normal points require many splits (they cluster with others). Anomalies require very few splits.
4. **Anomaly score**: Average path length across many trees. Short average path = anomalous.

### Why It Works for Network Security

- Handles **high-dimensional** log data naturally.
- Does **not** require labelled attack examples (unsupervised).
- Robust to **imbalanced classes** (attacks are rare).
- Linear time complexity O(n) - scales to millions of log entries.

### Contamination Parameter

The `contamination` parameter tells the model what fraction of training data to treat as anomalous. For enterprise networks:

- `0.05` - Low noise environments, strict alerting
- `0.10` - Recommended default, balanced sensitivity
- `0.15` - High-traffic environments with expected noise

---

## Feature Engineering

Raw log fields are transformed into numerical features that capture behavioural context:

| Feature | Derivation | Why It Matters |
|---|---|---|
| `bytes_per_second` | bytes / duration | Detects exfiltration bursts |
| `log_bytes` | log10(bytes + 1) | Reduces skew from huge transfers |
| `hour_of_day` | timestamp.hour | Captures after-hours activity |
| `is_business_hours` | 1 if 09:00-17:00 | Binary temporal flag |
| `port_category` | Port bucket (web/db/remote/other) | Protocol context |
| `connection_count_per_hour` | Count per src_ip per hour | Scanning/beaconing detection |

### Port Categories

| Category ID | Ports | Service Type |
|---|---|---|
| 0 | 80, 8080 | Web (HTTP) |
| 1 | 443, 8443 | Web (HTTPS) |
| 2 | 3306, 5432, 1433, 6379 | Databases |
| 3 | 22, 3389, 5900, 23 | Remote Access |
| 4 | 25, 465, 587, 110, 143 | Email |
| 5 | 53, 67, 123 | Infrastructure |
| 7 | High registered ports | Registered / Unknown |
| 8 | > 49151 | Ephemeral / Suspicious |

---

## Installation

```bash
# Clone or navigate to the project directory
cd anomaly-detection

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| pandas | >= 1.3 | Data loading and manipulation |
| scikit-learn | >= 1.0 | Isolation Forest model |
| numpy | >= 1.21 | Numerical operations |
| matplotlib | >= 3.4 | Visualisation charts |
| colorama | >= 0.4 | Coloured terminal output |

---

## Usage Modes

### Demo Mode (no data required)

Generates 200 synthetic log records (10% injected anomalies), trains a model, scores all events, and prints alerts.

```bash
python anomaly_detector.py --mode demo
```

### Train Mode

Train a new model on your historical log data and save baseline statistics.

```bash
python anomaly_detector.py \
  --mode train \
  --input sample_data/network_logs.csv \
  --baseline my_baseline.json \
  --contamination 0.1
```

This produces:
- `my_baseline.json` - Feature statistics (mean, std, min, max)
- `my_baseline_model.pkl` - Serialised Isolation Forest + scaler

### Detect Mode

Score new log data against an existing baseline and report anomalies.

```bash
# Basic detection
python anomaly_detector.py \
  --mode detect \
  --input new_logs.csv \
  --threshold 70

# With output export and plots
python anomaly_detector.py \
  --mode detect \
  --input new_logs.csv \
  --baseline my_baseline.json \
  --threshold 75 \
  --output scored_events.csv \
  --plot
```

### Full CLI Reference

```
usage: anomaly_detector.py [-h] [--mode {train,detect,demo}] [--input INPUT]
                            [--baseline BASELINE] [--threshold THRESHOLD]
                            [--contamination CONTAMINATION] [--output OUTPUT]
                            [--plot]

Options:
  --mode          Operation mode: train, detect, or demo (default: demo)
  --input, -i     Input CSV or JSON log file
  --baseline, -b  Baseline statistics JSON file (default: baseline_stats.json)
  --threshold, -t Anomaly score threshold for alerts, 0-100 (default: 70)
  --contamination Expected anomaly fraction for Isolation Forest (default: 0.1)
  --output, -o    Output path for scored events (.csv or .json)
  --plot          Generate matplotlib visualisation charts
```

### Input File Format

CSV files must contain these columns:

```
timestamp,src_ip,dst_ip,port,bytes,protocol,duration,user
2024-01-15 09:02:14,10.0.1.10,8.8.4.4,443,15234,TCP,0.43,alice
```

JSON files should be a list of event objects with the same fields.

---

## Score Interpretation

Anomaly scores range from 0 to 100, where higher scores indicate greater deviation from baseline behaviour.

| Score Range | Severity | Recommended Action |
|---|---|---|
| 0 - 50 | Normal | No action required |
| 51 - 69 | Low | Log for audit trail |
| 70 - 79 | Medium | Review during business hours |
| 80 - 89 | High | Alert SOC analyst within 1 hour |
| 90 - 100 | Critical | Immediate investigation required |

### Anomaly Explanation Output

Each alert includes contributing factors:

```
[1] Score: 94.3/100  Time: 2024-01-15 03:14:22  User: unknown_user
    10.0.1.99 -> 185.220.101.45:4444  |  5,234,567 bytes  |  18.73s
    Contributing factors:
      - bytes_per_second: 8.4 std dev above mean (value=279,534.00, mean=18,432.00)
      - log_bytes:        6.1 std dev above mean (value=6.72, mean=4.23)
      - hour_of_day:      3.7 std dev below mean (value=3.0, mean=12.8)
```

---

## Dashboard

Open `index.html` in any modern browser for an interactive anomaly detection dashboard featuring:

- **Real-time time-series chart**: Canvas-rendered 24-hour anomaly score timeline
- **Live monitoring**: "Start Monitoring" button streams new data points every 2 seconds
- **Event feed**: Colour-coded scrolling list of scored events
- **Anomaly detail panel**: Drill-down view with contributing feature deviations
- **CSV upload**: Upload your own log file for instant Z-score analysis
- **Alert correlation**: Groups related alerts by source IP and time window

---

## SOC Integration Guide

### SIEM Integration

Export scored events to your SIEM (Splunk, Elastic, QRadar) via the JSON output:

```bash
python anomaly_detector.py --mode detect --input live_feed.csv \
  --output /var/log/anomaly_scores.json
```

Configure your SIEM to ingest this JSON file and create dashboards based on the `anomaly_score` field.

### Automated Pipeline

```bash
#!/bin/bash
# Run every 15 minutes via cron
LOGS="/var/log/network/$(date +%Y%m%d_%H%M).csv"
/opt/anomaly-detection/.venv/bin/python /opt/anomaly-detection/anomaly_detector.py \
  --mode detect \
  --input "$LOGS" \
  --baseline /opt/anomaly-detection/production_baseline.json \
  --threshold 80 \
  --output /var/log/anomaly_alerts/$(date +%Y%m%d_%H%M)_alerts.json
```

### Alert Thresholds for SOC Tiers

| SOC Tier | Threshold | Rationale |
|---|---|---|
| Tier 1 (L1 Triage) | 70 | Broad net, high volume |
| Tier 2 (Investigation) | 80 | Focused, lower false positives |
| Tier 3 (Threat Intel) | 90 | Critical incidents only |

### Reducing False Positives

1. **Re-train weekly** with recent data to update the baseline as environment changes.
2. **Tune contamination** down (0.05) if too many false positives in steady-state environments.
3. **Use deduplication** (built-in 300-second window) to suppress repeated alerts from the same source.
4. **Whitelist known IPs**: Pre-filter known good addresses before running detection.
5. **Combine with threat intelligence**: Cross-reference `dst_ip` against blocklists (AbuseIPDB, VirusTotal).

### Evidence Preservation

When an alert fires, immediately capture:

```bash
# Preserve PCAP for the offending connection
tcpdump -i eth0 -w /evidence/$(date +%Y%m%d_%H%M%S)_suspicious.pcap \
  host <src_ip> and host <dst_ip>
```

---

## Contributing

Pull requests and issue reports are welcome. When adding new features, please include unit tests and update the sample data generator accordingly.

## License

MIT License. See LICENSE file for details.
