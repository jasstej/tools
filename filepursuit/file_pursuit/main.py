"""
Command-line interface for FilePursuit.
"""

import argparse
import sys
import os
import uuid
from datetime import datetime
from tabulate import tabulate
from colorama import Fore, Style, init

from .database import Database, CrawlTarget
from .logger import ActivityLogger
from .auth import MasterTokenManager
from .search_engine import SearchEngine
from .crawler import run_crawl_sync, Crawler, ConcurrentCrawler
from .server import FilePursuitServer
from .utils import format_bytes

# Initialize colorama for cross-platform colors
init(autoreset=True)


class FilePursuitCLI:
    """Command-line interface."""

    def __init__(self):
        """Initialize CLI."""
        self.db_path = "data/index.db"
        self.log_path = "data/crawl.log"
        self.token_path = "data/master_token.txt"
        self.targets_path = "data/targets.json"

        self.database = Database(self.db_path)
        self.logger = ActivityLogger(self.log_path)
        self.token_manager = MasterTokenManager(self.token_path)
        self.search_engine = SearchEngine(self.database)

    def run(self, args=None):
        """Run CLI with arguments."""
        parser = self._create_parser()
        args = parser.parse_args(args)

        if hasattr(args, "func"):
            try:
                return args.func(args)
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled.")
                return 1
            except Exception as e:
                print(f"{Fore.RED}Error: {e}")
                return 1
        else:
            parser.print_help()
            return 0

    def _create_parser(self):
        """Create argument parser."""
        parser = argparse.ArgumentParser(
            prog="filepursuit",
            description="Distributed file search engine for public file indexes"
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # add-target command
        add_target_parser = subparsers.add_parser(
            "add-target",
            help="Add a crawl target"
        )
        add_target_parser.add_argument("url", help="Target URL")
        add_target_parser.add_argument(
            "--type",
            choices=["apache", "nginx"],
            default="apache",
            help="Server type (default: apache)"
        )
        add_target_parser.set_defaults(func=self.cmd_add_target)

        # list-targets command
        list_targets_parser = subparsers.add_parser(
            "list-targets",
            help="List all crawl targets"
        )
        list_targets_parser.set_defaults(func=self.cmd_list_targets)

        # remove-target command
        remove_target_parser = subparsers.add_parser(
            "remove-target",
            help="Remove a crawl target"
        )
        remove_target_parser.add_argument("target_id", help="Target ID")
        remove_target_parser.set_defaults(func=self.cmd_remove_target)

        # crawl command
        crawl_parser = subparsers.add_parser(
            "crawl",
            help="Crawl targets and index files"
        )
        crawl_parser.add_argument(
            "--target-id",
            help="Specific target to crawl (default: all)"
        )
        crawl_parser.add_argument(
            "--concurrent",
            type=int,
            default=4,
            help="Concurrent workers (default: 4)"
        )
        crawl_parser.set_defaults(func=self.cmd_crawl)

        # search command
        search_parser = subparsers.add_parser(
            "search",
            help="Search the index"
        )
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument(
            "--type",
            help="Filter by file type (document, archive, media, source, etc.)"
        )
        search_parser.add_argument(
            "--min-size",
            type=int,
            help="Minimum file size in bytes"
        )
        search_parser.add_argument(
            "--max-size",
            type=int,
            help="Maximum file size in bytes"
        )
        search_parser.add_argument(
            "--sort",
            choices=["relevance", "size", "date"],
            default="relevance",
            help="Sort order (default: relevance)"
        )
        search_parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Results limit (default: 20)"
        )
        search_parser.set_defaults(func=self.cmd_search)

        # status command
        status_parser = subparsers.add_parser(
            "status",
            help="Show server status and statistics"
        )
        status_parser.set_defaults(func=self.cmd_status)

        # admin-token command
        token_parser = subparsers.add_parser(
            "admin-token",
            help="Show or regenerate admin token"
        )
        token_parser.add_argument(
            "--regenerate",
            action="store_true",
            help="Generate a new token"
        )
        token_parser.set_defaults(func=self.cmd_admin_token)

        # serve command
        serve_parser = subparsers.add_parser(
            "serve",
            help="Start HTTP API server"
        )
        serve_parser.add_argument(
            "--host",
            default="0.0.0.0",
            help="Server host (default: 0.0.0.0)"
        )
        serve_parser.add_argument(
            "--port",
            type=int,
            default=8080,
            help="Server port (default: 8080)"
        )
        serve_parser.set_defaults(func=self.cmd_serve)

        # config command
        config_parser = subparsers.add_parser(
            "config",
            help="Show or update configuration"
        )
        config_parser.set_defaults(func=self.cmd_config)

        return parser

    def cmd_add_target(self, args):
        """Add a crawl target."""
        url = args.url.strip()
        target_type = args.type

        if not url.startswith(("http://", "https://")):
            url = "http://" + url

        target = CrawlTarget(
            target_id=str(uuid.uuid4()),
            url=url,
            type=target_type,
            created_at=datetime.utcnow().isoformat() + "Z"
        )

        target = self.database.add_crawl_target(target)

        print(f"{Fore.GREEN}✓ Target added:")
        print(f"  ID: {target.target_id}")
        print(f"  URL: {target.url}")
        print(f"  Type: {target.type}")
        return 0

    def cmd_list_targets(self, args):
        """List all crawl targets."""
        targets = self.database.list_crawl_targets()

        if not targets:
            print(f"{Fore.YELLOW}No targets found.")
            return 0

        table_data = []
        for target in targets:
            table_data.append([
                target.target_id[:8] + "...",
                target.url,
                target.type,
                target.status,
                target.file_count,
                target.last_crawl_at or "-"
            ])

        headers = ["ID", "URL", "Type", "Status", "Files", "Last Crawl"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        return 0

    def cmd_remove_target(self, args):
        """Remove a crawl target."""
        target_id = args.target_id

        if self.database.remove_crawl_target(target_id):
            print(f"{Fore.GREEN}✓ Target removed.")
            return 0
        else:
            print(f"{Fore.RED}✗ Target not found.")
            return 1

    def cmd_crawl(self, args):
        """Crawl targets."""
        target_id = args.target_id
        concurrent = args.concurrent

        if target_id:
            target = self.database.get_crawl_target(target_id)
            if not target:
                print(f"{Fore.RED}✗ Target not found.")
                return 1
            targets = [target]
        else:
            targets = self.database.list_crawl_targets()
            if not targets:
                print(f"{Fore.YELLOW}No targets to crawl.")
                return 0

        print(f"{Fore.CYAN}Starting crawl of {len(targets)} target(s)...")

        results = run_crawl_sync(self.database, self.logger, targets, concurrent)

        total_discovered = sum(r.files_discovered for r in results)
        total_indexed = sum(r.files_indexed for r in results)
        total_errors = sum(r.errors_count for r in results)

        print(f"\n{Fore.GREEN}Crawl completed:")
        print(f"  Files discovered: {total_discovered}")
        print(f"  Files indexed: {total_indexed}")
        print(f"  Errors: {total_errors}")

        return 0

    def cmd_search(self, args):
        """Search the index."""
        query = args.query

        filters = {}
        if args.type:
            filters["file_type"] = args.type
        if args.min_size:
            filters["min_size"] = args.min_size
        if args.max_size:
            filters["max_size"] = args.max_size

        results, total, exec_time = self.search_engine.search(
            query,
            filters=filters,
            sort_by=args.sort,
            limit=args.limit
        )

        if not results:
            print(f"{Fore.YELLOW}No results found for '{query}'")
            return 0

        print(f"{Fore.CYAN}Found {total} results ({exec_time:.0f}ms):\n")

        table_data = []
        for r in results:
            table_data.append([
                r.filename[:40],
                r.extension,
                format_bytes(r.size_bytes),
                r.file_type,
                f"{r.relevance_score:.1f}"
            ])

        headers = ["Filename", "Type", "Size", "Category", "Score"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

        return 0

    def cmd_status(self, args):
        """Show server status."""
        stats = self.database.get_stats()

        print(f"{Fore.CYAN}FilePursuit Status:\n")

        print(f"  Total files indexed: {stats['total_files']}")
        print(f"  Number of targets: {stats['targets_count']}")
        print(f"  Last crawl: {stats['last_crawl'] or 'Never'}")

        if stats['type_distribution']:
            print(f"\n  File types:")
            for file_type, count in sorted(
                stats['type_distribution'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                print(f"    {file_type}: {count}")

        if stats['size_distribution']:
            print(f"\n  Size distribution:")
            for size_cat, count in stats['size_distribution'].items():
                print(f"    {size_cat}: {count}")

        return 0

    def cmd_admin_token(self, args):
        """Manage admin token."""
        if args.regenerate:
            token = self.token_manager.regenerate_token()
            print(f"{Fore.YELLOW}New admin token generated:")
        else:
            token = self.token_manager.get_or_create_token()
            print(f"{Fore.GREEN}Admin token:")

        print(f"  {Fore.BRIGHT}{token}{Style.RESET_ALL}")
        print(f"\nUsage: {Fore.CYAN}curl -H 'Authorization: Bearer {token}' http://localhost:8080/api/targets")

        return 0

    def cmd_config(self, args):
        """Show configuration."""
        print(f"{Fore.CYAN}FilePursuit Configuration:\n")
        print(f"  Database: {self.db_path}")
        print(f"  Log file: {self.log_path}")
        print(f"  Token file: {self.token_path}")

        return 0

    def cmd_serve(self, args):
        """Start HTTP server."""
        host = args.host
        port = args.port

        ui_path = os.path.join(os.path.dirname(__file__), "ui/index.html")

        server = FilePursuitServer(
            self.database,
            self.search_engine,
            self.logger,
            self.token_manager,
            ui_path,
            host,
            port
        )

        try:
            server.start()
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Server stopped.")
            return 0

    def cleanup(self):
        """Cleanup resources."""
        self.database.close()


def main():
    """Main entry point."""
    cli = FilePursuitCLI()
    try:
        return cli.run()
    finally:
        cli.cleanup()


if __name__ == "__main__":
    sys.exit(main())
