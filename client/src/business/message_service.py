import time

from .errors import ReplayAttackError


class MessageService:
    def __init__(self, crypto, storage, event_bus, session_manager):
        self.crypto = crypto
        self.storage = storage
        self.event_bus = event_bus
        self.session_manager = session_manager

    def handle_ws_payload(self, payload: dict):
        """
        Unified websocket dispatcher.
        """
        msg_type = payload.get("type")

        if msg_type == "new_message":
            return self._handle_new_message(payload)

        if msg_type == "delivery_receipt":
            return self._handle_delivery_receipt(payload)

        self.event_bus.emit("system.unknown_event", payload)
        return None

    def _handle_new_message(self, payload: dict):
        """
        Receiver-side flow:
        1. websocket receives envelope
        2. business dispatches by type
        3. business calls crypto.decrypt(pkg)
        4. business checks replay + ttl
        5. save local message
        6. update unread/UI
        """
        message_id = payload.get("message_id")
        conversation_id = payload.get("conversation_id")
        sender_id = payload.get("sender_id")
        encrypted_pkg = payload.get("encrypted_pkg", {})

        if message_id and self.storage.is_replay(message_id):
            security_event = {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "sender_id": sender_id,
                "status": "replay_detected",
            }
            self.event_bus.emit("security.replay_detected", security_event)
            raise ReplayAttackError(f"Replay detected: {message_id}")

        try:
            dec = self.crypto.decrypt(encrypted_pkg)
        except Exception as e:
            failed_msg = {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "sender_id": sender_id,
                "direction": "incoming",
                "text": "[decrypt failed]",
                "status": "decrypt_failed",
                "error": str(e),
                "received_at": int(time.time()),
            }
            self.storage.save_message(failed_msg)
            self.event_bus.emit("chat.message_received", failed_msg)
            return failed_msg

        plaintext = dec.get("plaintext", "")
        expired = bool(dec.get("expired", False))

        # 备用的ttl
        if not expired:
            ts = encrypted_pkg.get("timestamp")
            ttl = encrypted_pkg.get("ttl")
            if ts is not None and ttl is not None:
                if int(time.time()) > int(ts) + int(ttl):
                    expired = True

        if expired:
            final_text = "[message expired]"
            status = "expired"
        else:
            final_text = plaintext
            status = "received"

        conversation = self.session_manager.get_or_create_conversation(
            conversation_id=conversation_id,
            peer_user_id=sender_id
        )
        conversation["last_message"] = final_text
        self.storage.upsert_conversation(conversation)

        msg = {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "direction": "incoming",
            "text": final_text,
            "status": status,
            "server_time": payload.get("server_time"),
            "received_at": int(time.time()),
        }
        self.storage.save_message(msg)

        if message_id:
            self.storage.mark_seen_message(message_id)

        active_conv = self.session_manager.get_active_conversation()
        if active_conv != conversation_id:
            self.storage.increment_unread(conversation_id)
        else:
            self.storage.clear_unread(conversation_id)

        self.event_bus.emit("chat.message_received", msg)
        self.event_bus.emit("conversation.updated", conversation)
        return msg

    def _handle_delivery_receipt(self, payload: dict):
        self.event_bus.emit("chat.delivery_receipt", payload)
        return payload
