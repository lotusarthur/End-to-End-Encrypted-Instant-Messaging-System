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

from main import InstantMessagingClient, UIController


class ChatGUI(QMainWindow):
    """端到端加密聊天图形界面"""
    
    def __init__(self, server_url: str = "http://localhost:80"):
        super().__init__()
        
        # 初始化客户端
        self.client = InstantMessagingClient(server_url)
        self.ui_controller = UIController(self.client)
        
        self.current_user = None
        self.current_conversation = None
        self.friend_to_conv_id = {}
        
        # 设置界面
        self.setup_ui()
        self.setup_events()
        
        # 消息轮询线程
        self.polling_running = False
        self.polling_thread = None

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("Secure Chat - End-to-End Encrypted Messenger")
        self.setGeometry(100, 100, 900, 600)
        
        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # ========== 左侧面板 ==========
        left_panel = QWidget()
        left_panel.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_panel)
        
        self.user_label = QLabel("未登录")
        self.user_label.setStyleSheet("font-weight: bold; padding: 10px; background-color: #2c3e50; color: white;")
        left_layout.addWidget(self.user_label)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_conversations_tab(), "会话")
        self.tab_widget.addTab(self.create_friends_tab(), "好友")
        left_layout.addWidget(self.tab_widget)
        
        btn_layout = QHBoxLayout()
        self.add_friend_btn = QPushButton("添加好友")
        self.refresh_btn = QPushButton("刷新")
        self.logout_btn = QPushButton("登出")
        btn_layout.addWidget(self.add_friend_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.logout_btn)
        left_layout.addLayout(btn_layout)
        
        # ========== 右侧面板 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.chat_title = QLabel("请选择会话")
        self.chat_title.setStyleSheet("font-weight: bold; padding: 10px; background-color: #34495e; color: white;")
        right_layout.addWidget(self.chat_title)
        
        self.messages_text = QTextEdit()
        self.messages_text.setReadOnly(True)
        right_layout.addWidget(self.messages_text)
        
        input_layout = QHBoxLayout()
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("输入消息...")
        
        self.ttl_spin = QSpinBox()
        self.ttl_spin.setRange(5, 3600)
        self.ttl_spin.setValue(30)
        self.ttl_spin.setSuffix(" 秒")
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        
        input_layout.addWidget(self.message_input, 4)
        input_layout.addWidget(self.ttl_spin, 1)
        input_layout.addWidget(self.send_btn, 1)
        right_layout.addLayout(input_layout)
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)
        
        # ========== 添加好友对话框 ==========
        self.add_friend_dialog = AddFriendDialog(self)
        self.add_friend_dialog.add_friend_signal.connect(self.do_add_friend)
        
        # 连接信号
        self.send_btn.clicked.connect(self.send_message)
        self.add_friend_btn.clicked.connect(self.show_add_friend_dialog)
        self.refresh_btn.clicked.connect(self.refresh_all)
        self.logout_btn.clicked.connect(self.do_logout)
    
    def create_conversations_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.conversations_list = QListWidget()
        self.conversations_list.itemClicked.connect(self.on_conversation_selected)
        layout.addWidget(self.conversations_list)
        return widget
    
    def create_friends_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.friends_list = QListWidget()
        self.friends_list.itemClicked.connect(self.on_friend_selected)
        layout.addWidget(self.friends_list)
        return widget
    
    def setup_events(self):
        self.ui_controller.ui_register_callback("auth.login_success", self.on_login_success)
        self.ui_controller.ui_register_callback("auth.logout", self.on_logout)
        self.ui_controller.ui_register_callback("chat.message_received", self.on_message_received)
        self.ui_controller.ui_register_callback("chat.message_sent", self.on_message_sent)
        self.ui_controller.ui_register_callback("chat.message_failed", self.on_message_failed)
    
    # ========== 事件处理 ==========
    
    def on_login_success(self, data: dict):
        self.current_user = data.get('profile', {}).get('username', 'User')
        self.user_label.setText(f"用户: {self.current_user}")
        self.refresh_all()
        self.start_polling()
    
    def on_logout(self, data: dict):
        self.current_user = None
        self.user_label.setText("未登录")
        self.conversations_list.clear()
        self.friends_list.clear()
        self.messages_text.clear()
        self.stop_polling()
        # 登出后重新显示登录对话框
        self.hide()
        login_dialog = LoginDialog()
        if login_dialog.exec_() == QDialog.Accepted:
            # 登录成功，主窗口保持显示
            pass
        else:
            sys.exit(0)
    
    def on_message_received(self, data: dict):
        sender = data.get('sender_id', 'Unknown')
        text = data.get('text', '')
        if self.current_conversation == sender:
            self.add_message_to_display(sender, text, is_from_me=False)
        else:
            self.refresh_conversations()
            QApplication.beep()
    
    def on_message_sent(self, data: dict):
        text = data.get('text', '')
        self.add_message_to_display("我", text, is_from_me=True)
        self.message_input.clear()
    
    def on_message_failed(self, data: dict):
        error = data.get('error', 'Unknown error')
        QMessageBox.warning(self, "发送失败", f"消息发送失败: {error}")
    
    # ========== 业务操作 ==========
    
    def do_logout(self):
        self.ui_controller.ui_logout()
    
    def send_message(self):
        if not self.current_conversation:
            QMessageBox.warning(self, "提示", "请先选择一个会话")
            return
        text = self.message_input.toPlainText().strip()
        if not text:
            return
        ttl = self.ttl_spin.value()
        result = self.ui_controller.ui_send_message(self.current_conversation, text, ttl)
        if not result.get('success'):
            QMessageBox.warning(self, "发送失败", result.get('error', '发送失败'))
    
    def do_add_friend(self, username: str):
        result = self.ui_controller.ui_search_and_add_friend(username)
        if result.get('success'):
            QMessageBox.information(self, "成功", f"好友请求已发送给 {username}")
        else:
            QMessageBox.warning(self, "失败", result.get('error', '添加失败'))
    
    # ========== 刷新数据 ==========
    
    def refresh_all(self):
        self.refresh_conversations()
        self.refresh_friends()
    
    def refresh_conversations(self):
        self.conversations_list.clear()
        conversations = self.ui_controller.ui_get_conversations()
        for conv in conversations:
            peer = conv.get('peer_user_id', 'Unknown')
            last_msg = conv.get('last_message', '')[:30]
            unread = conv.get('unread_count', 0)
            item_text = f"{peer}"
            if unread > 0:
                item_text = f"🔴 {peer} ({unread})"
            if last_msg:
                item_text += f"\n  {last_msg}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, conv.get('conversation_id'))
            self.conversations_list.addItem(item)
            self.friend_to_conv_id[peer] = conv.get('conversation_id')
    
    def refresh_friends(self):
        self.friends_list.clear()
        conversations = self.ui_controller.ui_get_conversations()
        for conv in conversations:
            peer = conv.get('peer_user_id', 'Unknown')
            item = QListWidgetItem(peer)
            item.setData(Qt.UserRole, peer)
            self.friends_list.addItem(item)
    
    # ========== 会话选择 ==========
    
    def on_conversation_selected(self, item: QListWidgetItem):
        conv_id = item.data(Qt.UserRole)
        if conv_id:
            self.current_conversation = conv_id
            self.load_messages(conv_id)
            for peer, cid in self.friend_to_conv_id.items():
                if cid == conv_id:
                    self.chat_title.setText(f"正在与 {peer} 聊天")
                    break
    
    def on_friend_selected(self, item: QListWidgetItem):
        friend_name = item.data(Qt.UserRole)
        if friend_name:
            conv_id = self.friend_to_conv_id.get(friend_name)
            if conv_id:
                self.current_conversation = conv_id
                self.load_messages(conv_id)
                self.chat_title.setText(f"正在与 {friend_name} 聊天")
            else:
                self.current_conversation = friend_name
                self.chat_title.setText(f"正在与 {friend_name} 聊天（新会话）")
                self.messages_text.clear()
    
    def load_messages(self, conversation_id: str):
        self.messages_text.clear()
        messages = self.ui_controller.ui_get_messages(conversation_id, limit=50)
        for msg in reversed(messages):
            direction = "→" if msg.get('direction') == 'outgoing' else "←"
            text = msg.get('text', '')
            timestamp = msg.get('created_at', msg.get('timestamp', 0))
            time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M") if timestamp else "Unknown"
            self.add_message_to_display(
                "我" if direction == "→" else msg.get('sender_id', '对方'),
                text, direction == "→", time_str
            )
    
    def add_message_to_display(self, sender: str, text: str, is_from_me: bool = False, time_str: str = None):
        if time_str is None:
            time_str = datetime.now().strftime("%H:%M")
        if is_from_me:
            html = f'<div style="text-align: right; margin: 5px;"><span style="background-color: #27ae60; color: white; padding: 8px; border-radius: 10px; display: inline-block; max-width: 70%;"><b>{sender}</b><br>{text}</span><div style="font-size: 10px; color: gray;">{time_str}</div></div>'
        else:
            html = f'<div style="text-align: left; margin: 5px;"><span style="background-color: #34495e; color: white; padding: 8px; border-radius: 10px; display: inline-block; max-width: 70%;"><b>{sender}</b><br>{text}</span><div style="font-size: 10px; color: gray;">{time_str}</div></div>'
        self.messages_text.insertHtml(html)
        scrollbar = self.messages_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def show_add_friend_dialog(self):
        self.add_friend_dialog.show()
    
    # ========== 消息轮询 ==========
    
    def start_polling(self):
        self.polling_running = True
        self.polling_thread = threading.Thread(target=self.poll_messages, daemon=True)
        self.polling_thread.start()
    
    def stop_polling(self):
        self.polling_running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=2)
    
    def poll_messages(self):
        import time
        while self.polling_running:
            try:
                self.refresh_conversations()
                time.sleep(2)
            except:
                pass


