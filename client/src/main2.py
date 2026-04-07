#!/usr/bin/env python3
"""
客户端主程序 - 实现命令行界面的即时通讯功能
支持用户注册、登录、好友管理、消息收发等功能
"""

import os
import sys
import json
import asyncio
import getpass
from typing import Dict, List, Optional
# 添加项目根目录到sys.path，以便正确导入模块
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
# 导入网络模块
try:
    from client.src.network.api_client import NetworkClient
    from client.src.network.websocket_client import WebSocketClient
    from client.src.crypto.core import IdentityManager
    from shared.constants import DEFAULT_TTL
except ImportError:
    # 如果直接运行，尝试相对导入
    try:
        from network.api_client import NetworkClient
        from network.websocket_client import WebSocketClient
        from crypto.core import IdentityManager
        from shared.constants import DEFAULT_TTL
    except ImportError:
        # 如果还是不行，尝试绝对路径导入
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))
        from client.src.network.api_client import NetworkClient
        from client.src.network.websocket_client import WebSocketClient
        from client.src.crypto.core import IdentityManager
        from shared.constants import DEFAULT_TTL
class ClientFacade:
    """客户端外观类，整合所有功能"""
    
    def __init__(self, server_url: str = "http://localhost:80"):
        """初始化客户端"""
        self.network_client = NetworkClient(server_url)
        self.ws_client = None
        self.current_user = None
        self.friends_list = []
        self.messages_history = []
        self.friend_requests = []

    def register_user(self, username: str, password: str) -> tuple:
        """用户注册"""
        try:
            # 生成OTP secret
            otp_secret = IdentityManager.generate_otp_secret()
            print(f"生成的OTP密钥: {otp_secret}")
            print("请保存此密钥，用于设置OTP应用（如Google Authenticator）")
            print("登录时需要使用OTP应用生成的6位数字验证码")
            
            result = self.network_client.register(username, password, otp_secret)
            print(f"注册成功: {result}")
            return True, otp_secret
        except Exception as e:
            print(f"注册失败: {str(e)}")
            return False, None

    def login_user(self, username: str, password: str, otp_code: str = None) -> bool:
        """用户登录"""
        try:
            # 直接使用提供的OTP代码登录
            token = self.network_client.login(username, password, otp_code)
            
            self.current_user = username
            self.token = token
            print(f"登录成功，欢迎 {username}!")
            
            # 获取好友列表
            self.refresh_friends_list()
            return True
        except Exception as e:
            print(f"登录失败: {str(e)}")
            return False

    def upload_public_key(self, public_key: bytes) -> bool:
        """上传公钥到服务器"""
        try:
            if not public_key:
                print("公钥不能为空!")
                return False
            result = self.network_client.update_public_key(public_key)
            print(f"公钥上传成功: {result}")
            return True
        except Exception as e:
            print(f"公钥上传失败: {str(e)}")
            return False


    def get_user_public_key(self, username: str) -> str:
        """获取用户公钥"""
        try:
            public_key_bytes = self.network_client.get_public_key(username)
            public_key = public_key_bytes.decode('utf-8')
            print(f"成功获取 {username} 的公钥: {public_key}")
            return public_key
        except Exception as e:
            print(f"获取公钥失败: {str(e)}")
            return None

    def send_friend_request(self, target_user: str) -> bool:
        """发送好友请求"""
        try:
            request_id = self.network_client.send_friend_request(target_user)
            print(f"好友请求已发送给 {target_user}，请求ID: {request_id}")
            return True
        except Exception as e:
            print(f"发送好友请求失败: {str(e)}")
            return False

    def accept_friend_request(self, request_id: str) -> bool:
        """接受好友请求"""
        try:
            self.network_client.accept_friend_request(request_id)
            print(f"已接受好友请求: {request_id}")
            self.refresh_friends_list()
            return True
        except Exception as e:
            print(f"接受好友请求失败: {str(e)}")
            return False

    def decline_friend_request(self, request_id: str) -> bool:
        """拒绝好友请求"""
        try:
            self.network_client.decline_friend_request(request_id)
            print(f"已拒绝好友请求: {request_id}")
            return True
        except Exception as e:
            print(f"拒绝好友请求失败: {str(e)}")
            return False

    def get_friend_requests(self) -> List:
        """获取好友请求"""
        try:
            received_requests = self.network_client.get_friend_requests("received")
            sent_requests = self.network_client.get_friend_requests("sent")
            
            print("收到的好友请求:")
            for req in received_requests:
                # 服务器返回的是user_a和user_b，需要映射为from_user和to_user
                # 对于收到的请求，user_a是发送方
                from_user = req.get('from_user', req.get('user_a', 'Unknown'))
                req_id = req.get('request_id', req.get('id', 'Unknown'))
                status = req.get('status', 'Unknown')
                print(f"  来自 {from_user}, ID: {req_id}, "
                      f"状态: {status}")
            
            print("发送的好友请求:")
            for req in sent_requests:
                # 对于发送的请求，user_b是接收方
                to_user = req.get('to_user', req.get('user_b', 'Unknown'))
                req_id = req.get('request_id', req.get('id', 'Unknown'))
                status = req.get('status', 'Unknown')
                print(f"  发送给 {to_user}, ID: {req_id}, "
                      f"状态: {status}")
            
            return received_requests
        except Exception as e:
            print(f"获取好友请求失败: {str(e)}")
            return []

    def get_pending_requests(self) -> List:
        """获取待处理的好友请求（兼容 UI 调用）"""
        return self.get_friend_requests("received")
    
    def refresh_friends_list(self) -> List[str]:
        try:
            self.friends_list = self.network_client.get_friends()
            print("好友列表已更新:")
            for friend in self.friends_list:
                # 处理服务器返回的不同格式 - 可能是字符串或字典
                if isinstance(friend, dict):
                    username = friend.get('username', 'Unknown')
                    online_status = '在线' if friend.get('is_online', False) else '离线'
                    print(f"  - {username} ({online_status})")
                else:
                    # 如果返回的是字符串格式，则直接显示
                    print(f"  - {friend}")
            return self.friends_list
        except Exception as e:
            print(f"获取好友列表失败: {str(e)}")

    def get_conversations(self) -> List:
        """获取会话列表（从好友列表转换）"""
        return self.friends_list
    
    def get_messages(self, peer_user_id: str, limit: int = 50) -> List:
        """获取与某人的消息历史"""
        # 从离线消息中筛选
        messages = self.fetch_offline_messages()
        filtered = [m for m in messages if m.get('from_user') == peer_user_id or m.get('sender_id') == peer_user_id]
        return filtered[:limit]

    def send_message(self, target_user: str, message_content: str, ttl: int = DEFAULT_TTL) -> bool:
        """发送消息"""
        # 预留加密接口，实际不执行加密操作
        print("预留在此处实现消息加密功能")
        
        # 这里模拟加密过程（实际不加密）
        encrypted_message = self.encrypt_message(message_content)
        
        try:
            message_id = self.network_client.send_message(target_user, encrypted_message, ttl)
            print(f"消息已发送给 {target_user}，ID: {message_id}")
            return True
        except Exception as e:
            print(f"发送消息失败: {str(e)}")
            return False

    def encrypt_message(self, message: str) -> bytes:
        """预留消息加密接口"""
        # 实际不执行加密，只是返回原始消息的字节形式
        print("加密功能预留 - 实际未执行加密")
        return message.encode('utf-8')

    def decrypt_message(self, encrypted_message: bytes) -> str:
        """预留消息解密接口"""
        # 实际不解密，只是返回原始消息
        print("解密功能预留 - 实际未执行解密")
        return encrypted_message.decode('utf-8')

    def fetch_offline_messages(self) -> List:
        """获取离线消息"""
        try:
            messages = self.network_client.fetch_offline_messages()
            print("收到的离线消息:")
            for msg in messages:
                # 服务器可能返回不同的字段名，需要兼容处理
                sender = msg.get('from_user') or msg.get('sender_id', 'Unknown')
                # 获取密文内容，兼容不同字段名
                ciphertext_data = msg.get('ciphertext') or msg.get('ciphertext_b64', b'')
                # 如果是Base64编码的字符串，需要解码
                if isinstance(ciphertext_data, str):
                    import base64
                    try:
                        ciphertext_bytes = base64.b64decode(ciphertext_data)
                    except Exception:
                        ciphertext_bytes = ciphertext_data.encode('utf-8')
                else:
                    ciphertext_bytes = ciphertext_data
                # 解密消息内容（预留接口）
                decrypted_content = self.decrypt_message(ciphertext_bytes)
                print(f"来自 {sender}: {decrypted_content}")
            return messages
        except Exception as e:
            print(f"获取离线消息失败: {str(e)}")
            return []

    def setup_websocket_listener(self):
        """设置WebSocket监听器"""
        if self.ws_client is None:
            self.ws_client = WebSocketClient("https://ungladly-cremasterial-spring.ngrok-free.dev/", self.network_client.token)
        
        async def handle_message(message):
            print(f"\n收到新消息: {message}")
            # 处理不同类型的消息
            msg_type = message.get('type', '')
            if msg_type == 'message':
                content = message.get('content', '')
                sender = message.get('sender', 'Unknown')
                print(f"[新消息] {sender}: {content}")
        
        # 启动WebSocket连接
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.ws_client.connect(handle_message))
        return loop


