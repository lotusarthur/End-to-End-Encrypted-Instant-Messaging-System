import asyncio
import json
import sqlite3
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# Make server/ and shared/ importable when running from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO_ROOT / "server"
SHARED_DIR = REPO_ROOT / "shared"

import sys

sys.path.insert(0, str(SERVER_DIR))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SHARED_DIR))


from database_manager import DatabaseManager
from message_manager import MessageManager
from message_router import MessageRouter
from websocket_message_handler import WebSocketMessageHandler
from models import DatabaseSchema, User, Message


class DummyWsManager:
    def __init__(self, online_users: Optional[set[str]] = None):
        self._online_users = online_users or set()
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def is_user_online(self, username: str) -> bool:
        return username in self._online_users

    async def send_to_user(self, username: str, message: dict[str, Any]) -> bool:
        self.sent.append((username, message))
        return True


class DummyDB:
    """Intentionally minimal DB for WebSocketMessageHandler tests."""


class TestDatabaseManager(unittest.TestCase):
    def test_user_and_friend_and_message_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test_messaging.db")
            DatabaseSchema.init_database(db_path)
            db = DatabaseManager(db_path)

            alice = User(
                username="alice",
                password_hash="alice_pwd_hash",
                identity_public_key="alice_pub",
                otp_secret="alice_otp",
                is_online=False,
                last_seen=None,
            )
            bob = User(
                username="bob",
                password_hash="bob_pwd_hash",
                identity_public_key="bob_pub",
                otp_secret="bob_otp",
                is_online=False,
                last_seen=None,
            )

            self.assertTrue(db.add_user(alice))
            self.assertTrue(db.add_user(bob))
            self.assertFalse(db.add_user(alice), "Duplicate usernames should fail")

            alice_db = db.get_user("alice")
            self.assertIsNotNone(alice_db)
            self.assertEqual(alice_db.username, "alice")
            self.assertEqual(alice_db.identity_public_key, "alice_pub")

            self.assertTrue(db.update_user_online_status("alice", True))
            alice_db2 = db.get_user("alice")
            self.assertTrue(alice_db2.is_online)
            self.assertIsNotNone(alice_db2.last_seen)

            # Friend request: alice -> bob (so bob is the "received" side)
            req_id = db.add_friend_request("alice", "bob")
            self.assertIsNotNone(req_id)
            pending_received = db.get_friend_requests("bob", request_type="received")
            self.assertEqual(len(pending_received), 1)
            self.assertEqual(pending_received[0].id, req_id)
            self.assertEqual(pending_received[0].status, "pending")

            # Accept and verify not pending anymore.
            self.assertTrue(db.update_friend_request_status(req_id, "accepted"))
            pending_received_after = db.get_friend_requests("bob", request_type="received")
            self.assertEqual(len(pending_received_after), 0)

            friends_of_bob = db.get_friends("bob")
            self.assertEqual(len(friends_of_bob), 1)
            self.assertEqual(friends_of_bob[0]["username"], "alice")
            self.assertIn("added_at", friends_of_bob[0])

            self.assertTrue(db.remove_friend("bob", "alice"))
            self.assertEqual(db.get_friends("bob"), [])

            # Message: store as "sent" so it is visible as offline message.
            msg_id = "m1"
            now = int(time.time())
            msg = Message(
                message_id=msg_id,
                sender_id="alice",
                receiver_id="bob",
                ciphertext_b64="encrypted_payload",
                nonce_b64="nonce",
                mac_tag_b64="mac",
                ad_serialized="ad",
                timestamp=now,
                ttl_seconds=3600,
                status="sent",
                signature=None,
            )
            self.assertTrue(db.add_message(msg))

            offline = db.get_offline_messages("bob")
            self.assertEqual(len(offline), 1)
            self.assertEqual(offline[0].message_id, msg_id)
            self.assertEqual(offline[0].ciphertext_b64, "encrypted_payload")

            self.assertTrue(db.update_message_status(msg_id, "delivered"))
            # Offline messages are only those with status='sent'
            self.assertEqual(db.get_offline_messages("bob"), [])

            # Verify status in DB.
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT status, delivered_at, read_at FROM messages WHERE message_id = ?", (msg_id,))
            row = cur.fetchone()
            conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "delivered")
            self.assertIsNotNone(row[1])
            self.assertIsNone(row[2])


