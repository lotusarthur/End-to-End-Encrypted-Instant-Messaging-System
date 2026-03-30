import requests
from typing import Optional, Dict, List
from ..shared.constants import API_BASE_PATH

class NetworkClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.token = None

    # 认证相关方法
    def register(self, username: str, password: str, otp_secret: str = None) -> dict:
        """注册用户，返回用户信息"""
        pass

    def login(self, username: str, password: str, otp_code: str = None) -> str:
        """登录，返回 JWT token"""
        pass

    def logout(self) -> None:
        """登出"""
        pass

    def refresh_token(self) -> bool:
        """刷新 token"""
        pass

    # 用户与公钥相关方法
    def get_public_key(self, username: str) -> bytes:
        """获取用户公钥"""
        pass

    def get_my_info(self) -> dict:
        """获取当前用户信息"""
        pass

    # 好友管理相关方法
    def send_friend_request(self, to_user: str) -> str:
        """发送好友请求"""
        pass

    def accept_friend_request(self, request_id: str) -> None:
        """接受好友请求"""
        pass

    def decline_friend_request(self, request_id: str) -> None:
        """拒绝好友请求"""
        pass

    def cancel_friend_request(self, request_id: str) -> None:
        """取消好友请求"""
        pass

    def get_friend_requests(self, request_type: str = "received") -> list:
        """获取好友请求列表"""
        pass

    def get_friends(self) -> list:
        """获取好友列表"""
        pass

    def remove_friend(self, username: str) -> None:
        """删除好友"""
        pass

    def block_user(self, username: str) -> None:
        """屏蔽用户"""
        pass

    # 消息相关方法
    def send_message(self, to_user: str, ciphertext: bytes, ttl: int) -> str:
        """发送消息"""
        pass

    def fetch_offline_messages(self) -> list:
        """获取离线消息"""
        pass

    # 辅助方法
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """发送 HTTP 请求"""
        pass

    def _get_auth_headers(self) -> dict:
        """获取认证头"""
        pass