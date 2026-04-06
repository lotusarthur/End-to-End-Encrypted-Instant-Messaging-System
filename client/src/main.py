"""
端到端加密即时通讯系统 - 客户端主入口

这是一个完整的客户端系统，包含：
- 用户注册/登录功能
- 端到端加密消息传输
- 好友管理系统
- 历史消息同步
- 命令行界面和UI接口两套接口
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

# 添加当前目录到Python路径
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

# 导入业务层服务
try:
    from business.app_service import AppService
    from business.auth_service import AuthService
    from business.chat_service import ChatService
    from business.message_service import MessageService
    from business.session_manager import SessionManager
    from business.errors import AuthError, ValidationError
    from storage.db import LocalDatabase
    from network.api_client import NetworkClient
    from crypto.message_crypto import MessageCrypto
    from crypto.key_manager import KeyManager
except ImportError as e:
    print(f"导入模块失败: {e}")
    # 创建占位类以便继续开发
    class AppService:
        def __init__(self, *args, **kwargs):
            pass
        def register(self, username: str, password: str):
            return {"success": False, "error": "模块导入失败，无法注册"}
        def login(self, username: str, password: str, otp: str):
            return {"success": False, "error": "模块导入失败，无法登录"}
        def logout(self):
            pass
        def send_text_message(self, conversation_id: str, text: str, ttl: int = 30):
            return {"success": False, "error": "模块导入失败，无法发送消息"}
        def list_conversations(self):
            return []
        def list_messages(self, conversation_id: str, limit: int = 50):
            return []
        def open_conversation(self, conversation_id: str):
            pass
        def on(self, event_name: str, handler):
            pass
    class AuthService:
        def __init__(self, *args, **kwargs):
            pass
    class ChatService:
        def __init__(self, *args, **kwargs):
            pass
    class MessageService:
        def __init__(self, *args, **kwargs):
            pass
    class SessionManager:
        def __init__(self, *args, **kwargs):
            pass
    class LocalDatabase:
        def __init__(self, *args, **kwargs):
            pass
        def save_private_key(self, user_id: str, private_key: str):
            pass
        def get_private_key(self, user_id: str):
            return None
        def save_user_profile(self, profile: dict):
            pass
        def get_user_profile(self, user_id: str):
            return None
        def save_token(self, token: str):
            pass
    class NetworkClient:
        def __init__(self, *args, **kwargs):
            pass
    class MessageCrypto:
        def __init__(self, *args, **kwargs):
            pass
    class KeyManager:
        def __init__(self, *args, **kwargs):
            pass


class EventBus:
    """简单的事件总线实现"""
    def __init__(self):
        self._handlers = {}
    
    def subscribe(self, event_name: str, handler: Callable):
        """订阅事件"""
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
    
    def emit(self, event_name: str, data: Dict):
        """触发事件"""
        if event_name in self._handlers:
            for handler in self._handlers[event_name]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"事件处理错误 {event_name}: {e}")


class InstantMessagingClient:
    """端到端加密即时通讯客户端主类"""
    
    def __init__(self, server_url: str = "https://ungladly-cremasterial-spring.ngrok-free.dev"):
        self.server_url = server_url
        self.base_dir = Path(__file__).resolve().parent
        self.storage_dir = str(self.base_dir / ".secure_store")
        self.db_path = str(self.base_dir / "chat.db")
        
        # 确保存储目录存在
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # 初始化核心组件
        self._initialize_components()
        
        # UI回调函数
        self.ui_callbacks: Dict[str, Callable] = {}
        
        # 当前用户状态
        self.current_user: Optional[Dict] = None
        self.is_authenticated = False
        
        print(f"Instant Messaging Client initialized. Server: {server_url}")
    
    def _initialize_components(self):
        """初始化所有核心组件"""
        # 事件总线
        self.event_bus = EventBus()
        
        # 存储组件
        self.storage = LocalDatabase(self.db_path)
        
        # 网络组件
        self.api_client = NetworkClient(self.server_url)
        
        # 加密组件
        self.crypto = MessageCrypto()
        
        # 会话管理
        self.session_manager = SessionManager(self.storage)
        
        # 业务服务
        self.auth_service = AuthService(
            self.api_client, None, self.storage, self.event_bus, self.crypto
        )
        
        self.chat_service = ChatService(
            self.crypto, self.api_client, self.storage, self.event_bus, self.session_manager
        )
        
        self.message_service = MessageService(
            self.crypto, self.storage, self.event_bus, self.session_manager
        )
        
        # 主应用服务
        self.app_service = AppService(
            auth_service=self.auth_service,
            chat_service=self.chat_service,
            message_service=self.message_service,
            session_manager=self.session_manager,
            event_bus=self.event_bus,
            ws_client=None,  # WebSocket客户端暂未实现
            storage=self.storage
        )
        
        # 注册事件监听
        self._register_event_handlers()
        
        print("所有核心组件初始化完成")
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        # 认证事件
        self.event_bus.subscribe("auth.login_success", self._on_login_success)
        self.event_bus.subscribe("auth.logout", self._on_logout)
        
        # 聊天事件
        self.event_bus.subscribe("chat.message_received", self._on_message_received)
        self.event_bus.subscribe("chat.message_sent", self._on_message_sent)
        self.event_bus.subscribe("chat.message_failed", self._on_message_failed)
    
    def _on_login_success(self, data: Dict):
        """登录成功处理"""
        self.is_authenticated = True
        self.current_user = data.get("profile", {})
        print(f"用户登录成功: {self.current_user.get('username')}")
    
    def _on_logout(self, data: Dict):
        """登出处理"""
        self.is_authenticated = False
        self.current_user = None
        print("用户已登出")
    
    def _on_message_received(self, data: Dict):
        """收到消息处理"""
        print(f"收到新消息: {data.get('text')}")
    
    def _on_message_sent(self, data: Dict):
        """消息发送成功处理"""
        print(f"消息发送成功: {data.get('message_id')}")
    
    def _on_message_failed(self, data: Dict):
        """消息发送失败处理"""
        print(f"消息发送失败: {data.get('error')}")
    
    # ========== UI接口方法 ==========
    
    def register_ui_callback(self, event_name: str, callback: Callable):
        """注册UI回调函数"""
        self.ui_callbacks[event_name] = callback
        self.event_bus.subscribe(event_name, callback)
    
    def unregister_ui_callback(self, event_name: str):
        """注销UI回调函数"""
        if event_name in self.ui_callbacks:
            del self.ui_callbacks[event_name]
    
    # ========== 业务方法封装 ==========
    
    def register(self, username: str, password: str) -> Dict:
        """用户注册"""
        try:
            return self.app_service.register(username, password)
        except Exception as e:
            print(f"注册失败: {e}")
            return {"success": False, "error": str(e)}
    
    def login(self, username: str, password: str, otp: str) -> Dict:
        """用户登录"""
        try:
            return self.app_service.login(username, password, otp)
        except Exception as e:
            print(f"登录失败: {e}")
            return {"success": False, "error": str(e)}
    
    def logout(self):
        """用户登出"""
        try:
            self.app_service.logout()
        except Exception as e:
            print(f"登出失败: {e}")
    
    def send_message(self, conversation_id: str, text: str, ttl: int = 30) -> Dict:
        """发送消息"""
        try:
            return self.app_service.send_text_message(conversation_id, text, ttl)
        except Exception as e:
            print(f"发送消息失败: {e}")
            return {"success": False, "error": str(e)}
    
    def list_conversations(self) -> List[Dict]:
        """获取对话列表"""
        try:
            return self.app_service.list_conversations()
        except Exception as e:
            print(f"获取对话列表失败: {e}")
            return []
    
    def list_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """获取对话消息"""
        try:
            return self.app_service.list_messages(conversation_id, limit)
        except Exception as e:
            print(f"获取消息失败: {e}")
            return []
    
    def open_conversation(self, conversation_id: str):
        """打开对话"""
        try:
            self.app_service.open_conversation(conversation_id)
        except Exception as e:
            print(f"打开对话失败: {e}")
    
    def get_user_status(self) -> Dict:
        """获取用户状态"""
        return {
            "is_authenticated": self.is_authenticated,
            "current_user": self.current_user,
            "server_url": self.server_url
        }


class CommandLineInterface:
    """命令行界面"""
    
    def __init__(self, client: InstantMessagingClient):
        self.client = client
        self.running = False
    
    def start(self):
        """启动命令行界面"""
        self.running = True
        print("\n=== 命令行界面已启动 ===")
        print("输入 'help' 查看可用命令")
        
        while self.running:
            try:
                command = input("\ncmd> ").strip()
                if not command:
                    continue
                
                self._handle_command(command)
                
            except KeyboardInterrupt:
                print("\n\n正在退出...")
                self.running = False
            except Exception as e:
                print(f"命令执行错误: {e}")
    
    def _handle_command(self, command: str):
        """处理命令"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "exit":
            self.running = False
            print("退出命令行界面")
        
        elif cmd == "help":
            self._show_help()
        
        elif cmd == "status":
            status = self.client.get_user_status()
            print(f"当前状态: {status}")
        
        elif cmd == "register":
            if len(parts) < 3:
                print("用法: register <用户名> <密码>")
                return
            username, password = parts[1], parts[2]
            result = self.client.register(username, password)
            print(f"注册结果: {result}")
        
        elif cmd == "login":
            if len(parts) < 4:
                print("用法: login <用户名> <密码> <OTP码>")
                return
            username, password, otp = parts[1], parts[2], parts[3]
            result = self.client.login(username, password, otp)
            print(f"登录结果: {result}")
        
        elif cmd == "logout":
            self.client.logout()
            print("已登出")
        
        elif cmd == "send":
            if len(parts) < 3:
                print("用法: send <对话ID> <消息内容>")
                return
            conversation_id, text = parts[1], " ".join(parts[2:])
            result = self.client.send_message(conversation_id, text)
            print(f"发送结果: {result}")
        
        elif cmd == "conversations":
            conversations = self.client.list_conversations()
            print(f"对话列表 ({len(conversations)}个):")
            for conv in conversations:
                print(f"  - {conv.get('conversation_id')}: {conv.get('last_message', '')}")
        
        elif cmd == "messages":
            if len(parts) < 2:
                print("用法: messages <对话ID>")
                return
            conversation_id = parts[1]
            messages = self.client.list_messages(conversation_id)
            print(f"消息列表 ({len(messages)}条):")
            for msg in messages:
                direction = "→" if msg.get('direction') == 'outgoing' else "←"
                print(f"  {direction} {msg.get('text')}")
        
        else:
            print(f"未知命令: {cmd}")
            print("输入 'help' 查看可用命令")
    
    def _show_help(self):
        """显示帮助信息"""
        help_text = """
可用命令:
  help                    - 显示此帮助信息
  exit                    - 退出命令行界面
  status                  - 查看当前状态
  register <用户> <密码>   - 用户注册
  login <用户> <密码> <OTP> - 用户登录
  logout                  - 用户登出
  send <对话ID> <消息>     - 发送消息
  conversations           - 查看对话列表
  messages <对话ID>        - 查看对话消息
"""
        print(help_text)


