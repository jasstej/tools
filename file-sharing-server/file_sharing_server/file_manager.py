"""Share and file management."""

import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass, asdict

from .auth import TokenManager
from .utils import safe_join_path, validate_directory_path


@dataclass
class Share:
    """Represents a shared directory."""

    id: str
    path: str
    token: str
    created: str
    expires: Optional[str] = None
    max_file_size_mb: int = 500
    allowed_extensions: List[str] = None
    description: str = ""
    webhook_url: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        if self.allowed_extensions is None:
            data["allowed_extensions"] = []
        return data

    def is_expired(self) -> bool:
        """Check if share has expired."""
        if self.expires is None:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires.replace("Z", "+00:00"))
            return datetime.utcnow() > expiry.replace(tzinfo=None)
        except Exception:
            return False


class ShareManager:
    """Manage file shares."""

    def __init__(self, data_dir: Path):
        """
        Initialize share manager.

        Args:
            data_dir: Directory to store share metadata and uploads
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.shares_file = self.data_dir / "shares.json"
        self.uploads_dir = self.data_dir / "uploads"
        self.uploads_dir.mkdir(exist_ok=True)
        self._load_shares()

    def _load_shares(self) -> None:
        """Load shares from JSON file."""
        self.shares = {}
        if not self.shares_file.exists():
            return

        try:
            data = json.loads(self.shares_file.read_text())
            for share_data in data.get("shares", []):
                share = Share(**share_data)
                self.shares[share.id] = share
        except Exception as e:
            print(f"Warning: Could not load shares: {e}")

    def _save_shares(self) -> None:
        """Save shares to JSON file."""
        try:
            data = {
                "shares": [share.to_dict() for share in self.shares.values()],
                "updated": datetime.utcnow().isoformat() + "Z",
            }
            self.shares_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Warning: Could not save shares: {e}")

    def add_share(
        self,
        path: str,
        description: str = "",
        max_file_size_mb: int = 500,
        allowed_extensions: list = None,
        expires_in_hours: int = None,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Add a new share.

        Args:
            path: Directory path to share
            description: Share description
            max_file_size_mb: Max file size limit
            allowed_extensions: List of allowed file extensions
            expires_in_hours: Auto-expire after N hours (None = never)

        Returns:
            Tuple of (success, message, token)
        """
        # Validate path
        valid, error = validate_directory_path(path)
        if not valid:
            return False, error, None

        # Generate share ID and token
        share_id = TokenManager.generate_token()
        token = TokenManager.generate_token()

        expiry = None
        if expires_in_hours:
            expiry_dt = datetime.utcnow() + timedelta(hours=expires_in_hours)
            expiry = expiry_dt.isoformat() + "Z"

        share = Share(
            id=share_id,
            path=path,
            token=token,
            created=datetime.utcnow().isoformat() + "Z",
            expires=expiry,
            max_file_size_mb=max_file_size_mb,
            allowed_extensions=allowed_extensions or [],
            description=description,
        )

        self.shares[share_id] = share
        self._save_shares()

        return True, f"Share created: {share_id}", token

    def get_share(self, share_id: str) -> Optional[Share]:
        """Get share by ID."""
        return self.shares.get(share_id) if not self.shares.get(share_id, Share("", "", "", "")).is_expired() else None

    def remove_share(self, share_id: str) -> tuple[bool, str]:
        """Remove a share."""
        if share_id not in self.shares:
            return False, f"Share not found: {share_id}"

        del self.shares[share_id]
        self._save_shares()

        # Clean up upload directory
        upload_dir = self.uploads_dir / share_id
        if upload_dir.exists():
            try:
                shutil.rmtree(upload_dir)
            except Exception as e:
                print(f"Warning: Could not remove upload dir: {e}")

        return True, f"Share removed: {share_id}"

    def list_shares(self) -> List[dict]:
        """List all active shares."""
        active = []
        for share in self.shares.values():
            if not share.is_expired():
                data = share.to_dict()
                data["status"] = "active"
                active.append(data)
        return active

    def explore_directory(self, share_id: str, rel_path: str = "") -> tuple[bool, dict]:
        """
        Explore a directory within a share.

        Args:
            share_id: Share ID
            rel_path: Relative path within share

        Returns:
            Tuple of (success, directory listing dict)
        """
        share = self.get_share(share_id)
        if not share:
            return False, {"error": "Share not found or expired"}

        try:
            base_path = Path(share.path)
            target_path = safe_join_path(base_path, rel_path) if rel_path else base_path

            if not target_path.exists():
                return False, {"error": "Path not found"}

            if not target_path.is_dir():
                return False, {"error": "Path is not a directory"}

            # List directory contents
            items = []
            for item in sorted(target_path.iterdir()):
                if item.name.startswith("."):
                    continue  # Skip hidden files

                is_dir = item.is_dir()
                item_data = {
                    "name": item.name,
                    "type": "dir" if is_dir else "file",
                    "size": None if is_dir else item.stat().st_size,
                    "path": str(item.relative_to(base_path)),
                }
                items.append(item_data)

            return True, {"path": str(target_path.relative_to(base_path)), "items": items}
        except Exception as e:
            return False, {"error": str(e)}

    def upload_file(
        self,
        share_id: str,
        user_token: str,
        filename: str,
        file_content: bytes,
        rel_path: str = "",
    ) -> tuple[bool, str]:
        """
        Upload a file to a share.

        Args:
            share_id: Share ID
            user_token: User's access token
            filename: Filename
            file_content: File bytes
            rel_path: Upload relative path (for nested folders)

        Returns:
            Tuple of (success, message)
        """
        share = self.get_share(share_id)
        if not share:
            return False, "Share not found or expired"

        # Check file size
        if len(file_content) > share.max_file_size_mb * 1024 * 1024:
            return False, f"File exceeds size limit ({share.max_file_size_mb}MB)"

        # Check extension
        from .utils import validate_file_extension

        if share.allowed_extensions and not validate_file_extension(
            filename, share.allowed_extensions
        ):
            return False, f"File type not allowed: {filename}"

        # Create user's upload directory
        user_upload_dir = self.uploads_dir / share_id / user_token[:8]
        if rel_path:
            user_upload_dir = user_upload_dir / rel_path
        user_upload_dir.mkdir(parents=True, exist_ok=True)

        # Validate upload path
        try:
            upload_path = safe_join_path(user_upload_dir, filename)
        except ValueError as e:
            return False, f"Invalid filename: {str(e)}"

        # Save file
        try:
            upload_path.write_bytes(file_content)
            return True, f"File uploaded: {filename}"
        except Exception as e:
            return False, f"Upload failed: {str(e)}"

    def download_file(
        self, share_id: str, file_path: str
    ) -> tuple[bool, Optional[bytes], str]:
        """
        Download a file from shared directory.

        Args:
            share_id: Share ID
            file_path: Relative path within share

        Returns:
            Tuple of (success, file_content, message)
        """
        share = self.get_share(share_id)
        if not share:
            return False, None, "Share not found or expired"

        try:
            base_path = Path(share.path)
            target_path = safe_join_path(base_path, file_path)

            if not target_path.exists():
                return False, None, "File not found"

            if not target_path.is_file():
                return False, None, "Path is not a file"

            content = target_path.read_bytes()
            return True, content, "OK"
        except ValueError as e:
            return False, None, f"Invalid path: {str(e)}"
        except Exception as e:
            return False, None, f"Download failed: {str(e)}"

    def create_folder(
        self, share_id: str, user_token: str, folder_path: str
    ) -> tuple[bool, str]:
        """
        Create a folder in user uploads.

        Args:
            share_id: Share ID
            user_token: User's access token
            folder_path: Folder path to create (e.g., "projects/myproj")

        Returns:
            Tuple of (success, message)
        """
        share = self.get_share(share_id)
        if not share:
            return False, "Share not found or expired"

        try:
            user_upload_dir = self.uploads_dir / share_id / user_token[:8]
            target_path = safe_join_path(user_upload_dir, folder_path)
            target_path.mkdir(parents=True, exist_ok=True)
            return True, f"Folder created: {folder_path}"
        except Exception as e:
            return False, f"Failed to create folder: {str(e)}"

    def cleanup_expired(self) -> int:
        """
        Remove expired shares.

        Returns:
            Number of shares removed
        """
        expired = [
            share_id for share_id, share in self.shares.items() if share.is_expired()
        ]

        for share_id in expired:
            self.remove_share(share_id)

        return len(expired)
