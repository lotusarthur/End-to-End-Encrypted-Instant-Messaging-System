#!/usr/bin/env python3
"""
端到端加密即时通讯系统模拟测试
测试以下四个场景：
1. 两位用户注册自己的身份
2. 一位用户向另一位在线用户发送信息
3. 一位用户向另一位离线用户发送信息
4. 一位用户登录后拉取离线时服务器缓存的信息
"""

import asyncio
import json
import time
import uuid
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Set

from database_manager import DatabaseManager
from models import User, Message, FriendRelationship, DatabaseSchema, EncryptedNetworkPackage
from message_manager import MessageManager

class MockWebSocket:
    """模拟WebSocket连接"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.messages: List[dict] = []
        self.is_connected = True
    
    async def send(self, message: str):
        """模拟发送消息"""
        self.messages.append(json.loads(message))
        print(f"用户 {self.user_id} 收到消息: {message}")
    
    async def close(self):
        """模拟关闭连接"""
        self.is_connected = False

class TestScenarioRunner:
    """测试场景运行器"""
    
    def __init__(self):
        # 在初始化时完全清理测试数据库
        self._clean_test_database()
        
        # 初始化数据库
        DatabaseSchema.init_database("test_messaging.db")
        self.db_manager = DatabaseManager("test_messaging.db")
        self.message_manager = MessageManager(self.db_manager)
        
        # 模拟在线用户连接
        self.online_users: Dict[str, MockWebSocket] = {}
        
        # 测试用户数据
        self.test_users = {
            "alice": {
                "password": "alice_password",
                "public_key": "alice_public_key_123"
            },
            "bob": {
                "password": "bob_password", 
                "public_key": "bob_public_key_456"
            }
        }
    
    def _clean_test_database(self):
        """清理测试数据库中的所有数据"""
        print("清理测试数据库...")
        try:
            conn = sqlite3.connect("test_messaging.db")
            cursor = conn.cursor()
            
            # 删除所有表中的数据（按依赖顺序）
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM friend_relationships") 
            cursor.execute("DELETE FROM users")
            
            conn.commit()
            conn.close()
            print("✓ 测试数据库清理完成")
        except Exception as e:
            print(f"清理数据库时出错: {e}")
            # 如果数据库文件不存在，创建新的
            if "no such table" in str(e):
                print("数据库表不存在，将在初始化时创建")
    
    async def scenario_1_user_registration(self):
        """场景1: 两位用户注册自己的身份"""
        print("\n=== 场景1: 用户注册测试 ===")
        
        # 注册Alice
        alice = User(
            username="alice",
            password_hash="alice_password_hash",
            identity_public_key="alice_public_key_123",
            otp_secret="alice_otp_secret",
            is_online=False,
            last_seen=None
        )
        
        # 注册Bob
        bob = User(
            username="bob",
            password_hash="bob_password_hash", 
            identity_public_key="bob_public_key_456",
            otp_secret="bob_otp_secret",
            is_online=False,
            last_seen=None
        )
        
        # 添加到数据库
        try:
            print("正在注册用户 alice...")
            success1 = self.db_manager.add_user(alice)
            print(f"alice 注册结果: {success1}")
            
            print("正在注册用户 bob...")
            success2 = self.db_manager.add_user(bob)
            print(f"bob 注册结果: {success2}")
            
            if success1 and success2:
                print("✓ 用户注册成功: alice 和 bob")
                
                # 验证用户是否成功添加
                print("验证数据库中的用户数据...")
                alice_from_db = self.db_manager.get_user("alice")
                bob_from_db = self.db_manager.get_user("bob")
                
                print(f"从数据库获取的 alice: {alice_from_db}")
                print(f"从数据库获取的 bob: {bob_from_db}")
                
                if alice_from_db and bob_from_db:
                    print(f"✓ 数据库验证成功: alice={alice_from_db.username}, bob={bob_from_db.username}")
                    print(f"alice 在线状态: {alice_from_db.is_online}")
                    print(f"bob 在线状态: {bob_from_db.is_online}")
                else:
                    print("✗ 数据库验证失败")
                    print(f"  alice_from_db: {alice_from_db}")
                    print(f"  bob_from_db: {bob_from_db}")
                    return False
            else:
                print("✗ 用户注册失败")
                print(f"  alice注册结果: {success1}")
                print(f"  bob注册结果: {success2}")
                
                # 检查数据库连接和表结构
                print("检查数据库状态...")
                try:
                    conn = sqlite3.connect("test_messaging.db")
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    print(f"数据库中的表: {tables}")
                    
                    if tables:
                        cursor.execute("SELECT * FROM users LIMIT 5")
                        users = cursor.fetchall()
                        print(f"users 表中的数据: {users}")
                        
                        # 检查users表的结构
                        cursor.execute("PRAGMA table_info(users)")
                        columns = cursor.fetchall()
                        print(f"users表结构: {columns}")
                    conn.close()
                except Exception as db_error:
                    print(f"数据库检查失败: {db_error}")
                    import traceback
                    traceback.print_exc()
                
                return False
        except Exception as e:
            print(f"✗ 用户注册过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True
    
    async def scenario_2_online_message_send(self):
        """场景2: 一位用户向另一位在线用户发送信息"""
        print("\n=== 场景2: 在线消息发送测试 ===")
        
        # 模拟Alice和Bob都在线
        alice_ws = MockWebSocket("alice")
        bob_ws = MockWebSocket("bob")
        self.online_users["alice"] = alice_ws
        self.online_users["bob"] = bob_ws
        
        # 更新用户在线状态
        self.db_manager.update_user_online_status("alice", True)
        self.db_manager.update_user_online_status("bob", True)
        
        # Alice向Bob发送EncryptedNetworkPackage格式的消息
        message_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # 创建完整的EncryptedNetworkPackage
        encrypted_package = EncryptedNetworkPackage(
            message_id=message_id,
            sender_id="alice",
            receiver_id="bob",
            ciphertext_b64="ZW5jcnlwdGVkX29ubGluZV9tZXNzYWdlX2NvbnRlbnQ=",  # Base64编码的密文
            nonce_b64="bm9uY2VfZm9yX29ubGluZV9tZXNzYWdl",
            mac_tag_b64="bWFjX3RhZ19mb3Jfb25saW5lX21lc3NhZ2U=",
            ad_serialized='{"message_type": "text", "version": "1.0"}',
            timestamp=timestamp,
            ttl_seconds=3600,
            status="sent"
        )
        
        # 转换为Message格式存储（保持向后兼容）
        message = Message(
            message_id=message_id,
            from_user="alice",
            to_user="bob",
            ciphertext=encrypted_package.ciphertext_b64,
            timestamp=timestamp,
            ttl_seconds=3600,
            status="sent",
            signature=encrypted_package.mac_tag_b64
        )
        
        # 保存消息到数据库
        success = self.db_manager.add_message(message)
        
        if success:
            print("✓ 在线消息保存成功")
            print(f"  消息ID: {message_id}")
            print(f"  发送者: alice -> 接收者: bob")
            print(f"  密文: {encrypted_package.ciphertext_b64[:30]}...")
            
            # 模拟实时消息投递（使用EncryptedNetworkPackage格式）
            await self._deliver_encrypted_message_to_online_user(encrypted_package)
            
            # 验证Bob是否收到完整的EncryptedNetworkPackage消息
            if len(bob_ws.messages) > 0:
                last_message = bob_ws.messages[-1]
                
                # 验证消息结构
                required_fields = ['message_id', 'sender_id', 'receiver_id', 'ciphertext_b64', 
                                  'nonce_b64', 'mac_tag_b64', 'ad_serialized']
                
                if all(field in last_message for field in required_fields):
                    print("✓ 在线消息实时投递成功")
                    print(f"  Bob收到完整的EncryptedNetworkPackage消息")
                    print(f"  消息ID: {last_message['message_id']}")
                    print(f"  发送者: {last_message['sender_id']}")
                    print(f"  接收者: {last_message['receiver_id']}")
                else:
                    print("✗ 在线消息投递失败 - 消息结构不完整")
                    print(f"  收到的消息: {last_message}")
                    return False
            else:
                print("✗ 在线消息投递失败 - Bob未收到消息")
                return False
        else:
            print("✗ 在线消息保存失败")
            return False
        
        return True
    
    async def scenario_3_offline_message_send(self):
        """场景3: 一位用户向另一位离线用户发送信息"""
        print("\n=== 场景3: 离线消息发送测试 ===")
        
        # 模拟Bob离线
        if "bob" in self.online_users:
            await self.online_users["bob"].close()
            del self.online_users["bob"]
        self.db_manager.update_user_online_status("bob", False)
        
        # Alice向离线Bob发送EncryptedNetworkPackage格式的消息
        message_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # 创建完整的EncryptedNetworkPackage
        encrypted_package = EncryptedNetworkPackage(
            message_id=message_id,
            sender_id="alice",
            receiver_id="bob",
            ciphertext_b64="ZW5jcnlwdGVkX29mZmxpbmVfbWVzc2FnZV9jb250ZW50",  # Base64编码的密文
            nonce_b64="bm9uY2VfZm9yX29mZmxpbmVfbWVzc2FnZQ==",
            mac_tag_b64="bWFjX3RhZ19mb3Jfb2ZmbGluZV9tZXNzYWdl",
            ad_serialized='{"message_type": "text", "version": "1.0"}',
            timestamp=timestamp,
            ttl_seconds=3600,
            status="sent"
        )
        
        # 转换为Message格式存储
        message = Message(
            message_id=message_id,
            from_user="alice",
            to_user="bob",
            ciphertext=encrypted_package.ciphertext_b64,
            timestamp=timestamp,
            ttl_seconds=3600,
            status="sent",
            signature=encrypted_package.mac_tag_b64
        )
        
        # 保存消息到数据库
        success = self.db_manager.add_message(message)
        
        if success:
            print("✓ 离线消息保存成功")
            print(f"  消息ID: {message_id}")
            print(f"  发送者: alice -> 接收者: bob")
            print(f"  密文: {encrypted_package.ciphertext_b64[:30]}...")
            
            # 标记消息为已发送但未投递
            await self.message_manager.mark_message_sent(message_id, "alice", "bob")
            
            # 验证Bob是否在线（应该不在线）
            bob_user = self.db_manager.get_user("bob")
            if not bob_user:
                print("✗ 错误：Bob用户不存在")
                return False
            
            if not bob_user.is_online:
                print("✓ 离线消息正确缓存（Bob确实离线）")
                
                # 检查消息状态 - 通过获取离线消息列表来验证
                offline_messages = self.db_manager.get_offline_messages("bob")
                message_found = any(msg.message_id == message_id for msg in offline_messages)
                if message_found:
                    print("✓ 离线消息状态正确")
                    
                    # 验证离线消息包含完整的EncryptedNetworkPackage字段
                    offline_message = next((msg for msg in offline_messages if msg.message_id == message_id), None)
                    if offline_message and offline_message.ciphertext == encrypted_package.ciphertext_b64:
                        print("✓ 离线消息内容正确")
                    else:
                        print("✗ 离线消息内容不正确")
                        return False
                else:
                    print("✗ 离线消息状态不正确")
                    return False
            else:
                print("✗ Bob在线状态不正确")
                return False
        else:
            print("✗ 离线消息保存失败")
            return False
        
        return True
    
    async def scenario_4_offline_message_retrieval(self):
        """场景4: 用户登录后拉取离线时服务器缓存的信息"""
        print("\n=== 场景4: 离线消息拉取测试 ===")
        
        # 模拟Bob重新登录
        bob_ws = MockWebSocket("bob")
        self.online_users["bob"] = bob_ws
        self.db_manager.update_user_online_status("bob", True)
        
        print("✓ Bob重新登录，状态更新为在线")
        
        # 获取Bob的离线消息
        offline_messages = self.db_manager.get_offline_messages("bob")
        
        if offline_messages:
            print(f"✓ 发现 {len(offline_messages)} 条离线消息")
            
            # 投递离线消息（使用EncryptedNetworkPackage格式）
            for message in offline_messages:
                # 从离线消息重建EncryptedNetworkPackage
                encrypted_package = EncryptedNetworkPackage(
                    message_id=message.message_id,
                    sender_id=message.from_user,
                    receiver_id=message.to_user,
                    ciphertext_b64=message.ciphertext,
                    nonce_b64="bm9uY2VfZm9yX29mZmxpbmVfbWVzc2FnZQ==",  # 模拟nonce
                    mac_tag_b64=message.signature or "bWFjX3RhZ19mb3Jfb2ZmbGluZV9tZXNzYWdl",
                    ad_serialized='{"message_type": "text", "version": "1.0"}',
                    timestamp=message.timestamp,
                    ttl_seconds=message.ttl_seconds,
                    status="delivered"
                )
                
                await self._deliver_encrypted_message_to_online_user(encrypted_package)
                
                # 更新消息状态为已送达
                self.db_manager.update_message_status(message.message_id, "delivered")
                await self.message_manager.mark_message_delivered(message.message_id)
            
            # 验证Bob是否收到所有离线消息
            if len(bob_ws.messages) >= len(offline_messages):
                print("✓ 所有离线消息成功投递")
                
                # 验证收到的消息格式
                encrypted_messages = bob_ws.messages[-len(offline_messages):]
                valid_encrypted_count = 0
                
                for i, msg_data in enumerate(encrypted_messages):
                    # 检查是否包含EncryptedNetworkPackage的必需字段
                    required_fields = ['message_id', 'sender_id', 'receiver_id', 'ciphertext_b64', 
                                      'nonce_b64', 'mac_tag_b64', 'ad_serialized']
                    
                    if all(field in msg_data for field in required_fields):
                        valid_encrypted_count += 1
                        print(f"  消息{i+1}: 完整的EncryptedNetworkPackage格式")
                        print(f"    发送者: {msg_data['sender_id']} -> 接收者: {msg_data['receiver_id']}")
                        print(f"    密文: {msg_data['ciphertext_b64'][:30]}...")
                    else:
                        print(f"  消息{i+1}: 格式不完整")
                
                if valid_encrypted_count == len(offline_messages):
                    print("✓ 所有离线消息均为完整的EncryptedNetworkPackage格式")
                else:
                    print(f"✗ 只有 {valid_encrypted_count}/{len(offline_messages)} 条消息格式正确")
                    return False
                
                # 验证消息状态已更新 - 通过重新获取离线消息列表来验证状态更新
                updated_offline_messages = self.db_manager.get_offline_messages("bob")
                remaining_offline_count = len(updated_offline_messages)
                if remaining_offline_count == 0:
                    print("✓ 所有离线消息状态已正确更新")
                else:
                    print(f"✗ 仍有 {remaining_offline_count} 条消息未更新状态")
                    return False
            else:
                print("✗ 离线消息投递数量不匹配")
                return False
        else:
            print("✗ 未找到离线消息")
            return False
        
        return True
    
    async def _deliver_message_to_online_user(self, message: Message):
        """向在线用户投递消息（兼容旧格式）"""
        if message.to_user in self.online_users:
            ws = self.online_users[message.to_user]
            message_data = {
                "type": "message",
                "message_id": message.message_id,
                "from": message.from_user,
                "content": message.ciphertext,
                "timestamp": message.timestamp
            }
            await ws.send(json.dumps(message_data))
    
    async def _deliver_encrypted_message_to_online_user(self, encrypted_package: EncryptedNetworkPackage):
        """向在线用户投递EncryptedNetworkPackage格式的消息"""
        if encrypted_package.receiver_id in self.online_users:
            ws = self.online_users[encrypted_package.receiver_id]
            message_data = {
                "type": "message",
                "message_id": encrypted_package.message_id,
                "sender_id": encrypted_package.sender_id,
                "receiver_id": encrypted_package.receiver_id,
                "ciphertext_b64": encrypted_package.ciphertext_b64,
                "nonce_b64": encrypted_package.nonce_b64,
                "mac_tag_b64": encrypted_package.mac_tag_b64,
                "ad_serialized": encrypted_package.ad_serialized,
                "timestamp": encrypted_package.timestamp,
                "ttl_seconds": encrypted_package.ttl_seconds,
                "status": "delivered"
            }
            await ws.send(json.dumps(message_data))
    
    async def run_all_scenarios(self):
        """运行所有测试场景"""
        print("开始运行端到端加密即时通讯系统测试...")
        
        results = []
        
        # 场景1: 用户注册 - 这是所有后续测试的前提
        result1 = await self.scenario_1_user_registration()
        results.append(("用户注册", result1))
        
        
        # 场景2: 在线消息发送
        result2 = await self.scenario_2_online_message_send()
        results.append(("在线消息发送", result2))
        
        # 场景3: 离线消息发送
        result3 = await self.scenario_3_offline_message_send()
        results.append(("离线消息发送", result3))
        
        # 场景4: 离线消息拉取
        result4 = await self.scenario_4_offline_message_retrieval()
        results.append(("离线消息拉取", result4))
        
        # 输出测试结果摘要
        print("\n=== 测试结果摘要 ===")
        success_count = 0
        for scenario_name, result in results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{scenario_name}: {status}")
            if result:
                success_count += 1
        
        print(f"\n总测试场景: {len(results)}, 通过: {success_count}, 失败: {len(results) - success_count}")
        
        return all(result for _, result in results)

async def main():
    """主函数"""
    runner = TestScenarioRunner()
    success = await runner.run_all_scenarios()
    
    if success:
        print("\n🎉 所有测试场景通过！系统功能正常。")
    else:
        print("\n❌ 部分测试场景失败，请检查系统实现。")

if __name__ == "__main__":
    asyncio.run(main())