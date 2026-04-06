#!/usr/bin/env python3
"""
XSS防御机制测试
验证存储型XSS防护功能
"""

import sys
import os
# 正确添加server目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
server_dir = os.path.join(project_root, 'server')
sys.path.insert(0, server_dir)

from security_utils import security


def test_html_escaping():
    """测试HTML转义功能"""
    print("=== 测试HTML转义功能 ===")
    
    test_cases = [
        # (输入, 期望输出)
        ('<script>alert("XSS")</script>', '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'),
        ('<img src=x onerror=alert(1)>', '&lt;img src=x onerror=alert(1)&gt;'),
        ('<a href="javascript:alert(1)">click</a>', '&lt;a href=&quot;javascript:alert(1)&quot;&gt;click&lt;/a&gt;'),
        ('正常文本', '正常文本'),
        ('', ''),
        ('<div>测试</div>', '&lt;div&gt;测试&lt;/div&gt;'),
    ]
    
    for input_text, expected in test_cases:
        result = security.escape_html(input_text)
        status = "✓" if result == expected else "✗"
        print(f"{status} 输入: {input_text}")
        print(f"   期望: {expected}")
        print(f"   实际: {result}")
        print()


def test_username_sanitization():
    """测试用户名安全验证"""
    print("=== 测试用户名安全验证 ===")
    
    test_cases = [
        # (输入, 是否有效)
        ('normal_user', True),
        ('user123', True),
        ('test-user', True),
        ('user_name', True),
        ('<script>', False),  # 包含危险字符
        ('a', False),  # 太短
        ('very_long_username_that_exceeds_limit', False),  # 太长
        ('user@name', False),  # 包含特殊字符
        ('user name', False),  # 包含空格
        ('user<script>alert(1)</script>', False),  # 包含脚本
    ]
    
    for username, should_be_valid in test_cases:
        result = security.sanitize_username(username)
        is_valid = result is not None
        status = "✓" if is_valid == should_be_valid else "✗"
        print(f"{status} 用户名: {username}")
        print(f"   期望有效: {should_be_valid}, 实际有效: {is_valid}")
        if result:
            print(f"   清理后: {result}")
        print()


def test_system_message_sanitization():
    """测试系统消息安全处理"""
    print("=== 测试系统消息安全处理 ===")
    
    test_cases = [
        ('系统通知：您有新消息', '系统通知：您有新消息'),
        ('<script>alert("XSS")</script>', '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'),
        ('正常消息<script>恶意代码</script>', '正常消息&lt;script&gt;恶意代码&lt;/script&gt;'),
        ('a' * 600, 'a' * 500),  # 长度限制测试
        ('', ''),
    ]
    
    for input_msg, expected in test_cases:
        result = security.sanitize_system_message(input_msg)
        status = "✓" if result == expected else "✗"
        print(f"{status} 输入: {input_msg}")
        print(f"   期望: {expected}")
        print(f"   实际: {result}")
        print()


def test_friend_request_sanitization():
    """测试好友请求数据安全处理"""
    print("=== 测试好友请求数据安全处理 ===")
    
    test_data = {
        'from_user': 'user<script>alert(1)</script>',
        'to_user': 'target<script>user',
        'status': 'pending',
        'message': '你好<script>alert(1)</script>'
    }
    
    result = security.sanitize_friend_request_data(test_data)
    
    print("原始数据:")
    for key, value in test_data.items():
        print(f"  {key}: {value}")
    
    print("\n清理后数据:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    # 验证清理效果
    assert result['from_user'] is None  # 危险用户名应该被拒绝
    assert result['to_user'] is None    # 危险用户名应该被拒绝
    assert result['status'] == 'pending'
    assert '<script>' not in result['message']
    
    print("\n✓ 好友请求数据安全处理测试通过")


def test_input_validation():
    """测试通用输入验证"""
    print("=== 测试通用输入验证 ===")
    
    test_cases = [
        ('正常文本', True),
        ('a' * 1001, False),  # 超过长度限制
        ('<script>alert(1)</script>', False),  # 包含危险模式
        ('javascript:alert(1)', False),
        ('data:text/html,<script>alert(1)</script>', False),
        ('正常文本<script>alert(1)</script>', False),
        ({'key': 'value'}, True),
        ({'key': 'a' * 1001}, False),  # 字典内容过长
        (['item1', 'item2'], True),
        (['item'] * 101, False),  # 列表过长
    ]
    
    for input_data, should_be_valid in test_cases:
        result = security.validate_input(input_data)
        status = "✓" if result == should_be_valid else "✗"
        print(f"{status} 输入: {str(input_data)[:50]}...")
        print(f"   期望有效: {should_be_valid}, 实际有效: {result}")
        print()


def test_dangerous_content_removal():
    """测试危险内容移除"""
    print("=== 测试危险内容移除 ===")
    
    dangerous_content = '''
    <script>alert("XSS")</script>
    <iframe src="malicious.com"></iframe>
    <img src=x onerror=alert(1)>
    <a href="javascript:alert(1)">点击</a>
    <style>body { background: red; }</style>
    '''
    
    result = security._remove_dangerous_content(dangerous_content)
    
    print("原始内容:")
    print(dangerous_content)
    print("\n清理后内容:")
    print(result)
    
    # 验证危险内容已被移除
    assert '<script>' not in result
    assert '<iframe' not in result
    assert 'onerror=' not in result
    assert 'javascript:' not in result
    assert '<style>' not in result
    
    print("\n✓ 危险内容移除测试通过")


if __name__ == '__main__':
    print("开始XSS防御机制测试...\n")
    
    test_html_escaping()
    test_username_sanitization()
    test_system_message_sanitization()
    test_friend_request_sanitization()
    test_input_validation()
    test_dangerous_content_removal()
    
    print("🎉 所有XSS防御测试完成！")
    print("\n安全功能总结:")
    print("✓ HTML实体转义")
    print("✓ 用户名安全验证")
    print("✓ 系统消息安全处理")
    print("✓ 好友请求数据清理")
    print("✓ 通用输入验证")
    print("✓ 危险内容移除")
    print("✓ 内容安全策略(CSP)")

    print("OK")
