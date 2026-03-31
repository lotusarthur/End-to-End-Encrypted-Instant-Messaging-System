from typing import Optional
from ..shared.protocol.message_types import PlainMessage, Session
from shared.protocol.message_types import EncryptedNetworkPackage
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class CryptoError(Exception):
    pass

class ReplayAttackError(CryptoError):
    pass

class KeyChangedError(CryptoError):
    pass

class MessageCrypto:
    def __init__(self, session_manager):
        self.session_manager = session_manager

    def encrypt(self, session_id: str, plain_msg: PlainMessage) -> bytes:
        """
        使用会话加密明文消息。
        内部需将 PlainMessage 序列化为 JSON 或 Protobuf，然后进行 AEAD 加密，
        并绑定关联数据（sender, recipient, message_id, counter, ttl）。
        返回密文（包含 nonce 和认证标签）。
        """
        pass

    def decrypt(self, session_id: str, ciphertext: bytes, associated_data: dict) -> PlainMessage:
        """
        使用会话解密密文。
        先验证 AEAD，再反序列化得到 PlainMessage。
        如果计数器检查失败（重放），抛出 ReplayAttackError。
        """
        pass

    def get_peer_fingerprint(self, peer_user_id: str) -> str:
        """返回对方身份公钥的指纹（例如 SHA-256 前 16 字符）"""
        pass

    def check_key_change(self, peer_user_id: str, new_public_key: bytes) -> bool:
        """
        检查对方公钥是否变更。
        若变更，应返回 True，由上层决定如何处理。
        """
        pass

    def verify_signature(self, message_id: str, signature: bytes, public_key: bytes) -> bool:
        """验证消息签名"""
        pass

    def sign_message(self, message_id: str, private_key: bytes) -> bytes:
        """对消息进行签名"""
        pass
