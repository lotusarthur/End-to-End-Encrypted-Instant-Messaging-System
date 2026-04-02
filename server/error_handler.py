import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    MESSAGE_FORMAT_ERROR = "message_format_error"
    TARGET_USER_OFFLINE = "target_user_offline"
    DATABASE_ERROR = "database_error"
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0

@dataclass
class ErrorContext:
    """错误上下文"""
    error_type: ErrorType
    message: Optional[Dict[str, Any]] = None
    user: Optional[str] = None
    timestamp: float = None
    retry_count: int = 0

class ErrorHandler:
    """错误处理和重试机制"""
    
    def __init__(self, db, ws_manager, default_config: RetryConfig = None):
        self.db = db
        self.ws_manager = ws_manager
        self.default_config = default_config or RetryConfig()
        
        # 错误类型特定的重试配置
        self.error_configs = {
            ErrorType.NETWORK_ERROR: RetryConfig(max_retries=5, base_delay=2.0),
            ErrorType.AUTH_ERROR: RetryConfig(max_retries=1),  # 认证错误不重试
            ErrorType.TARGET_USER_OFFLINE: RetryConfig(max_retries=0),  # 用户离线不重试
            ErrorType.MESSAGE_FORMAT_ERROR: RetryConfig(max_retries=0),  # 格式错误不重试
        }
        
        # 错误处理策略
        self.error_handlers = {
            ErrorType.NETWORK_ERROR: self._handle_network_error,
            ErrorType.AUTH_ERROR: self._handle_auth_error,
            ErrorType.TARGET_USER_OFFLINE: self._handle_offline_error,
            ErrorType.MESSAGE_FORMAT_ERROR: self._handle_format_error,
            ErrorType.DATABASE_ERROR: self._handle_database_error,
        }
    
    async def handle_error(self, error_context: ErrorContext, 
                         operation: Callable, *args, **kwargs) -> bool:
        """处理错误并重试操作"""
        config = self.error_configs.get(error_context.error_type, self.default_config)
        
        for attempt in range(config.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(operation):
                    result = await operation(*args, **kwargs)
                else:
                    result = operation(*args, **kwargs)
                
                if result:
                    logger.info(f"操作成功 (尝试 {attempt + 1})")
                    return True
                
                # 操作返回False，继续重试
                logger.warning(f"操作返回False (尝试 {attempt + 1})")
                
            except Exception as e:
                error_context.retry_count = attempt + 1
                error_context.timestamp = time.time()
                
                logger.error(f"操作失败 (尝试 {attempt + 1}): {e}")
                
                # 调用特定的错误处理器
                handler = self.error_handlers.get(error_context.error_type)
                if handler:
                    await handler(error_context)
                
                # 如果是最后一次尝试，记录最终失败
                if attempt == config.max_retries:
                    self._log_final_failure(error_context, e)
                    return False
            
            # 计算下一次重试的延迟
            if attempt < config.max_retries:
                delay = self._calculate_retry_delay(attempt, config)
                logger.info(f"等待 {delay:.1f} 秒后重试...")
                await asyncio.sleep(delay)
        
        return False
    
    def _calculate_retry_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算重试延迟（指数退避）"""
        delay = config.base_delay * (config.backoff_factor ** attempt)
        return min(delay, config.max_delay)
    
    async def _handle_network_error(self, context: ErrorContext):
        """处理网络错误"""
        logger.warning("检测到网络错误，尝试重新连接...")
        
        # 可以在这里实现重新连接逻辑
        # 例如：重新初始化WebSocket连接
        
        # 记录网络错误统计
        self.db.record_error_statistics(
            error_type=context.error_type.value,
            user=context.user,
            timestamp=context.timestamp
        )
    
    async def _handle_auth_error(self, context: ErrorContext):
        """处理认证错误"""
        logger.error("认证错误，需要重新登录")
        
        if context.user:
            # 标记用户需要重新认证
            self.db.mark_user_needs_reauth(context.user)
            
            # 通知用户重新登录
            if self.ws_manager.is_user_online(context.user):
                await self.ws_manager.send_to_user(context.user, {
                    'type': 'auth_error',
                    'message': '请重新登录'
                })
    
    async def _handle_offline_error(self, context: ErrorContext):
        """处理用户离线错误"""
        if context.message and context.user:
            # 存储为离线消息
            self.db.store_offline_message(
                from_user=context.user,
                to_user=context.message.get('to'),
                message_type=context.message.get('type'),
                content=context.message
            )
            logger.info("消息已存储为离线消息")
    
    async def _handle_format_error(self, context: ErrorContext):
        """处理消息格式错误"""
        logger.error("消息格式错误，无法处理")
        
        # 可以发送错误响应给发送方
        if context.user and context.message:
            await self.ws_manager.send_to_user(context.user, {
                'type': 'error',
                'error_type': 'message_format_error',
                'message': '消息格式不正确'
            })
    
    async def _handle_database_error(self, context: ErrorContext):
        """处理数据库错误"""
        logger.error("数据库操作失败")
        
        # 可以尝试重新连接数据库或使用备用存储
        # 这里可以实现数据库重连逻辑
        
        # 记录数据库错误
        self.db.record_error_statistics(
            error_type=context.error_type.value,
            user=context.user,
            timestamp=context.timestamp
        )
    
    def _log_final_failure(self, context: ErrorContext, exception: Exception):
        """记录最终失败"""
        logger.error(f"操作最终失败: {context.error_type.value}")
        
        # 记录详细的错误信息
        error_info = {
            'error_type': context.error_type.value,
            'user': context.user,
            'retry_count': context.retry_count,
            'timestamp': context.timestamp,
            'exception': str(exception)
        }
        
        self.db.record_system_error(error_info)
    
    def create_error_context(self, error_type: ErrorType, **kwargs) -> ErrorContext:
        """创建错误上下文"""
        return ErrorContext(
            error_type=error_type,
            message=kwargs.get('message'),
            user=kwargs.get('user'),
            timestamp=time.time()
        )
    
    async def safe_execute(self, operation: Callable, *args, 
                         expected_error_type: ErrorType = ErrorType.UNKNOWN_ERROR,
                         **kwargs) -> bool:
        """安全执行操作，自动处理错误"""
        error_context = self.create_error_context(expected_error_type)
        
        if 'message' in kwargs:
            error_context.message = kwargs['message']
        if 'user' in kwargs:
            error_context.user = kwargs['user']
        
        return await self.handle_error(error_context, operation, *args, **kwargs)
