from typing import Optional

class KeyManager:
    def __init__(self, storage_path: str):
        """初始化密钥管理器"""
        self.storage_path = storage_path

    def generate_identity_keypair(self) -> None:
        """生成本地身份密钥对，保存到安全存储"""
        pass

    def get_identity_public_key(self) -> bytes:
        """返回身份公钥（原始字节）"""
        pass

    def get_identity_private_key(self) -> bytes:
        """返回身份私钥（仅本地使用）"""
        pass

    def get_prekey(self) -> Optional[bytes]:
        """获取一个未使用的预共享密钥"""
        pass

    def rotate_prekeys(self) -> None:
        """轮换预共享密钥"""
        pass