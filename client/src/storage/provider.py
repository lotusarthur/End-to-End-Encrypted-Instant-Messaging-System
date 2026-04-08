import sqlite3
import json
from typing import Optional, Dict, Any

class SQLiteStorageProvider:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构 - 确保所有业务表都存在"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 配置表 (存储 Token 等)
            cursor.execute('''CREATE TABLE IF NOT EXISTS config 
                            (key TEXT PRIMARY KEY, value TEXT)''')
            
            # 2. 身份表 (存储个人私钥)
            cursor.execute('''CREATE TABLE IF NOT EXISTS identity 
                            (username TEXT PRIMARY KEY, private_key_b64 TEXT)''')
            
            # 3. 联系人公钥表 (存储好友的公钥)
            cursor.execute('''CREATE TABLE IF NOT EXISTS contact_keys 
                            (contact_id TEXT PRIMARY KEY, pub_key_b64 TEXT)''')
            
            # 4. 会话密钥表 (存储协商后的对称密钥 - 刚才报错的地方)
            cursor.execute('''CREATE TABLE IF NOT EXISTS session_keys 
                            (contact_id TEXT PRIMARY KEY, session_key_b64 TEXT)''')
            
            # 5. 防重放攻击表 (存储已用的 Nonce)
            cursor.execute('''CREATE TABLE IF NOT EXISTS used_nonces 
                            (sender_id TEXT, nonce_b64 TEXT, PRIMARY KEY (sender_id, nonce_b64))''')
            
            conn.commit()

    # --- 防重放攻击对接接口 (CryptoEngine 调用) ---
    def is_nonce_used(self, sender_id: str, nonce_b64: str) -> bool:
        """检查该 Nonce 是否已被使用过"""
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT 1 FROM used_nonces WHERE sender_id = ? AND nonce_b64 = ?", 
                             (sender_id, nonce_b64)).fetchone()
            return res is not None

    def add_used_nonce(self, sender_id: str, nonce_b64: str):
        """记录新的 Nonce"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO used_nonces (sender_id, nonce_b64) VALUES (?, ?)", 
                         (sender_id, nonce_b64))

    # --- 其余接口保持不变 (适配 auth_service 与 main2) ---
    def save_private_key(self, username: str, pri_key_b64: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO identity (username, private_key_b64) VALUES (?, ?)", (username, pri_key_b64))

    def get_my_private_key(self) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT private_key_b64 FROM identity LIMIT 1").fetchone()
            return res[0] if res else None

    def save_token(self, token: str):
        self._set_config("token", token)

    def save_user_profile(self, profile: Dict):
        self._set_config("profile", json.dumps(profile))

    def save_contact_key(self, contact_id: str, pub_key_b64: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO contact_keys (contact_id, pub_key_b64) VALUES (?, ?)", (contact_id, pub_key_b64))

    def get_contact_key(self, contact_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT pub_key_b64 FROM contact_keys WHERE contact_id = ?", (contact_id,)).fetchone()
            return res[0] if res else None

    def save_session_key(self, contact_id: str, session_key_b64: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO session_keys (contact_id, session_key_b64) VALUES (?, ?)", (contact_id, session_key_b64))

    def get_session_key(self, contact_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT session_key_b64 FROM session_keys WHERE contact_id = ?", (contact_id,)).fetchone()
            return res[0] if res else None

    def _set_config(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))