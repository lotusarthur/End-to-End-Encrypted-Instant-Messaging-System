#!/usr/bin/env python3
"""
端到端加密即时通讯服务器
支持REST API和WebSocket实时通信
"""

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import jwt
import bcrypt
import pyotp
import websockets
from aiohttp import web
from dataclasses import dataclass, asdict

# 导入OTP库
import pyotp

# 导入OTP库
import pyotp

# 导入统一的数据库管理器
from database_manager import DatabaseManager
from models import DatabaseSchema, User, FriendRelationship, Message
from security_utils import security

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT配置
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"

@dataclass
class FriendRequest:
    """好友请求"""
    request_id: str
    from_user: str
    to_user: str
    status: str  # pending, accepted, declined, cancelled
    created_at: int = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = int(time.time())

class WebSocketManager:
    """WebSocket连接管理"""
    
    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
    
    async def add_connection(self, username: str, websocket):
        """添加WebSocket连接"""
        self.connections[username] = websocket
        logger.info(f"用户 {username} 已连接")
    
    async def remove_connection(self, username: str):
        """移除WebSocket连接"""
        if username in self.connections:
            del self.connections[username]
            logger.info(f"用户 {username} 已断开连接")
    
    async def send_to_user(self, username: str, message: dict):
        """向指定用户发送消息"""
        if username in self.connections:
            try:
                await self.connections[username].send(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"向用户 {username} 发送消息失败: {e}")
                await self.remove_connection(username)
        return False
    
    def is_user_online(self, username: str) -> bool:
        """检查用户是否在线"""
        return username in self.connections

