"""Message encryption/decryption."""
import base64
import hashlib
import hmac
import json
import os
from typing import Optional

try:
    from shared.protocol.message_types import PlainMessage
except ImportError:
    from ....shared.protocol.message_types import PlainMessage


class CryptoError(Exception):
    """Base crypto error."""
    pass


class ReplayAttackError(CryptoError):
    """Replay attack detected."""
    pass


class KeyChangedError(CryptoError):
    """Key has changed."""
    pass


class MessageCrypto:
    """Handles message encryption and decryption."""
    
    def __init__(self, session_manager):
        """Initialize with session manager."""
        self.session_manager = session_manager

    def encrypt(self, session_id: str, plain_msg: PlainMessage) -> bytes:
        """Encrypt a plaintext message."""
        session = self.session_manager.get_session(session_id)
        counter = session.send_counter
        nonce = os.urandom(12)
        payload = json.dumps(
            {
                "message_id": plain_msg.message_id,
                "sender": plain_msg.sender,
                "recipient": plain_msg.recipient,
                "content": plain_msg.content,
                "timestamp": plain_msg.timestamp,
                "ttl_seconds": plain_msg.ttl_seconds,
                "msg_type": plain_msg.msg_type,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        key_stream = hashlib.sha256(session.send_chain_key + nonce + counter.to_bytes(8, "big")).digest()
        ciphertext = bytes(b ^ key_stream[i % len(key_stream)] for i, b in enumerate(payload))
        mac = hmac.new(session.send_chain_key, nonce + counter.to_bytes(8, "big") + ciphertext, hashlib.sha256).digest()
        self.session_manager.update_session_counter(session_id, is_send=True)
        return nonce + counter.to_bytes(8, "big") + ciphertext + mac

    def decrypt(self, session_id: str, ciphertext: bytes, associated_data: dict) -> PlainMessage:
        """Decrypt a ciphertext message."""
        session = self.session_manager.get_session(session_id)
        if len(ciphertext) < 12 + 8 + 32:
            raise CryptoError("invalid ciphertext")
        nonce = ciphertext[:12]
        counter_bytes = ciphertext[12:20]
        body = ciphertext[20:-32]
        recv_mac = ciphertext[-32:]
        expected_mac = hmac.new(session.recv_chain_key, nonce + counter_bytes + body, hashlib.sha256).digest()
        if not hmac.compare_digest(recv_mac, expected_mac):
            raise CryptoError("message authentication failed")
        counter = int.from_bytes(counter_bytes, "big")
        if counter < session.recv_counter:
            raise ReplayAttackError("replayed message detected")
        key_stream = hashlib.sha256(session.recv_chain_key + nonce + counter_bytes).digest()
        plain_bytes = bytes(b ^ key_stream[i % len(key_stream)] for i, b in enumerate(body))
        data = json.loads(plain_bytes.decode("utf-8"))
        self.session_manager.update_session_counter(session_id, is_send=False)
        return PlainMessage(
            message_id=data["message_id"],
            sender=data["sender"],
            recipient=data["recipient"],
            content=data["content"],
            timestamp=int(data["timestamp"]),
            ttl_seconds=int(data["ttl_seconds"]),
            msg_type=data["msg_type"],
        )

    def get_peer_fingerprint(self, peer_user_id: str) -> str:
        """Get fingerprint of peer's public key."""
        digest = hashlib.sha256(peer_user_id.encode("utf-8")).hexdigest()
        return digest[:16]

    def check_key_change(self, peer_user_id: str, new_public_key: bytes) -> bool:
        """Check if peer's key has changed."""
        fingerprint_old = self.get_peer_fingerprint(peer_user_id)
        fingerprint_new = hashlib.sha256(new_public_key).hexdigest()[:16]
        return fingerprint_old != fingerprint_new

    def verify_signature(self, message_id: str, signature: bytes, public_key: bytes) -> bool:
        """Verify a message signature."""
        expected = hmac.new(public_key, message_id.encode("utf-8"), hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)

    def sign_message(self, message_id: str, private_key: bytes) -> bytes:
        """Sign a message."""
        return hmac.new(private_key, message_id.encode("utf-8"), hashlib.sha256).digest()