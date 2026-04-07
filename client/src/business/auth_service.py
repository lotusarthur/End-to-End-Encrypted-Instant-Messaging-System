from .errors import AuthError, ValidationError

from ..crypto.core import IdentityManager

class AuthService:
    def __init__(self, api_client, ws_client, storage, event_bus, crypto):
        self.api_client = api_client
        self.ws_client = ws_client
        self.storage = storage
        self.event_bus = event_bus
        self.crypto = crypto

    def register(self, username: str, password: str):
        """
        注册流程：
        1. 业务层生成 otp_secret
        2. 业务层生成身份密钥对
        3. 私钥保存到本地
        4. 公钥 + 注册信息提交给后端
        """
        if not username:
            raise ValidationError("username required")
        if not password:
            raise ValidationError("password required")

        try:
            otp_secret = IdentityManager.generate_otp_secret()
            pri_key_b64, pub_key_b64 = IdentityManager.generate_identity_keypair()
        except Exception as e:
            raise AuthError(f"register failed: identity init error: {e}")

        if not pri_key_b64 or not pub_key_b64:
            raise AuthError("register failed: identity keypair missing")

        # 注册阶段先把私钥落本地
        try:
            self.storage.save_private_key(username, pri_key_b64)
        except Exception as e:
            raise AuthError(f"register failed: save private key error: {e}")

        try:
            resp = self.api_client.register(
                username=username,
                password=password,
                otp_secret=otp_secret,
                public_key=pub_key_b64,
            )
        except Exception as e:
            raise AuthError(f"register failed: {e}")

        self.event_bus.emit("auth.register_success", {
            "user_id": resp.get("user_id"),
            "username": username,
        })
        return resp

    def login(self, username: str, password: str, otp: str):
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

        try:
            resp = self.api_client.login(
                username=username,
                password_hash=password_hash,
                otp=otp
            )
        except Exception as e:
            raise AuthError(f"login failed: {e}")

        token = resp.get("token")
        if not token:
            raise AuthError("login failed: token missing")

        self.storage.save_token(token)

        profile = {
            "user_id": resp.get("user_id"),
            "username": resp.get("username", username),
        }
        self.storage.save_user_profile(profile)

        self.ws_client.connect(token)

        self.event_bus.emit("auth.login_success", {
            "token": token,
            "profile": profile,
        })
        return resp

    def logout(self):
        self.ws_client.disconnect()
        self.event_bus.emit("auth.logout", {})