import argparse
import json
import socket
import time
from datetime import datetime


def parse_ports(raw: str) -> list[int]:
    return sorted({int(p.strip()) for p in raw.split(",") if p.strip()})


def scan_port(host: str, port: int, timeout: float = 1.0) -> dict:
    result = {"port": port, "open": False, "banner": "", "latency_ms": None}
    start = time.time()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            result["open"] = True
            sock.sendall(b"\r\n")
            result["banner"] = sock.recv(1024).decode("utf-8", errors="ignore").strip()
        except Exception:
            pass
    result["latency_ms"] = round((time.time() - start) * 1000, 2)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorized attack surface mapper starter")
    parser.add_argument("--target", required=True)
    parser.add_argument("--ports", required=True)
    parser.add_argument("--output", default="recon-report.json")
    args = parser.parse_args()

    report = {
        "target": args.target,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "results": [scan_port(args.target, p) for p in parse_ports(args.ports)],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Report written: {args.output}")


if __name__ == "__main__":
    main()
