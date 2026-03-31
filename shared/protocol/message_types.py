from dataclasses import dataclass, asdict
from typing import Optional
import base64
import json
import uuid
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# --------------------------
# 认证元数据（AD）：明文，绑定密文防篡改
# --------------------------
@dataclass
class MessageMetadata:
    sender_id: str
    receiver_id: str
    conversation_id: str
    message_counter: int
    message_id: str
    ttl_seconds: int
    expire_at: int
    timestamp: int
    is_self_destruct: bool
    device_fingerprint: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "MessageMetadata":
        return cls(**json.loads(json_str))

# --------------------------
# 加密网络包主体（你原有的类，优化版）
# --------------------------
@dataclass
class EncryptedNetworkPackage:
    message_id: str           
    sender_id: str            
    receiver_id: str          
    ciphertext_b64: str       
    nonce_b64: str            
    mac_tag_b64: str          
    ad_serialized: str        

    def get_metadata(self) -> MessageMetadata:
        return MessageMetadata.from_json(self.ad_serialized)

    def verify_ad_consistency(self) -> bool:
        """校验包字段与AD元数据一致性，防篡改"""
        ad = self.get_metadata()
        return (
            ad.sender_id == self.sender_id
            and ad.receiver_id == self.receiver_id
            and ad.message_id == self.message_id
        )

    @classmethod
    def create(
        cls,
        sender_id: str,
        receiver_id: str,
        conversation_id: str,
        message_counter: int,
        plaintext_content: bytes,
        aes_key: bytes,
        ttl_seconds: int = 0,
        device_fingerprint: str = ""
    ) -> "EncryptedNetworkPackage":
        """工厂方法：创建加密包（客户端发送时调用）"""
        message_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        is_self_destruct = ttl_seconds > 0
        expire_at = timestamp + ttl_seconds if is_self_destruct else 0

        # 构建AD元数据
        ad = MessageMetadata(
            sender_id=sender_id,
            receiver_id=receiver_id,
            conversation_id=conversation_id,
            message_counter=message_counter,
            message_id=message_id,
            ttl_seconds=ttl_seconds,
            expire_at=expire_at,
            timestamp=timestamp,
            is_self_destruct=is_self_destruct,
            device_fingerprint=device_fingerprint
        )
        ad_bytes = ad.to_json().encode("utf-8")

        # AES-GCM加密（AEAD，一次操作完成加密+认证）
        aesgcm = AESGCM(aes_key)
        nonce = AESGCM.generate_key(bit_length=96)  # 12字节标准nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext_content, ad_bytes)

        # Base64编码（网络传输用）
        ciphertext_b64 = base64.b64encode(ciphertext).decode("utf-8")
        nonce_b64 = base64.b64encode(nonce).decode("utf-8")
        mac_tag_b64 = ""  # AES-GCM标签已整合在密文中，留空兼容原有结构

        return cls(
            message_id=message_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            ciphertext_b64=ciphertext_b64,
            nonce_b64=nonce_b64,
            mac_tag_b64=mac_tag_b64,
            ad_serialized=ad.to_json()
        )

    def decrypt(self, aes_key: bytes) -> bytes:
        """解密包（客户端接收时调用）"""
        if not self.verify_ad_consistency():
            raise ValueError("包字段与AD元数据不一致，可能被篡改")

        # 解码Base64
        ciphertext = base64.b64decode(self.ciphertext_b64)
        nonce = base64.b64decode(self.nonce_b64)
        ad_bytes = self.ad_serialized.encode("utf-8")

        # AES-GCM解密（自动验证MAC标签）
        aesgcm = AESGCM(aes_key)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, ad_bytes)
        except InvalidTag:
            raise InvalidTag("消息认证失败，可能被篡改、重放或密钥错误")

        # 校验自毁消息是否过期
        ad = self.get_metadata()
        if ad.is_self_destruct:
            now = int(datetime.now().timestamp())
            if now > ad.expire_at:
                raise ValueError("消息已过期，自毁生效")

        return plaintext
