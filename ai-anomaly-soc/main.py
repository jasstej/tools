import argparse
import json

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="SOC anomaly detector starter")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="anomalies.json")
    parser.add_argument("--plot", default="anomalies.png")
    parser.add_argument("--threshold", type=float, default=3.0)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    if "value" not in df.columns:
        raise ValueError("Input CSV must include a 'value' column")

    mu = df["value"].mean()
    sigma = df["value"].std(ddof=0)
    df["zscore"] = (df["value"] - mu) / (sigma if sigma else 1)
    anoms = df[df["zscore"].abs() >= args.threshold]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(anoms.to_dict(orient="records"), f, indent=2)

    plt.figure(figsize=(10, 4))
    plt.plot(df.index, df["value"], label="value")
    plt.scatter(anoms.index, anoms["value"], color="red", label="anomaly")
    plt.legend()
    plt.tight_layout()
    plt.savefig(args.plot)

    print(f"Anomalies: {len(anoms)} | JSON: {args.output} | Plot: {args.plot}")


if __name__ == "__main__":
    main()
