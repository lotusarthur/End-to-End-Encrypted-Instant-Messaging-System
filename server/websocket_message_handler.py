import json
import logging
import time
from typing import Dict, Any
from security_utils import security

logger = logging.getLogger(__name__)

class WebSocketMessageHandler:
    """WebSocket消息处理器"""
    
    def __init__(self, ws_manager, db):
        self.ws_manager = ws_manager
        self.db = db
        self.message_handlers = {
            'message': self._handle_chat_message,
            'ack': self._handle_message_ack,
            'friend_request_response': self._handle_friend_request_response,
            'key_exchange': self._handle_key_exchange
        }
    
    async def handle_message(self, from_user: str, raw_message: str) -> bool:
        """处理WebSocket消息"""
        try:
            message = json.loads(raw_message)
            msg_type = message.get('type')
            
            if msg_type not in self.message_handlers:
                logger.warning(f"未知的消息类型: {msg_type}")
                return False
            
            handler = self.message_handlers[msg_type]
            await handler(from_user, message)
            return True
            
        except json.JSONDecodeError:
            logger.error(f"消息JSON格式错误: {raw_message}")
            return False
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            return False
    
    async def _handle_chat_message(self, from_user: str, message: Dict[str, Any]):
        """处理聊天消息 - 适配加密包格式"""
        # 提取加密包格式字段
        message_id = message.get('message_id')
        sender_id = message.get('sender_id')
        receiver_id = message.get('receiver_id')
        ciphertext_b64 = message.get('ciphertext_b64')
        nonce_b64 = message.get('nonce_b64')
        mac_tag_b64 = message.get('mac_tag_b64')
        ad_serialized = message.get('ad_serialized')
        
        if not all([message_id, sender_id, receiver_id, ciphertext_b64, nonce_b64, mac_tag_b64, ad_serialized]):
            logger.warning(f"加密包格式消息不完整: {message}")
            return
        
        # 验证发送者身份
        if sender_id != from_user:
            logger.warning(f"发送者身份不匹配: 声称的发送者 {sender_id} 与当前用户 {from_user}")
            return
        
        # 存储消息到数据库 - 使用加密包格式
        stored_message = self.db.store_message(
            message_id=message_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            ciphertext_b64=ciphertext_b64,
            nonce_b64=nonce_b64,
            mac_tag_b64=mac_tag_b64,
            ad_serialized=ad_serialized,
            timestamp=message.get('timestamp', int(time.time())),
            ttl_seconds=message.get('ttl_seconds', 86400)
        )
        
        # 尝试实时转发 - 使用完整的加密包格式
        if self.ws_manager.is_user_online(receiver_id):
            success = await self.ws_manager.send_to_user(receiver_id, {
                'type': 'message',
                'message_id': message_id,
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'ciphertext_b64': ciphertext_b64,
                'nonce_b64': nonce_b64,
                'mac_tag_b64': mac_tag_b64,
                'ad_serialized': ad_serialized,
                'timestamp': stored_message.timestamp,
                'ttl_seconds': stored_message.ttl_seconds,
                'status': 'delivered'
            })
            
            if success:
                # 更新消息状态为已送达
                self.db.update_message_status(stored_message.message_id, 'delivered')
        else:
            # 存储为离线消息
            self.db.store_offline_message(stored_message)
    
    async def _handle_message_ack(self, from_user: str, message: Dict[str, Any]):
        """处理消息确认"""
        message_id = message.get('message_id')
        ack_type = message.get('ack_type', 'delivered')  # delivered or read
        
        if message_id:
            self.db.update_message_status(message_id, ack_type)
    
    async def _handle_friend_request_response(self, from_user: str, message: Dict[str, Any]):
        """处理好友请求响应"""
        request_id = message.get('request_id')
        response = message.get('response')  # accepted or declined
        
        if request_id and response:
            self.db.update_friend_request_status(request_id, response)
            
            # 通知请求发送方
            friend_request = self.db.get_friend_request(request_id)
            if friend_request and self.ws_manager.is_user_online(friend_request.from_user):
                await self.ws_manager.send_to_user(friend_request.from_user, {
                    'type': 'friend_request_response',
                    'request_id': request_id,
                    'response': response,
                    'from_user': from_user
                })
    
    async def _handle_key_exchange(self, from_user: str, message: Dict[str, Any]):
        """处理密钥交换消息"""
        to_user = message.get('to')
        key_data = message.get('key_data')
        
        if to_user and key_data:
            # 存储会话密钥
            self.db.store_session_key(from_user, to_user, key_data)
            
            # 转发给目标用户
            if self.ws_manager.is_user_online(to_user):
                await self.ws_manager.send_to_user(to_user, {
                    'type': 'key_exchange',
                    'from': from_user,
                    'key_data': key_data
                })