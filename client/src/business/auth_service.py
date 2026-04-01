from .errors import AuthError, ValidationError


class AuthService:
    def __init__(self, api_client, ws_client, storage, event_bus, crypto):
        self.api_client = api_client
        self.ws_client = ws_client
        self.storage = storage
        self.event_bus = event_bus
        self.crypto = crypto

    def register(self, username: str, password: str):
        """
        Agreed flow:
        user inputs password -> business passes to crypto.init(password)
        -> crypto returns hash and derived key/private key material
        -> business sends request to backend
        """
        if not username:
            raise ValidationError("username required")
        if not password:
            raise ValidationError("password required")

        init_result = self.crypto.init(password)

        password_hash = init_result.get("password_hash")
        if not password_hash:
            raise AuthError("register failed: password_hash missing from crypto.init()")

        public_key = init_result.get("public_key")
        private_key = init_result.get("private_key")

        resp = self.api_client.register(
            username=username,
            password_hash=password_hash,
            public_key=public_key,
        )

        user_id = resp.get("user_id")
        if user_id and private_key:
            self.storage.save_private_key(user_id, private_key)

        self.event_bus.emit("auth.register_success", {
            "user_id": user_id,
            "username": username,
        })
        return resp

    def login(self, username: str, password: str, otp: str):
        """
        Uses agreed flow:
        password -> crypto.init(password) -> password_hash -> backend login
        """
        if not username:
            raise ValidationError("username required")
        if not password:
            raise ValidationError("password required")
        if not otp:
            raise ValidationError("otp required")

        init_result = self.crypto.init(password)
        password_hash = init_result.get("password_hash")
        if not password_hash:
            raise AuthError("login failed: password_hash missing from crypto.init()")

        resp = self.api_client.login(
            username=username,
            password_hash=password_hash,
            otp=otp
        )

        token = resp.get("token")
        if not token:
            raise AuthError("login failed: token missing")

        self.storage.save_token(token)

        profile = {
            "user_id": resp.get("user_id"),
            "username": resp.get("username", username),
        }
        self.storage.save_user_profile(profile)
        
        private_key = init_result.get("private_key")
        if profile["user_id"] and private_key:
            self.storage.save_private_key(profile["user_id"], private_key)

        self.ws_client.connect(token)

        self.event_bus.emit("auth.login_success", {
            "token": token,
            "profile": profile,
        })
        return resp

    def logout(self):
        self.ws_client.disconnect()
        self.event_bus.emit("auth.logout", {})