class UIController:
    """UI控制器 - 为图形界面提供接口"""
    
    def __init__(self, client: InstantMessagingClient):
        self.client = client
    
    # ========== 认证相关接口 ==========
    
    def ui_register(self, username: str, password: str) -> Dict:
        """UI注册接口"""
        return self.client.register(username, password)
    
    def ui_login(self, username: str, password: str, otp: str) -> Dict:
        """UI登录接口"""
        return self.client.login(username, password, otp)
    
    def ui_logout(self) -> Dict:
        """UI登出接口"""
        self.client.logout()
        return {"success": True, "message": "登出成功"}
    
    # ========== 聊天相关接口 ==========
    
    def ui_send_message(self, conversation_id: str, text: str, ttl: int = 30) -> Dict:
        """UI发送消息接口"""
        return self.client.send_message(conversation_id, text, ttl)
    
    def ui_get_conversations(self) -> List[Dict]:
        """UI获取对话列表接口"""
        return self.client.list_conversations()
    
    def ui_get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """UI获取消息接口"""
        return self.client.list_messages(conversation_id, limit)
    
    def ui_open_conversation(self, conversation_id: str) -> Dict:
        """UI打开对话接口"""
        self.client.open_conversation(conversation_id)
        return {"success": True, "conversation_id": conversation_id}
    
    def ui_get_user_status(self) -> Dict:
        """UI获取用户状态接口"""
        return self.client.get_user_status()
    
    # ========== 事件注册接口 ==========
    
    def ui_register_callback(self, event_name: str, callback: Callable) -> Dict:
        """UI注册回调接口"""
        self.client.register_ui_callback(event_name, callback)
        return {"success": True, "event_name": event_name}
    
    def ui_unregister_callback(self, event_name: str) -> Dict:
        """UI注销回调接口"""
        self.client.unregister_ui_callback(event_name)
        return {"success": True, "event_name": event_name}


