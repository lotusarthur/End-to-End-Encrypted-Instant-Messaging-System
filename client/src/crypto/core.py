import os
import json
import base64
import time
from typing import Dict, Tuple, Optional

# 导入OTP库
import pyotp

# 请确保通过 pip install cryptography 安装了库
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# ==========================================
# 模块 1: 密钥与身份管理 (IdentityManager)
# 负责生成本地密钥对、哈希密码、生成安全指纹与OTP种子
# ==========================================
class IdentityManager:
    
    @staticmethod
    def generate_otp_secret() -> str:
        """
        [新增] 生成标准的 TOTP (Time-based One-Time Password) 种子
        返回一个 16 字符的 Base32 编码字符串，兼容 Google Authenticator。
        业务层需将此字符串发给 UI 展示（或生成二维码），并随注册接口发给服务器。
        """
        # 生成 10 字节的强随机数，并用 Base32 编码（Authenticator 的标准格式）
        random_bytes = os.urandom(10)
        return base64.b32encode(random_bytes).decode('utf-8').replace('=', '')
    
    @staticmethod
    def generate_otp_code(otp_secret: str) -> str:
        """
        生成OTP验证码
        使用提供的OTP密钥生成当前的6位数字验证码
        """
        totp = pyotp.TOTP(otp_secret)
        return totp.now()

    @staticmethod
    def hash_password(password: str, salt_b64: Optional[str] = None) -> Tuple[str, str]:
        """
        R1: 在发送给服务器之前，在客户端对密码进行加盐哈希。
        前端调用此函数后，将 password_hash 发给后端。
        """
        salt = base64.b64decode(salt_b64) if salt_b64 else os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        pwd_hash = kdf.derive(password.encode('utf-8'))
        return base64.b64encode(pwd_hash).decode('utf-8'), base64.b64encode(salt).decode('utf-8')

    @staticmethod
    def generate_identity_keypair() -> Tuple[str, str]:
        """
        R4: 生成设备的长期身份密钥对 (X25519)
        返回: (private_key_b64, public_key_b64)
        注意：private_key_b64 必须由业务层加密保存在本地！public_key_b64 上传给服务器。
        """
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        pri_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(pri_bytes).decode('utf-8'), base64.b64encode(pub_bytes).decode('utf-8')

    @staticmethod
    def generate_fingerprint(public_key_b64: str) -> str:
        """
        R5: 生成用于 UI 展示的联系人安全指纹 (Safety Number)
        """
        pub_bytes = base64.b64decode(public_key_b64)
        digest = hashes.Hash(hashes.SHA256())
        digest.update(pub_bytes)
        fingerprint_bytes = digest.finalize()
        hex_str = fingerprint_bytes.hex().upper()
        return ':'.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))

# ==========================================
# 模块 2: 安全协议与防御逻辑 (SessionManager)
# 负责密钥协商、密钥变更检测
# ==========================================
class SessionManager:
    def __init__(self, my_private_key_b64: str, storage_provider):
        self.private_key = x25519.X25519PrivateKey.from_private_bytes(
            base64.b64decode(my_private_key_b64)
        )
        # 依赖业务层传入的持久化存储对象 (StorageProvider)
        self.storage = storage_provider 
        self._session_keys: Dict[str, bytes] = {}

    def establish_session(self, contact_id: str, contact_public_key_b64: str) -> bytes:
        """
        R7: 使用 ECDH 建立端到端会话密钥，防范中间人攻击
        """
        # 1. R6: 密钥变更检测 (从本地数据库比对)
        trusted_key = self.storage.get_contact_key(contact_id)
        if trusted_key:
            if trusted_key != contact_public_key_b64:
                raise PermissionError(f"CRITICAL: Key change detected for {contact_id}. Must re-verify fingerprint!")
        else:
            # 首次记录公钥到本地数据库
            self.storage.save_contact_key(contact_id, contact_public_key_b64)
            
        contact_pub_key = x25519.X25519PublicKey.from_public_bytes(
            base64.b64decode(contact_public_key_b64)
        )
        
        # 2. ECDH 交换计算共享秘密
        shared_secret = self.private_key.exchange(contact_pub_key)
        
        # 3. HKDF 派生高强度的 256 位会话密钥
        session_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'handshake data',
        ).derive(shared_secret)
        
        self._session_keys[contact_id] = session_key
        return session_key

    def get_session_key(self, contact_id: str) -> bytes:
        if contact_id not in self._session_keys:
            raise ValueError("Session not established. Fetch public key from server first.")
        return self._session_keys[contact_id]

