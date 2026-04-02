#!/usr/bin/env python3
"""
数据库管理类
实现完整的CRUD操作
"""

import sqlite3
import time
from typing import List, Optional, Dict, Any
from models import User, FriendRelationship, Message, UserPublicKey

class DatabaseManager:
    """数据库管理类 - 实现完整的CRUD操作"""
    
    def __init__(self, db_path: str = "messaging.db"):
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    # ========== 用户管理 ==========
    
    def add_user(self, user: User) -> bool:
        """添加用户"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, password_hash, identity_public_key, otp_secret, is_online, last_seen, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user.username, user.password_hash, user.identity_public_key, user.otp_secret, 
                  user.is_online, user.last_seen, int(time.time())))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_user(self, username: str) -> Optional[User]:
        """获取用户信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                username=row[0],
                password_hash=row[1],
                identity_public_key=row[2],
                otp_secret=row[3],
                is_online=bool(row[4]),
                last_seen=row[5],
                created_at=row[6]
            )
        return None
    
    def update_user_online_status(self, username: str, is_online: bool) -> bool:
        """更新用户在线状态"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET is_online = ?, last_seen = ? WHERE username = ?
            ''', (is_online, int(time.time()) if is_online else None, username))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception:
            return False
    
    # ========== 好友关系管理 ==========
    
    def add_friend_request(self, from_user: str, to_user: str) -> Optional[int]:
        """添加好友请求"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO friend_relationships (user_a, user_b, status, created_at)
                VALUES (?, ?, 'pending', ?)
            ''', (from_user, to_user, int(time.time())))
            request_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return request_id
        except sqlite3.IntegrityError:
            return None
    
    def get_friend_requests(self, username: str, request_type: str = "received") -> List[FriendRelationship]:
        """获取好友请求列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if request_type == "received":
            cursor.execute('''
                SELECT * FROM friend_relationships 
                WHERE user_b = ? AND status = 'pending'
            ''', (username,))
        else:  # sent
            cursor.execute('''
                SELECT * FROM friend_relationships 
                WHERE user_a = ? AND status = 'pending'
            ''', (username,))
        
        rows = cursor.fetchall()
        conn.close()
        
        requests = []
        for row in rows:
            requests.append(FriendRelationship(
                id=row[0], user_a=row[1], user_b=row[2], status=row[3],
                created_at=row[4], accepted_at=row[5]
            ))
        return requests
    
    def update_friend_request_status(self, request_id: int, status: str) -> bool:
        """更新好友请求状态"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if status == 'accepted':
                cursor.execute('''
                    UPDATE friend_relationships 
                    SET status = ?, accepted_at = ? 
                    WHERE id = ?
                ''', (status, int(time.time()), request_id))
            else:
                cursor.execute('''
                    UPDATE friend_relationships 
                    SET status = ? 
                    WHERE id = ?
                ''', (status, request_id))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception:
            return False
    
    def get_friends(self, username: str) -> List[Dict[str, Any]]:
        """获取好友列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.username, u.is_online, u.last_seen, fr.accepted_at
            FROM users u
            JOIN friend_relationships fr ON (
                (fr.user_a = ? AND fr.user_b = u.username) OR 
                (fr.user_b = ? AND fr.user_a = u.username)
            )
            WHERE fr.status = 'accepted' AND u.username != ?
        ''', (username, username, username))
        
        rows = cursor.fetchall()
        conn.close()
        
        friends = []
        for row in rows:
            friends.append({
                'username': row[0],
                'is_online': bool(row[1]),
                'last_seen': row[2],
                'added_at': row[3]
            })
        return friends
    
    def remove_friend(self, username: str, friend_username: str) -> bool:
        """删除好友关系"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM friend_relationships 
                WHERE ((user_a = ? AND user_b = ?) OR (user_a = ? AND user_b = ?))
                AND status = 'accepted'
            ''', (username, friend_username, friend_username, username))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception:
            return False
    
    # ========== 消息管理 ==========
    
    def add_message(self, message: Message) -> bool:
        """添加消息"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages 
                (message_id, from_user, to_user, ciphertext, timestamp, ttl_seconds, status, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (message.message_id, message.from_user, message.to_user, 
                  message.ciphertext, message.timestamp, message.ttl_seconds, 
                  message.status, message.signature))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    def get_offline_messages(self, username: str) -> List[Message]:
        """获取用户的离线消息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE to_user = ? AND status = 'sent'
            ORDER BY timestamp ASC
        ''', (username,))
        
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            messages.append(Message(
                message_id=row[0], from_user=row[1], to_user=row[2],
                ciphertext=row[3], timestamp=row[4], ttl_seconds=row[5],
                status=row[6], signature=row[7], delivered_at=row[8], read_at=row[9]
            ))
        return messages
    
    def update_message_status(self, message_id: str, status: str) -> bool:
        """更新消息状态"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            update_time = int(time.time())
            if status == 'delivered':
                cursor.execute('''
                    UPDATE messages SET status = ?, delivered_at = ? WHERE message_id = ?
                ''', (status, update_time, message_id))
            elif status == 'read':
                cursor.execute('''
                    UPDATE messages SET status = ?, read_at = ? WHERE message_id = ?
                ''', (status, update_time, message_id))
            else:
                cursor.execute('''
                    UPDATE messages SET status = ? WHERE message_id = ?
                ''', (status, message_id))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception:
            return False
    
    # ========== 公钥管理 ==========
    
    def save_user_public_key(self, username: str, public_key: str, prekey_bundle: str = None) -> bool:
        """保存用户公钥"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_public_keys 
                (username, identity_public_key, prekey_bundle, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (username, public_key, prekey_bundle, int(time.time())))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    def get_user_public_key(self, username: str) -> Optional[UserPublicKey]:
        """获取用户公钥"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_public_keys WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return UserPublicKey(
                username=row[0],
                identity_public_key=row[1],
                prekey_bundle=row[2],
                updated_at=row[3]
            )
        return None

# 测试代码
if __name__ == "__main__":
    from models import DatabaseSchema
    DatabaseSchema.init_database()
    
    db = DatabaseManager()
    
    # 测试用户操作
    test_user = User(
        username="test_user",
        password_hash="hashed_password",
        identity_public_key="test_public_key"
    )
    db.add_user(test_user)
    
    # 测试好友请求
    request_id = db.add_friend_request("user1", "user2")
    print(f"好友请求ID: {request_id}")
    
    # 测试消息添加
    test_message = Message(
        message_id="msg123",
        from_user="user1",
        to_user="user2",
        ciphertext="encrypted_message",
        timestamp=int(time.time()),
        ttl_seconds=3600,
        status="sent"
    )
    db.add_message(test_message)
    
    print("数据库管理类测试完成")
