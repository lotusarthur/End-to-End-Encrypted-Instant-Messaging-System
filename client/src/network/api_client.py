"""API client for HTTP operations."""
import requests
import base64
from typing import Optional, Dict, List

import os
import sys
# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from shared.constants import API_BASE_PATH


class NetworkClient:
    """HTTP client for messaging API."""
    
    def __init__(self, server_url: str):
        """Initialize API client."""
        self.server_url = server_url
        self.token = None

    # Authentication methods
    def register(self, username: str, password: str, otp_secret: str = None) -> dict:
        """Register a new user."""
        payload = {"username": username, "password": password}
        if otp_secret is not None:
            payload["otp_secret"] = otp_secret
        return self._make_request("POST", "/users", payload)

    def login(self, username: str, password: str, otp_code: str = None) -> str:
        """Login and get JWT token."""
        payload = {"username": username, "password": password}
        if otp_code is not None:
            payload["otp_code"] = otp_code
        result = self._make_request("POST", "/auth/login", payload)
        self.token = result.get("token")
        if not self.token:
            raise RuntimeError("login response missing token")
        return self.token

    def logout(self) -> None:
        """Logout."""
        self._make_request("POST", "/auth/logout")
        self.token = None

    def refresh_token(self) -> bool:
        """Refresh JWT token."""
        if not self.token:
            return False
        try:
            result = self._make_request("POST", "/auth/refresh")
            token = result.get("token")
            if token:
                self.token = token
                return True
        except Exception:
            return False
        return False

    # User and public key methods
    def get_public_key(self, username: str) -> bytes:
        """Get user public key."""
        result = self._make_request("GET", f"/users/{username}/public-key")
        key_b64 = result.get("identity_public_key")
        if not key_b64:
            raise RuntimeError("public key missing")
        return base64.b64decode(key_b64)

    def get_my_info(self) -> dict:
        """Get current user info."""
        return self._make_request("GET", "/users/me")

    # Friend management methods
    def send_friend_request(self, to_user: str) -> str:
        """Send friend request."""
        result = self._make_request("POST", "/friend-requests", {"to_user": to_user})
        return result["request_id"]

    def accept_friend_request(self, request_id: str) -> None:
        """Accept friend request."""
        self._make_request("PUT", f"/friend-requests/{request_id}", {"status": "accepted"})

    def decline_friend_request(self, request_id: str) -> None:
        """Decline friend request."""
        self._make_request("PUT", f"/friend-requests/{request_id}", {"status": "declined"})

    def cancel_friend_request(self, request_id: str) -> None:
        """Cancel friend request."""
        self._make_request("DELETE", f"/friend-requests/{request_id}")

    def get_friend_requests(self, request_type: str = "received") -> list:
        """Get friend requests."""
        result = self._make_request("GET", f"/friend-requests?type={request_type}")
        return result.get("requests", [])

    def get_friends(self) -> list:
        """Get friends list."""
        result = self._make_request("GET", "/friends")
        return result.get("friends", [])

    def remove_friend(self, username: str) -> None:
        """Remove a friend."""
        self._make_request("DELETE", f"/friends/{username}")

    def block_user(self, username: str) -> None:
        """Block a user."""
        self._make_request("POST", f"/friends/{username}/block")

    # Message methods
    def send_message(self, to_user: str, ciphertext: bytes, ttl: int) -> str:
        """Send a message."""
        result = self._make_request(
            "POST",
            "/messages",
            {
                "to": to_user,
                "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
                "ttl_seconds": ttl,
            },
        )
        return result["message_id"]

    def fetch_offline_messages(self) -> list:
        """Fetch offline messages."""
        result = self._make_request("GET", "/messages/offline")
        return result.get("messages", [])

    # Helper methods
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make HTTP request."""
        url = f"{self.server_url.rstrip('/')}{API_BASE_PATH}{endpoint}"
        headers = self._get_auth_headers()
        resp = requests.request(method=method, url=url, json=data, headers=headers, timeout=20)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
        if not resp.content:
            return {}
        return resp.json()

    def _get_auth_headers(self) -> dict:
        """Get authentication headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers