from typing import Dict, Optional


class SessionManager:
    def __init__(self, storage):
        self.storage = storage
        self._active_conversation_id: Optional[str] = None

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        for conv in self.storage.list_conversations():
            if conv.get("conversation_id") == conversation_id:
                return conv
        return None

    def get_or_create_conversation(self, conversation_id: str, peer_user_id: str) -> Dict:
        conv = self.get_conversation(conversation_id)
        if conv:
            return conv

        conv = {
            "conversation_id": conversation_id,
            "peer_user_id": peer_user_id,
            "last_message": "",
            "unread_count": 0,
        }
        self.storage.upsert_conversation(conv)
        return conv

    def set_active_conversation(self, conversation_id: Optional[str]) -> None:
        self._active_conversation_id = conversation_id
        if conversation_id:
            self.storage.clear_unread(conversation_id)

    def get_active_conversation(self) -> Optional[str]:
        return self._active_conversation_id