class LoginDialog(QDialog):
    """登录对话框 - 登录成功后返回主窗口"""

    login_success_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 / 注册")
        self.setup_ui()
        self.client = None
        self.login_success = False
        self.user_data = None
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        
        # 登录页
        login_widget = QWidget()
        login_layout = QFormLayout(login_widget)
        self.login_username = QLineEdit()
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_otp = QLineEdit()
        self.login_otp.setPlaceholderText("可选")
        login_layout.addRow("用户名:", self.login_username)
        login_layout.addRow("密码:", self.login_password)
        login_layout.addRow("OTP:", self.login_otp)
        self.login_btn = QPushButton("登录")
        self.login_btn.clicked.connect(self.on_login)
        login_layout.addRow(self.login_btn)
        
        # 注册页
        register_widget = QWidget()
        register_layout = QFormLayout(register_widget)
        self.register_username = QLineEdit()
        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.Password)
        register_layout.addRow("用户名:", self.register_username)
        register_layout.addRow("密码:", self.register_password)
        self.register_btn = QPushButton("注册")
        self.register_btn.clicked.connect(self.on_register)
        register_layout.addRow(self.register_btn)
        
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
        
        # 创建客户端并登录
        self.client = InstantMessagingClient("http://localhost:80")
        ui_controller = UIController(self.client)
        result = ui_controller.ui_login(username, password, otp if otp else "123456")
        
        if result.get('success'):
            self.user_data = {'username': username}
            self.login_success = True
            self.login_success_signal.emit(username)  # 发射信号
            self.close()  # 关闭对话框
        else:
            QMessageBox.warning(self, "登录失败", result.get('error', '登录失败'))
            
    def on_register(self):
        username = self.register_username.text().strip()
        password = self.register_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "错误", "请输入用户名和密码")
            return
        
        client = InstantMessagingClient("http://localhost:80")
        result = client.register(username, password)
        
        if result.get('success'):
            QMessageBox.information(self, "成功", "注册成功！请登录")
            self.tab_widget.setCurrentIndex(0)
            self.login_username.setText(username)
        else:
            QMessageBox.warning(self, "失败", result.get('error', '注册失败'))


class AddFriendDialog(QDialog):
    add_friend_signal = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加好友")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("输入好友用户名")
        layout.addWidget(self.username_input)
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加")
        self.cancel_btn = QPushButton("取消")
        self.add_btn.clicked.connect(self.on_add)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
    
    def on_add(self):
        username = self.username_input.text().strip()
        if username:
            self.add_friend_signal.emit(username)
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "请输入用户名")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 定义登录成功后的回调
    def on_login_success(username):
        # 登录成功，创建并显示主窗口
        window = ChatGUI(server_url="http://localhost:80")
        window.show()
    
    # 创建登录对话框
    login_dialog = LoginDialog()
    login_dialog.login_success_signal.connect(on_login_success)
    login_dialog.show()
    
    # 启动事件循环
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()