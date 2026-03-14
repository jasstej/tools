# AI-Driven Anomaly Detection System for SOC

Telemetry anomaly detection starter for SOC workflows.

## Features

- CSV ingest (`timestamp`, `value`)
- Z-score anomaly detection
- JSON alerts and plot output

## Usage

```bash
python main.py --input telemetry.csv --output anomalies.json --plot anomalies.png
```
