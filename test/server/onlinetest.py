#!/usr/bin/env python3
"""
API测试脚本 - 用于测试端到端加密即时通讯系统的所有接口
"""

import asyncio
import json
import requests
import time
from datetime import datetime

# 服务器配置
BASE_URL = "https://ungladly-cremasterial-spring.ngrok-free.dev"

def test_register():
    """测试用户注册接口"""
    print("=== 测试用户注册 ===")
    
    # 测试数据
    test_users = [
        {"username": "user1", "password": "pass123"},
        {"username": "user2", "password": "pass456"},
        {"username": "user3", "password": "pass789"}
    ]
    
    for user_data in test_users:
        response = requests.post(f"{BASE_URL}/api/v1/users", 
                                json=user_data)
        print(f"注册用户 {user_data['username']}: {response.status_code} - {response.text}")
        time.sleep(0.5)

def test_login():
    """测试用户登录接口"""
    print("\n=== 测试用户登录 ===")
    
    login_data = {"username": "user1", "password": "pass123"}
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", 
                            json=login_data)
    
    print(f"登录响应: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        token = result.get('token')
        print(f"获取到Token: {token[:20]}...")
        return token
    else:
        print(f"登录失败: {response.text}")
        return None

def test_get_user_info(token):
    """测试获取用户信息接口"""
    print("\n=== 测试获取用户信息 ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/v1/users/me", 
                           headers=headers)
    
    print(f"用户信息: {response.status_code} - {response.text}")

def test_send_friend_request(token):
    """测试发送好友请求接口"""
    print("\n=== 测试发送好友请求 ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    friend_request = {"to_user": "user2"}
    
    response = requests.post(f"{BASE_URL}/api/v1/friend-requests", 
                            json=friend_request, 
                            headers=headers)
    
    print(f"发送好友请求: {response.status_code} - {response.text}")

def test_get_friend_requests(token):
    """测试获取好友请求接口"""
    print("\n=== 测试获取好友请求 ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 获取收到的请求
    response = requests.get(f"{BASE_URL}/api/v1/friend-requests?type=received", 
                           headers=headers)
    print(f"收到的请求: {response.status_code} - {response.text}")
    
    # 获取发送的请求
    response = requests.get(f"{BASE_URL}/api/v1/friend-requests?type=sent", 
                           headers=headers)
    print(f"发送的请求: {response.status_code} - {response.text}")

def test_websocket_connection(token):
    """测试WebSocket连接"""
    print("\n=== 测试WebSocket连接 ===")
    print("注意：WebSocket测试需要异步环境，这里仅显示连接URL")
    print(f"WebSocket URL: ws://localhost/api/v1/ws?token={token}")

def test_duplicate_user_registration():
    """测试重复用户注册"""
    print("\n=== 测试重复用户注册 ===")
    
    # 测试数据
    user_data = {"username": "duplicate_user", "password": "testpass123"}
    
    # 第一次注册
    response1 = requests.post(f"{BASE_URL}/api/v1/users", json=user_data)
    print(f"第一次注册 {user_data['username']}: {response1.status_code} - {response1.text}")
    
    # 等待一小段时间
    time.sleep(0.5)
    
    # 第二次注册相同用户名
    response2 = requests.post(f"{BASE_URL}/api/v1/users", json=user_data)
    print(f"第二次注册 {user_data['username']}: {response2.status_code} - {response2.text}")
    
    # 验证测试结果
    if response1.status_code == 201:
        print("✓ First registration successful")
    else:
        print("✗ First registration failed")
    
    if response2.status_code == 400:
        print("✓ Second registration correctly returned 400 error")
        if "User already exists" in response2.text:
            print("✓ Error message correct: 'User already exists'")
        else:
            print("✗ Error message incorrect")
    else:
        print(f"✗ Second registration returned wrong status code: {response2.status_code}")
    
    return response1.status_code == 201 and response2.status_code == 400

def run_all_tests():
    """运行所有测试"""
    print("开始API接口测试...")
    print(f"服务器地址: {BASE_URL}")
    print("=" * 50)
    
    # 1. 测试注册
    test_register()
    
    # 2. 测试重复用户注册
    duplicate_test_result = test_duplicate_user_registration()
    
    # 3. 测试登录
    token = test_login()
    
    if token:
        # 4. 测试获取用户信息
        test_get_user_info(token)
        
        # 5. 测试好友请求
        test_send_friend_request(token)
        test_get_friend_requests(token)
        
        # 6. 测试WebSocket
        test_websocket_connection(token)
    
    print("\n" + "=" * 50)
    
    # 测试结果总结
    if duplicate_test_result:
        print("✓ 用户ID重复测试通过")
    else:
        print("✗ 用户ID重复测试失败")
    
    print("测试完成！")

if __name__ == "__main__":
    run_all_tests()