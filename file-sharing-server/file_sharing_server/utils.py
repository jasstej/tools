"""Utility functions for path validation and file operations."""

import os
from pathlib import Path
from typing import Tuple


def safe_join_path(base: Path, *parts: str) -> Path:
    """
    Safely join path parts, preventing directory traversal.

    Args:
        base: Base directory path
        parts: Path components to join

    Returns:
        Resolved path if safe (within base), otherwise raises ValueError
    """
    # Prevent absolute paths in parts
    for part in parts:
        if os.path.isabs(part):
            raise ValueError(f"Absolute paths not allowed: {part}")
        if ".." in part or part.startswith("/"):
            raise ValueError(f"Directory traversal not allowed: {part}")

    base = Path(base).resolve()
    result = (base / Path(*parts)).resolve()

    # Ensure result is within base
    if not str(result).startswith(str(base)):
        raise ValueError(f"Path escapes base directory: {result}")

    return result


def validate_file_extension(filename: str, allowed_extensions: list[str] = None) -> bool:
    """
    Validate file extension against allowed list.

    Args:
        filename: Filename to validate
        allowed_extensions: List of allowed extensions (None = all allowed)

    Returns:
        True if allowed, False otherwise
    """
    if allowed_extensions is None or not allowed_extensions:
        return True  # No restrictions

    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in [e.lower() for e in allowed_extensions]


def validate_directory_path(path: str) -> Tuple[bool, str]:
    """
    Validate that a directory path is safe and accessible.

    Args:
        path: Directory path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        p = Path(path).resolve()

        if not p.exists():
            return False, f"Directory does not exist: {path}"

        if not p.is_dir():
            return False, f"Path is not a directory: {path}"

        if not os.access(p, os.R_OK):
            return False, f"Directory not readable: {path}"

        return True, ""
    except Exception as e:
        return False, str(e)


def get_human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def validate_token_format(token: str) -> bool:
    """Validate token format (UUID)."""
    if len(token) != 36:
        return False
    parts = token.split("-")
    if len(parts) != 5:
        return False
    # Basic UUID format check
    return all(len(p) == expected for p, expected in zip(parts, [8, 4, 4, 4, 12]))
