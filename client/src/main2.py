#!/usr/bin/env python3
"""
客户端主程序 - 实现命令行界面的即时通讯功能
支持用户注册、登录、好友管理、消息收发等功能
"""

import os
import sys
import json
import uuid
import base64
import asyncio
import getpass
from typing import Dict, List, Optional

# 添加项目根目录到sys.path，以便正确导入模块
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# 导入网络模块
try:
    from client.src.network.api_client import NetworkClient
    from client.src.network.websocket_client import WebSocketClient
    from client.src.crypto.core import IdentityManager, SessionManager, CryptoEngine
    from client.src.storage.provider import SQLiteStorageProvider
    from shared.constants import DEFAULT_TTL
except ImportError:
    try:
        from network.api_client import NetworkClient
        from network.websocket_client import WebSocketClient
        from crypto.core import IdentityManager, SessionManager, CryptoEngine
        from storage.provider import SQLiteStorageProvider
        from shared.constants import DEFAULT_TTL
    except ImportError:
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))
        from client.src.network.api_client import NetworkClient
        from client.src.network.websocket_client import WebSocketClient
        from client.src.crypto.core import IdentityManager, SessionManager, CryptoEngine
        from client.src.storage.provider import SQLiteStorageProvider
        from shared.constants import DEFAULT_TTL


