#!/usr/bin/env python3
"""
定时任务管理器
定时删除未被拉取的消息和其他清理任务
"""

import asyncio
import time
import logging
from typing import List, Callable
from datetime import datetime, timedelta
from database_manager import DatabaseManager
from message_manager import MessageManager

class TaskScheduler:
    """定时任务管理器 - 定时删除未被拉取的消息"""
    
    def __init__(self, db_manager: DatabaseManager, message_manager: MessageManager):
        self.db_manager = db_manager
        self.message_manager = message_manager
        self.tasks: List[asyncio.Task] = []
        self.is_running = False
        self.logger = logging.getLogger(__name__)
    
    async def start(self) -> None:
        """启动定时任务"""
        if self.is_running:
            return
        
        self.is_running = True
        self.logger.info("定时任务管理器启动")
        
        # 启动各个定时任务
        tasks = [
            asyncio.create_task(self._cleanup_expired_messages_task()),
            asyncio.create_task(self._cleanup_old_undelivered_messages_task()),
            asyncio.create_task(self._cleanup_old_friend_requests_task()),
            asyncio.create_task(self._update_user_online_status_task())
        ]
        
        self.tasks.extend(tasks)
        
        try:
            # 等待所有任务完成（实际上会一直运行）
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error(f"定时任务执行异常: {e}")
        finally:
            self.is_running = False
    
    async def stop(self) -> None:
        """停止定时任务"""
        self.is_running = False
        for task in self.tasks:
            task.cancel()
        
        # 等待所有任务取消
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.logger.info("定时任务管理器已停止")
    
    async def _cleanup_expired_messages_task(self) -> None:
        """清理过期消息任务 - 每分钟执行一次"""
        while self.is_running:
            try:
                cleaned_count = await self.message_manager.cleanup_expired_messages()
                if cleaned_count > 0:
                    self.logger.info(f"清理了 {cleaned_count} 条过期消息")
            except Exception as e:
                self.logger.error(f"清理过期消息失败: {e}")
            
            await asyncio.sleep(60)  # 每分钟执行一次
    
    async def _cleanup_old_undelivered_messages_task(self) -> None:
        """清理长时间未被拉取的离线消息 - 每5分钟执行一次"""
        while self.is_running:
            try:
                cleaned_count = await self._cleanup_old_undelivered_messages()
                if cleaned_count > 0:
                    self.logger.info(f"清理了 {cleaned_count} 条长时间未拉取的消息")
            except Exception as e:
                self.logger.error(f"清理未拉取消息失败: {e}")
            
            await asyncio.sleep(300)  # 每5分钟执行一次
    
    async def _cleanup_old_undelivered_messages(self) -> int:
        """清理超过7天未被拉取的离线消息"""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            current_time = int(time.time())
            seven_days_ago = current_time - (7 * 24 * 3600)  # 7天前
            
            # 查找超过7天未被拉取的消息
            cursor.execute('''
                SELECT message_id FROM messages 
                WHERE status = 'sent' AND timestamp < ?
            ''', (seven_days_ago,))
            
            old_messages = cursor.fetchall()
            old_count = len(old_messages)
            
            if old_count > 0:
                # 删除这些消息
                cursor.execute('''
                    DELETE FROM messages 
                    WHERE status = 'sent' AND timestamp < ?
                ''', (seven_days_ago,))
                
                # 从消息管理器的待投递列表中移除
                for msg_id, in old_messages:
                    for user, messages in self.message_manager.pending_deliveries.items():
                        if msg_id in messages:
                            messages.remove(msg_id)
                            break
                
                conn.commit()
                self.logger.warning(f"删除了 {old_count} 条超过7天未被拉取的消息")
            
            conn.close()
            return old_count
        except Exception as e:
            self.logger.error(f"清理未拉取消息失败: {e}")
            return 0
    
    async def _cleanup_old_friend_requests_task(self) -> None:
        """清理过期好友请求"""
        while self.is_running:
            try:
                cleaned_count = await self._cleanup_old_friend_requests()
                if cleaned_count > 0:
                    self.logger.info(f"清理了 {cleaned_count} 条过期好友请求")
            except Exception as e:
                self.logger.error(f"清理过期好友请求失败: {e}")
            
            await asyncio.sleep(self.config.cleanup_friend_requests_interval)
    
    async def _cleanup_old_friend_requests(self) -> int:
        """清理超过配置时长未处理的好友请求"""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            current_time = int(time.time())
            retention_threshold = current_time - self.config.friend_requests_retention
            
            # 将超过配置时长的待处理请求标记为过期
            cursor.execute('''
                UPDATE friend_relationships 
                SET status = 'expired' 
                WHERE status = 'pending' AND created_at < ?
            ''', (retention_threshold,))
            
            expired_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return expired_count
        except Exception as e:
            self.logger.error(f"清理过期好友请求失败: {e}")
            return 0
    
    async def _update_user_online_status_task(self) -> None:
        """更新用户在线状态"""
        while self.is_running:
            try:
                await self._update_user_online_status()
            except Exception as e:
                self.logger.error(f"更新用户在线状态失败: {e}")
            
            await asyncio.sleep(self.config.update_online_status_interval)
    
    async def _update_user_online_status(self) -> None:
        """将超过配置时长未活动的用户标记为离线"""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            current_time = int(time.time())
            offline_threshold = current_time - self.config.user_offline_threshold
            
            cursor.execute('''
                UPDATE users 
                SET is_online = FALSE 
                WHERE is_online = TRUE AND last_seen < ?
            ''', (offline_threshold,))
            
            offline_count = cursor.rowcount
            if offline_count > 0:
                self.logger.info(f"将 {offline_count} 个用户标记为离线")
            
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"更新用户在线状态失败: {e}")
    
    def get_scheduler_status(self) -> Dict[str, any]:
        """获取定时任务状态"""
        return {
            'is_running': self.is_running,
            'active_tasks': len(self.tasks),
            'pending_deliveries': sum(len(messages) for messages in self.message_manager.pending_deliveries.values())
        }

# 集成测试
async def test_scheduler():
    from models import DatabaseSchema
    DatabaseSchema.init_database()
    
    db_manager = DatabaseManager()
    message_manager = MessageManager(db_manager)
    scheduler = TaskScheduler(db_manager, message_manager)
    
    print("启动定时任务管理器...")
    
    # 运行10秒后停止
    scheduler_task = asyncio.create_task(scheduler.start())
    await asyncio.sleep(10)
    
    print("停止定时任务管理器...")
    await scheduler.stop()
    
    print("定时任务管理器测试完成")

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(test_scheduler())