import sys
import os
import threading
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
client_src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(client_src_dir))

for path in [client_src_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

from main2 import ClientFacade


class FriendRequestWidget(QWidget):
    """好友请求项组件"""
    
    request_accepted = pyqtSignal(str)
    request_declined = pyqtSignal(str)
    
    def __init__(self, request_id, from_user, parent=None):
        super().__init__(parent)
        self.request_id = request_id
        self.from_user = from_user
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.label = QLabel(f"来自: {self.from_user}")
        self.label.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        self.accept_btn = QPushButton("✓")
        self.accept_btn.setFixedSize(30, 30)
        self.accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        self.accept_btn.clicked.connect(lambda: self.request_accepted.emit(self.request_id))
        
        self.decline_btn = QPushButton("✗")
        self.decline_btn.setFixedSize(30, 30)
        self.decline_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.decline_btn.clicked.connect(lambda: self.request_declined.emit(self.request_id))
        
        layout.addWidget(self.accept_btn)
        layout.addWidget(self.decline_btn)


class SentRequestWidget(QWidget):
    """已发送请求项组件"""
    
    def __init__(self, to_user, status, parent=None):
        super().__init__(parent)
        self.to_user = to_user
        self.status = status
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        status_text = "等待接受" if self.status == "pending" else "已接受"
        status_color = "#f39c12" if self.status == "pending" else "#27ae60"
        
        self.label = QLabel(f"发送给: {self.to_user}")
        self.label.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        self.status_label = QLabel(status_text)
        self.status_label.setStyleSheet(f"color: {status_color}; font-size: 20px;")
        layout.addWidget(self.status_label)


class FriendRequestPanel(QDialog):
    """好友请求管理面板"""
    
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("好友请求管理")
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)
        self.setModal(True)
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 添加好友区域
        add_group = QGroupBox("添加好友")
        add_layout = QVBoxLayout(add_group)
        
        input_layout = QHBoxLayout()
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("输入好友用户名")
        self.add_input.returnPressed.connect(self.add_friend)
        
        self.add_btn = QPushButton("添加")
        self.add_btn.setFixedHeight(32)
        self.add_btn.clicked.connect(self.add_friend)
        
        input_layout.addWidget(self.add_input)
        input_layout.addWidget(self.add_btn)
        
        self.add_result = QLabel("")
        self.add_result.setStyleSheet("color: gray; font-size: 20px;")
        
        add_layout.addLayout(input_layout)
        add_layout.addWidget(self.add_result)
        layout.addWidget(add_group)
        
        # 收到的请求区域
        received_group = QGroupBox("收到的好友请求")
        received_layout = QVBoxLayout(received_group)
        
        self.received_scroll = QScrollArea()
        self.received_scroll.setWidgetResizable(True)
        self.received_scroll.setStyleSheet("border: none;")
        
        self.received_container = QWidget()
        self.received_layout = QVBoxLayout(self.received_container)
        self.received_layout.setAlignment(Qt.AlignTop)
        self.received_layout.setSpacing(5)
        
        self.received_scroll.setWidget(self.received_container)
        received_layout.addWidget(self.received_scroll)
        layout.addWidget(received_group)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(35)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def load_data(self):
        """加载好友请求数据"""
        self.load_received_requests()
    
    def load_received_requests(self):
        """加载收到的请求"""
        self.clear_layout(self.received_layout)
        
        requests = self.client.get_friend_requests()
        
        if not requests:
            empty_label = QLabel("暂无收到的好友请求")
            empty_label.setStyleSheet("color: gray; padding: 20px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.received_layout.addWidget(empty_label)
        else:
            for req in requests:
                from_user = req.get('from_user') or req.get('user_a', 'Unknown')
                request_id = req.get('request_id') or req.get('id', '')
                
                widget = FriendRequestWidget(request_id, from_user)
                widget.request_accepted.connect(self.accept_request)
                widget.request_declined.connect(self.decline_request)
                self.received_layout.addWidget(widget)
    
    def clear_layout(self, layout):
        """清空布局"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def add_friend(self):
        """添加好友"""
        username = self.add_input.text().strip()
        if not username:
            self.add_result.setText("请输入用户名")
            self.add_result.setStyleSheet("color: red; font-size: 20px;")
            return
        
        if username == self.client.current_user:
            self.add_result.setText("不能添加自己为好友")
            self.add_result.setStyleSheet("color: red; font-size: 20px;")
            return
        
        success = self.client.send_friend_request(username)
        if success:
            self.add_result.setText(f"好友请求已发送给 {username}")
            self.add_result.setStyleSheet("color: green; font-size: 20px;")
            self.add_input.clear()
        else:
            self.add_result.setText(f"发送失败，用户 {username} 可能不存在")
            self.add_result.setStyleSheet("color: red; font-size: 20px;")
    
    def accept_request(self, request_id):
        """接受好友请求"""
        success = self.client.accept_friend_request(request_id)
        if success:
            self.load_received_requests()
            if self.parent():
                self.parent().refresh_friends()
        else:
            QMessageBox.warning(self, "失败", "接受好友请求失败")
    
    def decline_request(self, request_id):
        """拒绝好友请求"""
        success = self.client.decline_friend_request(request_id)
        if success:
            self.load_received_requests()
        else:
            QMessageBox.warning(self, "失败", "拒绝好友请求失败")


class AddFriendButton(QPushButton):
    """添加好友按钮"""
    
    def __init__(self, parent=None):
        super().__init__("+", parent)
        self.setFixedSize(40, 35)
        self.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                font-size: 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        self.has_notification = False
        self.notification_label = None
    
    def show_notification(self, show=True):
        """显示/隐藏红点提示"""
        self.has_notification = show
        if show:
            if not self.notification_label:
                self.notification_label = QLabel(self)
                self.notification_label.setStyleSheet("""
                    background-color: #e74c3c;
                    border-radius: 5px;
                    min-width: 10px;
                    max-width: 10px;
                    min-height: 10px;
                    max-height: 10px;
                """)
                self.notification_label.move(30, 5)
                self.notification_label.resize(10, 10)
                self.notification_label.raise_()
                self.notification_label.show()
        else:
            if self.notification_label:
                self.notification_label.hide()
                self.notification_label.deleteLater()
                self.notification_label = None

class ChatGUI(QMainWindow):
    """端到端加密聊天图形界面"""
    
    def __init__(self, client: ClientFacade = None):
        super().__init__()
        
        self.client = client if client else ClientFacade()
        self.current_user = self.client.current_user
        self.current_conversation = None
        self.friend_to_conv_id = {}
        
        self.setup_ui()
        
        self.polling_running = False
        self.polling_thread = None
        
        if self.current_user:
            self.user_label.setText(f"用户: {self.current_user}")
            self.refresh_all()
            self.start_polling()
            self.check_pending_requests()

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("Secure Chat - End-to-End Encrypted Messenger")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # ========== 左侧面板 ==========
        left_panel = QWidget()
        left_panel.setMaximumWidth(280)
        left_panel.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(10)
        
        # 用户信息区域（包含用户名和加号按钮）
        user_widget = QWidget()
        user_widget.setStyleSheet("background-color: #2c3e50; border-radius: 5px;")
        user_layout = QHBoxLayout(user_widget)
        user_layout.setContentsMargins(10, 5, 10, 5)
        
        self.user_label = QLabel("未登录")
        self.user_label.setStyleSheet("color: white; font-weight: bold; font-size: 20px;")
        user_layout.addWidget(self.user_label)
        user_layout.addStretch()
        
        # 添加好友按钮
        self.add_friend_btn = AddFriendButton()
        self.add_friend_btn.clicked.connect(self.open_friend_request_panel)
        user_layout.addWidget(self.add_friend_btn)
        
        left_layout.addWidget(user_widget)
        
        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_conversations_tab(), "会话")
        self.tab_widget.addTab(self.create_friends_tab(), "好友")
        left_layout.addWidget(self.tab_widget)
        
        # 刷新和登出按钮
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setSpacing(10)
        
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setFixedHeight(32)
        
        self.btn_logout = QPushButton("登出")
        self.btn_logout.setFixedHeight(32)
        
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_logout)
        btn_layout.addStretch()
        left_layout.addWidget(btn_widget)
        
        # ========== 右侧面板 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(10)

        # 聊天标题
        chat_header = QWidget()
        chat_header.setStyleSheet("background-color: #34495e; border-radius: 5px;")
        chat_layout = QHBoxLayout(chat_header)

        self.chat_title = QLabel("请选择会话")
        self.chat_title.setStyleSheet("color: white; font-weight: bold; font-size: 20px; padding: 8px;")
        chat_layout.addWidget(self.chat_title)
        chat_layout.addStretch()

        right_layout.addWidget(chat_header)

        # 消息显示区域
        self.messages_text = QTextEdit()
        self.messages_text.setReadOnly(True)
        self.messages_text.setStyleSheet("""
            QTextEdit {
                font-family: "Microsoft YaHei";
                font-size: 20px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        right_layout.addWidget(self.messages_text, 1)  # 添加 stretch 因子，让它占满剩余空间

        # 消息输入区域
        input_container = QWidget()
        input_container.setStyleSheet("border: 1px solid #bdc3c7; border-radius: 5px;")
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)
        input_layout.setSpacing(5)

        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.setStyleSheet("border: none; font-size: 20px;")
        input_layout.addWidget(self.message_input)

        # 底部工具栏
        toolbar = QWidget()
        toolbar.setMaximumHeight(30)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(5)

        ttl_label = QLabel("自毁时间:")
        ttl_label.setFixedHeight(25)
        toolbar_layout.addWidget(ttl_label)

        self.ttl_spin = QSpinBox()
        self.ttl_spin.setRange(5, 3600)
        self.ttl_spin.setValue(30)
        self.ttl_spin.setSuffix("秒")
        self.ttl_spin.setFixedWidth(80)
        self.ttl_spin.setFixedHeight(25)
        self.ttl_spin.setStyleSheet("QSpinBox { padding: 0px; }")
        toolbar_layout.addWidget(self.ttl_spin)

        toolbar_layout.addStretch()

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedHeight(28)
        self.send_btn.setFixedWidth(60)
        self.send_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        toolbar_layout.addWidget(self.send_btn)

        input_layout.addWidget(toolbar)
        right_layout.addWidget(input_container)
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)
        
        # 连接信号
        self.send_btn.clicked.connect(self.send_message)
        self.btn_refresh.clicked.connect(self.refresh_all)
        self.btn_logout.clicked.connect(self.do_logout)
    
    def create_conversations_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.conversations_list = QListWidget()
        self.conversations_list.setAlternatingRowColors(True)
        self.conversations_list.itemClicked.connect(self.on_conversation_selected)
        layout.addWidget(self.conversations_list)
        return widget
    
    def create_friends_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.friends_list = QListWidget()
        self.friends_list.setAlternatingRowColors(True)
        self.friends_list.itemClicked.connect(self.on_friend_selected)
        layout.addWidget(self.friends_list)
        return widget
    
    def open_friend_request_panel(self):
        """打开好友请求管理面板"""
        panel = FriendRequestPanel(self.client, self)
        panel.exec_()
        # 关闭面板后刷新数据
        self.refresh_friends()
        self.check_pending_requests()
    
    def check_pending_requests(self):
        """检查是否有待处理的好友请求，更新红点提示"""
        requests = self.client.get_friend_requests()
        has_pending = len(requests) > 0
        self.add_friend_btn.show_notification(has_pending)
    
    def do_logout(self):
        """登出"""
        self.client.current_user = None
        self.current_user = None
        self.user_label.setText("未登录")
        self.conversations_list.clear()
        self.friends_list.clear()
        self.messages_text.clear()
        self.chat_title.setText("请选择会话")
        self.stop_polling()
        self.hide()
        
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, LoginDialog):
                widget.show()
                break
    
    def send_message(self):
        """发送消息"""
        if not self.current_conversation:
            QMessageBox.warning(self, "提示", "请先选择一个会话")
            return
        
        text = self.message_input.toPlainText().strip()
        if not text:
            return
        
        ttl = self.ttl_spin.value()
        success = self.client.send_message(self.current_conversation, text, ttl)
        
        if success:
            self.message_input.clear()
            self.display_message("我", text, True)
        else:
            QMessageBox.warning(self, "发送失败", "消息发送失败")
    
    def display_message(self, sender: str, text: str, is_from_me: bool = False):
        """显示消息"""
        time_str = datetime.now().strftime("%H:%M")
        
        if is_from_me:
            self.messages_text.append(f"[{time_str}] 我: {text}")
        else:
            self.messages_text.append(f"[{time_str}] {sender}: {text}")
        
        scrollbar = self.messages_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def refresh_all(self):
        """刷新所有数据"""
        self.refresh_friends()
        self.refresh_conversations()
        self.check_pending_requests()
    
    def refresh_friends(self):
        """刷新好友列表 - 不清空，直接更新"""
        friends = self.client.refresh_friends_list()
        
        if not friends:
            if self.friends_list.count() == 0:
                self.friends_list.addItem("暂无好友")
            return
        
        # 构建新数据字典
        new_friends = {}
        for friend in friends:
            if isinstance(friend, dict):
                name = friend.get('username', 'Unknown')
                status = '在线' if friend.get('is_online', False) else '离线'
                display_text = f"{name} ({status})"
            else:
                name = str(friend)
                display_text = name
            new_friends[name] = display_text
        
        # 更新现有项或添加新项
        existing_names = set()
        for i in range(self.friends_list.count()):
            item = self.friends_list.item(i)
            item_text = item.text()
            # 从显示文本中提取用户名
            if " (" in item_text:
                old_name = item_text.split(" (")[0]
            else:
                old_name = item_text
            
            existing_names.add(old_name)
            
            if old_name in new_friends:
                # 更新现有项
                if item.text() != new_friends[old_name]:
                    item.setText(new_friends[old_name])
                del new_friends[old_name]
            else:
                # 删除不再存在的项
                self.friends_list.takeItem(i)
        
        # 添加新项
        for name, display_text in new_friends.items():
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, name)
            self.friends_list.addItem(item)

        
    def refresh_conversations(self):
        """刷新会话列表 - 不清空，直接更新"""
        friends = self.client.friends_list
        
        if not friends:
            if self.conversations_list.count() == 0:
                self.conversations_list.addItem("暂无会话")
            return
        
        # 构建新数据字典
        new_conversations = {}
        for friend in friends:
            if isinstance(friend, dict):
                name = friend.get('username', 'Unknown')
            else:
                name = str(friend)
            new_conversations[name] = name
            self.friend_to_conv_id[name] = name
        
        # 更新现有项或添加新项
        existing_names = set()
        for i in range(self.conversations_list.count()):
            item = self.conversations_list.item(i)
            old_name = item.text()
            
            if old_name == "暂无会话":
                self.conversations_list.takeItem(i)
                continue
            
            existing_names.add(old_name)
            
            if old_name in new_conversations:
                # 存在，标记为已处理
                del new_conversations[old_name]
            else:
                # 不再存在，删除
                self.conversations_list.takeItem(i)
        
        # 添加新项
        for name in new_conversations.values():
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)
            self.conversations_list.addItem(item)
    
    def on_conversation_selected(self, item: QListWidgetItem):
        """选择会话"""
        friend_name = item.data(Qt.UserRole)
        if friend_name and friend_name != "暂无会话":
            self.current_conversation = friend_name
            self.chat_title.setText(f"正在与 {friend_name} 聊天")
            self.messages_text.clear()
            self.load_offline_messages(friend_name)
    
    def on_friend_selected(self, item: QListWidgetItem):
        """选择好友"""
        friend_name = item.data(Qt.UserRole)
        if friend_name and friend_name != "暂无好友":
            self.current_conversation = friend_name
            self.chat_title.setText(f"正在与 {friend_name} 聊天")
            self.messages_text.clear()
            self.load_offline_messages(friend_name)
    
    def load_offline_messages(self, friend_name: str):
        """加载与好友的离线消息"""
        messages = self.client.fetch_offline_messages()
        
        for msg in messages:
            sender = msg.get('from_user') or msg.get('sender_id', 'Unknown')
            if sender == friend_name:
                ciphertext = msg.get('ciphertext') or msg.get('ciphertext_b64', b'')
                if isinstance(ciphertext, str):
                    import base64
                    try:
                        text = base64.b64decode(ciphertext).decode('utf-8')
                    except:
                        text = ciphertext
                else:
                    text = ciphertext.decode('utf-8') if isinstance(ciphertext, bytes) else str(ciphertext)
                
                timestamp = msg.get('timestamp', 0)
                time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M") if timestamp else "?"
                self.messages_text.append(f"[{time_str}] {sender}: {text}")
    
    def start_polling(self):
        """启动消息轮询"""
        self.polling_running = True
        self.polling_thread = threading.Thread(target=self.poll_messages, daemon=True)
        self.polling_thread.start()
    
    def stop_polling(self):
        """停止消息轮询"""
        self.polling_running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=2)
    
    def poll_messages(self):
        """轮询新消息"""
        import time
        while self.polling_running:
            try:
                if self.current_user:
                    self.refresh_friends()
                    self.check_pending_requests()
                time.sleep(3)
            except:
                pass


