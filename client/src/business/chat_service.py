import time
import uuid

from .errors import ConversationNotFoundError, ValidationError


class ChatService:
    def __init__(self, crypto, api_client, storage, event_bus, session_manager):
        self.crypto = crypto
        self.api_client = api_client
        self.storage = storage
        self.event_bus = event_bus
        self.session_manager = session_manager

    def send_text_message(self, conversation_id: str, text: str, ttl: int = 30):
        """
        Agreed flow:
        business calls crypto.encrypt(text, ttl)
        crypto returns encrypted package
        business wraps it into envelope and sends via network
        """
        if not conversation_id:
            raise ValidationError("conversation_id required")
        if not text or not text.strip():
            raise ValidationError("text required")
        if ttl <= 0:
            raise ValidationError("ttl must be positive")

        conversation = self.session_manager.get_conversation(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(f"conversation not found: {conversation_id}")

        message_id = str(uuid.uuid4())
        now = int(time.time())

        # 本地
        local_msg = {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "recipient_id": conversation["peer_user_id"],
            "direction": "outgoing",
            "text": text,
            "status": "sending",
            "ttl": ttl,
            "created_at": now,
        }
        self.storage.save_message(local_msg)
        self.event_bus.emit("chat.message_local_created", local_msg)

        try:
            encrypted_pkg = self.crypto.encrypt(text, ttl)

            envelope = {
                "type": "text",
                "message_id": message_id,
                "conversation_id": conversation_id,
                "recipient_id": conversation["peer_user_id"],
                "encrypted_pkg": encrypted_pkg,
                "ttl": ttl,
                "client_time": now,
            }

            resp = self.api_client.send_message(envelope)

            local_msg["status"] = "sent"
            local_msg["server_time"] = resp.get("server_time")
            self.storage.save_message(local_msg)

            conversation["last_message"] = text
            self.storage.upsert_conversation(conversation)

            self.event_bus.emit("chat.message_sent", local_msg)
            self.event_bus.emit("conversation.updated", conversation)
            return local_msg

        except Exception as e:
            local_msg["status"] = "failed"
            local_msg["error"] = str(e)
            self.storage.save_message(local_msg)
            self.event_bus.emit("chat.message_failed", local_msg)
            raise