# ==========================================
# 模块 3: 核心加密引擎 (CryptoEngine)
# 负责 AES-GCM 加解密、AD绑定、防重放检测
# ==========================================
class CryptoEngine:
    def __init__(self, my_id: str, session_manager: SessionManager, storage_provider):
        self.my_id = my_id
        self.session_manager = session_manager
        # 依赖业务层传入的持久化存储对象处理重放攻击列表
        self.storage = storage_provider 

    def encrypt_message(self, receiver_id: str, message_id: str, content: str, ttl_seconds: int = 0) -> dict:
        """
        R8: 加密消息，生成符合服务器 WebSocket JSON 格式的数据包
        """
        session_key = self.session_manager.get_session_key(receiver_id)
        aesgcm = AESGCM(session_key)
        current_ts = int(time.time())
        
        # 构建并序列化认证关联数据 (AD)
        ad_data = {
            "sender_id": self.my_id,
            "receiver_id": receiver_id,
            "message_id": message_id,
            "timestamp": current_ts,
            "ttl_seconds": ttl_seconds  # R10: 绑定自毁时间，防篡改
        }
        ad_serialized = json.dumps(ad_data, separators=(',', ':')).encode('utf-8')
        
        nonce = os.urandom(12)
        encrypted_data = aesgcm.encrypt(nonce, content.encode('utf-8'), ad_serialized)
        
        ciphertext = encrypted_data[:-16]
        mac_tag = encrypted_data[-16:]
        
        # 完全兼容服务器 1(1).txt 中定义的 EncryptedNetworkPackage 格式
        return {
            "type": "message",
            "message_id": message_id,
            "sender_id": self.my_id,
            "receiver_id": receiver_id,
            "ciphertext_b64": base64.b64encode(ciphertext).decode('utf-8'),
            "nonce_b64": base64.b64encode(nonce).decode('utf-8'),
            "mac_tag_b64": base64.b64encode(mac_tag).decode('utf-8'),
            "ad_serialized": base64.b64encode(ad_serialized).decode('utf-8'),
            "timestamp": current_ts,
            "ttl_seconds": ttl_seconds,
            "status": "sent"
        }

    def decrypt_message(self, package: dict) -> str:
        """
        R8, R9: 解密收到的服务器 JSON 数据包，并执行全面的安全校验
        """
        sender_id = package.get("sender_id")
        msg_id = package.get("message_id")
        
        # 1. 重放攻击检测 (查本地数据库)
        if self.storage.is_message_processed(msg_id):
            raise ValueError(f"Replay Attack Detected: Message {msg_id} already processed.")
            
        session_key = self.session_manager.get_session_key(sender_id)
        aesgcm = AESGCM(session_key)
        
        try:
            nonce = base64.b64decode(package["nonce_b64"])
            ciphertext = base64.b64decode(package["ciphertext_b64"])
            mac_tag = base64.b64decode(package["mac_tag_b64"])
            ad_serialized = base64.b64decode(package["ad_serialized"])
            
            # 2. MAC 完整性与认证校验
            decrypted_data = aesgcm.decrypt(nonce, ciphertext + mac_tag, ad_serialized)
            
            # 3. AD 字段一致性校验
            ad_dict = json.loads(ad_serialized.decode('utf-8'))
            
            # 重点检查：确保外层的 ttl_seconds 和 message_id 没有被服务器修改
            if ad_dict["message_id"] != msg_id:
                raise ValueError(f"Message ID Mismatch! Expected {ad_dict['message_id']}, got {msg_id}")
            
            if ad_dict.get("ttl_seconds") != package.get("ttl_seconds"):
                raise ValueError("TTL Mismatch: Server tried to tamper with self-destruct timer!")
                
            # 4. 记录此消息为已处理（防重放）
            self.storage.add_processed_message(msg_id)
            
            return decrypted_data.decode('utf-8')          
        except InvalidTag:
            raise ValueError("Integrity Error: MAC Tag verification failed. Data tampered!")
        # 移除那个会包装一切错误的 RuntimeError，让 ValueError 直接抛出