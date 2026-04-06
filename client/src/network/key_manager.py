"""Key manager for identity and prekeys."""
import os
import hashlib
import secrets
import uuid
from typing import Optional

try:
    from client.src.storage.key_storage import KeyStorage
except ImportError:
    from ...storage.key_storage import KeyStorage


class KeyManager:
    """Manages cryptographic keys for the messaging client."""
    
    def __init__(self, storage_path: str):
        """Initialize the key manager."""
        self.storage_path = storage_path
        self.storage = KeyStorage(storage_path)

    def generate_identity_keypair(self) -> None:
        """Generate and save identity keypair."""
        private_key = secrets.token_bytes(32)
        public_key = hashlib.sha256(private_key).digest()
        self.storage.save_identity_keypair(public_key, private_key)

    def get_identity_public_key(self) -> bytes:
        """Get identity public key."""
        keypair = self.storage.load_identity_keypair()
        if keypair is None:
            self.generate_identity_keypair()
            keypair = self.storage.load_identity_keypair()
        return keypair[0]

    def get_identity_private_key(self) -> bytes:
        """Get identity private key."""
        keypair = self.storage.load_identity_keypair()
        if keypair is None:
            self.generate_identity_keypair()
            keypair = self.storage.load_identity_keypair()
        return keypair[1]

    def get_prekey(self) -> Optional[bytes]:
        """Get an unused prekey."""
        prekeys_dir = os.path.join(self.storage_path, "prekeys")
        if not os.path.exists(prekeys_dir):
            return None
        for filename in os.listdir(prekeys_dir):
            if filename.endswith(".bin"):
                prekey_id = filename[:-4]
                data = self.storage.load_prekey(prekey_id)
                if data is not None:
                    os.remove(os.path.join(prekeys_dir, filename))
                    return data
        return None

    def rotate_prekeys(self) -> None:
        """Rotate prekeys - generate new ones."""
        for _ in range(10):
            prekey_id = str(uuid.uuid4())
            self.storage.save_prekey(prekey_id, secrets.token_bytes(32))
