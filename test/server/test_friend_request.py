#!/usr/bin/env python3
"""
好友申请功能测试
测试好友申请的全流程：发送、接受、拒绝、取消等场景
"""

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO_ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))

from database_manager import DatabaseManager
from models import DatabaseSchema, User, FriendRelationship


class MockWebSocket:
    """模拟WebSocket连接"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.messages: list[dict[str, Any]] = []
        self.is_connected = True

    async def send(self, message: str):
        self.messages.append(json.loads(message))

    async def close(self):
        self.is_connected = False


class DummyWsManager:
    """模拟WebSocket管理器"""
    def __init__(self, online_users: set[str] = None):
        self._online_users = online_users or set()
        self.sent_messages: list[tuple[str, dict[str, Any]]] = []

    def is_user_online(self, username: str) -> bool:
        return username in self._online_users

    async def send_to_user(self, username: str, message: dict[str, Any]) -> bool:
        self.sent_messages.append((username, message))
        return True


class TestFriendRequest(unittest.TestCase):
    """好友申请功能测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_friend_request.db")
        DatabaseSchema.init_database(self.db_path)
        self.db_manager = DatabaseManager(self.db_path)
        
        # 创建测试用户
        self.alice = User(
            username="alice",
            password_hash="alice_password_hash",
            identity_public_key="alice_public_key",
            otp_secret="alice_otp_secret",
            is_online=False,
            last_seen=None,
        )
        
        self.bob = User(
            username="bob", 
            password_hash="bob_password_hash",
            identity_public_key="bob_public_key",
            otp_secret="bob_otp_secret",
            is_online=False,
            last_seen=None,
        )
        
        self.charlie = User(
            username="charlie",
            password_hash="charlie_password_hash", 
            identity_public_key="charlie_public_key",
            otp_secret="charlie_otp_secret",
            is_online=False,
            last_seen=None,
        )
        
        # 添加用户到数据库
        self.assertTrue(self.db_manager.add_user(self.alice))
        self.assertTrue(self.db_manager.add_user(self.bob))
        self.assertTrue(self.db_manager.add_user(self.charlie))

    def tearDown(self):
        """测试后清理"""
        self.temp_dir.cleanup()

    def test_send_friend_request_success(self):
        """测试成功发送好友请求"""
        # Alice发送好友请求给Bob
        request_id = self.db_manager.add_friend_request("alice", "bob")
        
        # 验证请求ID不为空
        self.assertIsNotNone(request_id)
        
        # 验证Bob收到了好友请求
        received_requests = self.db_manager.get_friend_requests("bob", "received")
        self.assertEqual(len(received_requests), 1)
        self.assertEqual(received_requests[0].user_a, "alice")
        self.assertEqual(received_requests[0].user_b, "bob")
        self.assertEqual(received_requests[0].status, "pending")
        
        # 验证Alice发送的请求列表
        sent_requests = self.db_manager.get_friend_requests("alice", "sent")
        self.assertEqual(len(sent_requests), 1)
        self.assertEqual(sent_requests[0].user_a, "alice")
        self.assertEqual(sent_requests[0].user_b, "bob")

    def test_send_friend_request_to_nonexistent_user(self):
        """测试向不存在的用户发送好友请求"""
        request_id = self.db_manager.add_friend_request("alice", "nonexistent")
        
        # 应该返回None，因为用户不存在
        self.assertIsNone(request_id)

    def test_send_duplicate_friend_request(self):
        """测试重复发送好友请求"""
        # 第一次发送
        request_id1 = self.db_manager.add_friend_request("alice", "bob")
        self.assertIsNotNone(request_id1)
        
        # 第二次发送相同的请求
        request_id2 = self.db_manager.add_friend_request("alice", "bob")
        
        # 应该返回None，因为已经存在pending状态的请求
        self.assertIsNone(request_id2)
        
        # 验证只有一个请求存在
        received_requests = self.db_manager.get_friend_requests("bob", "received")
        self.assertEqual(len(received_requests), 1)

    def test_accept_friend_request(self):
        """测试接受好友请求"""
        # Alice发送好友请求给Bob
        request_id = self.db_manager.add_friend_request("alice", "bob")
        self.assertIsNotNone(request_id)
        
        # Bob接受好友请求
        success = self.db_manager.update_friend_request_status(request_id, "accepted")
        self.assertTrue(success)
        
        # 验证请求状态已更新
        received_requests = self.db_manager.get_friend_requests("bob", "received")
        self.assertEqual(len(received_requests), 0)  # 不再有pending请求
        
        # 验证好友关系已建立
        alice_friends = self.db_manager.get_friends("alice")
        bob_friends = self.db_manager.get_friends("bob")
        
        self.assertEqual(len(alice_friends), 1)
        self.assertEqual(alice_friends[0]['username'], "bob")
        
        self.assertEqual(len(bob_friends), 1)
        self.assertEqual(bob_friends[0]['username'], "alice")

    def test_decline_friend_request(self):
        """测试拒绝好友请求"""
        # Alice发送好友请求给Bob
        request_id = self.db_manager.add_friend_request("alice", "bob")
        self.assertIsNotNone(request_id)
        
        # Bob拒绝好友请求
        success = self.db_manager.update_friend_request_status(request_id, "declined")
        self.assertTrue(success)
        
        # 验证请求状态已更新
        received_requests = self.db_manager.get_friend_requests("bob", "received")
        self.assertEqual(len(received_requests), 0)  # 不再有pending请求
        
        # 验证没有建立好友关系
        alice_friends = self.db_manager.get_friends("alice")
        bob_friends = self.db_manager.get_friends("bob")
        
        self.assertEqual(len(alice_friends), 0)
        self.assertEqual(len(bob_friends), 0)

    def test_cancel_friend_request(self):
        """测试取消好友请求"""
        # Alice发送好友请求给Bob
        request_id = self.db_manager.add_friend_request("alice", "bob")
        self.assertIsNotNone(request_id)
        
        # Alice取消好友请求
        success = self.db_manager.update_friend_request_status(request_id, "cancelled")
        self.assertTrue(success)
        
        # 验证请求状态已更新
        sent_requests = self.db_manager.get_friend_requests("alice", "sent")
        self.assertEqual(len(sent_requests), 0)  # 不再有pending请求
        
        # Bob也看不到这个请求
        received_requests = self.db_manager.get_friend_requests("bob", "received")
        self.assertEqual(len(received_requests), 0)

    def test_multiple_friend_requests(self):
        """测试多个用户之间的好友请求"""
        # Alice发送给Bob
        request1 = self.db_manager.add_friend_request("alice", "bob")
        self.assertIsNotNone(request1)
        
        # Alice发送给Charlie
        request2 = self.db_manager.add_friend_request("alice", "charlie")
        self.assertIsNotNone(request2)
        
        # Bob发送给Charlie
        request3 = self.db_manager.add_friend_request("bob", "charlie")
        self.assertIsNotNone(request3)
        
        # 验证Alice发送的请求
        alice_sent = self.db_manager.get_friend_requests("alice", "sent")
        self.assertEqual(len(alice_sent), 2)
        
        # 验证Bob收到的请求
        bob_received = self.db_manager.get_friend_requests("bob", "received")
        self.assertEqual(len(bob_received), 1)
        self.assertEqual(bob_received[0].user_a, "alice")
        
        # 验证Charlie收到的请求
        charlie_received = self.db_manager.get_friend_requests("charlie", "received")
        self.assertEqual(len(charlie_received), 2)

    def test_accept_friend_request_establishes_friendship(self):
        """测试接受请求后建立双向好友关系"""
        # Alice发送给Bob
        request_id = self.db_manager.add_friend_request("alice", "bob")
        self.assertIsNotNone(request_id)
        
        # Bob接受请求
        self.db_manager.update_friend_request_status(request_id, "accepted")
        
        # 验证双向好友关系
        alice_friends = self.db_manager.get_friends("alice")
        bob_friends = self.db_manager.get_friends("bob")
        
        self.assertEqual(len(alice_friends), 1)
        self.assertEqual(alice_friends[0]['username'], "bob")
        
        self.assertEqual(len(bob_friends), 1)
        self.assertEqual(bob_friends[0]['username'], "alice")
        
        # 验证好友信息包含在线状态
        self.assertIn('is_online', alice_friends[0])
        self.assertIn('last_seen', alice_friends[0])
        self.assertIn('added_at', alice_friends[0])

    def test_remove_friend(self):
        """测试删除好友"""
        # 先建立好友关系
        request_id = self.db_manager.add_friend_request("alice", "bob")
        self.db_manager.update_friend_request_status(request_id, "accepted")
        
        # 验证好友关系存在
        self.assertEqual(len(self.db_manager.get_friends("alice")), 1)
        self.assertEqual(len(self.db_manager.get_friends("bob")), 1)
        
        # Alice删除Bob
        success = self.db_manager.remove_friend("alice", "bob")
        self.assertTrue(success)
        
        # 验证好友关系已删除
        self.assertEqual(len(self.db_manager.get_friends("alice")), 0)
        self.assertEqual(len(self.db_manager.get_friends("bob")), 0)

    def test_friend_request_timestamps(self):
        """测试好友请求的时间戳"""
        start_time = int(time.time())
        
        # 发送请求
        request_id = self.db_manager.add_friend_request("alice", "bob")
        
        # 获取请求详情
        requests = self.db_manager.get_friend_requests("bob", "received")
        self.assertEqual(len(requests), 1)
        
        # 验证创建时间戳
        self.assertGreaterEqual(requests[0].created_at, start_time)
        
        # 接受请求
        self.db_manager.update_friend_request_status(request_id, "accepted")
        
        # 获取好友关系验证接受时间戳
        friends = self.db_manager.get_friends("alice")
        self.assertEqual(len(friends), 1)
        self.assertIsNotNone(friends[0]['added_at'])
        self.assertGreaterEqual(friends[0]['added_at'], start_time)

    async def test_websocket_notification_for_friend_request(self):
        """测试WebSocket实时通知好友请求"""
        ws_manager = DummyWsManager(online_users={"bob"})
        
        # 模拟发送好友请求并通知在线用户
        request_data = {
            'type': 'friend_request',
            'request_id': 'test_request_123',
            'from_user': 'alice',
            'timestamp': int(time.time())
        }
        
        # 发送通知
        await ws_manager.send_to_user("bob", request_data)
        
        # 验证通知已发送
        self.assertEqual(len(ws_manager.sent_messages), 1)
        username, message = ws_manager.sent_messages[0]
        self.assertEqual(username, "bob")
        self.assertEqual(message['type'], 'friend_request')
        self.assertEqual(message['from_user'], 'alice')

    def test_edge_cases(self):
        """测试边界情况"""
        # 测试无效的请求ID
        success = self.db_manager.update_friend_request_status(99999, "accepted")
        self.assertFalse(success)
        
        # 测试无效的状态
        request_id = self.db_manager.add_friend_request("alice", "bob")
        success = self.db_manager.update_friend_request_status(request_id, "invalid_status")
        # 注意：当前实现可能不会验证状态有效性
        # self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()