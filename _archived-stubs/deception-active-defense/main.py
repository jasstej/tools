import argparse
import json
import time
from pathlib import Path

import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class DecoyHandler(FileSystemEventHandler):
    def __init__(self, log_file: Path, webhook: str | None):
        self.log_file = log_file
        self.webhook = webhook

    def on_any_event(self, event):
        if event.is_directory:
            return
        payload = {"ts": int(time.time()), "event": event.event_type, "path": event.src_path}
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
        if self.webhook:
            try:
                requests.post(self.webhook, json=payload, timeout=3)
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Deception monitor starter")
    parser.add_argument("--watch", required=True)
    parser.add_argument("--log", default="alerts.log")
    parser.add_argument("--webhook", default=None)
    args = parser.parse_args()

    watch_path = Path(args.watch)
    watch_path.mkdir(parents=True, exist_ok=True)

    observer = Observer()
    observer.schedule(DecoyHandler(Path(args.log), args.webhook), str(watch_path), recursive=True)
    observer.start()

    print(f"Monitoring: {watch_path}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