def main():
    """客户端主函数"""
    print("=== 端到端加密即时通讯客户端 ===")
    print("正在初始化客户端...")
    
    # 创建客户端实例
    client = InstantMessagingClient()
    
    print("客户端初始化完成!")
    print("\n可用功能:")
    print("- 用户注册/登录")
    print("- 端到端加密消息传输")
    print("- 好友申请/管理")
    print("- 历史消息同步")
    print("- 实时消息推送")
    
    # 创建命令行界面和UI控制器
    cli = CommandLineInterface(client)
    ui_controller = UIController(client)
    
    print("\n选择运行模式:")
    print("1. 命令行界面 (CLI)")
    print("2. UI接口模式 (等待外部调用)")
    
    try:
        choice = input("请选择模式 (1/2): ").strip()
        
        if choice == "1":
            # 启动命令行界面
            cli.start()
        elif choice == "2":
            # 启动图形界面
            print("\n正在启动图形界面...")
            try:
                from PyQt5.QtWidgets import QApplication
                from ui.gui import LoginDialog, ChatGUI
                import sys
                
                app = QApplication(sys.argv)
                
                # 创建登录对话框
                login_dialog = LoginDialog()
                main_window = None
                
                def on_login_success(username):
                    nonlocal main_window
                    # 登录成功后创建主窗口
                    main_window = ChatGUI(server_url=client.server_url)
                    main_window.show()
                    login_dialog.close()
                
                login_dialog.login_success_signal.connect(on_login_success)
                login_dialog.show()
                
                sys.exit(app.exec_())
            except ImportError as e:
                print(f"无法启动图形界面: {e}")
            except Exception as e:
                print(f"图形界面启动失败: {e}")
        else:
            print("无效选择，退出程序")
            
    except KeyboardInterrupt:
        print("\n\n客户端已退出")
    except Exception as e:
        print(f"客户端运行错误: {e}")


# ========== 示例使用代码 ==========

def demo_usage():
    """演示如何使用客户端"""
    client = InstantMessagingClient()
    
    # 注册UI回调示例
    def on_message_received(data):
        print(f"UI回调: 收到新消息: {data}")
    
    def on_login_success(data):
        print(f"UI回调: 登录成功: {data}")
    
    # 注册回调
    client.register_ui_callback("chat.message_received", on_message_received)
    client.register_ui_callback("auth.login_success", on_login_success)
    
    print("演示完成!")


if __name__ == "__main__":
    main()
