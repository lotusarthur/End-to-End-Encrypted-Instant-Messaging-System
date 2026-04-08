import sys
import os
import threading
import qtawesome as qta
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

# 颜色常量
COLOR_PRIMARY = "#313e50"
COLOR_SECONDARY = "#5c6672"
COLOR_WHITE = "#ffffff"
COLOR_BLACK = "#000000"
COLOR_DANGER = "#e74c3c"
COLOR_SUCCESS = "#27ae60"
COLOR_INFO = "#3498db"
COLOR_WARNING = "#f39c12"

# 全局字体大小
FONT_SIZE = 25


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
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_WHITE};
                border-radius: 8px;
                margin: 2px;
            }}
            QWidget:hover {{
                background-color: #f5f5f5;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        self.label = QLabel(f"来自: {self.from_user}")
        self.label.setStyleSheet(f"font-size: {FONT_SIZE}px; color: {COLOR_BLACK};")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        self.accept_btn = QPushButton("接受")
        self.accept_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_SUCCESS};
                font-weight: bold;
                font-size: {FONT_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: rgba(39, 174, 96, 0.1);
            }}
        """)
        self.accept_btn.clicked.connect(lambda: self.request_accepted.emit(self.request_id))

        
        self.decline_btn = QPushButton("拒绝")
        self.decline_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_DANGER};
                font-weight: bold;
                font-size: {FONT_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: rgba(231, 76, 60, 0.1);
            }}
        """)
        self.decline_btn.clicked.connect(lambda: self.request_declined.emit(self.request_id))
        
        layout.addWidget(self.accept_btn)
        layout.addWidget(self.decline_btn)


