# 消息类型常量
MSG_TYPE_TEXT = "text"
MSG_TYPE_DELIVERY_RECEIPT = "delivery_receipt"
MSG_TYPE_KEY_EXCHANGE = "key_exchange"

# 好友请求状态常量
FRIEND_REQUEST_PENDING = "pending"
FRIEND_REQUEST_ACCEPTED = "accepted"
FRIEND_REQUEST_DECLINED = "declined"
FRIEND_REQUEST_CANCELLED = "cancelled"

# TTL 时间常量
DEFAULT_TTL = 86400  # 默认消息保留一天（非自毁）
MAX_TTL = 604800     # 最大 TTL 一周

# API 端点常量
API_BASE_PATH = "/api/v1"
WS_ENDPOINT = "/api/v1/ws"

# 服务器配置
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8765
SERVER_WS_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"
SERVER_API_URL = f"http://{SERVER_HOST}:{SERVER_PORT + 1}"  # 给api_client用

# 加密配置
AES_KEY_SIZE = 32  # AES-256
NONCE_SIZE = 12    # AES-GCM标准nonce长度
SIGNATURE_ALG = "Ed25519"  # 身份签名算法

# WebSocket消息类型（协议规范）
MSG_TYPE_AUTH = "auth"
MSG_TYPE_MESSAGE = "message"
MSG_TYPE_FETCH_OFFLINE = "fetch_offline"
MSG_TYPE_ACK = "ack"
MSG_TYPE_FRIEND_REQUEST = "friend_request"
MSG_TYPE_DELIVERY_ACK = "delivery_ack"
MSG_TYPE_KEY_EXCHANGE = "key_exchange"

# 消息状态
STATUS_SENT = "sent"
STATUS_DELIVERED = "delivered"
STATUS_READ = "read"

# 自毁消息TTL选项
DEFAULT_TTL_OPTIONS = [0, 30, 60, 300, 3600]  # 0=永久, 30s, 1min, 5min, 1h

# 防重放窗口（秒）
REPLAY_WINDOW = 300  # 5分钟内的消息才有效