class ClientFacade:
    """客户端外观类，整合所有功能"""

    def __init__(self, server_url: str = "http://localhost:80"):
        """初始化客户端"""
        self.network_client = NetworkClient(server_url)
        self.ws_client = None
        self.current_user = None
        self.token = None
        self.friends_list = []
        self.messages_history = []
        self.friend_requests = []

        # 安全组件
        self.storage = None
        self.session_mgr = None
        self.crypto_engine = None

    # ---------- 私钥本地存储 ----------
    def _private_key_file(self, username: str) -> str:
        """本地私钥文件路径"""
        return f"{username}_private_key.txt"

    def _save_private_key_local(self, username: str, private_key_b64: str):
        """本地保存私钥"""
        with open(self._private_key_file(username), "w", encoding="utf-8") as f:
            f.write(private_key_b64)

    def _load_private_key_local(self, username: str) -> str:
        """本地读取私钥"""
        key_file = self._private_key_file(username)
        if not os.path.exists(key_file):
            raise FileNotFoundError(f"本地私钥文件不存在: {key_file}")
        with open(key_file, "r", encoding="utf-8") as f:
            return f.read().strip()

    def setup_crypto(self, username: str, private_key_b64: str):
        """
        登录成功后执行：
        1. 启动数据库
        2. 启动会话管理
        3. 启动加密引擎
        """
        self.storage = SQLiteStorageProvider(f"{username}_local.db")
        self.session_mgr = SessionManager(private_key_b64, self.storage)
        self.crypto_engine = CryptoEngine(username, self.session_mgr, self.storage)
        print(f"已完成 {username} 的安全组件初始化")

    # ---------- 用户注册 ----------
    def register_user(self, username: str, password: str) -> tuple:
        """用户注册，生成密钥对并自动上传公钥"""
        try:
            # 生成OTP secret
            otp_secret = IdentityManager.generate_otp_secret()
            print(f"生成的OTP密钥: {otp_secret}")
            print("请保存此密钥，用于设置OTP应用（如Google Authenticator）")
            print("登录时需要使用OTP应用生成的6位数字验证码")

            # 生成身份密钥对
            private_key_b64, public_key_b64 = IdentityManager.generate_identity_keypair()
            self._save_private_key_local(username, private_key_b64)
            print(f"私钥已保存到本地文件: {self._private_key_file(username)}")

            # 注册用户
            result = self.network_client.register(username, password, otp_secret)
            print(f"注册成功: {result}")

            # 自动登录并上传公钥
            otp_code = IdentityManager.generate_otp_code(otp_secret)
            self.network_client.login(username, password, otp_code)
            self.token = self.network_client.token
            self.network_client.update_public_key(public_key_b64.encode("utf-8"))
            print("身份公钥已上传到服务器")

            # 保持登录状态（用户无需再次登录）
            self.current_user = username
            self.setup_crypto(username, private_key_b64)
            self.refresh_friends_list()

            return True, otp_secret
        except Exception as e:
            print(f"注册失败: {str(e)}")
            return False, None

    # ---------- 用户登录 ----------
    def login_user(self, username: str, password: str, otp_code: str = None) -> bool:
        """用户登录，不检查私钥文件是否存在"""
        try:
            self.network_client.login(username, password, otp_code)
            self.token = self.network_client.token
            self.current_user = username
            print(f"登录成功，欢迎 {username}!")

            # 尝试加载本地私钥，如果不存在则不初始化加密组件
            try:
                private_key_b64 = self._load_private_key_local(username)
                self.setup_crypto(username, private_key_b64)
                print("已加载本地私钥并初始化安全组件")
            except FileNotFoundError:
                print("未找到本地私钥文件，信息发送、好友添加功能暂时不可用")
                # 不初始化加密组件，后续需要时再处理

            self.refresh_friends_list()
            return True
        except Exception as e:
            print(f"登录失败: {str(e)}")
            return False

    # ---------- 公钥操作 ----------
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
        """获取用户公钥并尝试建立加密会话"""
        try:
            # api_client 返回原始字节，转换为 base64
            public_key_bytes = self.network_client.get_public_key(username)
            public_key_b64 = base64.b64encode(public_key_bytes).decode("utf-8")

            if not self.crypto_engine:
                print("错误：安全引擎尚未初始化，无法建立加密会话")
                return public_key_b64

            # 建立会话（生成共享密钥）
            try:
                self.session_mgr.establish_session(username, public_key_b64)
                print(f"成功与 {username} 建立加密隧道 (会话密钥已生成)")
            except PermissionError as e:
                print(f"⚠️ 严重安全警告: {str(e)}")
                return None

            print(f"成功获取 {username} 的公钥")
            return public_key_b64
        except Exception as e:
            print(f"获取公钥失败: {str(e)}")
            return None

    # ---------- 好友管理 ----------
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
                from_user = req.get('from_user', req.get('user_a', 'Unknown'))
                req_id = req.get('request_id', req.get('id', 'Unknown'))
                status = req.get('status', 'Unknown')
                print(f"  来自 {from_user}, ID: {req_id}, 状态: {status}")

            print("发送的好友请求:")
            for req in sent_requests:
                to_user = req.get('to_user', req.get('user_b', 'Unknown'))
                req_id = req.get('request_id', req.get('id', 'Unknown'))
                status = req.get('status', 'Unknown')
                print(f"  发送给 {to_user}, ID: {req_id}, 状态: {status}")

            return received_requests
        except Exception as e:
            print(f"获取好友请求失败: {str(e)}")
            return []

    def refresh_friends_list(self) -> List:
        """刷新好友列表"""
        try:
            self.friends_list = self.network_client.get_friends()
            print("好友列表已更新:")
            for friend in self.friends_list:
                if isinstance(friend, dict):
                    username = friend.get('username', 'Unknown')
                    online_status = '在线' if friend.get('is_online', False) else '离线'
                    print(f"  - {username} ({online_status})")
                else:
                    print(f"  - {friend}")
            return self.friends_list
        except Exception as e:
            print(f"获取好友列表失败: {str(e)}")
            return []

    # ---------- 消息收发（加密）----------
    def send_message(self, target_user: str, message_content: str, ttl: int = DEFAULT_TTL) -> bool:
        """发送加密消息"""
        try:
            if not self.crypto_engine:
                raise RuntimeError("安全引擎未初始化，请先登录")

            # 确保加密会话已建立
            try:
                self.session_mgr.get_session_key(target_user)
            except Exception:
                public_key_b64 = self.get_user_public_key(target_user)
                if not public_key_b64:
                    raise RuntimeError(f"无法获取 {target_user} 的公钥，不能建立加密会话")

            # 加密消息
            encrypted_pkg = self.crypto_engine.encrypt_message(
                receiver_id=target_user,
                message_id=str(uuid.uuid4()),
                content=message_content,
                ttl_seconds=ttl
            )

            # 发送加密包
            message_id = self.network_client.send_message(target_user, encrypted_pkg, ttl)
            print(f"消息已发送给 {target_user}，ID: {message_id}")
            return True
        except Exception as e:
            print(f"发送消息失败: {str(e)}")
            return False

    def fetch_offline_messages(self) -> List:
        """获取离线消息并解密"""
        try:
            if not self.crypto_engine:
                raise RuntimeError("安全引擎未初始化，请先登录")

            messages = self.network_client.fetch_offline_messages()
            print("收到的离线消息:")

            for msg_pkg in messages:
                try:
                    clear_text = self.crypto_engine.decrypt_message(msg_pkg)
                    sender = msg_pkg.get('sender_id') or msg_pkg.get('from_user', 'Unknown')
                    print(f"来自 {sender} 的加密消息: {clear_text}")
                except Exception as e:
                    sender = msg_pkg.get('sender_id') or msg_pkg.get('from_user', 'Unknown')
                    print(f"来自 {sender} 的消息解密失败，消息可能被篡改: {e}")

            return messages
        except Exception as e:
            print(f"获取离线消息失败: {str(e)}")
            return []

    def get_conversations(self) -> List:
        """获取会话列表（从好友列表转换）"""
        return self.friends_list

    def get_messages(self, peer_user_id: str, limit: int = 50) -> List:
        """获取与某人的消息历史（从离线消息中筛选，不解密）"""
        messages = self.fetch_offline_messages()
        filtered = [m for m in messages if m.get('from_user') == peer_user_id or m.get('sender_id') == peer_user_id]
        return filtered[:limit]

    # ---------- WebSocket 实时消息 ----------
    def setup_websocket_listener(self):
        """设置WebSocket监听器，解密实时消息"""
        if self.ws_client is None:
            self.ws_client = WebSocketClient(
                "https://ungladly-cremasterial-spring.ngrok-free.dev/",
                self.network_client.token
            )

        async def handle_message(message):
            print(f"\n收到新消息: {message}")
            msg_type = message.get('type', '')

            if msg_type == 'message':
                try:
                    if self.crypto_engine:
                        clear_text = self.crypto_engine.decrypt_message(message)
                        sender = message.get('sender_id') or message.get('sender', 'Unknown')
                        print(f"[新消息] {sender}: {clear_text}")
                    else:
                        print("[警告] 安全引擎未初始化，无法解密实时消息")
                except Exception as e:
                    print(f"[警告] 实时消息解密失败: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.ws_client.connect(handle_message))
        return loop


def print_menu():
    """打印菜单（命令行模式用）"""
    print("\n" + "=" * 50)
    print("端到端加密即时通讯系统 - 客户端")
    print("=" * 50)
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
    print("=" * 50)


def main():
    """命令行入口（GUI失败时回退）"""
    client = ClientFacade()

    print("欢迎使用端到端加密即时通讯系统客户端!")

    while True:
        print_menu()
        try:
            choice = input("请选择功能 (0-12): ").strip()

            if choice == '1':
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
                if client.current_user:
                    print(f"当前已登录用户: {client.current_user}，请先退出登录")
                    continue

                username = input("请输入用户名: ").strip()
                password = getpass.getpass("请输入密码: ")
                otp_code = input("请输入OTP应用生成的6位数字验证码: ").strip()

                if client.login_user(username, password, otp_code):
                    print(f"登录成功! 欢迎 {username}")
                    try:
                        print("正在连接WebSocket服务...")
                    except Exception as e:
                        print(f"WebSocket连接失败: {str(e)}")

            elif choice == '3':
                if not client.current_user:
                    print("请先登录!")
                    continue

                target_user = input("请输入目标用户名: ").strip()
                if not target_user:
                    print("用户名不能为空!")
                    continue

                client.send_friend_request(target_user)

            elif choice == '4':
                if not client.current_user:
                    print("请先登录!")
                    continue

                client.get_friend_requests()

            elif choice == '5':
                if not client.current_user:
                    print("请先登录!")
                    continue

                request_id = input("请输入要接受的好友请求ID: ").strip()
                if not request_id:
                    print("请求ID不能为空!")
                    continue

                client.accept_friend_request(request_id)

            elif choice == '6':
                if not client.current_user:
                    print("请先登录!")
                    continue

                request_id = input("请输入要拒绝的好友请求ID: ").strip()
                if not request_id:
                    print("请求ID不能为空!")
                    continue

                client.decline_friend_request(request_id)

            elif choice == '7':
                if not client.current_user:
                    print("请先登录!")
                    continue

                client.refresh_friends_list()

            elif choice == '8':
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
                if not client.current_user:
                    print("请先登录!")
                    continue

                client.fetch_offline_messages()

            elif choice == '10':
                if not client.current_user:
                    print("请先登录!")
                    continue

                print("此功能用于上传用户公钥到服务器")
                public_key = input("请输入公钥(Base64字符串): ").strip()
                if not public_key:
                    print("公钥不能为空!")
                    continue
                client.upload_public_key(public_key.encode("utf-8"))

            elif choice == '11':
                if not client.current_user:
                    print("请先登录!")
                    continue

                target_user = input("请输入要获取公钥的用户名: ").strip()
                if not target_user:
                    print("用户名不能为空!")
                    continue

                client.get_user_public_key(target_user)

            elif choice == '12':
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
        # 尝试启动图形界面
        from PyQt5.QtWidgets import QApplication
        from ui.gui import LoginDialog, ChatGUI

        # 设置 Qt 平台插件路径（可选，解决部分环境问题）
        pyqt5_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
            os.path.join(os.environ.get('APPDATA', ''), 'Python', 'Python39', 'site-packages', 'PyQt5', 'Qt5', 'plugins'),
            os.path.join(os.path.dirname(os.__file__), 'site-packages', 'PyQt5', 'Qt5', 'plugins')
        ]
        for path in pyqt5_paths:
            if os.path.exists(os.path.join(path, 'platforms', 'qwindows.dll')):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(path, 'platforms')
                break

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        main_window_ref = [None]
        client_ref = [None]

        def on_login_success(username, password, otp):
            client = ClientFacade(server_url="https://ungladly-cremasterial-spring.ngrok-free.dev/")
            if client.login_user(username, password, otp):
                client_ref[0] = client
                main_window_ref[0] = ChatGUI(client)
                main_window_ref[0].show()
                for widget in app.topLevelWidgets():
                    if isinstance(widget, LoginDialog):
                        widget.close()
            else:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(None, "登录失败", "用户名、密码或OTP验证码错误")

        login_dialog = LoginDialog()
        login_dialog.login_success_signal.connect(on_login_success)
        login_dialog.show()

        sys.exit(app.exec_())

    except ImportError as e:
        print(f"无法启动图形界面: {e}")
        print("请确保已安装 PyQt5: pip install PyQt5")
        main()
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        if "Could not find the Qt platform plugin" in str(e):
            print("\nQt 平台插件错误: 无法找到 'windows' 平台插件")
            print("建议尝试重新安装 PyQt5: pip install --force-reinstall PyQt5")
        main()
