from typing import Optional, List, Dict
from ..network.api_client import NetworkClient
from ..crypto.message_crypto import MessageCrypto
from ..crypto.session import SessionManager
from ..shared.protocol.message_types import PlainMessage

class ChatFacade:
    def __init__(self, network: NetworkClient, crypto: MessageCrypto, session_mgr: SessionManager, db_path: str):
        self.network = network
        self.crypto = crypto
        self.session_mgr = session_mgr
        self.db_path = db_path

    # 认证与初始化
    def login(self, username: str, password: str, otp_code: str = None) -> bool:
        """登录，获取 token，初始化本地密钥等"""
        pass

    def register(self, username: str, password: str, otp_secret: str = None) -> bool:
        """注册，并生成本地身份密钥对"""
        pass

    def logout(self) -> None:
        """登出"""
        pass

    # 好友管理
    def search_user(self, username: str) -> Optional[dict]:
        """查找用户，返回基本信息"""
        pass

    def send_friend_request(self, username: str) -> str:
        """发送好友请求，返回 request_id"""
        pass

    def accept_friend_request(self, request_id: str) -> None:
        """接受请求后，自动建立加密会话"""
        pass

    def decline_friend_request(self, request_id: str) -> None:
        """拒绝好友请求"""
        pass

    def get_pending_requests(self) -> list:
        """获取待处理的好友请求（包括发送和接收）"""
        pass

    def get_friends(self) -> list:
        """返回好友列表（包含用户名、指纹等）"""
        pass

    def remove_friend(self, username: str) -> None:
        """删除好友，同时删除本地会话和消息"""
        pass

    # 消息功能
    def send_text_message(self, to_user: str, text: str, ttl_seconds: int = 30) -> str:
        """发送文本消息，返回本地消息 ID"""
        pass

    def get_conversations(self) -> list:
        """返回会话列表，按最后消息时间排序，包含未读数、最后消息预览"""
        pass

    def get_messages(self, peer_user_id: str, limit: int = 50, offset: int = 0) -> list:
        """获取与某个好友的消息历史（按时间升序）"""
        pass

    def mark_messages_read(self, peer_user_id: str) -> None:
        """将与该好友的未读消息标记为已读"""
        pass

    # 安全功能
    def get_contact_fingerprint(self, peer_user_id: str) -> str:
        """获取联系人的指纹"""
        pass

    def verify_contact_identity(self, peer_user_id: str, expected_fingerprint: str) -> bool:
        """验证联系人身份"""
        pass

    # 内部方法
    def _initialize_session(self, peer_user_id: str) -> str:
        """初始化加密会话"""
        pass

    def _save_message_locally(self, message: PlainMessage) -> None:
        """本地保存消息"""
        pass

    def _sync_offline_messages(self) -> None:
        """同步离线消息"""
        pass