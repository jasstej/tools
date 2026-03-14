import argparse
import json
from random import randint


SCENARIOS = {
    "basic-ransomware-chain": [
        "initial_access",
        "execution",
        "privilege_escalation",
        "detection",
        "containment",
    ]
}


def simulate(name: str) -> dict:
    events = []
    blue = 0
    red = 0

    for stage in SCENARIOS[name]:
        detected = randint(0, 1) == 1
        events.append({"stage": stage, "detected": detected})
        if detected:
            blue += 10
        else:
            red += 10

    return {"scenario": name, "events": events, "scores": {"blue": blue, "red": red}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise cyber defense simulator starter")
    parser.add_argument("--scenario", required=True, choices=SCENARIOS.keys())
    parser.add_argument("--output", default="simulation-report.json")
    args = parser.parse_args()

    report = simulate(args.scenario)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Simulation complete: {args.output}")


if __name__ == "__main__":
    main()
