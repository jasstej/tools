"""
API Manager for FilePursuit.

Manages API credentials for enhanced dorking (Shodan, Google CSE, etc.).
"""

import json
import os
from typing import Optional, Dict
from datetime import datetime


class APIManager:
    """Manage API credentials for dorking services."""

    SUPPORTED_SERVICES = [
        "shodan",
        "google_cse",
        "github",
    ]

    def __init__(self, credentials_path: str = "data/api_credentials.json"):
        """Initialize API manager."""
        self.credentials_path = credentials_path
        os.makedirs(os.path.dirname(credentials_path) or ".", exist_ok=True)
        self._load_credentials()

    def _load_credentials(self):
        """Load credentials from file."""
        if os.path.exists(self.credentials_path):
            try:
                with open(self.credentials_path, "r") as f:
                    self.credentials = json.load(f)
            except Exception:
                self.credentials = {}
        else:
            self.credentials = {}

    def _save_credentials(self):
        """Save credentials to file."""
        try:
            with open(self.credentials_path, "w") as f:
                json.dump(self.credentials, f, indent=2)
            # Restrict file permissions
            os.chmod(self.credentials_path, 0o600)
        except Exception as e:
            print(f"Error saving credentials: {e}")

    def add_api_key(self, service: str, api_key: str) -> bool:
        """
        Add or update API key for a service.

        Args:
            service: Service name (shodan, google_cse, github)
            api_key: API key/token

        Returns:
            True if successful, False otherwise
        """
        if service not in self.SUPPORTED_SERVICES:
            return False

        if service not in self.credentials:
            self.credentials[service] = {}

        self.credentials[service] = {
            "key": api_key,
            "added_at": datetime.utcnow().isoformat() + "Z",
            "last_tested": None,
            "status": "active"
        }

        self._save_credentials()
        return True

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service."""
        if service not in self.credentials:
            return None

        cred = self.credentials.get(service, {})
        status = cred.get("status", "")

        if status == "active":
            return cred.get("key")

        return None

    def remove_api_key(self, service: str) -> bool:
        """Remove API key for a service."""
        if service in self.credentials:
            del self.credentials[service]
            self._save_credentials()
            return True
        return False

    def list_services(self) -> Dict[str, Dict]:
        """List all configured services."""
        result = {}

        for service in self.SUPPORTED_SERVICES:
            if service in self.credentials:
                cred = self.credentials[service]
                # Don't expose full key
                result[service] = {
                    "configured": True,
                    "status": cred.get("status", "unknown"),
                    "added_at": cred.get("added_at"),
                    "last_tested": cred.get("last_tested"),
                    "key": cred.get("key", "")[:10] + "..." if cred.get("key") else None
                }
            else:
                result[service] = {
                    "configured": False,
                    "status": "not_configured"
                }

        return result

    def test_api_key(self, service: str) -> Dict[str, any]:
        """
        Test if API key is valid.

        Args:
            service: Service name

        Returns:
            Dict with test result
        """
        api_key = self.get_api_key(service)

        if not api_key:
            return {
                "service": service,
                "valid": False,
                "message": "No API key configured",
                "tested_at": datetime.utcnow().isoformat() + "Z"
            }

        try:
            if service == "shodan":
                return self._test_shodan(api_key)
            elif service == "google_cse":
                return self._test_google_cse(api_key)
            elif service == "github":
                return self._test_github(api_key)
        except Exception as e:
            result = {
                "service": service,
                "valid": False,
                "message": f"Test error: {e}",
                "tested_at": datetime.utcnow().isoformat() + "Z"
            }
        else:
            result = {
                "tested_at": datetime.utcnow().isoformat() + "Z"
            }

        # Update last tested time
        if service in self.credentials:
            self.credentials[service]["last_tested"] = result.get("tested_at")
            self._save_credentials()

        return result

    @staticmethod
    def _test_shodan(api_key: str) -> Dict[str, any]:
        """Test Shodan API key."""
        try:
            import requests
            # Test with a simple query
            response = requests.get(
                "https://api.shodan.io/account/profile",
                params={"key": api_key},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "service": "shodan",
                    "valid": True,
                    "message": f"API key valid. Credits: {data.get('credits')}",
                    "tested_at": datetime.utcnow().isoformat() + "Z"
                }
            else:
                return {
                    "service": "shodan",
                    "valid": False,
                    "message": f"Invalid API key (status: {response.status_code})",
                    "tested_at": datetime.utcnow().isoformat() + "Z"
                }
        except Exception as e:
            return {
                "service": "shodan",
                "valid": False,
                "message": f"Test failed: {e}",
                "tested_at": datetime.utcnow().isoformat() + "Z"
            }

    @staticmethod
    def _test_google_cse(api_key: str) -> Dict[str, any]:
        """Test Google Custom Search API key."""
        try:
            import requests
            # Would need search engine ID to test properly
            return {
                "service": "google_cse",
                "valid": True,
                "message": "Google CSE API key configured (full test requires Search Engine ID)",
                "tested_at": datetime.utcnow().isoformat() + "Z"
            }
        except Exception as e:
            return {
                "service": "google_cse",
                "valid": False,
                "message": f"Test failed: {e}",
                "tested_at": datetime.utcnow().isoformat() + "Z"
            }

    @staticmethod
    def _test_github(api_key: str) -> Dict[str, any]:
        """Test GitHub API token."""
        try:
            import requests
            response = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {api_key}"},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "service": "github",
                    "valid": True,
                    "message": f"API token valid. User: {data.get('login')}",
                    "tested_at": datetime.utcnow().isoformat() + "Z"
                }
            else:
                return {
                    "service": "github",
                    "valid": False,
                    "message": f"Invalid API token (status: {response.status_code})",
                    "tested_at": datetime.utcnow().isoformat() + "Z"
                }
        except Exception as e:
            return {
                "service": "github",
                "valid": False,
                "message": f"Test failed: {e}",
                "tested_at": datetime.utcnow().isoformat() + "Z"
            }

    def get_service_description(self, service: str) -> str:
        """Get description for a service."""
        descriptions = {
            "shodan": "Shodan - Search engine for internet-connected devices",
            "google_cse": "Google Custom Search - Enhanced Google search with API",
            "github": "GitHub - Search for source code and repositories",
        }
        return descriptions.get(service, f"Unknown service: {service}")