class FriendRequestPanel(QDialog):
    """好友请求管理面板"""
    
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("好友请求管理")
        self.setMinimumWidth(500)
        self.setMinimumHeight(550)
        self.setModal(True)
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_WHITE};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: {FONT_SIZE}px;
                color: {COLOR_PRIMARY};
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QLineEdit {{
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                font-size: {FONT_SIZE}px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_INFO};
            }}
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: {FONT_SIZE}px;
                padding: 10px 16px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SECONDARY};
            }}
            QLabel {{
                font-size: {FONT_SIZE}px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 添加好友区域
        add_group = QGroupBox("添加好友")
        add_layout = QVBoxLayout(add_group)
        
        input_layout = QHBoxLayout()
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("输入好友用户名")
        self.add_input.returnPressed.connect(self.add_friend)
        
        self.add_btn = QPushButton("添加")
        self.add_btn.setFixedHeight(40)
        self.add_btn.clicked.connect(self.add_friend)
        
        input_layout.addWidget(self.add_input)
        input_layout.addWidget(self.add_btn)
        
        self.add_result = QLabel("")
        self.add_result.setStyleSheet("color: gray;")
        
        add_layout.addLayout(input_layout)
        add_layout.addWidget(self.add_result)
        layout.addWidget(add_group)
        
        # 收到的请求区域
        received_group = QGroupBox("收到的好友请求")
        received_layout = QVBoxLayout(received_group)
        
        self.received_scroll = QScrollArea()
        self.received_scroll.setWidgetResizable(True)
        self.received_scroll.setStyleSheet("border: none; background-color: transparent;")
        
        self.received_container = QWidget()
        self.received_container.setStyleSheet("background-color: transparent;")
        self.received_layout = QVBoxLayout(self.received_container)
        self.received_layout.setAlignment(Qt.AlignTop)
        self.received_layout.setSpacing(5)
        
        self.received_scroll.setWidget(self.received_container)
        received_layout.addWidget(self.received_scroll)
        layout.addWidget(received_group)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(45)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def load_data(self):
        self.load_received_requests()
    
    def load_received_requests(self):
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
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def add_friend(self):
        username = self.add_input.text().strip()
        if not username:
            self.add_result.setText("请输入用户名")
            self.add_result.setStyleSheet("color: red;")
            return
        
        if username == self.client.current_user:
            self.add_result.setText("不能添加自己为好友")
            self.add_result.setStyleSheet("color: red;")
            return
        
        success = self.client.send_friend_request(username)
        if success:
            self.add_result.setText(f"好友请求已发送给 {username}")
            self.add_result.setStyleSheet("color: green;")
            self.add_input.clear()
        else:
            self.add_result.setText(f"发送失败，用户 {username} 可能不存在")
            self.add_result.setStyleSheet("color: red;")
    
    def accept_request(self, request_id):
        success = self.client.accept_friend_request(request_id)
        if success:
            self.load_received_requests()
            if self.parent():
                self.parent().refresh_friends()
        else:
            QMessageBox.warning(self, "失败", "接受好友请求失败")
    
    def decline_request(self, request_id):
        success = self.client.decline_friend_request(request_id)
        if success:
            self.load_received_requests()
        else:
            QMessageBox.warning(self, "失败", "拒绝好友请求失败")


class ChatGUI(QMainWindow):
    """端到端加密聊天图形界面"""
    
    def __init__(self, client: ClientFacade = None):
        super().__init__()
        
        self.client = client if client else ClientFacade()
        self.current_user = self.client.current_user
        self.current_conversation = None
        
        self.setup_ui()
        
        self.polling_running = False
        self.polling_thread = None
        
        if self.current_user:
            self.user_label.setText(self.current_user)
            self.refresh_all()
            self.start_polling()
            self.check_pending_requests()

    def setup_ui(self):
        self.setWindowTitle("Secure Chat")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 700)
        
        # 设置全局字体
        global_font = QFont("Microsoft YaHei", 12)
        QApplication.setFont(global_font)
        
        # 设置全局样式
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_WHITE};
            }}
            QListWidget {{
                border: none;
                outline: none;
                background-color: transparent;
                font-family: "HYQiHei";
            }}
            QListWidget::item {{
                padding: 15px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                font-size: {FONT_SIZE}px;
                color: {COLOR_WHITE};
            }}
            QListWidget::item:selected {{
                background-color: rgba(255,255,255,0.2);
            }}
            QListWidget::item:hover {{
                background-color: rgba(255,255,255,0.1);
            }}
            QTextEdit {{
                border: none;
                background-color: #f8f9fa;
                border-radius: 12px;
                padding: 15px;
                font-size: {FONT_SIZE}px;
                font-family: "HYQiHei";
            }}
            QPushButton {{
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: {FONT_SIZE}px;
                font-family: "HYQiHei";
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QLabel {{
                font-size: {FONT_SIZE}px;
                font-family: "HYQiHei";
            }}
            QSpinBox {{
                font-size: {FONT_SIZE - 2}px;
                font-family: "HYQiHei";
            }}
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ========== 左侧面板 ==========
        left_panel = QWidget()
        left_panel.setFixedWidth(320)
        left_panel.setStyleSheet(f"background-color: {COLOR_PRIMARY};")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 30, 20, 20)
        left_layout.setSpacing(20)
        
        self.user_label = QLabel(self.current_user if self.current_user else "未登录")
        self.user_label.setStyleSheet(f"color: {COLOR_WHITE}; font-size: {FONT_SIZE + 4}px; font-weight: bold;")
        
        user_info_layout = QVBoxLayout()
        user_info_layout.addWidget(self.user_label, 0, Qt.AlignHCenter)
        left_layout.addLayout(user_info_layout)
        
        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: rgba(255,255,255,0.2); max-height: 1px; border: none;")
        left_layout.addWidget(line)
        
        # 好友列表标题栏
        friends_header = QWidget()
        friends_header_layout = QHBoxLayout(friends_header)
        friends_header_layout.setContentsMargins(0, 0, 0, 0)
        
        friends_label = QLabel("好友列表")
        friends_label.setStyleSheet(f"color: {COLOR_WHITE}; font-size: {FONT_SIZE}px; font-weight: bold;")
        friends_header_layout.addWidget(friends_label)
        friends_header_layout.addStretch()
        
        # 刷新按钮
        self.btn_refresh = QPushButton()
        refresh_icon = qta.icon('fa5s.sync-alt', color='white')
        self.btn_refresh.setIcon(refresh_icon)
        self.btn_refresh.setIconSize(QSize(24, 24))
        self.btn_refresh.setToolTip("刷新")
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.2);
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh_all)
        friends_header_layout.addWidget(self.btn_refresh)
        
        # 添加好友按钮
        self.add_friend_btn = QPushButton()
        add_icon = qta.icon('fa5s.plus-circle', color='white')
        self.add_friend_btn.setIcon(add_icon)
        self.add_friend_btn.setIconSize(QSize(24, 24))
        self.add_friend_btn.setToolTip("添加好友")
        self.add_friend_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.2);
            }}
        """)
        self.add_friend_btn.clicked.connect(self.open_friend_request_panel)
        friends_header_layout.addWidget(self.add_friend_btn)
        
        left_layout.addWidget(friends_header)
        
        # 好友列表
        self.friends_list = QListWidget()
        self.friends_list.setStyleSheet("""
            QListWidget {
                border: none;
                outline: none;
                background-color: transparent;
            }
            QListWidget::item {
                font-size: 14px;
                padding: 12px;
                border-bottom: none;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: rgba(255,255,255,0.2);
                border-radius: 8px;
            }
            QListWidget::item:hover {
                background-color: rgba(255,255,255,0.1);
                border-radius: 8px;
            }
            /* 现代简约滚动条 */
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255,255,255,0.3);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255,255,255,0.5);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.friends_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.friends_list.itemClicked.connect(self.on_friend_selected)

        left_layout.addWidget(self.friends_list, 1)
        
        # 底部按钮区域
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setSpacing(12)
        
        self.btn_otp = QPushButton("生成OTP")
        self.btn_otp.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_WHITE};
                padding: 12px;
                font-size: {FONT_SIZE}px;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #6c7a8a;
            }}
        """)
        self.btn_otp.clicked.connect(self.show_otp_generator)
        bottom_layout.addWidget(self.btn_otp)
        
        self.btn_upload_key = QPushButton("上传公钥")
        self.btn_upload_key.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_WHITE};
                padding: 12px;
                font-size: {FONT_SIZE}px;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #6c7a8a;
            }}
        """)
        self.btn_upload_key.clicked.connect(self.upload_public_key)
        bottom_layout.addWidget(self.btn_upload_key)
        
        self.btn_get_key = QPushButton("获取公钥")
        self.btn_get_key.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_WHITE};
                padding: 12px;
                font-size: {FONT_SIZE}px;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #6c7a8a;
            }}
        """)
        self.btn_get_key.clicked.connect(self.get_public_key)
        bottom_layout.addWidget(self.btn_get_key)
        
        self.btn_logout = QPushButton("登出")
        self.btn_logout.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_WHITE};
                padding: 12px;
                font-size: {FONT_SIZE}px;
                border-radius: 10px;
                border: 1px solid {COLOR_SECONDARY};
            }}
            QPushButton:hover {{
                background-color: {COLOR_DANGER};
                border: 1px solid {COLOR_DANGER};
            }}
        """)
        self.btn_logout.clicked.connect(self.do_logout)
        bottom_layout.addWidget(self.btn_logout)
        
        left_layout.addStretch()
        left_layout.addWidget(bottom_widget)
        
        # 红点提示标签
        self.notification_label = None
        
        # ========== 右侧面板 ==========
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background-color: {COLOR_WHITE};")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # 聊天头部
        chat_header = QWidget()
        chat_header.setFixedHeight(80)
        chat_header.setStyleSheet(f"background-color: {COLOR_WHITE}; border-bottom: 1px solid #e0e0e0;")
        chat_layout = QHBoxLayout(chat_header)
        chat_layout.setContentsMargins(30, 0, 30, 0)
        
        self.chat_title = QLabel("请选择好友开始聊天")
        self.chat_title.setStyleSheet(f"font-size: {FONT_SIZE + 4}px; font-weight: bold; color: {COLOR_BLACK};")
        chat_layout.addWidget(self.chat_title)
        chat_layout.addStretch()
        
        right_layout.addWidget(chat_header)
        
        # 消息显示区域
        self.messages_text = QTextEdit()
        self.messages_text.setReadOnly(True)
        self.messages_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #f8f9fa;
                border: none;
                padding: 25px;
                font-family: "HYQiHei";
                font-size: {FONT_SIZE}px;
            }}
        """)
        right_layout.addWidget(self.messages_text, 1)
        
        # 消息输入区域
        input_container = QWidget()
        input_container.setStyleSheet("background-color: white;")
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(30, 20, 30, 20)
        input_layout.setSpacing(15)
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(120)
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                padding: 15px;
                font-size: {FONT_SIZE}px;
                font-family: "HYQiHei";
            }}
            QTextEdit:focus {{
                border: 1px solid {COLOR_INFO};
            }}
        """)
        input_layout.addWidget(self.message_input)
        
        # 底部工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(15)
        
        ttl_label = QLabel("消息自毁时间:")
        ttl_label.setStyleSheet(f"font-size: {FONT_SIZE - 2}px; color: #666;")
        toolbar_layout.addWidget(ttl_label)
        
        self.ttl_spin = QSpinBox()
        self.ttl_spin.setRange(5, 3600)
        self.ttl_spin.setValue(30)
        self.ttl_spin.setSuffix(" 秒")
        self.ttl_spin.setFixedWidth(100)
        self.ttl_spin.setFixedHeight(36)
        self.ttl_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 6px;
                font-size: {FONT_SIZE - 2}px;
            }}
        """)
        toolbar_layout.addWidget(self.ttl_spin)
        
        toolbar_layout.addStretch()
        
        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(100, 42)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
                font-weight: bold;
                font-size: {FONT_SIZE}px;
                border-radius: 21px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SECONDARY};
            }}
        """)
        self.send_btn.clicked.connect(self.send_message)
        toolbar_layout.addWidget(self.send_btn)
        
        input_layout.addWidget(toolbar)
        right_layout.addWidget(input_container)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

        self.center_window()

    def center_window(self):
        """将窗口居中显示"""
        screen = QApplication.primaryScreen().geometry()
        window = self.frameGeometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)
    
    def show_notification(self, show=True):
        if show:
            if not self.notification_label:
                self.notification_label = QLabel(self.add_friend_btn)
                self.notification_label.setStyleSheet(f"""
                    background-color: {COLOR_DANGER};
                    border-radius: 6px;
                    min-width: 12px;
                    max-width: 12px;
                    min-height: 12px;
                    max-height: 12px;
                """)
                self.notification_label.move(22, 5)
                self.notification_label.resize(12, 12)
                self.notification_label.raise_()
                self.notification_label.show()
        else:
            if self.notification_label:
                self.notification_label.hide()
                self.notification_label.deleteLater()
                self.notification_label = None
    
    def open_friend_request_panel(self):
        panel = FriendRequestPanel(self.client, self)
        panel.exec_()
        self.refresh_friends()
        self.check_pending_requests()
    
    def check_pending_requests(self):
        requests = self.client.get_friend_requests()
        has_pending = len(requests) > 0
        self.show_notification(has_pending)
    
    def do_logout(self):
        self.client.current_user = None
        self.current_user = None
        self.user_label.setText("未登录")
        self.friends_list.clear()
        self.messages_text.clear()
        self.chat_title.setText("请选择好友开始聊天")
        self.stop_polling()
        self.hide()
        
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, LoginDialog):
                widget.show()
                break
    
    def send_message(self):
        if not self.current_conversation:
            QMessageBox.warning(self, "提示", "请先选择一个好友")
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
        time_str = datetime.now().strftime("%H:%M")
        
        if is_from_me:
            self.messages_text.append(f"[{time_str}] 我: {text}")
        else:
            self.messages_text.append(f"[{time_str}] {sender}: {text}")
        
        scrollbar = self.messages_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def refresh_all(self):
        self.refresh_friends()
        self.check_pending_requests()
    
    def refresh_friends(self):
        friends = self.client.refresh_friends_list()
        
        self.friends_list.clear()
        
        if not friends:
            self.friends_list.addItem("暂无好友")
            return
        
        for friend in friends:
            if isinstance(friend, dict):
                name = friend.get('username', 'Unknown')
                status = '● 在线' if friend.get('is_online', False) else '○ 离线'
                display_text = f"{name}\n{status}"
            else:
                display_text = str(friend)
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, name if isinstance(friend, dict) else str(friend))
            self.friends_list.addItem(item)
    
    def on_friend_selected(self, item: QListWidgetItem):
        friend_name = item.data(Qt.UserRole)
        if friend_name and friend_name != "暂无好友":
            self.current_conversation = friend_name
            self.chat_title.setText(f"{friend_name}")
            self.messages_text.clear()
            self.load_offline_messages(friend_name)
    
    def load_offline_messages(self, friend_name: str):
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
                if self.current_user:
                    self.refresh_friends()
                    self.check_pending_requests()
                time.sleep(3)
            except:
                pass
    
    def show_otp_generator(self):
        otp_secret, ok = QInputDialog.getText(self, "生成OTP验证码", "请输入OTP密钥:")
        if ok and otp_secret:
            try:
                from main2 import IdentityManager
                otp_code = IdentityManager.generate_otp_code(otp_secret)
                QMessageBox.information(self, "OTP验证码", f"当前验证码: {otp_code}\n此验证码将在30秒后失效")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"生成失败: {str(e)}")
    
    def upload_public_key(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("上传公钥")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(200)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        label = QLabel("请输入您的公钥:")
        label.setStyleSheet(f"font-size: {FONT_SIZE}px; font-weight: bold;")
        layout.addWidget(label)
        
        text_input = QTextEdit()
        text_input.setPlaceholderText("公钥内容...")
        text_input.setMinimumHeight(100)
        text_input.setStyleSheet(f"""
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px;
            font-size: {FONT_SIZE - 2}px;
        """)
        layout.addWidget(text_input)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_WHITE};
                padding: 10px 20px;
                border-radius: 8px;
                font-size: {FONT_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: #6c7a8a;
            }}
        """)
        cancel_btn.clicked.connect(dialog.reject)
        
        confirm_btn = QPushButton("上传")
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
                padding: 10px 20px;
                border-radius: 8px;
                font-size: {FONT_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SECONDARY};
            }}
        """)
        
        def on_confirm():
            public_key = text_input.toPlainText().strip()
            if public_key:
                success = self.client.upload_public_key(public_key.encode())
                if success:
                    QMessageBox.information(dialog, "成功", "公钥上传成功")
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "失败", "公钥上传失败")
            else:
                QMessageBox.warning(dialog, "错误", "公钥不能为空")
        
        confirm_btn.clicked.connect(on_confirm)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec_()
    
    def get_public_key(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("获取公钥")
        dialog.setMinimumWidth(450)
        dialog.setMinimumHeight(180)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        label = QLabel("请输入用户名:")
        label.setStyleSheet(f"font-size: {FONT_SIZE}px; font-weight: bold;")
        layout.addWidget(label)
        
        username_input = QLineEdit()
        username_input.setPlaceholderText("用户名")
        username_input.setMinimumHeight(40)
        username_input.setStyleSheet(f"""
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px;
            font-size: {FONT_SIZE}px;
        """)
        layout.addWidget(username_input)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_WHITE};
                padding: 10px 20px;
                border-radius: 8px;
                font-size: {FONT_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: #6c7a8a;
            }}
        """)
        cancel_btn.clicked.connect(dialog.reject)
        
        confirm_btn = QPushButton("获取")
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
                padding: 10px 20px;
                border-radius: 8px;
                font-size: {FONT_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SECONDARY};
            }}
        """)
        
        def on_confirm():
            username = username_input.text().strip()
            if username:
                public_key = self.client.get_user_public_key(username)
                if public_key:
                    result_dialog = QDialog(dialog)
                    result_dialog.setWindowTitle("公钥信息")
                    result_dialog.setMinimumWidth(500)
                    result_dialog.setMinimumHeight(200)
                    result_layout = QVBoxLayout(result_dialog)
                    result_layout.setContentsMargins(25, 25, 25, 25)
                    
                    result_label = QLabel(f"{username} 的公钥:")
                    result_label.setStyleSheet(f"font-size: {FONT_SIZE}px; font-weight: bold; margin-bottom: 10px;")
                    result_layout.addWidget(result_label)
                    
                    key_text = QTextEdit()
                    key_text.setText(public_key)
                    key_text.setReadOnly(True)
                    key_text.setStyleSheet(f"""
                        border: 1px solid #e0e0e0;
                        border-radius: 8px;
                        padding: 10px;
                        font-size: {FONT_SIZE - 2}px;
                        background-color: #f8f9fa;
                    """)
                    result_layout.addWidget(key_text)
                    
                    close_btn = QPushButton("关闭")
                    close_btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {COLOR_PRIMARY};
                            color: {COLOR_WHITE};
                            padding: 10px 20px;
                            border-radius: 8px;
                            font-size: {FONT_SIZE}px;
                        }}
                        QPushButton:hover {{
                            background-color: {COLOR_SECONDARY};
                        }}
                    """)
                    close_btn.clicked.connect(result_dialog.accept)
                    result_layout.addWidget(close_btn, 0, Qt.AlignCenter)
                    
                    result_dialog.exec_()
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "失败", f"获取用户 {username} 的公钥失败")
            else:
                QMessageBox.warning(dialog, "错误", "用户名不能为空")
        
        confirm_btn.clicked.connect(on_confirm)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec_()


class LoginDialog(QDialog):
    """登录对话框"""
    
    login_success_signal = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Secure Chat")
        self.setMinimumWidth(500)
        self.setMinimumHeight(580)
        self.setModal(False)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_WHITE};
            }}
            QLineEdit {{
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 14px;
                font-size: {FONT_SIZE}px;
                font-family: "HYQiHei";
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_INFO};
            }}
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
                border: none;
                border-radius: 10px;
                font-weight: bold;
                padding: 14px;
                font-size: {FONT_SIZE}px;
                font-family: "HYQiHei";
            }}
            QPushButton:hover {{
                background-color: {COLOR_SECONDARY};
            }}
            QTabWidget::pane {{
                border: none;
                background-color: {COLOR_WHITE};
            }}
            QTabWidget::tab-bar {{
                alignment: center;
            }}
            QTabBar::tab {{
                background-color: #f0f0f0;
                padding: 12px 40px;
                font-size: {FONT_SIZE}px;
                font-weight: bold;
                font-family: "HYQiHei";
            }}
            QTabBar::tab:selected {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
            }}
            QLabel {{
                font-size: {FONT_SIZE}px;
                font-family: "HYQiHei";
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(25)
        layout.setContentsMargins(35, 35, 35, 35)
        
        title_label = QLabel("Secure Chat")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {COLOR_PRIMARY};")
        layout.addWidget(title_label)
        
        subtitle_label = QLabel("端到端加密即时通讯")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet(f"font-size: {FONT_SIZE - 2}px; color: #888; margin-bottom: 10px;")
        layout.addWidget(subtitle_label)
        
        self.tab_widget = QTabWidget()
        
        # 登录页
        login_widget = QWidget()
        login_layout = QFormLayout(login_widget)
        login_layout.setSpacing(18)
        login_layout.setContentsMargins(25, 25, 25, 25)
        
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("请输入用户名")
        self.login_username.setMinimumHeight(45)
        
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setPlaceholderText("请输入密码")
        self.login_password.setMinimumHeight(45)
        
        login_layout.addRow("用户名:", self.login_username)
        login_layout.addRow("密码:", self.login_password)
        
        # OTP 密钥输入区域
        otp_key_layout = QHBoxLayout()
        self.otp_key_input = QLineEdit()
        self.otp_key_input.setPlaceholderText("输入OTP密钥")
        
        self.generate_otp_btn = QPushButton("生成")
        self.generate_otp_btn.setFixedSize(80, 45)
        self.generate_otp_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_WHITE};
                font-weight: bold;
                border-radius: 8px;
                padding: 0px;
                font-size: {FONT_SIZE - 2}px;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
        """)
        self.generate_otp_btn.clicked.connect(self.generate_otp_code)
        
        otp_key_layout.addWidget(self.otp_key_input)
        otp_key_layout.addWidget(self.generate_otp_btn)
        login_layout.addRow("OTP密钥:", otp_key_layout)
        
        # 生成的验证码显示
        self.generated_otp_label = QLabel("")
        self.generated_otp_label.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: {FONT_SIZE - 2}px; font-weight: bold;")
        
        # OTP验证码输入
        self.login_otp = QLineEdit()
        self.login_otp.setPlaceholderText("请输入6位验证码")
        self.login_otp.setMinimumHeight(45)
        login_layout.addRow("验证码:", self.login_otp)
        
        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedHeight(50)
        self.login_btn.clicked.connect(self.on_login)
        login_layout.addRow(self.login_btn)
        
        # 注册页
        register_widget = QWidget()
        register_layout = QFormLayout(register_widget)
        register_layout.setSpacing(18)
        register_layout.setContentsMargins(25, 25, 25, 25)

        self.register_username = QLineEdit()
        self.register_username.setPlaceholderText("请输入用户名")
        self.register_username.setMinimumHeight(45)

        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.Password)
        self.register_password.setPlaceholderText("请输入密码")
        self.register_password.setMinimumHeight(45)

        self.register_confirm_password = QLineEdit()
        self.register_confirm_password.setEchoMode(QLineEdit.Password)
        self.register_confirm_password.setPlaceholderText("请再次输入密码")
        self.register_confirm_password.setMinimumHeight(45)

        register_layout.addRow("用户名:", self.register_username)
        register_layout.addRow("密码:", self.register_password)
        register_layout.addRow("确认密码:", self.register_confirm_password)  # 添加这一行

        password_hint = QLabel("密码长度至少为6位")
        password_hint.setStyleSheet(f"color: #888; font-size: {FONT_SIZE - 4}px;")
        register_layout.addRow("", password_hint)

        self.register_btn = QPushButton("注册")
        self.register_btn.setFixedHeight(50)
        self.register_btn.clicked.connect(self.on_register)
        register_layout.addRow(self.register_btn)

        register_hint = QLabel("注册成功后会生成OTP密钥，请妥善保存")
        register_hint.setStyleSheet(f"color: #888; font-size: {FONT_SIZE - 4}px;")
        register_hint.setWordWrap(True)
        register_layout.addRow("", register_hint)

        self.tab_widget.addTab(login_widget, "登录")
        self.tab_widget.addTab(register_widget, "注册")
        layout.addWidget(self.tab_widget)
        
    def generate_otp_code(self):
        otp_secret = self.otp_key_input.text().strip()
        
        if not otp_secret:
            QMessageBox.warning(self, "错误", "请输入OTP密钥")
            return
        
        try:
            from main2 import IdentityManager
            otp_code = IdentityManager.generate_otp_code(otp_secret)
            self.generated_otp_label.setText(otp_code)
            self.login_otp.setText(otp_code)
            QMessageBox.information(self, "成功", f"验证码已生成: {otp_code}\n请在30秒内使用")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"生成验证码失败: {str(e)}")
            self.generated_otp_label.setText("生成失败")

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
    
    def on_register(self):
        username = self.register_username.text().strip()
        password = self.register_password.text().strip()
        confirm_password = self.register_confirm_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "错误", "请输入用户名和密码")
            return
        
        if len(username) < 4:
            QMessageBox.warning(self, "错误", "用户名长度至少为4个字符")
            return
    
        if len(password) < 6:
            QMessageBox.warning(self, "错误", "密码长度至少为6位")
            return

        if password != confirm_password:
            QMessageBox.warning(self, "错误", "两次输入的密码不一致")
            return
        
        
        client = ClientFacade()
        success, otp_secret = client.register_user(username, password)
        
        if success:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("注册成功")
            msg_box.setText(f"用户 {username} 注册成功！")
            msg_box.setInformativeText(
                f"OTP密钥: {otp_secret}\n\n"
                "请保存此密钥\n"
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
    
    global_font = QFont("Microsoft YaHei", 10)
    app.setFont(global_font)
    
    main_window_ref = [None]
    
    def on_login_success(username, password, otp):
        client = ClientFacade(server_url="http://localhost:80")
        if client.login_user(username, password, otp):

            # 先创建并显示主窗口
            main_window_ref[0] = ChatGUI(client)
            main_window_ref[0].show()
            
            # 关闭登录对话框
            for widget in app.topLevelWidgets():
                if isinstance(widget, LoginDialog):
                    widget.close()
            
            # 在后台线程中加载数据
            def load_data():
                main_window_ref[0].refresh_all()
                main_window_ref[0].start_polling()
                main_window_ref[0].check_pending_requests()
            
            threading.Thread(target=load_data, daemon=True).start()
        else:
            QMessageBox.warning(None, "登录失败", "用户名、密码或OTP验证码错误")
        

    login_dialog = LoginDialog()
    login_dialog.login_success_signal.connect(on_login_success)
    login_dialog.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()