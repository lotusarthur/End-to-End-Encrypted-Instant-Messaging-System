from dataclasses import dataclass
from typing import Optional
import time
import uuid

@dataclass
class Envelope:
    """客户端 ↔ 服务器 传输的密文信封"""
    message_id: str
    from_user: str
    to_user: str
    ciphertext: bytes          # 加密模块输出的密文（包含 nonce、认证标签等）
    timestamp: int             # 发送时间戳（Unix 秒）
    ttl_seconds: int           # 生存时间（秒）
    signature: Optional[bytes] = None   # 可选，用于端到端签名

    @staticmethod
    def create(from_user: str, to_user: str, ciphertext: bytes, ttl: int) -> "Envelope":
        return Envelope(
            message_id=str(uuid.uuid4()),
            from_user=from_user,
            to_user=to_user,
            ciphertext=ciphertext,
            timestamp=int(time.time()),
            ttl_seconds=ttl
        )

@dataclass
class PlainMessage:
    """加密前的明文，包含业务信息"""
    message_id: str
    sender: str
    recipient: str
    content: str
    timestamp: int
    ttl_seconds: int
    msg_type: str   # "text", "delivery_receipt", "key_exchange"

@dataclass
class Session:
    """与某个联系人的加密会话"""
    session_id: str
    peer_user_id: str
    root_key: bytes
    send_chain_key: bytes
    recv_chain_key: bytes
    send_counter: int
    recv_counter: int
    created_at: int
    last_used: intfrom dataclasses import dataclass
from typing import Optional
import time
import uuid

@dataclass
class Envelope:
    """客户端 ↔ 服务器 传输的密文信封"""
    message_id: str
    from_user: str
    to_user: str
    ciphertext: bytes          # 加密模块输出的密文（包含 nonce、认证标签等）
    timestamp: int             # 发送时间戳（Unix 秒）
    ttl_seconds: int           # 生存时间（秒）
    signature: Optional[bytes] = None   # 可选，用于端到端签名

    @staticmethod
    def create(from_user: str, to_user: str, ciphertext: bytes, ttl: int) -> "Envelope":
        return Envelope(
            message_id=str(uuid.uuid4()),
            from_user=from_user,
            to_user=to_user,
            ciphertext=ciphertext,
            timestamp=int(time.time()),
            ttl_seconds=ttl
        )

@dataclass
class PlainMessage:
    """加密前的明文，包含业务信息"""
    message_id: str
    sender: str
    recipient: str
    content: str
    timestamp: int
    ttl_seconds: int
    msg_type: str   # "text", "delivery_receipt", "key_exchange"

@dataclass
class Session:
    """与某个联系人的加密会话"""
    session_id: str
    peer_user_id: str
    root_key: bytes
    send_chain_key: bytes
    recv_chain_key: bytes
    send_counter: int
    recv_counter: int
    created_at: int
    last_used: intfrom dataclasses import dataclass
from typing import Optional
import time
import uuid

@dataclass
class Envelope:
    """客户端 ↔ 服务器 传输的密文信封"""
    message_id: str
    from_user: str
    to_user: str
    ciphertext: bytes          # 加密模块输出的密文（包含 nonce、认证标签等）
    timestamp: int             # 发送时间戳（Unix 秒）
    ttl_seconds: int           # 生存时间（秒）
    signature: Optional[bytes] = None   # 可选，用于端到端签名

    @staticmethod
    def create(from_user: str, to_user: str, ciphertext: bytes, ttl: int) -> "Envelope":
        return Envelope(
            message_id=str(uuid.uuid4()),
            from_user=from_user,
            to_user=to_user,
            ciphertext=ciphertext,
            timestamp=int(time.time()),
            ttl_seconds=ttl
        )

@dataclass
class PlainMessage:
    """加密前的明文，包含业务信息"""
    message_id: str
    sender: str
    recipient: str
    content: str
    timestamp: int
    ttl_seconds: int
    msg_type: str   # "text", "delivery_receipt", "key_exchange"

@dataclass
class Session:
    """与某个联系人的加密会话"""
    session_id: str
    peer_user_id: str
    root_key: bytes
    send_chain_key: bytes
    recv_chain_key: bytes
    send_counter: int
    recv_counter: int
    created_at: int
    last_used: intfrom dataclasses import dataclass
from typing import Optional
import time
import uuid

@dataclass
class Envelope:
    """客户端 ↔ 服务器 传输的密文信封"""
    message_id: str
    from_user: str
    to_user: str
    ciphertext: bytes          # 加密模块输出的密文（包含 nonce、认证标签等）
    timestamp: int             # 发送时间戳（Unix 秒）
    ttl_seconds: int           # 生存时间（秒）
    signature: Optional[bytes] = None   # 可选，用于端到端签名

    @staticmethod
    def create(from_user: str, to_user: str, ciphertext: bytes, ttl: int) -> "Envelope":
        return Envelope(
            message_id=str(uuid.uuid4()),
            from_user=from_user,
            to_user=to_user,
            ciphertext=ciphertext,
            timestamp=int(time.time()),
            ttl_seconds=ttl
        )

@dataclass
class PlainMessage:
    """加密前的明文，包含业务信息"""
    message_id: str
    sender: str
    recipient: str
    content: str
    timestamp: int
    ttl_seconds: int
    msg_type: str   # "text", "delivery_receipt", "key_exchange"

@dataclass
class Session:
    """与某个联系人的加密会话"""
    session_id: str
    peer_user_id: str
    root_key: bytes
    send_chain_key: bytes
    recv_chain_key: bytes
    send_counter: int
    recv_counter: int
    created_at: int
    last_used: int