import os
import hashlib
import secrets
import uuid
from typing import Optional

try:
    from storage.key_storage import KeyStorage
except ImportError:
    from ..storage.key_storage import KeyStorage

class KeyManager:
    def __init__(self, storage_path: str):
        """初始化密钥管理器"""
        self.storage_path = storage_path
        self.storage = KeyStorage(storage_path)

    def generate_identity_keypair(self) -> None:
        """生成本地身份密钥对，保存到安全存储"""
        private_key = secrets.token_bytes(32)
        public_key = hashlib.sha256(private_key).digest()
        self.storage.save_identity_keypair(public_key, private_key)

    def get_identity_public_key(self) -> bytes:
        """返回身份公钥（原始字节）"""
        keypair = self.storage.load_identity_keypair()
        if keypair is None:
            self.generate_identity_keypair()
            keypair = self.storage.load_identity_keypair()
        return keypair[0]

    def get_identity_private_key(self) -> bytes:
        """返回身份私钥（仅本地使用）"""
        keypair = self.storage.load_identity_keypair()
        if keypair is None:
            self.generate_identity_keypair()
            keypair = self.storage.load_identity_keypair()
        return keypair[1]

    def get_prekey(self) -> Optional[bytes]:
        """获取一个未使用的预共享密钥"""
        prekeys_dir = os.path.join(self.storage_path, "prekeys")
        if not os.path.exists(prekeys_dir):
            return None
        for filename in os.listdir(prekeys_dir):
            if filename.endswith(".bin"):
                prekey_id = filename[:-4]
                data = self.storage.load_prekey(prekey_id)
                if data is not None:
                    os.remove(os.path.join(prekeys_dir, filename))
                    return data
        return None

    def rotate_prekeys(self) -> None:
        """轮换预共享密钥"""
        for _ in range(10):
            prekey_id = str(uuid.uuid4())
            self.storage.save_prekey(prekey_id, secrets.token_bytes(32))
