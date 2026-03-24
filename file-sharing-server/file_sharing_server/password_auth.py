"""Enhanced authentication with optional password support."""

import hashlib
import secrets
from pathlib import Path
from typing import Optional, Tuple


class PasswordHasher:
    """Secure password hashing using PBKDF2."""

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> str:
        """
        Hash password using PBKDF2.

        Args:
            password: Password to hash
            salt: Salt string (generated if not provided)

        Returns:
            "salt:hash" format for storage
        """
        if salt is None:
            salt = secrets.token_hex(16)

        hash_obj = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            iterations=100000,
        )
        password_hash = hash_obj.hex()
        return f"{salt}:{password_hash}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """
        Verify password against stored hash.

        Args:
            password: Password to verify
            stored_hash: Stored hash in "salt:hash" format

        Returns:
            True if password matches
        """
        try:
            salt, _ = stored_hash.split(":")
            computed = PasswordHasher.hash_password(password, salt)
            return computed == stored_hash
        except (ValueError, AttributeError):
            return False


class SharePasswordManager:
    """Manage optional password protection for shares."""

    def __init__(self, data_dir: Path):
        """
        Initialize password manager.

        Args:
            data_dir: Data directory for storing password hashes
        """
        self.data_dir = Path(data_dir)
        self.password_file = self.data_dir / "share_passwords.json"

    def set_password(self, share_id: str, password: str) -> bool:
        """
        Set password for a share.

        Args:
            share_id: Share ID
            password: Plain text password

        Returns:
            True if successful
        """
        import json

        try:
            passwords = {}
            if self.password_file.exists():
                passwords = json.loads(self.password_file.read_text())

            passwords[share_id] = PasswordHasher.hash_password(password)
            self.password_file.write_text(json.dumps(passwords))
            self.password_file.chmod(0o600)
            return True
        except Exception:
            return False

    def verify_password(self, share_id: str, password: str) -> bool:
        """
        Verify password for a share.

        Args:
            share_id: Share ID
            password: Plain text password to verify

        Returns:
            True if password is correct
        """
        import json

        try:
            if not self.password_file.exists():
                return False

            passwords = json.loads(self.password_file.read_text())
            stored_hash = passwords.get(share_id)
            if not stored_hash:
                return False

            return PasswordHasher.verify_password(password, stored_hash)
        except Exception:
            return False

    def remove_password(self, share_id: str) -> bool:
        """
        Remove password for a share.

        Args:
            share_id: Share ID

        Returns:
            True if successful
        """
        import json

        try:
            if not self.password_file.exists():
                return False

            passwords = json.loads(self.password_file.read_text())
            passwords.pop(share_id, None)
            self.password_file.write_text(json.dumps(passwords))
            return True
        except Exception:
            return False

    def has_password(self, share_id: str) -> bool:
        """
        Check if a share has password protection.

        Args:
            share_id: Share ID

        Returns:
            True if share is password protected
        """
        import json

        try:
            if not self.password_file.exists():
                return False

            passwords = json.loads(self.password_file.read_text())
            return share_id in passwords
        except Exception:
            return False
