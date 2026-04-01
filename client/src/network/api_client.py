import requests
import base64
from typing import Optional, Dict, List
try:
    from shared.constants import API_BASE_PATH
except ImportError:
    from ...shared.constants import API_BASE_PATH

class NetworkClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.token = None

    # 认证相关方法
    def register(self, username: str, password: str, otp_secret: str = None) -> dict:
        """注册用户，返回用户信息"""
        payload = {"username": username, "password": password}
        if otp_secret is not None:
            payload["otp_secret"] = otp_secret
        return self._make_request("POST", "/users", payload)

    def login(self, username: str, password: str, otp_code: str = None) -> str:
        """登录，返回 JWT token"""
        payload = {"username": username, "password": password}
        if otp_code is not None:
            payload["otp_code"] = otp_code
        result = self._make_request("POST", "/auth/login", payload)
        self.token = result.get("token")
        if not self.token:
            raise RuntimeError("login response missing token")
        return self.token

    def logout(self) -> None:
        """登出"""
        self._make_request("POST", "/auth/logout")
        self.token = None

    def refresh_token(self) -> bool:
        """刷新 token"""
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

    # 用户与公钥相关方法
    def get_public_key(self, username: str) -> bytes:
        """获取用户公钥"""
        result = self._make_request("GET", f"/users/{username}/public-key")
        key_b64 = result.get("identity_public_key")
        if not key_b64:
            raise RuntimeError("public key missing")
        return base64.b64decode(key_b64)

    def get_my_info(self) -> dict:
        """获取当前用户信息"""
        return self._make_request("GET", "/users/me")

    # 好友管理相关方法
    def send_friend_request(self, to_user: str) -> str:
        """发送好友请求"""
        result = self._make_request("POST", "/friend-requests", {"to_user": to_user})
        return result["request_id"]

    def accept_friend_request(self, request_id: str) -> None:
        """接受好友请求"""
        self._make_request("PUT", f"/friend-requests/{request_id}", {"status": "accepted"})

    def decline_friend_request(self, request_id: str) -> None:
        """拒绝好友请求"""
        self._make_request("PUT", f"/friend-requests/{request_id}", {"status": "declined"})

    def cancel_friend_request(self, request_id: str) -> None:
        """取消好友请求"""
        self._make_request("DELETE", f"/friend-requests/{request_id}")

    def get_friend_requests(self, request_type: str = "received") -> list:
        """获取好友请求列表"""
        result = self._make_request("GET", f"/friend-requests?type={request_type}")
        return result.get("requests", [])

    def get_friends(self) -> list:
        """获取好友列表"""
        result = self._make_request("GET", "/friends")
        return result.get("friends", [])

    def remove_friend(self, username: str) -> None:
        """删除好友"""
        self._make_request("DELETE", f"/friends/{username}")

    def block_user(self, username: str) -> None:
        """屏蔽用户"""
        self._make_request("POST", f"/friends/{username}/block")

    # 消息相关方法
    def send_message(self, to_user: str, ciphertext: bytes, ttl: int) -> str:
        """发送消息"""
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
        """获取离线消息"""
        result = self._make_request("GET", "/messages/offline")
        return result.get("messages", [])

    # 辅助方法
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """发送 HTTP 请求"""
        url = f"{self.server_url.rstrip('/')}{API_BASE_PATH}{endpoint}"
        headers = self._get_auth_headers()
        resp = requests.request(method=method, url=url, json=data, headers=headers, timeout=20)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
        if not resp.content:
            return {}
        return resp.json()

    def _get_auth_headers(self) -> dict:
        """获取认证头"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
