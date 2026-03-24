"""Main entry point for python -m execution."""

try:
    # For normal Python execution
    from .main import main
except ImportError:
    # For PyInstaller bundled executable
    from file_sharing_server.main import main

import sys

if __name__ == "__main__":
    sys.exit(main())
