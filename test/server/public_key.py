import asyncio
import json
import sqlite3
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Make server/ and shared/ importable when running from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO_ROOT / "server"
SHARED_DIR = REPO_ROOT / "shared"

import sys

sys.path.insert(0, str(SERVER_DIR))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SHARED_DIR))

from database_manager import DatabaseManager
from models import DatabaseSchema, User, UserPublicKey


class TestPublicKeyManagement(unittest.TestCase):
    """测试公钥管理功能：注册、更新、获取公钥"""
    
    def setUp(self):
        """测试前设置"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_messaging.db"
        
        # 初始化测试数据库
        DatabaseSchema.init_database(str(self.db_path))
        self.db = DatabaseManager(str(self.db_path))
    
    def tearDown(self):
        """测试后清理"""
        self.temp_dir.cleanup()
    
    def test_register_user_with_public_key(self):
        """测试注册用户时附带公钥"""
        # 测试数据
        test_username = "testuser1"
        test_password_hash = "hashed_password_123"
        test_public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----"
        
        # 创建用户并附带公钥
        user = User(
            username=test_username,
            password_hash=test_password_hash,
            identity_public_key=test_public_key
        )
        
        # 保存用户
        result = self.db.add_user(user)
        self.assertTrue(result, "用户注册失败")
        
        # 验证用户信息
        saved_user = self.db.get_user(test_username)
        self.assertIsNotNone(saved_user, "用户未正确保存")
        self.assertEqual(saved_user.username, test_username)
        self.assertEqual(saved_user.identity_public_key, test_public_key)
        
        # 验证公钥表
        public_key_info = self.db.get_user_public_key(test_username)
        self.assertIsNotNone(public_key_info, "公钥未正确保存")
        self.assertEqual(public_key_info.identity_public_key, test_public_key)
        self.assertIsNotNone(public_key_info.updated_at)
    
    def test_update_existing_user_public_key(self):
        """测试已有用户更新公钥"""
        # 先注册用户
        test_username = "testuser2"
        initial_public_key = "initial_public_key_123"
        
        user = User(
            username=test_username,
            password_hash="hashed_password",
            identity_public_key=initial_public_key
        )
        self.db.add_user(user)
        
        # 更新公钥
        new_public_key = "updated_public_key_456"
        prekey_bundle = "prekey_bundle_data"
        
        result = self.db.save_user_public_key(test_username, new_public_key, prekey_bundle)
        self.assertTrue(result, "公钥更新失败")
        
        # 验证更新后的公钥
        updated_key = self.db.get_user_public_key(test_username)
        self.assertIsNotNone(updated_key)
        self.assertEqual(updated_key.identity_public_key, new_public_key)
        self.assertEqual(updated_key.prekey_bundle, prekey_bundle)
        self.assertGreater(updated_key.updated_at, time.time() - 10)  # 应该是最近更新的
    
    def test_get_other_user_public_key(self):
        """测试获取其他用户的公钥"""
        # 创建两个用户
        user1 = User(
            username="user1",
            password_hash="hash1",
            identity_public_key="user1_public_key"
        )
        user2 = User(
            username="user2", 
            password_hash="hash2",
            identity_public_key="user2_public_key"
        )
        
        self.db.add_user(user1)
        self.db.add_user(user2)
        
        # 用户1获取用户2的公钥
        user2_public_key = self.db.get_user_public_key("user2")
        self.assertIsNotNone(user2_public_key)
        self.assertEqual(user2_public_key.identity_public_key, "user2_public_key")
        self.assertEqual(user2_public_key.username, "user2")
        
        # 用户2获取用户1的公钥
        user1_public_key = self.db.get_user_public_key("user1")
        self.assertIsNotNone(user1_public_key)
        self.assertEqual(user1_public_key.identity_public_key, "user1_public_key")
    
    def test_public_key_not_found(self):
        """测试获取不存在的用户的公钥"""
        non_existent_key = self.db.get_user_public_key("nonexistent_user")
        self.assertIsNone(non_existent_key, "不存在的用户应该返回None")
    
    def test_multiple_public_key_updates(self):
        """测试多次更新公钥，验证时间戳更新"""
        test_username = "multiuser"
        user = User(
            username=test_username,
            password_hash="hash",
            identity_public_key="key1"
        )
        self.db.add_user(user)
        
        # 第一次更新
        time.sleep(1.1)  # 确保时间戳不同，需要至少1秒
        self.db.save_user_public_key(test_username, "key2")
        key_info_1 = self.db.get_user_public_key(test_username)
        timestamp_1 = key_info_1.updated_at
        
        # 第二次更新
        time.sleep(1.1)
        self.db.save_user_public_key(test_username, "key3")
        key_info_2 = self.db.get_user_public_key(test_username)
        timestamp_2 = key_info_2.updated_at
        
        # 验证时间戳更新
        self.assertGreater(timestamp_2, timestamp_1)
        self.assertEqual(key_info_2.identity_public_key, "key3")


class TestPublicKeyAPI(unittest.TestCase):
    """测试公钥相关的API接口"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_api_messaging.db"
        DatabaseSchema.init_database(str(self.db_path))
        
        # 导入服务器模块
        sys.path.insert(0, str(SERVER_DIR))
        from main import MessagingServer
        
        # 创建测试服务器实例
        self.server = MessagingServer()
        self.server.db = DatabaseManager(str(self.db_path))
    
    def tearDown(self):
        """清理测试环境"""
        self.temp_dir.cleanup()
    
    def _create_test_user(self, username, public_key=None):
        """创建测试用户"""
        import bcrypt
        from models import User
        
        password_hash = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()
        user = User(
            username=username,
            password_hash=password_hash,
            identity_public_key=public_key
        )
        self.server.db.add_user(user)
        return user
    
    def _create_auth_header(self, username):
        """创建认证头"""
        from main import JWT_SECRET, JWT_ALGORITHM
        import jwt
        from datetime import datetime, timedelta
        
        payload = {
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return {'Authorization': f'Bearer {token}'}
    
    async def test_update_public_key_api(self):
        """测试更新公钥API"""
        # 创建测试用户
        test_user = self._create_test_user("apiuser", "old_public_key")
        auth_headers = self._create_auth_header("apiuser")
        
        # 模拟API请求
        from aiohttp import web
        from aiohttp.test_utils import make_mocked_request
        
        request = make_mocked_request(
            'PUT', 
            '/api/v1/users/me/public-key',
            headers=auth_headers,
            payload=json.dumps({
                'identity_public_key': 'new_public_key_123',
                'prekey_bundle': 'test_prekey_bundle'
            })
        )
        
        # 调用API方法
        response = await self.server.update_my_public_key(request)
        
        # 验证响应
        self.assertEqual(response.status, 200)
        response_data = json.loads(response.text)
        self.assertEqual(response_data['message'], '公钥更新成功')
        self.assertEqual(response_data['username'], 'apiuser')
        
        # 验证数据库更新
        updated_key = self.server.db.get_user_public_key('apiuser')
        self.assertEqual(updated_key.identity_public_key, 'new_public_key_123')
        self.assertEqual(updated_key.prekey_bundle, 'test_prekey_bundle')
    
    async def test_update_public_key_unauthorized(self):
        """测试未授权访问更新公钥API"""
        from aiohttp.test_utils import make_mocked_request
        
        request = make_mocked_request('PUT', '/api/v1/users/me/public-key')
        response = await self.server.update_my_public_key(request)
        
        self.assertEqual(response.status, 401)
        response_data = json.loads(response.text)
        self.assertEqual(response_data['error'], '未授权，请先登录')
    
    async def test_update_public_key_invalid_json(self):
        """测试无效JSON格式"""
        test_user = self._create_test_user("jsonuser")
        auth_headers = self._create_auth_header("jsonuser")
        
        from aiohttp.test_utils import make_mocked_request
        
        request = make_mocked_request(
            'PUT',
            '/api/v1/users/me/public-key',
            headers=auth_headers,
            payload="invalid json"
        )
        
        response = await self.server.update_my_public_key(request)
        self.assertEqual(response.status, 400)
        response_data = json.loads(response.text)
        self.assertEqual(response_data['error'], '无效的JSON格式')
    
    async def test_update_public_key_missing_required_field(self):
        """测试缺少必需字段"""
        test_user = self._create_test_user("fielduser")
        auth_headers = self._create_auth_header("fielduser")
        
        from aiohttp.test_utils import make_mocked_request
        
        request = make_mocked_request(
            'PUT',
            '/api/v1/users/me/public-key',
            headers=auth_headers,
            payload=json.dumps({'prekey_bundle': 'only_bundle'})  # 缺少identity_public_key
        )
        
        response = await self.server.update_my_public_key(request)
        self.assertEqual(response.status, 400)
        response_data = json.loads(response.text)
        self.assertEqual(response_data['error'], '身份公钥不能为空')


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)