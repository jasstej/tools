"""Authentication and token management."""

import uuid
import json
from pathlib import Path
from typing import Optional


class TokenManager:
    """Generate and validate access tokens."""

    @staticmethod
    def generate_token() -> str:
        """Generate a new UUID-based access token."""
        return str(uuid.uuid4())

    @staticmethod
    def validate_token(token: str) -> bool:
        """
        Validate token format (basic UUID check).

        Args:
            token: Token string to validate

        Returns:
            True if valid UUID format
        """
        try:
            uuid.UUID(token)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def generate_master_token() -> str:
        """Generate a master token for admin access."""
        return str(uuid.uuid4())


class MasterTokenManager:
    """Manage master token for admin access."""

    def __init__(self, token_file: Path):
        """
        Initialize master token manager.

        Args:
            token_file: Path to store master token
        """
        self.token_file = Path(token_file)

    def get_or_create(self) -> str:
        """
        Get existing master token or create new one.

        Returns:
            Master token string
        """
        if self.token_file.exists():
            try:
                return self.token_file.read_text().strip()
            except Exception:
                pass

        # Create new master token
        token = TokenManager.generate_master_token()
        try:
            self.token_file.write_text(token)
            self.token_file.chmod(0o600)  # Restrict to owner only
        except Exception as e:
            print(f"Warning: Could not save master token: {e}")

        return token

    def validate(self, token: str) -> bool:
        """
        Validate master token.

        Args:
            token: Token to validate

        Returns:
            True if token matches master token
        """
        if not self.token_file.exists():
            return False

        try:
            stored_token = self.token_file.read_text().strip()
            return token == stored_token
        except Exception:
            return False
