import base64
import hashlib
import secrets
import time
import uuid
from typing import Optional
try:
    from shared.protocol.message_types import Session
except ImportError:
    from ...shared.protocol.message_types import Session
try:
    from storage.key_storage import KeyStorage
except ImportError:
    from ..storage.key_storage import KeyStorage

class SessionManager:
    def __init__(self, storage_path: str):
        """初始化会话管理器"""
        self.storage_path = storage_path
        self.storage = KeyStorage(storage_path)
        self._cache: dict[str, Session] = {}

    def create_outbound_session(self, peer_user_id: str, peer_public_key: bytes) -> str:
        """
        发起与对方的会话（调用 DH 交换等），返回 session_id。
        该 session_id 用于后续加密。
        """
        session_id = str(uuid.uuid4())
        now = int(time.time())
        root_key = hashlib.sha256(peer_public_key + secrets.token_bytes(16)).digest()
        session = Session(
            session_id=session_id,
            peer_user_id=peer_user_id,
            root_key=root_key,
            send_chain_key=hashlib.sha256(root_key + b"send").digest(),
            recv_chain_key=hashlib.sha256(root_key + b"recv").digest(),
            send_counter=0,
            recv_counter=0,
            created_at=now,
            last_used=now,
        )
        self._save(session)
        return session_id

    def create_inbound_session(self, peer_user_id: str, initiator_public_key: bytes) -> str:
        """
        响应对方的会话建立请求，返回 session_id。
        """
        session_id = str(uuid.uuid4())
        now = int(time.time())
        root_key = hashlib.sha256(initiator_public_key + secrets.token_bytes(16)).digest()
        session = Session(
            session_id=session_id,
            peer_user_id=peer_user_id,
            root_key=root_key,
            send_chain_key=hashlib.sha256(root_key + b"recv").digest(),
            recv_chain_key=hashlib.sha256(root_key + b"send").digest(),
            send_counter=0,
            recv_counter=0,
            created_at=now,
            last_used=now,
        )
        self._save(session)
        return session_id

    def get_session(self, session_id: str) -> Session:
        """获取会话对象（用于加密/解密）"""
        if session_id in self._cache:
            return self._cache[session_id]
        payload = self.storage.load_session(session_id)
        if payload is None:
            raise KeyError(f"Session not found: {session_id}")
        session = self._deserialize(payload)
        self._cache[session_id] = session
        return session

    def get_session_by_peer(self, peer_user_id: str) -> Optional[Session]:
        """获取与指定用户的已有会话"""
        for session_id in self.storage.list_sessions():
            try:
                s = self.get_session(session_id)
            except KeyError:
                continue
            if s.peer_user_id == peer_user_id:
                return s
        return None

    def delete_session(self, session_id: str) -> None:
        """删除会话（例如用户屏蔽时）"""
        self.storage.delete_session(session_id)
        self._cache.pop(session_id, None)

    def update_session_counter(self, session_id: str, is_send: bool) -> None:
        """更新会话计数器"""
        session = self.get_session(session_id)
        if is_send:
            session.send_counter += 1
        else:
            session.recv_counter += 1
        session.last_used = int(time.time())
        self._save(session)

    def list_sessions(self) -> list[str]:
        """获取所有会话的ID列表"""
        return self.storage.list_sessions()

    def _serialize(self, session: Session) -> dict:
        return {
            "session_id": session.session_id,
            "peer_user_id": session.peer_user_id,
            "root_key": base64.b64encode(session.root_key).decode("ascii"),
            "send_chain_key": base64.b64encode(session.send_chain_key).decode("ascii"),
            "recv_chain_key": base64.b64encode(session.recv_chain_key).decode("ascii"),
            "send_counter": session.send_counter,
            "recv_counter": session.recv_counter,
            "created_at": session.created_at,
            "last_used": session.last_used,
        }

    def _deserialize(self, payload: dict) -> Session:
        return Session(
            session_id=payload["session_id"],
            peer_user_id=payload["peer_user_id"],
            root_key=base64.b64decode(payload["root_key"]),
            send_chain_key=base64.b64decode(payload["send_chain_key"]),
            recv_chain_key=base64.b64decode(payload["recv_chain_key"]),
            send_counter=int(payload["send_counter"]),
            recv_counter=int(payload["recv_counter"]),
            created_at=int(payload["created_at"]),
            last_used=int(payload["last_used"]),
        )

    def _save(self, session: Session) -> None:
        self.storage.save_session(session.session_id, self._serialize(session))
        self._cache[session.session_id] = session
