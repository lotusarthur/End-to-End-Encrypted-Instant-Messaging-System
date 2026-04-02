import time
import logging
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class MessageStatus(Enum):
    """消息状态枚举"""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass
class MessageState:
    """消息状态信息"""
    message_id: str
    status: MessageStatus
    timestamp: int
    retry_count: int = 0
    last_attempt: Optional[int] = None

class MessageStatusManager:
    """消息状态管理器"""
    
    def __init__(self, db, cleanup_interval: int = 3600):
        self.db = db
        self.cleanup_interval = cleanup_interval
        self.message_states: Dict[str, MessageState] = {}
        self._last_cleanup = time.time()
    
    def update_message_status(self, message_id: str, status: MessageStatus) -> bool:
        """更新消息状态"""
        try:
            current_time = int(time.time())
            
            # 更新内存中的状态
            if message_id in self.message_states:
                self.message_states[message_id].status = status
                self.message_states[message_id].timestamp = current_time
            else:
                self.message_states[message_id] = MessageState(
                    message_id=message_id,
                    status=status,
                    timestamp=current_time
                )
            
            # 更新数据库状态
            self.db.update_message_status(message_id, status.value)
            
            logger.info(f"消息状态更新: {message_id} -> {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"更新消息状态失败: {e}")
            return False
    
    def get_message_status(self, message_id: str) -> Optional[MessageStatus]:
        """获取消息状态"""
        if message_id in self.message_states:
            return self.message_states[message_id].status
        
        # 从数据库查询
        db_status = self.db.get_message_status(message_id)
        if db_status:
            status = MessageStatus(db_status)
            self.message_states[message_id] = MessageState(
                message_id=message_id,
                status=status,
                timestamp=int(time.time())
            )
            return status
        
        return None
    
    def increment_retry_count(self, message_id: str) -> int:
        """增加重试计数"""
        if message_id not in self.message_states:
            self.message_states[message_id] = MessageState(
                message_id=message_id,
                status=MessageStatus.SENT,
                timestamp=int(time.time())
            )
        
        self.message_states[message_id].retry_count += 1
        self.message_states[message_id].last_attempt = int(time.time())
        
        return self.message_states[message_id].retry_count
    
    def should_retry(self, message_id: str, max_retries: int = 3) -> bool:
        """检查是否应该重试"""
        if message_id not in self.message_states:
            return True
        
        state = self.message_states[message_id]
        
        # 检查重试次数
        if state.retry_count >= max_retries:
            return False
        
        # 检查重试间隔（指数退避）
        current_time = int(time.time())
        retry_delay = min(2 ** state.retry_count, 60)  # 最大延迟60秒
        
        if state.last_attempt and (current_time - state.last_attempt) < retry_delay:
            return False
        
        return True
    
    def get_expired_messages(self, ttl: int = 86400) -> List[str]:
        """获取过期的消息ID"""
        current_time = int(time.time())
        expired_messages = []
        
        for message_id, state in self.message_states.items():
            if current_time - state.timestamp > ttl:
                expired_messages.append(message_id)
        
        # 从数据库查询更多过期消息
        db_expired = self.db.get_expired_messages(ttl)
        expired_messages.extend(db_expired)
        
        return expired_messages
    
    def cleanup_expired_messages(self, ttl: int = 86400):
        """清理过期消息"""
        try:
            expired_ids = self.get_expired_messages(ttl)
            
            for message_id in expired_ids:
                # 更新状态为过期
                self.update_message_status(message_id, MessageStatus.EXPIRED)
                
                # 从内存中移除
                if message_id in self.message_states:
                    del self.message_states[message_id]
            
            # 清理数据库中的过期消息
            self.db.cleanup_expired_messages(ttl)
            
            logger.info(f"清理了 {len(expired_ids)} 条过期消息")
            
        except Exception as e:
            logger.error(f"清理过期消息失败: {e}")
    
    def periodic_cleanup(self):
        """定期清理"""
        current_time = time.time()
        if current_time - self._last_cleanup >= self.cleanup_interval:
            self.cleanup_expired_messages()
            self._last_cleanup = current_time
    
    def get_delivery_statistics(self, time_range: int = 3600) -> Dict:
        """获取投递统计信息"""
        current_time = int(time.time())
        start_time = current_time - time_range
        
        stats = {
            'total': 0,
            'delivered': 0,
            'read': 0,
            'failed': 0,
            'expired': 0,
            'delivery_rate': 0.0,
            'read_rate': 0.0
        }
        
        # 统计内存中的消息状态
        for state in self.message_states.values():
            if state.timestamp >= start_time:
                stats['total'] += 1
                if state.status == MessageStatus.DELIVERED:
                    stats['delivered'] += 1
                elif state.status == MessageStatus.READ:
                    stats['read'] += 1
                elif state.status == MessageStatus.FAILED:
                    stats['failed'] += 1
                elif state.status == MessageStatus.EXPIRED:
                    stats['expired'] += 1
        
        # 计算比率
        if stats['total'] > 0:
            stats['delivery_rate'] = stats['delivered'] / stats['total']
            stats['read_rate'] = stats['read'] / stats['total']
        
        return stats
