import sqlite3
from typing import List, Dict, Optional
from ..shared.protocol.message_types import PlainMessage

class LocalDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        pass

    def save_message(self, message: PlainMessage) -> None:
        """保存消息到本地数据库"""
        pass

    def get_messages(self, peer_user_id: str, limit: int = 50, offset: int = 0) -> List[PlainMessage]:
        """获取与指定用户的消息"""
        pass

    def get_conversations(self) -> List[Dict]:
        """获取会话列表"""
        pass

    def mark_messages_read(self, peer_user_id: str) -> None:
        """标记消息为已读"""
        pass

    def delete_conversation(self, peer_user_id: str) -> None:
        """删除整个会话"""
        pass

    def get_unread_count(self, peer_user_id: str) -> int:
        """获取未读消息数量"""
        pass