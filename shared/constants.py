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