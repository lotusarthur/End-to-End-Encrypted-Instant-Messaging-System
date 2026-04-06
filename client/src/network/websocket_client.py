"""WebSocket client for real-time messaging."""
import asyncio
import json
from typing import Callable, Optional

try:
    import websockets
except ImportError:
    websockets = None

try:
    from shared.constants import WS_ENDPOINT
except ImportError:
    from ...shared.constants import WS_ENDPOINT


class WebSocketClient:
    """WebSocket client for messaging server."""
    
    def __init__(self, server_url: str, token: str):
        """Initialize WebSocket client."""
        self.server_url = server_url
        self.token = token
        self.websocket = None
        self.is_connected = False
        self.on_message_callback = None

    async def connect(self, on_message_callback: Callable) -> bool:
        """Connect to WebSocket server."""
        if websockets is None:
            raise RuntimeError("websockets library not installed")
        
        self.on_message_callback = on_message_callback
        ws_url = self.server_url.rstrip("/") + WS_ENDPOINT + f"?token={self.token}"
        self.websocket = await websockets.connect(ws_url)
        self.is_connected = True
        asyncio.create_task(self._listen())
        return True

    async def disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        if self.websocket is not None:
            await self.websocket.close()
        self.websocket = None
        self.is_connected = False

    async def send_message(self, message: dict) -> bool:
        """Send a message via WebSocket."""
        if not self.is_alive():
            return False
        await self.websocket.send(json.dumps(message, ensure_ascii=False))
        return True

    async def _listen(self) -> None:
        """Listen for incoming messages."""
        try:
            async for raw in self.websocket:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if self.on_message_callback:
                    result = self.on_message_callback(message)
                    if asyncio.iscoroutine(result):
                        await result
        except Exception:
            self.is_connected = False
            await self._reconnect()

    async def _reconnect(self) -> bool:
        """Attempt to reconnect."""
        for _ in range(3):
            await asyncio.sleep(1)
            try:
                if self.on_message_callback is None:
                    return False
                return await self.connect(self.on_message_callback)
            except Exception:
                continue
        return False

    def is_alive(self) -> bool:
        """Check if connection is alive."""
        return self.is_connected and self.websocket is not None
