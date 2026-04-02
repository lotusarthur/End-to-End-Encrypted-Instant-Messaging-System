#!/usr/bin/env python3
"""
数据库模型定义
定义用户关系、消息、用户公钥三表
"""

import sqlite3
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

@dataclass
class User:
    """用户表模型"""
    username: str
    password_hash: str
    identity_public_key: Optional[str] = None
    otp_secret: Optional[str] = None
    is_online: bool = False
    last_seen: Optional[int] = None
    created_at: Optional[int] = None

@dataclass
class FriendRelationship:
    """好友关系表模型"""
    id: int
    user_a: str
    user_b: str
    status: str  # 'pending', 'accepted', 'blocked'
    created_at: int
    accepted_at: Optional[int] = None

@dataclass
class Message:
    """消息表模型"""
    message_id: str
    from_user: str
    to_user: str
    ciphertext: str
    timestamp: int
    ttl_seconds: int
    status: str  # 'sent', 'delivered', 'read', 'expired'
    signature: Optional[str] = None
    delivered_at: Optional[int] = None
    read_at: Optional[int] = None

@dataclass
class UserPublicKey:
    """用户公钥表模型"""
    username: str
    identity_public_key: str
    updated_at: int
    prekey_bundle: Optional[str] = None

class DatabaseSchema:
    """数据库表结构定义"""
    
    @staticmethod
    def init_database(db_path: str = "messaging.db"):
        """初始化数据库表结构"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                identity_public_key TEXT,
                otp_secret TEXT,
                is_online BOOLEAN DEFAULT FALSE,
                last_seen INTEGER,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # 好友关系表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friend_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_a TEXT NOT NULL,
                user_b TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'blocked', 'cancelled')),
                created_at INTEGER NOT NULL,
                accepted_at INTEGER,
                FOREIGN KEY (user_a) REFERENCES users(username),
                FOREIGN KEY (user_b) REFERENCES users(username),
                UNIQUE(user_a, user_b)
            )
        ''')
        
        # 消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                from_user TEXT NOT NULL,
                to_user TEXT NOT NULL,
                ciphertext TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                ttl_seconds INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('sent', 'delivered', 'read', 'expired')),
                signature TEXT,
                delivered_at INTEGER,
                read_at INTEGER,
                FOREIGN KEY (from_user) REFERENCES users(username),
                FOREIGN KEY (to_user) REFERENCES users(username)
            )
        ''')
        
        # 用户公钥表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_public_keys (
                username TEXT PRIMARY KEY,
                identity_public_key TEXT NOT NULL,
                prekey_bundle TEXT,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username)
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_to_user ON messages(to_user, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_friends_user_a ON friend_relationships(user_a, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_friends_user_b ON friend_relationships(user_b, status)')
        
        conn.commit()
        conn.close()
        
        print("数据库初始化完成")

if __name__ == "__main__":
    DatabaseSchema.init_database()