class AppService:
    def __init__(
        self,
        auth_service,
        chat_service,
        message_service,
        session_manager,
        event_bus,
        ws_client,
        storage,
    ):
        self.auth_service = auth_service
        self.chat_service = chat_service
        self.message_service = message_service
        self.session_manager = session_manager
        self.event_bus = event_bus
        self.ws_client = ws_client
        self.storage = storage

        self.ws_client.set_handler(self._on_ws_message)

    def _on_ws_message(self, payload: dict):
        self.message_service.handle_ws_payload(payload)

    def register(self, username: str, password: str):
        return self.auth_service.register(username, password)

    def login(self, username: str, password: str, otp: str):
        return self.auth_service.login(username, password, otp)

    def logout(self):
        return self.auth_service.logout()

    # chat部分
    def send_text_message(self, conversation_id: str, text: str, ttl: int = 30):
        return self.chat_service.send_text_message(conversation_id, text, ttl)

    def open_conversation(self, conversation_id: str):
        self.session_manager.set_active_conversation(conversation_id)
        self.event_bus.emit("conversation.opened", {"conversation_id": conversation_id})

    def list_conversations(self):
        return self.storage.list_conversations()

    def list_messages(self, conversation_id: str, limit: int = 50):
        return self.storage.get_messages(conversation_id, limit=limit)

    def on(self, event_name: str, handler):
        self.event_bus.subscribe(event_name, handler)