class MessagingServer:
    """即时通讯服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 80):
        self.host = host
        self.port = port
        # 初始化数据库表结构
        from pathlib import Path
        # 获取server目录下的messaging.db路径
        db_path = str(Path(__file__).parent / "messaging.db")
        DatabaseSchema.init_database(db_path)
        self.db = DatabaseManager(db_path)
        self.ws_manager = WebSocketManager()
        self.app = web.Application()
        self._setup_routes()
        self._setup_middleware()
    
    def _setup_middleware(self):
        """设置中间件"""
        # 添加全局错误处理中间件
        async def error_handling_middleware(app, handler):
            async def middleware_handler(request):
                try:
                    response = await handler(request)
                    return response
                except Exception as e:
                    import traceback
                    logger.error(f"请求处理错误: {e}")
                    logger.error(f"请求路径: {request.path}")
                    logger.error(f"请求方法: {request.method}")
                    logger.error(f"详细错误信息: {traceback.format_exc()}")
                    logger.error(f"错误类型: {type(e).__name__}")
                    from aiohttp import web
                    return web.json_response({
                        'error': 'Internal server error', 
                        'details': str(e), 
                        'error_type': type(e).__name__,
                        'path': request.path,
                        'method': request.method
                    }, status=500)
            return middleware_handler
        
        # 添加内容安全策略中间件
        async def csp_middleware(app, handler):
            async def middleware_handler(request):
                try:
                    response = await handler(request)
                    
                    # 添加CSP头
                    response.headers['Content-Security-Policy'] = security.get_csp_header()
                    
                    # 添加其他安全头
                    response.headers['X-Content-Type-Options'] = 'nosniff'
                    response.headers['X-Frame-Options'] = 'DENY'
                    response.headers['X-XSS-Protection'] = '1; mode=block'
                    
                    return response
                except Exception as e:
                    import traceback
                    logger.error(f"CSP中间件错误: {e}")
                    logger.error(f"详细错误信息: {traceback.format_exc()}")
                    logger.error(f"错误类型: {type(e).__name__}")
                    from aiohttp import web
                    return web.json_response({
                        'error': 'Middleware error', 
                        'details': str(e), 
                        'error_type': type(e).__name__,
                        'path': request.path
                    }, status=500)
            return middleware_handler
        
        # 注册中间件 - 注意顺序很重要
        self.app.middlewares.append(error_handling_middleware)
        self.app.middlewares.append(csp_middleware)
    
    def _setup_routes(self):
        """设置API路由"""
        # 认证相关
        self.app.router.add_post('/api/v1/users', self.register)
        self.app.router.add_post('/api/v1/auth/login', self.login)
        self.app.router.add_post('/api/v1/auth/logout', self.logout)
        self.app.router.add_post('/api/v1/auth/refresh', self.refresh_token)
        
        # 用户相关
        self.app.router.add_get('/api/v1/users/me', self.get_my_info)
        self.app.router.add_get('/api/v1/users/{username}/public-key', self.get_public_key)
        self.app.router.add_put('/api/v1/users/me/public-key', self.update_my_public_key)
        
        # 好友相关
        self.app.router.add_post('/api/v1/friend-requests', self.send_friend_request)
        self.app.router.add_get('/api/v1/friend-requests', self.get_friend_requests)
        self.app.router.add_put('/api/v1/friend-requests/{request_id}', self.update_friend_request)
        self.app.router.add_delete('/api/v1/friend-requests/{request_id}', self.cancel_friend_request)
        self.app.router.add_get('/api/v1/friends', self.get_friends)
        self.app.router.add_delete('/api/v1/friends/{username}', self.remove_friend)
        self.app.router.add_post('/api/v1/friends/{username}/block', self.block_user)
        
        # 消息相关
        self.app.router.add_post('/api/v1/messages', self.send_message)
        self.app.router.add_get('/api/v1/messages/offline', self.get_offline_messages)
        
        # 消息相关
        self.app.router.add_post('/api/v1/messages', self.send_message)
        self.app.router.add_get('/api/v1/messages/offline', self.get_offline_messages)
    
    async def _get_user_from_token(self, request: web.Request) -> Optional[User]:
        """从JWT token中获取用户"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = payload.get('username')
            return self.db.get_user(username)
        except jwt.InvalidTokenError:
            return None
    
    def _create_token(self, username: str) -> str:
        """创建JWT token"""
        payload = {
            'username': username,
            'exp': datetime.utcnow() + timedelta(days=7)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # REST API处理函数
    async def register(self, request: web.Request) -> web.Response:
        """用户注册"""
        try:
            '''
            # 调试功能：查看原始请求体
            raw_body = await request.text()
            logger.info(f"接收到的原始数据: {raw_body}")
            '''
            try:
                data = await request.json()
            except json.JSONDecodeError as e:
                # 调试功能：查看原始请求体
                raw_body = await request.text()
                logger.error(f"JSON解析失败: {e}")
                logger.error(f"原始请求体: {raw_body}")
                logger.error(f"请求头: {dict(request.headers)}")
                logger.error(f"请求方法: {request.method}")
                logger.error(f"请求路径: {request.path}")
                # 尝试修复非标准JSON格式（缺少双引号的属性名和值）
                try:
                    # 修复属性名和属性值的双引号
                    import re
                    # 第一步：为属性名添加双引号
                    fixed_body = re.sub(r'(\w+):', r'"\1":', raw_body)
                    # 第二步：为字符串值添加双引号（匹配 : 后面的非特殊字符）
                    fixed_body = re.sub(r':(\w+)', r':"\1"', fixed_body)
                    logger.info(f"修复后的JSON: {fixed_body}")
                    data = json.loads(fixed_body)
                except Exception as fix_error:
                    logger.error(f"JSON修复失败: {fix_error}")
                    logger.error(f"修复错误详情: {str(fix_error)}")
                    return web.json_response({'error': 'Invalid JSON format. Please use standard JSON format: {"username":"testuser","password":"testpass"}'}, status=400)
            
            username = data.get('username')
            password = data.get('password')
            identity_public_key = data.get('identity_public_key')
            otp_secret = data.get('otp_secret')
            
            if not username or not password:
                return web.json_response({'error': 'Username and password cannot be empty'}, status=400)
            
            # XSS安全防护：用户名验证和清理
            sanitized_username = security.sanitize_username(username)
            if not sanitized_username:
                return web.json_response({'error': 'Invalid username format. Username must be 3-20 characters and contain only letters, numbers, underscores, and hyphens.'}, status=400)
            
            username = sanitized_username
            
            # 检查用户是否已存在
            if self.db.get_user(username):
                return web.json_response({'error': 'User already exists'}, status=400)
            
            # 创建用户 - 使用models.py中的User类
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(
                username=username, 
                password_hash=password_hash, 
                identity_public_key=identity_public_key,
                otp_secret=otp_secret,
                is_online=False,
                last_seen=None
            )
            
            if self.db.add_user(user):
                # 如果提供了公钥，同时保存到user_public_keys表
                if identity_public_key:
                    self.db.save_user_public_key(username, identity_public_key, None)
                
                return web.json_response({
                    'user_id': username,
                    'message': 'Registration successful'
                }, status=201)
            else:
                return web.json_response({'error': 'Registration failed'}, status=500)
                
        except Exception as e:
            import traceback
            logger.error(f"注册失败: {e}")
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            logger.error(f"错误类型: {type(e).__name__}")
            return web.json_response({'error': 'Internal server error', 'details': str(e), 'error_type': type(e).__name__}, status=500)
    
    async def login(self, request: web.Request) -> web.Response:
        """用户登录"""
        try:
            # 捕获并记录原始请求数据
            raw_body = await request.text()
            logger.debug(f"登录请求原始数据: {raw_body}")
            
            # 尝试解析JSON
            try:
                data = json.loads(raw_body)
            except json.JSONDecodeError as json_err:
                logger.error(f"登录JSON解析失败: {json_err}")
                logger.error(f"原始请求体: {raw_body}")
                logger.error(f"请求头: {dict(request.headers)}")
                logger.error(f"请求方法: {request.method}")
                logger.error(f"请求路径: {request.path}")
                return web.json_response({'error': '无效的JSON格式'}, status=400)
            
            username = data.get('username')
            password = data.get('password')
            otp_code = data.get('otp_code')
            
            if not username or not password:
                return web.json_response({'error': '用户名和密码不能为空'}, status=400)
            
            user = self.db.get_user(username)
            if not user:
                return web.json_response({'error': '用户不存在'}, status=401)
            
            # 验证密码
            if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                return web.json_response({'error': '密码错误'}, status=401)
            
            # 验证OTP（如果启用）
            if user.otp_secret:
                logger.debug(f"开始OTP验证，用户: {username}")
                if not otp_code:
                    logger.debug("OTP验证失败: 未提供验证码")
                    return web.json_response({'error': '需要OTP验证码'}, status=401)
                logger.debug(f"接收到的OTP验证码: {otp_code}")
                totp = pyotp.TOTP(user.otp_secret)
                current_code = totp.now()
                logger.debug(f"生成的当前OTP验证码: {current_code}")
                # 允许前后1个时间窗口的误差，以解决时间同步问题
                if not totp.verify(otp_code, valid_window=1):
                    logger.debug(f"OTP验证失败: 验证码不匹配")
                    return web.json_response({'error': 'OTP验证码错误'}, status=401)
                logger.info(f"OTP验证成功，用户: {username}")
                logger.debug(f"OTP验证详情: 提供的验证码={otp_code}, 当前验证码={current_code}")
            
            # 创建token
            token = self._create_token(username)
            
            return web.json_response({
                'token': token,
                'message': '登录成功'
            })
                
        except Exception as e:
            import traceback
            logger.error(f"登录失败: {e}")
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            logger.error(f"错误类型: {type(e).__name__}")
            global last_error_info
            last_error_info = {
                'error': str(e),
                'error_type': type(e).__name__,
                'traceback': traceback.format_exc()
            }
            return web.json_response({'error': 'Internal server error', 'details': str(e), 'error_type': type(e).__name__}, status=500)
    
    async def logout(self, request: web.Request) -> web.Response:
        """用户登出"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        # 更新在线状态
        self.db.update_user_online_status(user.username, False)
        
        return web.json_response({'message': 'Logout successful'})
    
    async def refresh_token(self, request: web.Request) -> web.Response:
        """刷新token"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        new_token = self._create_token(user.username)
        return web.json_response({'token': new_token})
    
    async def get_my_info(self, request: web.Request) -> web.Response:
        """获取当前用户信息"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        return web.json_response({
            'username': user.username,
            'created_at': user.created_at,
            'is_online': user.is_online
        })
    
    async def get_public_key(self, request: web.Request) -> web.Response:
        """获取用户公钥"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        username = request.match_info['username']
        target_user = self.db.get_user(username)
        if not target_user:
            return web.json_response({'error': '用户不存在'}, status=404)
        
        # 首先尝试从user_public_keys表获取公钥
        public_key_entry = self.db.get_user_public_key(username)
        if public_key_entry and public_key_entry.identity_public_key:
            return web.json_response({
                'identity_public_key': public_key_entry.identity_public_key
            })
        
        # 如果没有找到，从users表获取
        if target_user.identity_public_key:
            return web.json_response({
                'identity_public_key': target_user.identity_public_key
            })
        
        # 如果两个表都没有公钥，返回错误
        return web.json_response({'error': '公钥不存在'}, status=404)

    
    async def update_my_public_key(self, request: web.Request) -> web.Response:
        """更新当前用户的公钥（需要登录状态）"""
        # 验证用户登录状态
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权，请先登录'}, status=401)
        
        try:
            data = await request.json()
            identity_public_key = data.get('identity_public_key')
            prekey_bundle = data.get('prekey_bundle')
            
            if not identity_public_key:
                return web.json_response({'error': '身份公钥不能为空'}, status=400)
            
            # 更新用户公钥
            if self.db.save_user_public_key(user.username, identity_public_key, prekey_bundle):
                logger.info(f"用户 {user.username} 更新了公钥")
                return web.json_response({
                    'message': '公钥更新成功',
                    'username': user.username,
                    'updated_at': int(time.time())
                })
            else:
                return web.json_response({'error': '公钥更新失败'}, status=500)
                
        except json.JSONDecodeError:
            return web.json_response({'error': '无效的JSON格式'}, status=400)
        except Exception as e:
            logger.error(f"更新公钥失败: {e}")
            return web.json_response({'error': '服务器内部错误'}, status=500)
    
    async def send_friend_request(self, request: web.Request) -> web.Response:
        """发送好友请求"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        data = await request.json()
        to_user = data.get('to_user')
        
        if not to_user:
            return web.json_response({'error': '目标用户不能为空'}, status=400)
        
        # XSS安全防护：目标用户名验证和清理
        sanitized_to_user = security.sanitize_username(to_user)
        if not sanitized_to_user:
            return web.json_response({'error': 'Invalid target username format'}, status=400)
        
        to_user = sanitized_to_user
        
        if to_user == user.username:
            return web.json_response({'error': '不能添加自己为好友'}, status=400)
        
        target_user = self.db.get_user(to_user)
        if not target_user:
            return web.json_response({'error': '目标用户不存在'}, status=404)
        
        # 创建好友请求
        request_id = self.db.add_friend_request(user.username, to_user)
        if request_id:
            # 如果目标用户在线，实时通知
            if self.ws_manager.is_user_online(to_user):
                await self.ws_manager.send_to_user(to_user, {
                    'type': 'friend_request',
                    'request_id': str(request_id),
                    'from_user': user.username,
                    'timestamp': int(time.time())
                })
            
            return web.json_response({'request_id': str(request_id)})
        else:
            return web.json_response({'error': '发送好友请求失败'}, status=500)
    
    async def get_friend_requests(self, request: web.Request) -> web.Response:
        """获取好友请求列表"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        request_type = request.query.get('type', 'received')
        requests = self.db.get_friend_requests(user.username, request_type)
        
        return web.json_response({
            'requests': requests
        })
    
    async def update_friend_request(self, request: web.Request) -> web.Response:
        """更新好友请求状态"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        request_id = request.match_info['request_id']
        data = await request.json()
        status = data.get('status')
        
        if status not in ['accepted', 'declined']:
            return web.json_response({'error': '无效的状态'}, status=400)
        
        try:
            # 尝试转换请求ID为整数
            try:
                req_id = int(request_id)
            except ValueError:
                # 如果转换失败，尝试将其作为用户名处理
                req_id = request_id
            
            logger.info(f"处理好友请求: {req_id}")
            
            # 获取请求详情
            if isinstance(req_id, int):
                friend_request = self.db.get_friend_request(req_id)
            else:
                # 尝试通过用户名查找好友请求
                friend_request = None
                # 查找来自该用户的待处理请求
                conn = self.db._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM friend_relationships 
                    WHERE user_a = ? AND user_b = ? AND status = 'pending'
                ''', (req_id, user.username))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    friend_request = {
                        'id': row[0],
                        'from_user': row[1],
                        'to_user': row[2],
                        'status': row[3],
                        'created_at': row[4],
                        'accepted_at': row[5]
                    }
            
            if not friend_request:
                logger.warning(f"好友请求不存在: {req_id}")
                return web.json_response({'error': '请求不存在'}, status=404)
            
            # 验证请求接收者是否为当前用户
            if friend_request['to_user'] != user.username:
                logger.warning(f"无权操作此请求: {req_id}, 当前用户: {user.username}, 请求接收者: {friend_request['to_user']}")
                return web.json_response({'error': '无权操作此请求'}, status=403)
            
            # 使用数据库中的正确请求ID更新状态
            actual_request_id = friend_request['id']
            self.db.update_friend_request_status(actual_request_id, status)
            logger.info(f"好友请求状态更新成功: {actual_request_id}, 新状态: {status}")
            
            # 如果接受请求，通知发送方
            if status == 'accepted' and self.ws_manager.is_user_online(friend_request['from_user']):
                await self.ws_manager.send_to_user(friend_request['from_user'], {
                    'type': 'friend_request_response',
                    'request_id': str(actual_request_id),
                    'response': 'accepted',
                    'from_user': user.username
                })
                logger.info(f"已通知请求发送方: {friend_request['from_user']}")
            
            return web.json_response({'message': '操作成功'})
        except Exception as e:
            logger.error(f"处理好友请求失败: {e}")
            return web.json_response({'error': '服务器内部错误'}, status=500)
    
    async def cancel_friend_request(self, request: web.Request) -> web.Response:
        """取消好友请求"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        request_id = request.match_info['request_id']
        try:
            # 获取请求详情
            friend_request = self.db.get_friend_request(int(request_id))
            if not friend_request:
                return web.json_response({'error': '请求不存在'}, status=404)
            
            # 验证请求发送者是否为当前用户
            if friend_request['from_user'] != user.username:
                return web.json_response({'error': '无权操作此请求'}, status=403)
            
            self.db.update_friend_request_status(int(request_id), 'cancelled')
            
            return web.json_response({'message': '取消成功'})
        except ValueError:
            return web.json_response({'error': '无效的请求ID'}, status=400)
    
    async def get_friends(self, request: web.Request) -> web.Response:
        """获取好友列表"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        friends = self.db.get_friends(user.username)
        
        return web.json_response({
            'friends': friends
        })
    
    async def remove_friend(self, request: web.Request) -> web.Response:
        """删除好友"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        username = request.match_info['username']
        # 在实际实现中需要删除好友关系
        
        return web.json_response({'message': '删除成功'})
    
    async def block_user(self, request: web.Request) -> web.Response:
        """屏蔽用户"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        username = request.match_info['username']
        # 在实际实现中需要添加屏蔽逻辑
        
        return web.json_response({'message': '屏蔽成功'})
    
    async def send_message(self, request: web.Request) -> web.Response:
        """发送消息"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        try:
            data = await request.json()
            message_id = data.get('message_id')
            sender_id = data.get('sender_id')
            receiver_id = data.get('receiver_id')
            ciphertext_b64 = data.get('ciphertext_b64')
            nonce_b64 = data.get('nonce_b64')
            mac_tag_b64 = data.get('mac_tag_b64')
            ad_serialized = data.get('ad_serialized')
            timestamp = data.get('timestamp', int(time.time()))
            ttl_seconds = data.get('ttl_seconds', 86400)
            
            # 验证必需字段
            if not all([message_id, sender_id, receiver_id, ciphertext_b64, nonce_b64, mac_tag_b64, ad_serialized]):
                return web.json_response({'error': '消息格式不完整'}, status=400)
            
            # 验证发送者身份
            if sender_id != user.username:
                return web.json_response({'error': '发送者身份不匹配'}, status=403)
            
            # 验证是否为好友
            if not self.db.are_friends(sender_id, receiver_id):
                return web.json_response({'error': '只能向好友发送消息'}, status=403)
            
            # 存储消息
            message = Message(
                message_id=message_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                ciphertext_b64=ciphertext_b64,
                nonce_b64=nonce_b64,
                mac_tag_b64=mac_tag_b64,
                ad_serialized=ad_serialized,
                timestamp=timestamp,
                ttl_seconds=ttl_seconds,
                status='sent',
                signature=mac_tag_b64
            )
            self.db.store_message(message)
            
            # 如果目标用户在线，实时转发
            if self.ws_manager.is_user_online(receiver_id):
                await self.ws_manager.send_to_user(receiver_id, {
                    'type': 'message',
                    'message_id': message_id,
                    'sender_id': sender_id,
                    'receiver_id': receiver_id,
                    'ciphertext_b64': ciphertext_b64,
                    'nonce_b64': nonce_b64,
                    'mac_tag_b64': mac_tag_b64,
                    'ad_serialized': ad_serialized,
                    'timestamp': timestamp,
                    'ttl_seconds': ttl_seconds,
                    'status': 'delivered'
                })
                self.db.update_message_status(message_id, 'delivered')
            
            return web.json_response({'message_id': message_id})
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return web.json_response({'error': '服务器内部错误'}, status=500)
    
    async def get_offline_messages(self, request: web.Request) -> web.Response:
        """获取离线消息"""
        user = await self._get_user_from_token(request)
        if not user:
            return web.json_response({'error': '未授权'}, status=401)
        
        try:
            offline_messages = self.db.get_offline_messages(user.username)
            # 转换为前端期望的格式
            messages = []
            for msg in offline_messages:
                messages.append({
                    'message_id': msg.message_id,
                    'sender_id': msg.sender_id,
                    'receiver_id': msg.receiver_id,
                    'ciphertext_b64': msg.ciphertext_b64,
                    'nonce_b64': msg.nonce_b64,
                    'mac_tag_b64': msg.mac_tag_b64,
                    'ad_serialized': msg.ad_serialized,
                    'timestamp': msg.timestamp,
                    'ttl_seconds': msg.ttl_seconds,
                    'status': msg.status,
                    'signature': msg.signature
                })
            return web.json_response({'messages': messages})
        except Exception as e:
            logger.error(f"获取离线消息失败: {e}")
            return web.json_response({'error': '服务器内部错误'}, status=500)
    
    # WebSocket处理
    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket连接处理"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # 验证token
        token = request.query.get('token')
        if not token:
            await ws.close(code=4001, message='缺少token')
            return ws
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = payload.get('username')
            user = self.db.get_user(username)
            
            if not user:
                await ws.close(code=4001, message='用户不存在')
                return ws
            
            # 添加连接
            await self.ws_manager.add_connection(username, ws)
            self.db.update_user_online_status(username, True)
            
            # 发送离线消息
            offline_messages = self.db.get_offline_messages(username)
            for msg in offline_messages:
                await ws.send(json.dumps({
                    'type': 'message',
                    'message_id': msg.message_id,
                    'sender_id': msg.sender_id,
                    'receiver_id': msg.receiver_id,
                    'ciphertext_b64': msg.ciphertext_b64,
                    'nonce_b64': msg.nonce_b64,
                    'mac_tag_b64': msg.mac_tag_b64,
                    'ad_serialized': msg.ad_serialized,
                    'timestamp': msg.timestamp,
                    'ttl_seconds': msg.ttl_seconds,
                    'status': 'delivered',
                    'signature': msg.signature
                }))
                # 更新消息状态为已送达
                self.db.update_message_status(msg.message_id, 'delivered')
            
            # 处理消息
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_websocket_message(user, data)
                    except json.JSONDecodeError:
                        logger.warning(f"收到无效的JSON消息: {msg.data}")
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket错误: {ws.exception()}")
            
        except jwt.InvalidTokenError:
            await ws.close(code=4001, message='无效的token')
        except Exception as e:
            logger.error(f"WebSocket处理错误: {e}")
        finally:
            if 'username' in locals():
                await self.ws_manager.remove_connection(username)
                self.db.update_user_online_status(username, False)
        
        return ws
    
    async def _handle_websocket_message(self, user: User, data: dict):
        """处理WebSocket消息"""
        msg_type = data.get('type')
        
        if msg_type == 'message':
            # 处理EncryptedNetworkPackage格式的消息
            message_id = data.get('message_id')
            sender_id = data.get('sender_id')
            receiver_id = data.get('receiver_id')
            ciphertext_b64 = data.get('ciphertext_b64')
            nonce_b64 = data.get('nonce_b64')
            mac_tag_b64 = data.get('mac_tag_b64')
            ad_serialized = data.get('ad_serialized')
            timestamp = data.get('timestamp', int(time.time()))
            ttl_seconds = data.get('ttl_seconds', 86400)
            
            # 验证必需字段
            if not all([message_id, sender_id, receiver_id, ciphertext_b64, nonce_b64, mac_tag_b64, ad_serialized]):
                logger.warning(f"收到不完整的EncryptedNetworkPackage消息: {data}")
                return
            
            # 验证发送者身份
            if sender_id != user.username:
                logger.warning(f"发送者身份不匹配: 声称的发送者 {sender_id} 与当前用户 {user.username}")
                return
            
            # 验证是否为好友
            if not self.db.are_friends(sender_id, receiver_id):
                logger.warning(f"非好友间通信: {sender_id} -> {receiver_id}")
                return
            
            # 存储消息 - 直接使用加密包格式的Message结构
            message = Message(
                message_id=message_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                ciphertext_b64=ciphertext_b64,
                nonce_b64=nonce_b64,
                mac_tag_b64=mac_tag_b64,
                ad_serialized=ad_serialized,
                timestamp=timestamp,
                ttl_seconds=ttl_seconds,
                status='sent',
                signature=mac_tag_b64  # 使用mac_tag作为签名
            )
            self.db.store_message(message)
            
            # 如果目标用户在线，实时转发完整的EncryptedNetworkPackage
            if self.ws_manager.is_user_online(receiver_id):
                await self.ws_manager.send_to_user(receiver_id, {
                    'type': 'message',
                    'message_id': message_id,
                    'sender_id': sender_id,
                    'receiver_id': receiver_id,
                    'ciphertext_b64': ciphertext_b64,
                    'nonce_b64': nonce_b64,
                    'mac_tag_b64': mac_tag_b64,
                    'ad_serialized': ad_serialized,
                    'timestamp': timestamp,
                    'ttl_seconds': ttl_seconds,
                    'status': 'delivered'
                })
                self.db.update_message_status(message_id, 'delivered')
            
            logger.info(f"消息 {message_id} 已从 {sender_id} 发送到 {receiver_id}")
        
        elif msg_type == 'ack':
            # 处理消息确认
            message_id = data.get('message_id')
            status = data.get('status', 'read')
            
            if message_id:
                self.db.update_message_status(message_id, status)
        
        elif msg_type == 'friend_request_response':
            # 处理好友请求响应
            request_id = data.get('request_id')
            response = data.get('response')
            
            if request_id and response:
                try:
                    # 获取请求详情
                    friend_request = self.db.get_friend_request(int(request_id))
                    if friend_request and friend_request['to_user'] == user.username:
                        # 更新状态
                        self.db.update_friend_request_status(int(request_id), response)
                        
                        # 通知请求发送方
                        if self.ws_manager.is_user_online(friend_request['from_user']):
                            await self.ws_manager.send_to_user(friend_request['from_user'], {
                                'type': 'friend_request_response',
                                'request_id': request_id,
                                'response': response,
                                'from_user': user.username
                            })
                except ValueError:
                    logger.warning(f"无效的好友请求ID: {request_id}")
    
    async def start(self):
        """启动服务器"""
        # 添加WebSocket路由
        self.app.router.add_get('/api/v1/ws', self.websocket_handler)
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"服务器启动在 http://{self.host}:{self.port}")
        logger.info(f"WebSocket端点: ws://{self.host}:{self.port}/api/v1/ws")
    
    async def stop(self):
        """停止服务器"""
        await self.app.shutdown()
        await self.app.cleanup()

async def main():
    """主函数"""
    server = MessagingServer(host="0.0.0.0", port=80)
    
    try:
        await server.start()
        
        # 保持运行
        while True:
            await asyncio.sleep(3600)  # 每小时检查一次
            
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭服务器...")
        await server.stop()
    except Exception as e:
        logger.error(f"服务器错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())