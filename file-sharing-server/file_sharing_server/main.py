"""CLI entry point for file sharing server."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .server import FileShareServer
from .file_manager import ShareManager
from .auth import MasterTokenManager


class FileShareCLI:
    """Command-line interface for file sharing server."""

    def __init__(self, data_dir: str = None):
        """
        Initialize CLI.

        Args:
            data_dir: Data directory for shares and logs
        """
        self.data_dir = Path(data_dir or "./data")
        self.share_manager = ShareManager(self.data_dir)
        self.master_token_manager = MasterTokenManager(self.data_dir / "master_token.txt")

    def cmd_share(
        self,
        path: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        description: str = "",
        max_size: int = 500,
        allowed_types: Optional[str] = None,
        expires_in: Optional[int] = None,
        ui_file: str = None,
        use_https: bool = False,
        enable_rate_limit: bool = True,
    ) -> int:
        """
        Add a share and start server.

        Args:
            path: Directory path to share
            host: Server bind address
            port: Server bind port
            description: Share description
            max_size: Max file size in MB
            allowed_types: Comma-separated allowed file types
            expires_in: Auto-expire after N hours (None = never)
            ui_file: Path to UI HTML file

        Returns:
            Exit code
        """
        # Add share
        allowed_extensions = (
            [t.strip() for t in allowed_types.split(",")] if allowed_types else None
        )
        success, message, token = self.share_manager.add_share(
            path,
            description=description,
            max_file_size_mb=max_size,
            allowed_extensions=allowed_extensions,
            expires_in_hours=expires_in,
        )

        if not success:
            print(f"Error: {message}", file=sys.stderr)
            return 1

        print(f"✓ {message}")
        print(f"├─ Share token: {token}")
        print()

        # Get master token
        master_token = self.master_token_manager.get_or_create()
        print(f"Master token (admin access): {master_token}")
        print()

        # Start server
        protocol = "https" if use_https else "http"
        print()
        print("Access share:")
        print(f"  http://{host}:{port}/?token={token}")
        print()
        print("Admin panel:")
        print(f"  http://{host}:{port}/admin?token={master_token}")
        print()
        print("Press Ctrl+C to stop server")
        print()

        # Create server
        ui_path = Path(ui_file) if ui_file else self._get_default_ui_path()

        # Print protocol
        protocol = "https" if use_https else "http"
        print(f"Starting server on {protocol}://{host}:{port}")

        server = FileShareServer(
            host=host,
            port=port,
            data_dir=self.data_dir,
            ui_file=ui_path,
            use_https=use_https,
            enable_rate_limit=enable_rate_limit,
        )

        try:
            server.run()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        return 0

    def cmd_list(self) -> int:
        """List all active shares."""
        self.share_manager._load_shares()  # Reload from disk
        shares = self.share_manager.list_shares()

        if not shares:
            print("No active shares")
            return 0

        print(f"Active Shares ({len(shares)}):")
        print()

        for share in shares:
            print(f"Share: {share['id']}")
            print(f"  Path: {share['path']}")
            print(f"  Token: {share['token']}")
            print(f"  Max size: {share['max_file_size_mb']}MB")
            print(f"  Created: {share['created']}")
            if share.get("expires"):
                print(f"  Expires: {share['expires']}")
            print()

        return 0

    def cmd_remove(self, share_id: str) -> int:
        """Remove a share by ID."""
        success, message = self.share_manager.remove_share(share_id)
        if success:
            print(f"✓ {message}")
            return 0
        else:
            print(f"Error: {message}", file=sys.stderr)
            return 1

    def cmd_config(
        self,
        share_id: str,
        max_size: Optional[int] = None,
        allowed_types: Optional[str] = None,
    ) -> int:
        """Configure a share."""
        share = self.share_manager.get_share(share_id)
        if not share:
            print(f"Error: Share not found: {share_id}", file=sys.stderr)
            return 1

        # Update settings
        if max_size:
            share.max_file_size_mb = max_size
        if allowed_types:
            share.allowed_extensions = [
                t.strip() for t in allowed_types.split(",")
            ]

        self.share_manager.shares[share_id] = share
        self.share_manager._save_shares()

        print(f"✓ Share configured: {share_id}")
        return 0

    def cmd_status(self) -> int:
        """Show server status."""
        self.share_manager._load_shares()  # Reload from disk

        shares = self.share_manager.list_shares()
        master_token_exists = (self.data_dir / "master_token.txt").exists()

        print("File Sharing Server Status:")
        print(f"  Data directory: {self.data_dir}")
        print(f"  Active shares: {len(shares)}")
        print(f"  Master token: {'Yes' if master_token_exists else 'No'}")
        print(f"  Activity log: {self.data_dir / 'activity.log'}")
        print()

        return 0

    def _get_default_ui_path(self) -> Path:
        """Get path to default UI file."""
        # Try to find UI in package directory
        package_dir = Path(__file__).parent.parent
        ui_path = package_dir / "ui" / "index.html"
        if ui_path.exists():
            return ui_path

        # Fallback
        return Path(__file__).parent / "ui" / "index.html"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="File Sharing Server - Share files on local network"
    )
    parser.add_argument(
        "--data-dir",
        help="Data directory (default: ./data)",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # share command
    share_parser = subparsers.add_parser(
        "share", help="Add a share and start server"
    )
    share_parser.add_argument("path", help="Directory path to share")
    share_parser.add_argument(
        "--host", default="0.0.0.0", help="Server bind address (default: 0.0.0.0)"
    )
    share_parser.add_argument(
        "--port", type=int, default=8000, help="Server port (default: 8000)"
    )
    share_parser.add_argument(
        "--description", default="", help="Share description"
    )
    share_parser.add_argument(
        "--max-size",
        type=int,
        default=500,
        help="Max file size in MB (default: 500)",
    )
    share_parser.add_argument(
        "--allowed-types",
        help="Comma-separated file types (e.g., exe,deb,txt)",
    )
    share_parser.add_argument(
        "--expires-in",
        type=int,
        help="Auto-expire after N hours",
    )
    share_parser.add_argument(
        "--ui-file",
        help="Path to custom UI HTML file",
    )
    share_parser.add_argument(
        "--https",
        action="store_true",
        help="Enable HTTPS/TLS (generates self-signed cert)",
    )
    share_parser.add_argument(
        "--no-rate-limit",
        action="store_true",
        help="Disable rate limiting",
    )

    # list command
    subparsers.add_parser("list", help="List active shares")

    # remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a share")
    remove_parser.add_argument("share_id", help="Share ID")

    # config command
    config_parser = subparsers.add_parser("config", help="Configure a share")
    config_parser.add_argument("share_id", help="Share ID")
    config_parser.add_argument(
        "--max-size", type=int, help="Max file size in MB"
    )
    config_parser.add_argument(
        "--allowed-types", help="Comma-separated file types"
    )

    # status command
    subparsers.add_parser("status", help="Show server status")

    args = parser.parse_args()

    # Create CLI
    cli = FileShareCLI(data_dir=args.data_dir)

    # Route commands
    if args.command == "share":
        return cli.cmd_share(
            path=args.path,
            host=args.host,
            port=args.port,
            description=args.description,
            max_size=args.max_size,
            allowed_types=args.allowed_types,
            expires_in=args.expires_in,
            ui_file=args.ui_file,
            use_https=args.https,
            enable_rate_limit=not args.no_rate_limit,
        )
    elif args.command == "list":
        return cli.cmd_list()
    elif args.command == "remove":
        return cli.cmd_remove(args.share_id)
    elif args.command == "config":
        return cli.cmd_config(
            share_id=args.share_id,
            max_size=args.max_size,
            allowed_types=args.allowed_types,
        )
    elif args.command == "status":
        return cli.cmd_status()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
