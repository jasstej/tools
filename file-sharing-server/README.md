# File Sharing Server

Secure LAN file sharing with a browser-based UI.

This project lets you share one or more local folders over HTTP/HTTPS with token-based access, upload controls, and activity logging.

## Features

- Token-protected share links
- Browser UI for browse, upload, and download
- Optional HTTPS with auto-generated self-signed certificate
- Per-share controls:
  - Max upload size
  - Allowed file extensions
  - Optional expiration
  - Description metadata
- Share management commands (`share`, `list`, `remove`, `config`, `status`)
- Basic rate limiting (enabled by default)
- Activity logging in local data directory

## Requirements

- Python 3.9+
- Linux, macOS, or Windows

## Installation

### Option 1: Editable install (development)

```bash
pip install -e .
```

### Option 2: Standard install

```bash
pip install .
```

After install, you can run either:

```bash
file-sharing-server --help
```

or:

```bash
python -m file_sharing_server --help
```

## Quick Start

Share a folder and start the server:

```bash
python -m file_sharing_server share /path/to/folder
```

Default bind is `0.0.0.0:8000`.

The command prints:

- Share URL with share token
- Admin URL with master token

Open the printed URL in any browser on your network.

## CLI Usage

Global option:

```bash
python -m file_sharing_server --data-dir ./data <command> [options]
```

Commands:

### `share`

Create a share and start the server.

```bash
python -m file_sharing_server share /path/to/folder \
  --host 0.0.0.0 \
  --port 8000 \
  --description "Team drop" \
  --max-size 500 \
  --allowed-types pdf,txt,zip \
  --expires-in 24 \
  --https
```

Options:

- `--host` bind address (default `0.0.0.0`)
- `--port` port (default `8000`)
- `--description` text label for share
- `--max-size` max upload size in MB (default `500`)
- `--allowed-types` comma-separated extensions
- `--expires-in` expiration in hours
- `--ui-file` custom HTML UI path
- `--https` enable TLS (self-signed cert)
- `--no-rate-limit` disable rate limiting

### `list`

List active shares.

```bash
python -m file_sharing_server list
```

### `remove`

Remove share by ID.

```bash
python -m file_sharing_server remove <share_id>
```

### `config`

Update share settings.

```bash
python -m file_sharing_server config <share_id> --max-size 1000 --allowed-types iso,zip
```

### `status`

Show status, including data dir and active share count.

```bash
python -m file_sharing_server status
```

## Data and Logs

Default runtime data directory is `./data` (or custom via `--data-dir`).

Typical files:

- `shares.json` share metadata
- `master_token.txt` admin token
- `activity.log` request/activity log

## Security Notes

- Tokens grant access. Share them only with intended users.
- Use `--https` on untrusted networks.
- Restrict file types and max upload size where possible.
- Rotate shares/tokens by removing and recreating shares if needed.

## Packaging and Builds

- Python package config: `pyproject.toml`
- PyInstaller spec: `file_sharing_server.spec`
- Build helper scripts:
  - `build_linux.sh`
  - `build_windows.bat`
- Extra build documentation: `BUILD.md`

## Development

Install dev dependencies:

```bash
pip install -r requirements-dev.txt
```

Run lint/tests as configured in your environment.

## License

MIT License. See `LICENSE`.