class LoginDialog(QDialog):
    """登录对话框"""
    
    login_success_signal = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 / 注册")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        self.setModal(False)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel("Secure Chat")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title_label)
        
        self.tab_widget = QTabWidget()
        
        # 登录页
        login_widget = QWidget()
        login_layout = QFormLayout(login_widget)
        login_layout.setSpacing(15)
        login_layout.setContentsMargins(20, 20, 20, 20)
        
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("请输入用户名")
        
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setPlaceholderText("请输入密码")
        
        self.login_otp = QLineEdit()
        self.login_otp.setPlaceholderText("6位数字验证码")
        
        login_layout.addRow("用户名:", self.login_username)
        login_layout.addRow("密码:", self.login_password)
        login_layout.addRow("OTP验证码:", self.login_otp)
        
        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedHeight(35)
        self.login_btn.clicked.connect(self.on_login)
        login_layout.addRow(self.login_btn)
        
        # 注册页
        register_widget = QWidget()
        register_layout = QFormLayout(register_widget)
        register_layout.setSpacing(15)
        register_layout.setContentsMargins(20, 20, 20, 20)
        
        self.register_username = QLineEdit()
        self.register_username.setPlaceholderText("请输入用户名")
        
        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.Password)
        self.register_password.setPlaceholderText("请输入密码")
        
        register_layout.addRow("用户名:", self.register_username)
        register_layout.addRow("密码:", self.register_password)
        
        password_hint = QLabel("密码长度至少为6位")
        password_hint.setStyleSheet("color: gray; font-size: 20px;")
        register_layout.addRow("", password_hint)
        
        self.register_btn = QPushButton("注册")
        self.register_btn.setFixedHeight(35)
        self.register_btn.clicked.connect(self.on_register)
        register_layout.addRow(self.register_btn)
        
        register_hint = QLabel("注册成功后会生成OTP密钥，请妥善保存")
        register_hint.setStyleSheet("color: gray; font-size: 20px;")
        register_layout.addRow("", register_hint)
        
        self.tab_widget.addTab(login_widget, "登录")
        self.tab_widget.addTab(register_widget, "注册")
        layout.addWidget(self.tab_widget)
    
    def on_login(self):
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()
        otp = self.login_otp.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "错误", "请输入用户名和密码")
            return
        
        if not otp:
            QMessageBox.warning(self, "错误", "请输入OTP验证码")
            return
        
        self.login_success_signal.emit(username, password, otp)
        self.close()
    
    def on_register(self):
        username = self.register_username.text().strip()
        password = self.register_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "错误", "请输入用户名和密码")
            return
        
        if len(password) < 6:
            QMessageBox.warning(self, "错误", "密码长度至少为6位")
            return
        
        client = ClientFacade()
        success, otp_secret = client.register_user(username, password)
        
        if success:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("注册成功")
            msg_box.setText(f"用户 {username} 注册成功！")
            msg_box.setInformativeText(
                f"OTP密钥: {otp_secret}\n\n"
                "请保存此密钥，用于设置OTP应用（如Google Authenticator）\n"
                "登录时需要使用OTP应用生成的6位数字验证码。"
            )
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
            
            self.tab_widget.setCurrentIndex(0)
            self.login_username.setText(username)
            self.login_otp.setFocus()
        else:
            QMessageBox.warning(self, "注册失败", "用户名已存在或注册失败")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    default_font = QFont("Microsoft YaHei", 10)
    app.setFont(default_font)
    
    main_window_ref = [None]
    
    def on_login_success(username, password, otp):
        client = ClientFacade(server_url="http://localhost:80")
        if client.login_user(username, password, otp):
            main_window_ref[0] = ChatGUI(client)
            main_window_ref[0].show()
            for widget in app.topLevelWidgets():
                if isinstance(widget, LoginDialog):
                    widget.close()
        else:
            QMessageBox.warning(None, "登录失败", "用户名、密码或OTP验证码错误")
    
    login_dialog = LoginDialog()
    login_dialog.login_success_signal.connect(on_login_success)
    login_dialog.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()