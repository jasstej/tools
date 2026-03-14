import argparse
import hashlib
import json
import re
from pathlib import Path


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_baseline(root: Path) -> dict:
    data = {}
    for p in root.rglob("*"):
        if p.is_file():
            data[str(p)] = file_hash(p)
    return data


def compare(root: Path, old: dict) -> list[str]:
    alerts = []
    current = build_baseline(root)
    for path, old_hash in old.items():
        new_hash = current.get(path)
        if new_hash is None:
            alerts.append(f"DELETED: {path}")
        elif new_hash != old_hash:
            alerts.append(f"MODIFIED: {path}")
    for path in current:
        if path not in old:
            alerts.append(f"NEW FILE: {path}")
    return alerts


def scan_log(log_path: Path, pattern: str) -> list[str]:
    rx = re.compile(pattern, re.IGNORECASE)
    return [line.rstrip() for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines() if rx.search(line)]


def main() -> None:
    parser = argparse.ArgumentParser(description="HIDS starter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("baseline")
    b.add_argument("--path", required=True)
    b.add_argument("--db", required=True)

    c = sub.add_parser("check")
    c.add_argument("--path", required=True)
    c.add_argument("--db", required=True)

    l = sub.add_parser("scan-log")
    l.add_argument("--log", required=True)
    l.add_argument("--pattern", required=True)

    args = parser.parse_args()

    if args.cmd == "baseline":
        Path(args.db).write_text(json.dumps(build_baseline(Path(args.path)), indent=2), encoding="utf-8")
        print(f"Baseline written: {args.db}")
    elif args.cmd == "check":
        old = json.loads(Path(args.db).read_text(encoding="utf-8"))
        alerts = compare(Path(args.path), old)
        print("\n".join(alerts) if alerts else "No changes detected")
    else:
        hits = scan_log(Path(args.log), args.pattern)
        print("\n".join(hits) if hits else "No matching events")


if __name__ == "__main__":
    main()