class TestMessageManager(unittest.TestCase):
    def test_mark_delivered_and_cleanup_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test_messaging.db")
            DatabaseSchema.init_database(db_path)
            db = DatabaseManager(db_path)
            message_manager = MessageManager(db)

            # Need actual message row for mark_message_delivered/update_message_status to succeed.
            msg_id = "m_deliv"
            old_ts = int(time.time()) - 3600
            msg = Message(
                message_id=msg_id,
                sender_id="alice",
                receiver_id="bob",
                ciphertext_b64="x",
                nonce_b64="nonce",
                mac_tag_b64="mac",
                ad_serialized="ad",
                timestamp=old_ts,
                ttl_seconds=1,
                status="sent",
                signature=None,
            )
            # Add users so foreign keys pass (messages has FK to users).
            db.add_user(
                User(
                    username="alice",
                    password_hash="a",
                    identity_public_key="a_pub",
                    otp_secret=None,
                    is_online=False,
                    last_seen=None,
                )
            )
            db.add_user(
                User(
                    username="bob",
                    password_hash="b",
                    identity_public_key="b_pub",
                    otp_secret=None,
                    is_online=False,
                    last_seen=None,
                )
            )
            self.assertTrue(db.add_message(msg))

            # Simulate pending delivery list and then delivery completion.
            asyncio.run(message_manager.mark_message_sent(msg_id, "alice", "bob"))
            self.assertIn(msg_id, message_manager.pending_deliveries.get("bob", set()))
            asyncio.run(message_manager.mark_message_delivered(msg_id))
            self.assertNotIn(msg_id, message_manager.pending_deliveries.get("bob", set()))

            # Put an expired message back and test cleanup.
            msg2_id = "m_expired"
            msg2 = Message(
                message_id=msg2_id,
                sender_id="alice",
                receiver_id="bob",
                ciphertext_b64="y",
                nonce_b64="nonce",
                mac_tag_b64="mac",
                ad_serialized="ad",
                timestamp=old_ts,
                ttl_seconds=1,
                status="sent",
                signature=None,
            )
            self.assertTrue(db.add_message(msg2))
            cleaned = asyncio.run(message_manager.cleanup_expired_messages())
            self.assertGreaterEqual(cleaned, 1)

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT status FROM messages WHERE message_id = ?", (msg2_id,))
            status = cur.fetchone()[0]
            conn.close()
            self.assertEqual(status, "expired")


class TestMessageRouter(unittest.TestCase):
    def test_route_message_online_delivers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test_messaging.db")
            DatabaseSchema.init_database(db_path)
            db = DatabaseManager(db_path)
            
            alice = User(
                username="alice",
                password_hash="alice_pwd_hash",
                identity_public_key="alice_pub",
                otp_secret="alice_otp",
                is_online=False,
                last_seen=None,
            )
            bob = User(
                username="bob",
                password_hash="bob_pwd_hash",
                identity_public_key="bob_pub",
                otp_secret="bob_otp",
                is_online=False,
                last_seen=None,
            )
            self.assertTrue(db.add_user(alice))
            self.assertTrue(db.add_user(bob))
            
            req_id = db.add_friend_request("alice", "bob")
            self.assertIsNotNone(req_id)
            self.assertTrue(db.update_friend_request_status(req_id, "accepted"))

            ws = DummyWsManager(online_users={"bob"})
            router = MessageRouter(ws_manager=ws, db=db, max_retries=1)

            async def run():
                ok_inner = await router.route_message("alice", {"type": "message", "to": "bob", "message_id": "m1"})
                self.assertTrue(ok_inner)

                task_inner = router.pending_messages.get("m1")
                self.assertIsNotNone(task_inner)
                result_inner = await task_inner
                self.assertTrue(result_inner)

                self.assertEqual(len(ws.sent), 1)
                self.assertEqual(ws.sent[0][0], "bob")
                self.assertEqual(ws.sent[0][1]["message_id"], "m1")

            asyncio.run(run())

    def test_route_unknown_type_returns_false(self):
        ws = DummyWsManager(online_users={"bob"})
        db = DatabaseManager(":memory:")
        router = MessageRouter(ws_manager=ws, db=db, max_retries=1)
        ok = asyncio.run(router.route_message("alice", {"type": "unknown", "message_id": "m1"}))
        self.assertFalse(ok)


class TestWebSocketMessageHandler(unittest.TestCase):
    def test_handle_message_unknown_type_and_invalid_json(self):
        handler = WebSocketMessageHandler(ws_manager=DummyWsManager(), db=DummyDB())

        async def run():
            res1 = await handler.handle_message("alice", "{not-json}")
            self.assertFalse(res1)
            res2 = await handler.handle_message("alice", json.dumps({"type": "unknown"}))
            self.assertFalse(res2)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()