from pathlib import Path

from network.api_client import NetworkClient
from crypto.session import SessionManager
from crypto.message_crypto import MessageCrypto
from business.chat_facade import ChatFacade


def build_chat_facade(server_url: str = "http://127.0.0.1:8000") -> ChatFacade:
    base_dir = Path(__file__).resolve().parent
    storage_dir = str(base_dir / ".secure_store")
    db_path = str(base_dir / "chat.db")

    network = NetworkClient(server_url)
    session_mgr = SessionManager(storage_dir)
    crypto = MessageCrypto(session_mgr)
    return ChatFacade(network, crypto, session_mgr, db_path)


if __name__ == "__main__":
    facade = build_chat_facade()
    print("Chat client facade initialized.")
