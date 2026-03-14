import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path


COMMANDS = {
    "processes.txt": ["ps", "aux"],
    "network.txt": ["ss", "-tulpen"],
    "logged_in_users.txt": ["who"],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def collect(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, cmd in COMMANDS.items():
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        (out_dir / filename).write_text(res.stdout + "\n" + res.stderr, encoding="utf-8")

    manifest = {"collected_at": datetime.utcnow().isoformat() + "Z", "files": {}}
    for p in out_dir.glob("*.txt"):
        manifest["files"][p.name] = sha256(p)

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="DFIR collection starter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect")
    c.add_argument("--output", default="evidence")

    args = parser.parse_args()

    if args.cmd == "collect":
        collect(Path(args.output))
        print(f"Evidence collected in: {args.output}")


if __name__ == "__main__":
    main()
