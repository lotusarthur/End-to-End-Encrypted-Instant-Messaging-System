LOGIN_REQUEST_FIELDS = ["username", "password_hash", "otp"]
LOGIN_RESPONSE_FIELDS = ["token", "user_id", "username"]

MESSAGE_ENVELOPE_FIELDS = [
    "type",
    "message_id",
    "conversation_id",
    "recipient_id",
    "encrypted_pkg",
    "ttl",
    "client_time",
]

WS_NEW_MESSAGE_FIELDS = [
    "type",
    "message_id",
    "conversation_id",
    "sender_id",
    "encrypted_pkg",
    "server_time",
]

DELIVERY_RECEIPT_FIELDS = [
    "type",
    "message_id",
    "conversation_id",
    "status",
    "server_time",
]
