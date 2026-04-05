import asyncio
import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from typing import Any

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO_ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))

from database_manager import DatabaseManager
from message_manager import MessageManager
from models import DatabaseSchema, User, Message


class MockWebSocket:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.messages: list[dict[str, Any]] = []
        self.is_connected = True

    async def send(self, message: str):
        self.messages.append(json.loads(message))

    async def close(self):
        self.is_connected = False


class TestE2EScenarios(unittest.TestCase):
    def test_four_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test_messaging.db")
            DatabaseSchema.init_database(db_path)
            db_manager = DatabaseManager(db_path)
            message_manager = MessageManager(db_manager)

            online_users: dict[str, MockWebSocket] = {}

            async def deliver_message_to_online_user(message: Message):
                if message.to_user in online_users:
                    ws = online_users[message.to_user]
                    message_data = {
                        "type": "message",
                        "message_id": message.message_id,
                        "from": message.from_user,
                        "content": message.ciphertext,
                        "timestamp": message.timestamp,
                    }
                    await ws.send(json.dumps(message_data))

            async def run_all():
                # Scenario 1: register alice and bob
                alice = User(
                    username="alice",
                    password_hash="alice_password_hash",
                    identity_public_key="alice_public_key_123",
                    otp_secret="alice_otp_secret",
                    is_online=False,
                    last_seen=None,
                )
                bob = User(
                    username="bob",
                    password_hash="bob_password_hash",
                    identity_public_key="bob_public_key_456",
                    otp_secret="bob_otp_secret",
                    is_online=False,
                    last_seen=None,
                )
                self.assertTrue(db_manager.add_user(alice))
                self.assertTrue(db_manager.add_user(bob))
                self.assertIsNotNone(db_manager.get_user("alice"))
                self.assertIsNotNone(db_manager.get_user("bob"))

                # Scenario 2: alice -> bob (bob online)
                alice_ws = MockWebSocket("alice")
                bob_ws = MockWebSocket("bob")
                online_users["alice"] = alice_ws
                online_users["bob"] = bob_ws
                self.assertTrue(db_manager.update_user_online_status("alice", True))
                self.assertTrue(db_manager.update_user_online_status("bob", True))

                message_id_2 = str(uuid.uuid4())
                message_2 = Message(
                    message_id=message_id_2,
                    from_user="alice",
                    to_user="bob",
                    ciphertext="encrypted_online_message",
                    timestamp=int(time.time()),
                    ttl_seconds=3600,
                    status="sent",
                    signature=None,
                )
                self.assertTrue(db_manager.add_message(message_2))
                await deliver_message_to_online_user(message_2)
                self.assertGreaterEqual(len(bob_ws.messages), 1)
                self.assertEqual(bob_ws.messages[-1]["message_id"], message_id_2)
                self.assertEqual(bob_ws.messages[-1]["from"], "alice")
                self.assertEqual(bob_ws.messages[-1]["content"], "encrypted_online_message")

                # Scenario 3: alice -> bob (bob offline)
                # Switch bob to offline
                if "bob" in online_users:
                    await online_users["bob"].close()
                    del online_users["bob"]
                self.assertTrue(db_manager.update_user_online_status("bob", False))

                message_id_3 = str(uuid.uuid4())
                message_3 = Message(
                    message_id=message_id_3,
                    from_user="alice",
                    to_user="bob",
                    ciphertext="encrypted_offline_message",
                    timestamp=int(time.time()),
                    ttl_seconds=3600,
                    status="sent",
                    signature=None,
                )
                self.assertTrue(db_manager.add_message(message_3))
                await message_manager.mark_message_sent(message_id_3, "alice", "bob")

                bob_user = db_manager.get_user("bob")
                self.assertIsNotNone(bob_user)
                self.assertFalse(bob_user.is_online)

                offline_messages = db_manager.get_offline_messages("bob")
                self.assertTrue(any(m.message_id == message_id_3 for m in offline_messages))

                # Scenario 4: bob reconnects and fetches offline messages
                bob_ws2 = MockWebSocket("bob")
                online_users["bob"] = bob_ws2
                self.assertTrue(db_manager.update_user_online_status("bob", True))

                offline_messages2 = db_manager.get_offline_messages("bob")
                self.assertGreaterEqual(len(offline_messages2), 1)

                # Deliver all offline messages and mark delivered
                for m in offline_messages2:
                    await deliver_message_to_online_user(m)
                    self.assertTrue(db_manager.update_message_status(m.message_id, "delivered"))
                    await message_manager.mark_message_delivered(m.message_id)

                # After delivery, there should be no "sent" offline messages.
                self.assertEqual(db_manager.get_offline_messages("bob"), [])
                # Pending should be cleared for the delivered msg_id.
                self.assertNotIn(
                    message_id_3,
                    message_manager.pending_deliveries.get("bob", set()),
                )

            asyncio.run(run_all())


if __name__ == "__main__":
    unittest.main()