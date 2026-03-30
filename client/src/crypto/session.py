from typing import Optional
from ..shared.protocol.message_types import Session

class SessionManager:
    def __init__(self, storage_path: str):
        """初始化会话管理器"""
        self.storage_path = storage_path

    def create_outbound_session(self, peer_user_id: str, peer_public_key: bytes) -> str:
        """
        发起与对方的会话（调用 DH 交换等），返回 session_id。
        该 session_id 用于后续加密。
        """
        pass

    def create_inbound_session(self, peer_user_id: str, initiator_public_key: bytes) -> str:
        """
        响应对方的会话建立请求，返回 session_id。
        """
        pass

    def get_session(self, session_id: str) -> Session:
        """获取会话对象（用于加密/解密）"""
        pass

    def get_session_by_peer(self, peer_user_id: str) -> Optional[Session]:
        """获取与指定用户的已有会话"""
        pass

    def delete_session(self, session_id: str) -> None:
        """删除会话（例如用户屏蔽时）"""
        pass

    def update_session_counter(self, session_id: str, is_send: bool) -> None:
        """更新会话计数器"""
        pass

    def list_sessions(self) -> list[str]:
        """获取所有会话的ID列表"""
        pass