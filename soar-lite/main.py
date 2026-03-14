import argparse
import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def apply_rules(alerts: list[dict], playbook: dict) -> list[dict]:
    outputs = []
    for alert in alerts:
        matches = []
        for rule in playbook.get("rules", []):
            cond = rule.get("if", {})
            if all(alert.get(k) == v for k, v in cond.items()):
                matches.append({"rule": rule["name"], "actions": rule.get("actions", [])})
        outputs.append({"alert": alert, "matches": matches})
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="SOAR-lite starter")
    parser.add_argument("--alerts", required=True)
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--output", default="outcomes.json")
    args = parser.parse_args()

    alerts = load_jsonl(Path(args.alerts))
    playbook = json.loads(Path(args.playbook).read_text(encoding="utf-8"))
    outcomes = apply_rules(alerts, playbook)

    Path(args.output).write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
    print(f"Processed {len(alerts)} alerts. Output: {args.output}")


if __name__ == "__main__":
    main()
