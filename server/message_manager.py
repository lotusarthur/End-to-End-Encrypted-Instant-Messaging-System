#!/usr/bin/env python3
"""
消息状态管理器
处理已发送、已送达状态管理
"""

import asyncio
import time
from typing import Dict, Set, List, Optional
from dataclasses import dataclass
from database_manager import DatabaseManager

@dataclass
class MessageDeliveryStatus:
    """消息投递状态"""
    message_id: str
    from_user: str
    to_user: str
    status: str  # 'sent', 'delivered', 'read'
    timestamp: int
    delivered_at: Optional[int] = None
    read_at: Optional[int] = None

class MessageManager:
    """消息状态管理器 - 处理已发送、已送达状态管理"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.pending_deliveries: Dict[str, Set[str]] = {}  # user -> set of message_ids
        self.delivery_callbacks: Dict[str, List[callable]] = {}  # message_id -> callbacks
    
    async def mark_message_sent(self, message_id: str, from_user: str, to_user: str) -> bool:
        """标记消息为已发送状态"""
        try:
            # 添加到待投递列表
            if to_user not in self.pending_deliveries:
                self.pending_deliveries[to_user] = set()
            self.pending_deliveries[to_user].add(message_id)
            
            print(f"消息 {message_id} 标记为已发送，等待用户 {to_user} 上线")
            return True
        except Exception as e:
            print(f"标记消息发送状态失败: {e}")
            return False
    
    async def mark_message_delivered(self, message_id: str) -> bool:
        """标记消息为已送达状态"""
        try:
            # 更新数据库状态
            success = self.db_manager.update_message_status(message_id, 'delivered')
            
            if success:
                # 从待投递列表中移除
                for user, messages in self.pending_deliveries.items():
                    if message_id in messages:
                        messages.remove(message_id)
                        break
                
                # 触发送达回调
                if message_id in self.delivery_callbacks:
                    for callback in self.delivery_callbacks[message_id]:
                        try:
                            await callback(message_id, 'delivered')
                        except Exception as e:
                            print(f"送达回调执行失败: {e}")
                    del self.delivery_callbacks[message_id]
                
                print(f"消息 {message_id} 已标记为送达")
                return True
            return False
        except Exception as e:
            print(f"标记消息送达状态失败: {e}")
            return False
    
    async def mark_message_read(self, message_id: str) -> bool:
        """标记消息为已读状态"""
        try:
            success = self.db_manager.update_message_status(message_id, 'read')
            if success:
                print(f"消息 {message_id} 已标记为已读")
                return True
            return False
        except Exception as e:
            print(f"标记消息已读状态失败: {e}")
            return False
    
    def get_undelivered_messages(self, username: str) -> List[str]:
        """获取用户未送达的消息ID列表"""
        if username in self.pending_deliveries:
            return list(self.pending_deliveries[username])
        return []
    
    async def notify_user_online(self, username: str) -> None:
        """通知用户上线，准备投递离线消息"""
        try:
            # 获取离线消息
            offline_messages = self.db_manager.get_offline_messages(username)
            
            if offline_messages:
                print(f"用户 {username} 上线，准备投递 {len(offline_messages)} 条离线消息")
                
                # 这里可以触发WebSocket推送或其他通知机制
                for msg in offline_messages:
                    # 在实际实现中，这里应该通过WebSocket推送消息
                    await self.mark_message_delivered(msg.message_id)
            
        except Exception as e:
            print(f"处理用户上线通知失败: {e}")
    
    def register_delivery_callback(self, message_id: str, callback: callable) -> None:
        """注册消息送达回调"""
        if message_id not in self.delivery_callbacks:
            self.delivery_callbacks[message_id] = []
        self.delivery_callbacks[message_id].append(callback)
    
    async def cleanup_expired_messages(self) -> int:
        """清理过期消息"""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            current_time = int(time.time())
            cursor.execute('''
                SELECT message_id FROM messages 
                WHERE timestamp + ttl_seconds < ?
            ''', (current_time,))
            
            expired_messages = cursor.fetchall()
            expired_count = len(expired_messages)
            
            if expired_count > 0:
                # 删除过期消息
                cursor.execute('''
                    DELETE FROM messages 
                    WHERE timestamp + ttl_seconds < ?
                ''', (current_time,))
                
                # 从待投递列表中移除过期消息
                for msg_id, in expired_messages:
                    for user, messages in self.pending_deliveries.items():
                        if msg_id in messages:
                            messages.remove(msg_id)
                            break
                
                conn.commit()
                print(f"清理了 {expired_count} 条过期消息")
            
            conn.close()
            return expired_count
        except Exception as e:
            print(f"清理过期消息失败: {e}")
            return 0

# 测试代码
async def test_message_manager():
    from models import DatabaseSchema
    DatabaseSchema.init_database()
    
    db_manager = DatabaseManager()
    message_manager = MessageManager(db_manager)
    
    # 测试消息状态管理
    test_message_id = "test_msg_123"
    
    # 标记发送
    await message_manager.mark_message_sent(test_message_id, "user1", "user2")
    
    # 注册送达回调
    async def delivery_callback(msg_id, status):
        print(f"回调: 消息 {msg_id} 状态变为 {status}")
    
    message_manager.register_delivery_callback(test_message_id, delivery_callback)
    
    # 模拟送达
    await message_manager.mark_message_delivered(test_message_id)
    
    print("消息状态管理器测试完成")

if __name__ == "__main__":
    asyncio.run(test_message_manager())