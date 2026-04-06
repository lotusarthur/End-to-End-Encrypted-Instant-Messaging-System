import sqlite3
import time
from typing import Optional

class SQLiteStorageProvider:
    def __init__(self, db_path: str = "local_chat_data.db"):
        """
        初始化 SQLite 数据库连接并自动创建所需的安全表。
        """
        self.db_path = db_path
        # check_same_thread=False 允许在 UI 线程和网络线程中共享数据库连接
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        
        # 表1：受信任的联系人公钥库（用于防御 R6: 中间人攻击）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trusted_keys (
                contact_id TEXT PRIMARY KEY,
                public_key_b64 TEXT NOT NULL,
                added_at INTEGER NOT NULL
            )
        ''')
        
        # 表2：已处理的消息ID库（用于防御 R9: 重放攻击）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at INTEGER NOT NULL
            )
        ''')
        self.conn.commit()

    # ==========================================
    # 接口 1：防中间人攻击 (对接 SessionManager)
    # ==========================================
    def get_contact_key(self, contact_id: str) -> Optional[str]:
        """获取本地记录的联系人公钥"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT public_key_b64 FROM trusted_keys WHERE contact_id = ?', (contact_id,))
        row = cursor.fetchone()
        return row[0] if row else None

    def save_contact_key(self, contact_id: str, public_key_b64: str):
        """保存新的联系人公钥"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO trusted_keys (contact_id, public_key_b64, added_at)
            VALUES (?, ?, ?)
        ''', (contact_id, public_key_b64, int(time.time())))
        self.conn.commit()

    # ==========================================
    # 接口 2：防重放攻击 (对接 CryptoEngine)
    # ==========================================
    def is_message_processed(self, msg_id: str) -> bool:
        """检查消息是否已经被处理过"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM processed_messages WHERE message_id = ?', (msg_id,))
        return cursor.fetchone() is not None

    def add_processed_message(self, msg_id: str):
        """记录已解密的消息ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO processed_messages (message_id, processed_at)
            VALUES (?, ?)
        ''', (msg_id, int(time.time())))
        self.conn.commit()