def print_menu():
    """打印菜单"""
    print("\n" + "="*50)
    print("端到端加密即时通讯系统 - 客户端")
    print("="*50)
    print("1. 用户注册")
    print("2. 用户登录")
    print("3. 发送好友请求")
    print("4. 查看好友请求")
    print("5. 接受好友请求")
    print("6. 拒绝好友请求")
    print("7. 查看好友列表")
    print("8. 发送消息")
    print("9. 查看离线消息")
    print("10. 上传公钥")
    print("11. 获取他人公钥")
    print("12. 生成OTP验证码")
    print("0. 退出")
    print("="*50)


def main():
    """主函数"""
    client = ClientFacade()
    
    print("欢迎使用端到端加密即时通讯系统客户端!")
    
    while True:
        print_menu()
        try:
            choice = input("请选择功能 (0-12): ").strip()
            
            if choice == '1':
                # 用户注册
                username = input("请输入用户名: ").strip()
                if not username:
                    print("用户名不能为空!")
                    continue
                
                password = getpass.getpass("请输入密码: ")
                if len(password) < 6:
                    print("密码长度至少为6位!")
                    continue
                
                confirm_password = getpass.getpass("请确认密码: ")
                if password != confirm_password:
                    print("两次输入的密码不一致!")
                    continue
                
                client.register_user(username, password)
                
            elif choice == '2':
                # 用户登录
                if client.current_user:
                    print(f"当前已登录用户: {client.current_user}，请先退出登录")
                    continue
                
                username = input("请输入用户名: ").strip()
                password = getpass.getpass("请输入密码: ")
                otp_code = input("请输入OTP应用生成的6位数字验证码: ").strip()
                
                if client.login_user(username, password, otp_code):
                    print(f"登录成功! 欢迎 {username}")
                    
                    # 尝试启动WebSocket监听
                    try:
                        print("正在连接WebSocket服务...")
                        # 注意：在实际应用中，我们可能需要异步运行WebSocket
                    except Exception as e:
                        print(f"WebSocket连接失败: {str(e)}")
                
            elif choice == '3':
                # 发送好友请求
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                target_user = input("请输入目标用户名: ").strip()
                if not target_user:
                    print("用户名不能为空!")
                    continue
                
                client.send_friend_request(target_user)
                
            elif choice == '4':
                # 查看好友请求
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                client.get_friend_requests()
                
            elif choice == '5':
                # 接受好友请求
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                request_id = input("请输入要接受的好友请求ID: ").strip()
                if not request_id:
                    print("请求ID不能为空!")
                    continue
                
                client.accept_friend_request(request_id)
                
            elif choice == '6':
                # 拒绝好友请求
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                request_id = input("请输入要拒绝的好友请求ID: ").strip()
                if not request_id:
                    print("请求ID不能为空!")
                    continue
                
                client.decline_friend_request(request_id)
                
            elif choice == '7':
                # 查看好友列表
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                client.refresh_friends_list()
                
            elif choice == '8':
                # 发送消息
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                target_user = input("请输入接收者用户名: ").strip()
                if not target_user:
                    print("用户名不能为空!")
                    continue
                
                message = input("请输入消息内容: ").strip()
                if not message:
                    print("消息内容不能为空!")
                    continue
                
                ttl_input = input(f"请输入消息生存时间（秒，默认{DEFAULT_TTL}）: ").strip()
                try:
                    ttl = int(ttl_input) if ttl_input else DEFAULT_TTL
                except ValueError:
                    ttl = DEFAULT_TTL
                    print(f"输入无效，使用默认值 {DEFAULT_TTL}")
                
                client.send_message(target_user, message, ttl)
                
            elif choice == '9':
                # 查看离线消息
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                client.fetch_offline_messages()
                
            elif choice == '10':
                # 上传公钥
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                print("此功能用于上传用户公钥到服务器")
                # 这里可以模拟生成或输入公钥
                # 为了演示，我们使用预留接口
                public_key = input("请输入公钥: ").encode()
                if not public_key:
                    print("公钥不能为空!")
                    continue
                client.upload_public_key(public_key)
                
            elif choice == '11':
                # 获取他人公钥
                if not client.current_user:
                    print("请先登录!")
                    continue
                
                target_user = input("请输入要获取公钥的用户名: ").strip()
                if not target_user:
                    print("用户名不能为空!")
                    continue
                
                client.get_user_public_key(target_user)
                
            elif choice == '12':
                # 生成OTP验证码
                otp_secret = input("请输入OTP密钥: ").strip()
                if not otp_secret:
                    print("OTP密钥不能为空!")
                    continue
                try:
                    otp_code = IdentityManager.generate_otp_code(otp_secret)
                    print(f"当前OTP验证码: {otp_code}")
                    print("此验证码将在30秒后失效")
                except Exception as e:
                    print(f"生成OTP验证码失败: {str(e)}")
            elif choice == '0':
                print("感谢使用，再见!")
                break
            

            else:
                print("无效选择，请重新输入!")
                
        except KeyboardInterrupt:
            print("\n\n程序被用户中断")
            break
        except Exception as e:
            print(f"发生错误: {str(e)}")


