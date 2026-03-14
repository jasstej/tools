#!/usr/bin/env python3
"""
AI-Driven Network Anomaly Detection System
==========================================
Uses Isolation Forest and statistical baselines to detect anomalous
network behavior from log data.
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _red(text):
    return (Fore.RED + str(text) + Style.RESET_ALL) if HAS_COLORAMA else str(text)

def _yellow(text):
    return (Fore.YELLOW + str(text) + Style.RESET_ALL) if HAS_COLORAMA else str(text)

def _green(text):
    return (Fore.GREEN + str(text) + Style.RESET_ALL) if HAS_COLORAMA else str(text)

def _cyan(text):
    return (Fore.CYAN + str(text) + Style.RESET_ALL) if HAS_COLORAMA else str(text)

def _bold(text):
    return (Style.BRIGHT + str(text) + Style.RESET_ALL) if HAS_COLORAMA else str(text)


REQUIRED_FIELDS = [
    "timestamp", "src_ip", "dst_ip", "port",
    "bytes", "protocol", "duration", "user",
]


# ---------------------------------------------------------------------------
# 1. DATA INGESTION
# ---------------------------------------------------------------------------

def validate_fields(df, required=None):
    """Raise ValueError if any required columns are missing."""
    if required is None:
        required = REQUIRED_FIELDS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return True


def load_network_logs(csv_file):
    """Load network logs from a CSV file into a pandas DataFrame."""
    if not HAS_PANDAS:
        raise RuntimeError("pandas is required. Install it with: pip install pandas")
    if not os.path.isfile(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    df = pd.read_csv(csv_file)
    # Normalise column names
    df.columns = [c.strip().lower() for c in df.columns]
    validate_fields(df)

    # Parse types
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["bytes"] = pd.to_numeric(df["bytes"], errors="coerce").fillna(0).astype(int)
    df["port"] = pd.to_numeric(df["port"], errors="coerce").fillna(0).astype(int)
    df["duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0.0)

    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(_green(f"[+] Loaded {len(df)} records from {csv_file}"))
    return df


def load_json_events(json_file):
    """Load events from a JSON file (list of dicts) into a DataFrame."""
    if not HAS_PANDAS:
        raise RuntimeError("pandas is required.")
    if not os.path.isfile(json_file):
        raise FileNotFoundError(f"JSON file not found: {json_file}")

    with open(json_file, "r") as fh:
        data = json.load(fh)

    if not isinstance(data, list):
        raise ValueError("JSON file must contain a list of event objects.")

    df = pd.DataFrame(data)
    df.columns = [c.strip().lower() for c in df.columns]
    validate_fields(df)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["bytes"] = pd.to_numeric(df["bytes"], errors="coerce").fillna(0).astype(int)
    df["port"] = pd.to_numeric(df["port"], errors="coerce").fillna(0).astype(int)
    df["duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0.0)

    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(_green(f"[+] Loaded {len(df)} events from {json_file}"))
    return df


# ---------------------------------------------------------------------------
# 2. FEATURE ENGINEERING
# ---------------------------------------------------------------------------

def _port_category(port):
    """Categorise TCP/UDP port into broad service buckets."""
    if port in (80, 8080, 8443):
        return 0   # web-http
    if port in (443, 8443):
        return 1   # web-https
    if port in (3306, 5432, 1433, 1521, 6379, 27017):
        return 2   # database
    if port in (22, 3389, 5900, 23):
        return 3   # remote access
    if port in (25, 465, 587, 110, 143, 993, 995):
        return 4   # email
    if port in (53, 67, 68, 123):
        return 5   # infrastructure
    if port < 1024:
        return 6   # other well-known
    if port > 49151:
        return 8   # ephemeral / high
    return 7       # registered / unknown


def add_features(df):
    """
    Derive additional numerical features from raw log columns.

    New columns added:
        bytes_per_second       - transfer rate
        log_bytes              - log10(bytes + 1) to reduce skew
        hour_of_day            - 0-23
        is_business_hours      - 1 if 09:00-17:00, else 0
        port_category          - integer bucket (0-8)
        connection_count_per_hour - rolling count per src_ip per hour window
    """
    if not HAS_PANDAS or not HAS_NUMPY:
        raise RuntimeError("pandas and numpy are required for feature engineering.")

    df = df.copy()

    # bytes_per_second (avoid division by zero)
    df["bytes_per_second"] = df["bytes"] / df["duration"].replace(0, 0.001)

    # log_bytes
    df["log_bytes"] = np.log10(df["bytes"].clip(lower=1))

    # temporal features
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["is_business_hours"] = ((df["hour_of_day"] >= 9) & (df["hour_of_day"] < 17)).astype(int)

    # port category
    df["port_category"] = df["port"].apply(_port_category)

    # connection count per source IP per hour window
    df = df.sort_values("timestamp")
    df["ts_floor_hour"] = df["timestamp"].dt.floor("H")
    conn_counts = (
        df.groupby(["src_ip", "ts_floor_hour"])
        .transform("count")["bytes"]
    )
    df["connection_count_per_hour"] = conn_counts.values
    df.drop(columns=["ts_floor_hour"], inplace=True)

    return df


# ---------------------------------------------------------------------------
# 3. BASELINE MODELLING
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "bytes_per_second",
    "log_bytes",
    "hour_of_day",
    "is_business_hours",
    "port_category",
    "connection_count_per_hour",
]


def train_isolation_forest(df, contamination=0.1):
    """
    Fit an Isolation Forest model on engineered features.

    Returns:
        model  - fitted IsolationForest
        scaler - fitted StandardScaler
        stats  - dict of per-feature mean/std for anomaly explanation
    """
    if not HAS_SKLEARN or not HAS_NUMPY:
        raise RuntimeError("scikit-learn and numpy are required for model training.")

    df = add_features(df)
    X = df[FEATURE_COLS].fillna(0).values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        contamination=contamination,
        n_estimators=200,
        max_samples="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    stats = {}
    for i, col in enumerate(FEATURE_COLS):
        stats[col] = {
            "mean": float(np.mean(X[:, i])),
            "std": float(np.std(X[:, i])),
            "min": float(np.min(X[:, i])),
            "max": float(np.max(X[:, i])),
        }

    print(_green(f"[+] Isolation Forest trained on {len(df)} samples "
                 f"(contamination={contamination})"))
    return model, scaler, stats


def z_score_baseline(series):
    """
    Compute Z-scores for a numeric series.

    Returns a dict with mean, std, and the z_scores Series.
    """
    if not HAS_NUMPY or not HAS_PANDAS:
        raise RuntimeError("numpy and pandas required for z-score baseline.")

    arr = pd.to_numeric(series, errors="coerce").fillna(0)
    mean = float(arr.mean())
    std = float(arr.std())
    if std == 0:
        z_scores = pd.Series([0.0] * len(arr), index=arr.index)
    else:
        z_scores = (arr - mean) / std
    return {"mean": mean, "std": std, "z_scores": z_scores}


# ---------------------------------------------------------------------------
# 4. ANOMALY SCORING
# ---------------------------------------------------------------------------

def score_events(df, model, scaler):
    """
    Score each event 0-100, where 100 = most anomalous.

    The Isolation Forest returns raw scores in the range (-0.5, 0.5).
    We normalise these to 0-100 and invert so higher = more anomalous.

    Returns df with new 'anomaly_score' column.
    """
    if not HAS_SKLEARN:
        raise RuntimeError("scikit-learn required for scoring.")

    df = add_features(df)
    X = df[FEATURE_COLS].fillna(0).values
    X_scaled = scaler.transform(X)

    raw_scores = model.decision_function(X_scaled)  # higher = more normal
    # Normalise: typical range is roughly -0.3 to 0.3
    # Map to 0-100, invert direction
    min_s, max_s = raw_scores.min(), raw_scores.max()
    if max_s == min_s:
        normalised = [50.0] * len(raw_scores)
    else:
        normalised = [(max_s - s) / (max_s - min_s) * 100 for s in raw_scores]

    df = df.copy()
    df["anomaly_score"] = [round(s, 1) for s in normalised]
    return df


def explain_anomaly(row, baseline_stats):
    """
    Return a list of (feature, deviation_message) tuples explaining
    which features deviate most from the baseline.
    """
    explanations = []
    for col in FEATURE_COLS:
        if col not in baseline_stats:
            continue
        value = row.get(col, 0)
        mean = baseline_stats[col]["mean"]
        std = baseline_stats[col]["std"]
        if std < 1e-9:
            continue
        z = (value - mean) / std
        if abs(z) >= 2.0:
            direction = "above" if z > 0 else "below"
            explanations.append((col, f"{abs(z):.1f} std dev {direction} mean "
                                       f"(value={value:.2f}, mean={mean:.2f})"))

    explanations.sort(key=lambda x: -float(x[1].split()[0]))
    return explanations


# ---------------------------------------------------------------------------
# 5. ALERTING
# ---------------------------------------------------------------------------

def threshold_alert(events, threshold=70):
    """
    Filter scored events to those exceeding the threshold.
    events: list of dicts or DataFrame rows with 'anomaly_score'.
    Returns sorted list of alert dicts.
    """
    if HAS_PANDAS and isinstance(events, pd.DataFrame):
        alerts = events[events["anomaly_score"] >= threshold].copy()
        alerts.sort_values("anomaly_score", ascending=False, inplace=True)
        return alerts.to_dict(orient="records")

    alerts = [e for e in events if e.get("anomaly_score", 0) >= threshold]
    alerts.sort(key=lambda x: x.get("anomaly_score", 0), reverse=True)
    return alerts


def deduplicate(alerts, window_seconds=300):
    """
    Remove duplicate alerts from the same source IP within a time window.
    Returns de-duplicated list.
    """
    seen = {}
    deduped = []
    for alert in alerts:
        src = alert.get("src_ip", "unknown")
        ts_raw = alert.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                ts = datetime.now()
        elif isinstance(ts_raw, datetime):
            ts = ts_raw
        else:
            ts = datetime.now()

        last_ts = seen.get(src)
        if last_ts is None or (ts - last_ts).total_seconds() > window_seconds:
            deduped.append(alert)
            seen[src] = ts

    return deduped


# ---------------------------------------------------------------------------
# 6. VISUALISATION
# ---------------------------------------------------------------------------

def plot_anomaly_timeline(df, output_path="anomaly_timeline.png"):
    """Plot anomaly scores over time as a line chart."""
    if not HAS_MATPLOTLIB:
        print(_yellow("[!] matplotlib not available - skipping plot."))
        return

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_facecolor("#0f1117")
    fig.patch.set_facecolor("#0f1117")

    ax.plot(df["timestamp"], df["anomaly_score"],
            color="#40c463", linewidth=0.8, alpha=0.7, label="Anomaly Score")

    anomalies = df[df["anomaly_score"] >= 70]
    ax.scatter(anomalies["timestamp"], anomalies["anomaly_score"],
               color="#f85149", zorder=5, s=40, label="High Anomaly (>=70)")

    ax.axhline(y=70, color="#f0883e", linestyle="--", linewidth=0.9, alpha=0.6,
               label="Threshold (70)")

    ax.set_xlabel("Time", color="white")
    ax.set_ylabel("Anomaly Score (0-100)", color="white")
    ax.set_title("Network Anomaly Score Timeline", color="white", fontsize=13)
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("#30363d")
    ax.spines["left"].set_color("#30363d")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, 105)
    ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(_green(f"[+] Timeline plot saved to {output_path}"))


def plot_feature_distribution(df, output_path="feature_distribution.png"):
    """Plot histograms for each engineered feature, coloured by anomaly label."""
    if not HAS_MATPLOTLIB:
        print(_yellow("[!] matplotlib not available - skipping plot."))
        return

    if "anomaly_score" not in df.columns:
        print(_yellow("[!] Score events first before plotting distributions."))
        return

    normal = df[df["anomaly_score"] < 70]
    anomalous = df[df["anomaly_score"] >= 70]

    n_cols = 3
    n_rows = math.ceil(len(FEATURE_COLS) / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows))
    fig.patch.set_facecolor("#0f1117")
    axes = axes.flatten()

    for i, col in enumerate(FEATURE_COLS):
        ax = axes[i]
        ax.set_facecolor("#161b22")
        if col in normal.columns:
            ax.hist(normal[col].dropna(), bins=20, color="#40c463", alpha=0.6,
                    label="Normal", density=True)
        if col in anomalous.columns and len(anomalous) > 0:
            ax.hist(anomalous[col].dropna(), bins=20, color="#f85149", alpha=0.7,
                    label="Anomalous", density=True)
        ax.set_title(col, color="white", fontsize=9)
        ax.tick_params(colors="white", labelsize=7)
        ax.spines["bottom"].set_color("#30363d")
        ax.spines["left"].set_color("#30363d")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white",
                  fontsize=7)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    plt.suptitle("Feature Distributions: Normal vs Anomalous", color="white",
                 fontsize=12, y=1.01)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(_green(f"[+] Feature distribution plot saved to {output_path}"))


# ---------------------------------------------------------------------------
# 7. SAMPLE DATA GENERATOR
# ---------------------------------------------------------------------------

def generate_sample_data(n=200, seed=42):
    """
    Generate n rows of synthetic network log data.
    Approximately 10% are injected as anomalous records.
    Returns a pandas DataFrame (requires pandas).
    """
    if not HAS_PANDAS:
        raise RuntimeError("pandas required for sample data generation.")

    random.seed(seed)
    users = ["alice", "bob", "charlie", "dave", "eve", "frank"]
    normal_ports = [80, 443, 22, 8080, 8443]
    external_ips = ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1",
                    "208.67.222.222", "208.67.220.220"]
    internal_subnet = "10.0.{}.{}"

    records = []
    base_time = datetime(2024, 1, 15, 8, 0, 0)

    n_normal = int(n * 0.90)
    n_anomalous = n - n_normal

    # Normal records
    for i in range(n_normal):
        hour = random.randint(9, 16)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        ts = datetime(2024, 1, 15, hour, minute, second)
        src = internal_subnet.format(random.randint(1, 5), random.randint(10, 20))
        dst = random.choice(external_ips)
        port = random.choice(normal_ports)
        byte_count = random.randint(1000, 50000)
        duration = round(random.uniform(0.1, 2.0), 2)
        user = random.choice(users)
        records.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "src_ip": src,
            "dst_ip": dst,
            "port": port,
            "bytes": byte_count,
            "protocol": "TCP",
            "duration": duration,
            "user": user,
        })

    # Anomalous records
    anomaly_templates = [
        # Off-hours + huge bytes + unusual port + unknown user
        lambda: {
            "timestamp": datetime(2024, 1, 15, random.randint(0, 5),
                                   random.randint(0, 59),
                                   random.randint(0, 59)).strftime("%Y-%m-%d %H:%M:%S"),
            "src_ip": internal_subnet.format(random.randint(50, 99),
                                              random.randint(1, 254)),
            "dst_ip": f"185.{random.randint(100, 230)}.{random.randint(1, 254)}.{random.randint(1, 254)}",
            "port": random.choice([4444, 6667, 1337, 31337]),
            "bytes": random.randint(3_000_000, 15_000_000),
            "protocol": "TCP",
            "duration": round(random.uniform(15.0, 60.0), 2),
            "user": random.choice(["unknown_user", "hacker99", "sysadmin_backup"]),
        },
        # Known user + massive exfiltration during business hours
        lambda: {
            "timestamp": datetime(2024, 1, 15, random.randint(9, 17),
                                   random.randint(0, 59),
                                   random.randint(0, 59)).strftime("%Y-%m-%d %H:%M:%S"),
            "src_ip": internal_subnet.format(random.randint(1, 5),
                                              random.randint(10, 20)),
            "dst_ip": f"94.{random.randint(100, 150)}.{random.randint(1, 254)}.{random.randint(1, 254)}",
            "port": 443,
            "bytes": random.randint(50_000_000, 200_000_000),
            "protocol": "TCP",
            "duration": round(random.uniform(100.0, 500.0), 2),
            "user": random.choice(users),
        },
    ]

    for _ in range(n_anomalous):
        tmpl = random.choice(anomaly_templates)
        records.append(tmpl())

    random.shuffle(records)
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(_green(f"[+] Generated {len(df)} synthetic records "
                 f"({n_anomalous} anomalous injected)"))
    return df


# ---------------------------------------------------------------------------
# 8. COMMAND-LINE INTERFACE
# ---------------------------------------------------------------------------

def print_alert_table(alerts, baseline_stats=None):
    """Pretty-print a list of alert dicts to stdout."""
    if not alerts:
        print(_green("[+] No anomalies detected above threshold."))
        return

    print(_bold(_red(f"\n{'='*70}")))
    print(_bold(_red(f"  ANOMALY ALERTS ({len(alerts)} detected)")))
    print(_bold(_red(f"{'='*70}")))

    for i, alert in enumerate(alerts, 1):
        score = alert.get("anomaly_score", 0)
        colour = _red if score >= 85 else (_yellow if score >= 70 else _green)
        print(f"\n  [{i}] {colour(f'Score: {score:.1f}/100')}  "
              f"Time: {alert.get('timestamp', 'N/A')}  "
              f"User: {_cyan(str(alert.get('user', 'N/A')))}")
        print(f"      {alert.get('src_ip','?')} -> {alert.get('dst_ip','?')}:"
              f"{alert.get('port','?')}  |  "
              f"{alert.get('bytes', 0):,} bytes  |  "
              f"{alert.get('duration', 0):.2f}s")

        if baseline_stats:
            explanations = explain_anomaly(alert, baseline_stats)
            if explanations:
                print("      Contributing factors:")
                for feat, msg in explanations[:3]:
                    print(f"        - {_yellow(feat)}: {msg}")

    print(_bold(_red(f"{'='*70}\n")))


def run_demo_mode():
    """Run a self-contained demo with synthetic data."""
    print(_bold(_cyan("\n[DEMO MODE] Generating synthetic network data...")))

    df = generate_sample_data(n=200)
    print(_cyan("[*] Engineering features..."))
    model, scaler, stats = train_isolation_forest(df, contamination=0.1)

    print(_cyan("[*] Scoring events..."))
    df_scored = score_events(df, model, scaler)

    alerts = threshold_alert(df_scored, threshold=70)
    deduped = deduplicate(alerts, window_seconds=300)

    print_alert_table(deduped, baseline_stats=stats)

    summary = df_scored["anomaly_score"].describe()
    print(_bold("\n[+] Score Distribution Summary:"))
    print(f"    Mean:  {summary['mean']:.1f}")
    print(f"    Max:   {summary['max']:.1f}")
    print(f"    >=70:  {(df_scored['anomaly_score'] >= 70).sum()}")
    print(f"    >=85:  {(df_scored['anomaly_score'] >= 85).sum()}")

    return df_scored, stats


def run_train_mode(args):
    """Train a model and save baseline statistics."""
    print(_bold(_cyan(f"[TRAIN MODE] Loading data from {args.input}...")))

    if args.input.endswith(".json"):
        df = load_json_events(args.input)
    else:
        df = load_network_logs(args.input)

    model, scaler, stats = train_isolation_forest(
        df, contamination=args.contamination
    )

    # Persist baseline stats as JSON
    baseline_path = args.baseline or "baseline_stats.json"
    with open(baseline_path, "w") as fh:
        json.dump(stats, fh, indent=2)
    print(_green(f"[+] Baseline stats saved to {baseline_path}"))

    # Optionally save the trained model
    try:
        import pickle
        model_path = baseline_path.replace(".json", "_model.pkl")
        with open(model_path, "wb") as fh:
            pickle.dump({"model": model, "scaler": scaler}, fh)
        print(_green(f"[+] Trained model saved to {model_path}"))
    except Exception as exc:
        print(_yellow(f"[!] Could not persist model: {exc}"))


def run_detect_mode(args):
    """Load data, score it, and report anomalies."""
    print(_bold(_cyan(f"[DETECT MODE] Loading data from {args.input}...")))

    if args.input.endswith(".json"):
        df = load_json_events(args.input)
    else:
        df = load_network_logs(args.input)

    # Attempt to load pre-trained model
    baseline_stats = None
    model = None
    scaler = None

    baseline_path = args.baseline or "baseline_stats.json"
    model_path = baseline_path.replace(".json", "_model.pkl")

    if os.path.isfile(model_path):
        try:
            import pickle
            with open(model_path, "rb") as fh:
                saved = pickle.load(fh)
            model = saved["model"]
            scaler = saved["scaler"]
            print(_green(f"[+] Loaded pre-trained model from {model_path}"))
        except Exception as exc:
            print(_yellow(f"[!] Could not load model ({exc}). Training fresh."))

    if os.path.isfile(baseline_path):
        with open(baseline_path, "r") as fh:
            baseline_stats = json.load(fh)

    if model is None:
        model, scaler, baseline_stats = train_isolation_forest(
            df, contamination=args.contamination
        )

    df_scored = score_events(df, model, scaler)
    alerts = threshold_alert(df_scored, threshold=args.threshold)
    deduped = deduplicate(alerts, window_seconds=300)
    print_alert_table(deduped, baseline_stats=baseline_stats)

    if args.output:
        out_path = args.output
        if out_path.endswith(".json"):
            df_scored.to_json(out_path, orient="records", date_format="iso",
                              indent=2)
        else:
            df_scored.to_csv(out_path, index=False)
        print(_green(f"[+] Scored events written to {out_path}"))

    if args.plot:
        if "anomaly_score" in df_scored.columns:
            plot_anomaly_timeline(df_scored, "anomaly_timeline.png")
            plot_feature_distribution(df_scored, "feature_distribution.png")


def main():
    parser = argparse.ArgumentParser(
        description="AI-Driven Network Anomaly Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick demo with synthetic data
  python anomaly_detector.py --mode demo

  # Train on a CSV, save baseline
  python anomaly_detector.py --mode train --input logs.csv --baseline baseline.json

  # Detect anomalies in new data
  python anomaly_detector.py --mode detect --input new_logs.csv --threshold 75 --plot

  # Detect and export results
  python anomaly_detector.py --mode detect --input logs.csv --output scored.csv
""",
    )
    parser.add_argument(
        "--mode", choices=["train", "detect", "demo"], default="demo",
        help="Operation mode (default: demo)"
    )
    parser.add_argument(
        "--input", "-i", default=None,
        help="Input CSV or JSON file path"
    )
    parser.add_argument(
        "--baseline", "-b", default="baseline_stats.json",
        help="Path to baseline statistics JSON (default: baseline_stats.json)"
    )
    parser.add_argument(
        "--threshold", "-t", type=float, default=70.0,
        help="Anomaly score threshold for alerts (0-100, default: 70)"
    )
    parser.add_argument(
        "--contamination", "-c", type=float, default=0.1,
        help="Expected fraction of anomalies for Isolation Forest (default: 0.1)"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output path for scored events (.csv or .json)"
    )
    parser.add_argument(
        "--plot", action="store_true",
        help="Generate matplotlib visualisation charts"
    )

    args = parser.parse_args()

    if not HAS_PANDAS or not HAS_NUMPY:
        print(_red("[ERROR] pandas and numpy are required. "
                   "Run: pip install pandas numpy"))
        sys.exit(1)

    if args.mode == "demo":
        run_demo_mode()

    elif args.mode == "train":
        if not args.input:
            parser.error("--input is required for train mode")
        run_train_mode(args)

    elif args.mode == "detect":
        if not args.input:
            parser.error("--input is required for detect mode")
        run_detect_mode(args)


if __name__ == "__main__":
    main()
