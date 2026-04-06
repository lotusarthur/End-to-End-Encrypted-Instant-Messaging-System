#!/usr/bin/env python3
"""
安全工具模块
实现存储型XSS防御机制
"""

import html
import re
from typing import Union, List, Dict, Any


class XSSDefense:
    """XSS防御工具类"""
    
    # 危险标签和属性模式
    DANGEROUS_TAGS = {
        'script', 'iframe', 'object', 'embed', 'applet', 'base', 'link', 'meta',
        'style', 'form', 'input', 'button', 'textarea', 'select', 'option'
    }
    
    DANGEROUS_ATTRIBUTES = {
        'onclick', 'onload', 'onerror', 'onmouseover', 'onmouseout',
        'onkeydown', 'onkeyup', 'onfocus', 'onblur', 'onsubmit',
        'onchange', 'onselect', 'href', 'src', 'action', 'style'
    }
    
    # 内容安全策略
    CSP_HEADER = "default-src 'self'; script-src 'none'; object-src 'none';"
    
    @staticmethod
    def escape_html(content: str) -> str:
        """
        HTML实体转义
        防止存储型XSS攻击
        """
        if not content:
            return ""
        
        # 基本的HTML转义
        escaped = html.escape(content)
        
        # 额外的安全处理
        escaped = escaped.replace('`', '&#96;')  # 防止模板注入
        escaped = escaped.replace('$', '&#36;')  # 防止变量注入
        
        return escaped
    
    @staticmethod
    def sanitize_username(username: str) -> Union[str, None]:
        """
        用户名安全验证和清理
        """
        if not username:
            return None
        
        # 长度限制
        if len(username) < 3 or len(username) > 20:
            return None
        
        # 只允许字母、数字、下划线和短横线
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return None
        
        # 转义特殊字符
        return XSSDefense.escape_html(username)
    
    @staticmethod
    def sanitize_system_message(message: str) -> str:
        """
        系统消息安全处理
        """
        if not message:
            return ""
        
        # 长度限制
        if len(message) > 500:
            message = message[:500]
        
        # HTML转义
        sanitized = XSSDefense.escape_html(message)
        
        # 移除危险内容
        sanitized = XSSDefense._remove_dangerous_content(sanitized)
        
        return sanitized
    
    @staticmethod
    def sanitize_friend_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        好友请求数据安全处理
        """
        sanitized = {}
        
        # 处理用户名
        if 'from_user' in data:
            sanitized['from_user'] = XSSDefense.sanitize_username(data['from_user'])
        
        if 'to_user' in data:
            sanitized['to_user'] = XSSDefense.sanitize_username(data['to_user'])
        
        # 处理状态字段
        if 'status' in data:
            status = data['status']
            if status in ['pending', 'accepted', 'declined', 'cancelled']:
                sanitized['status'] = status
        
        # 处理消息内容（如果有）
        if 'message' in data:
            sanitized['message'] = XSSDefense.sanitize_system_message(data['message'])
        
        return sanitized
    
    @staticmethod
    def _remove_dangerous_content(text: str) -> str:
        """
        移除危险HTML标签和属性
        """
        # 移除危险标签
        for tag in XSSDefense.DANGEROUS_TAGS:
            pattern = re.compile(f'<{tag}[^>]*>.*?</{tag}>', re.IGNORECASE | re.DOTALL)
            text = pattern.sub('', text)
        
        # 移除危险属性
        for attr in XSSDefense.DANGEROUS_ATTRIBUTES:
            # 匹配带引号的属性值：onerror="alert(1)" 或 onerror='alert(1)'
            pattern1 = re.compile(f'{attr}\\s*=\\s*["\'][^"\']*["\']', re.IGNORECASE)
            text = pattern1.sub('', text)
            
            # 匹配不带引号的属性值：onerror=alert(1)
            pattern2 = re.compile(f'{attr}\\s*=\\s*[^\\s>]+', re.IGNORECASE)
            text = pattern2.sub('', text)
        
        return text
    
    @staticmethod
    def validate_input(input_data: Union[str, Dict, List], max_length: int = 1000) -> bool:
        """
        通用输入验证
        """
        if isinstance(input_data, str):
            # 字符串长度检查
            if len(input_data) > max_length:
                return False
            
            # 检查是否包含危险字符序列
            dangerous_patterns = [
                r'<script', r'javascript:', r'vbscript:', r'expression\s*\(',
                r'on\w+\s*=', r'data:', r'<iframe'
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, input_data, re.IGNORECASE):
                    return False
        
        elif isinstance(input_data, dict):
            # 字典深度检查
            if len(str(input_data)) > max_length:
                return False
        
        elif isinstance(input_data, list):
            # 列表长度检查
            if len(input_data) > 100:  # 限制列表项数量
                return False
        
        return True
    
    @staticmethod
    def get_csp_header() -> str:
        """
        获取内容安全策略头
        """
        return XSSDefense.CSP_HEADER


# 全局安全工具实例
security = XSSDefense()