if __name__ == "__main__":
    try:
        from PyQt5.QtWidgets import QApplication
        from ui.gui import LoginDialog, ChatGUI
        
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        # 存储主窗口引用（使用列表避免 nonlocal 问题）
        main_window_ref = [None]
        # 存储客户端引用
        client_ref = [None]
        
        def on_login_success(username, password, otp):
            # 创建客户端并登录
            client = ClientFacade(server_url="http://localhost:80")
            if client.login_user(username, password, otp):
                # 保存客户端引用
                client_ref[0] = client
                # 创建主窗口，传入 client
                main_window_ref[0] = ChatGUI(client)
                main_window_ref[0].show()
                # 关闭所有登录对话框
                for widget in app.topLevelWidgets():
                    if isinstance(widget, LoginDialog):
                        widget.close()
            else:
                # 登录失败，显示错误
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(None, "登录失败", "用户名、密码或OTP验证码错误")
        
        # 显示登录对话框
        login_dialog = LoginDialog()
        login_dialog.login_success_signal.connect(on_login_success)
        login_dialog.show()
        
        sys.exit(app.exec_())
        
    except ImportError as e:
        print(f"无法启动图形界面: {e}")
        print("请确保已安装 PyQt5: pip install PyQt5")
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        # 如果 GUI 启动失败，回退到命令行界面
        main()