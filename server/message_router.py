import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MessageRoute:
    """消息路由信息"""
    target_user: str
    message_type: str
    priority: int  # 优先级：0-高，1-中，2-低
    require_ack: bool

class MessageRouter:
    """消息路由分发器"""
    
    def __init__(self, ws_manager, db, max_retries: int = 3):
        self.ws_manager = ws_manager
        self.db = db
        self.max_retries = max_retries
        self.pending_messages: Dict[str, asyncio.Task] = {}
        
        # 消息类型到路由规则的映射
        self.routing_rules = {
            'message': MessageRoute(target_user='to', message_type='message', priority=1, require_ack=True),
            'friend_request': MessageRoute(target_user='to_user', message_type='friend_request', priority=0, require_ack=True),
            'key_exchange': MessageRoute(target_user='to', message_type='key_exchange', priority=0, require_ack=True),
            'system_notification': MessageRoute(target_user='to', message_type='system', priority=2, require_ack=False)
        }
    
    async def route_message(self, from_user: str, message: Dict[str, Any]) -> bool:
        """路由分发消息"""
        msg_type = message.get('type')
        
        if msg_type not in self.routing_rules:
            logger.warning(f"未知的消息类型，无法路由: {msg_type}")
            return False
        
        route_rule = self.routing_rules[msg_type]
        target_user = message.get(route_rule.target_user)
        
        if not target_user:
            logger.error(f"消息缺少目标用户字段: {route_rule.target_user}")
            return False
        
        # 创建路由任务
        task = asyncio.create_task(
            self._deliver_message(from_user, target_user, message, route_rule)
        )
        
        # 跟踪待处理消息
        message_id = message.get('message_id')
        if message_id:
            self.pending_messages[message_id] = task
        
        return True
    
    async def _deliver_message(self, from_user: str, target_user: str, 
                             message: Dict[str, Any], route_rule: MessageRoute) -> bool:
        """投递消息到目标用户"""
        for attempt in range(self.max_retries):
            try:
                # 检查目标用户是否在线
                if self.ws_manager.is_user_online(target_user):
                    # 实时投递
                    success = await self.ws_manager.send_to_user(target_user, message)
                    
                    if success and route_rule.require_ack:
                        # 等待确认
                        ack_received = await self._wait_for_ack(message.get('message_id'))
                        if ack_received:
                            return True
                    elif success:
                        return True
                
                # 如果实时投递失败或用户离线，存储为离线消息
                if attempt == self.max_retries - 1:
                    self._store_offline_message(from_user, target_user, message, route_rule)
                    return True
                
                # 等待重试
                await asyncio.sleep(2 ** attempt)  # 指数退避
                
            except Exception as e:
                logger.error(f"投递消息失败 (尝试 {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    self._store_offline_message(from_user, target_user, message, route_rule)
                    return False
        
        return False
    
    async def _wait_for_ack(self, message_id: str, timeout: int = 30) -> bool:
        """等待消息确认"""
        try:
            # 这里可以实现等待ACK的逻辑
            # 简化实现：直接返回True
            await asyncio.sleep(0.1)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"等待消息 {message_id} 确认超时")
            return False
    
    def _store_offline_message(self, from_user: str, target_user: str, 
                             message: Dict[str, Any], route_rule: MessageRoute):
        """存储离线消息"""
        try:
            self.db.store_offline_message(
                from_user=from_user,
                to_user=target_user,
                message_type=route_rule.message_type,
                content=message,
                priority=route_rule.priority
            )
            logger.info(f"消息已存储为离线消息: {from_user} -> {target_user}")
        except Exception as e:
            logger.error(f"存储离线消息失败: {e}")
    
    def cancel_pending_message(self, message_id: str):
        """取消待处理的消息"""
        if message_id in self.pending_messages:
            self.pending_messages[message_id].cancel()
            del self.pending_messages[message_id]
    
    async def cleanup(self):
        """清理资源"""
        for task in self.pending_messages.values():
            task.cancel()
        self.pending_messages.clear()
