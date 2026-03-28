"""
Authentication module for FilePursuit.

Handles admin token generation and validation.
"""

import os
import uuid
from typing import Optional


class MasterTokenManager:
    """Manages master admin token."""

    def __init__(self, token_path: str = "data/master_token.txt"):
        """Initialize token manager."""
        self.token_path = token_path
        os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)

    def get_or_create_token(self) -> str:
        """Get existing token or create new one."""
        if os.path.exists(self.token_path):
            with open(self.token_path, "r") as f:
                token = f.read().strip()
                if token:
                    return token

        # Generate new token
        token = str(uuid.uuid4())
        self._save_token(token)
        return token

    def regenerate_token(self) -> str:
        """Generate a new token (invalidates old one)."""
        token = str(uuid.uuid4())
        self._save_token(token)
        return token

    def validate_token(self, token: str) -> bool:
        """Validate provided token."""
        if not token:
            return False

        if not os.path.exists(self.token_path):
            return False

        try:
            with open(self.token_path, "r") as f:
                stored_token = f.read().strip()
                return token == stored_token
        except Exception:
            return False

    def _save_token(self, token: str) -> None:
        """Save token to file with restricted permissions."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.token_path) or ".", exist_ok=True)

        # Write token
        with open(self.token_path, "w") as f:
            f.write(token)

        # Set restrictive permissions (owner read/write only)
        os.chmod(self.token_path, 0o600)

    def get_token(self) -> str:
        """Get current token without creating new one."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, "r") as f:
                    token = f.read().strip()
                    if token:
                        return token
            except Exception:
                pass
        return ""
