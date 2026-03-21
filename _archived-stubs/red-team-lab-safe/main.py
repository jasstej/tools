import argparse
import json
import time

SCENARIOS = {
    "phishing-initial-access": [
        {"stage": "recon", "technique": "T1598", "action": "Collect public metadata"},
        {"stage": "initial-access", "technique": "T1566", "action": "Simulated phishing delivery"},
        {"stage": "execution", "technique": "T1059", "action": "Mock script execution event"},
        {"stage": "persistence", "technique": "T1547", "action": "Mock startup entry"},
    ]
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab-safe red team simulator")
    parser.add_argument("--scenario", required=True, choices=SCENARIOS.keys())
    parser.add_argument("--output", default="simulation-log.json")
    args = parser.parse_args()

    timeline = []
    for step in SCENARIOS[args.scenario]:
        event = {"ts": int(time.time()), **step}
        timeline.append(event)
        print(f"[{step['stage']}] {step['action']} ({step['technique']})")
        time.sleep(0.2)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2)

    print(f"Simulation complete: {args.output}")


if __name__ == "__main__":
    main()
