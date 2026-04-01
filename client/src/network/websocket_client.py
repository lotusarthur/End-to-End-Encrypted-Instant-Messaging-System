import asyncio
import json
import websockets
from typing import Callable, Optional
try:
    from shared.constants import WS_ENDPOINT
except ImportError:
    from ...shared.constants import WS_ENDPOINT

class WebSocketClient:
    def __init__(self, server_url: str, token: str):
        self.server_url = server_url
        self.token = token
        self.websocket = None
        self.is_connected = False
        self.on_message_callback = None

    async def connect(self, on_message_callback: Callable) -> bool:
        """
        连接 WebSocket 服务器
        on_message_callback: 消息回调函数
        """
        self.on_message_callback = on_message_callback
        ws_url = self.server_url.rstrip("/") + WS_ENDPOINT + f"?token={self.token}"
        self.websocket = await websockets.connect(ws_url)
        self.is_connected = True
        asyncio.create_task(self._listen())
        return True

    async def disconnect(self) -> None:
        """断开 WebSocket 连接"""
        if self.websocket is not None:
            await self.websocket.close()
        self.websocket = None
        self.is_connected = False

    async def send_message(self, message: dict) -> bool:
        """通过 WebSocket 发送消息"""
        if not self.is_alive():
            return False
        await self.websocket.send(json.dumps(message, ensure_ascii=False))
        return True

    async def _listen(self) -> None:
        """监听 WebSocket 消息"""
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
        """重连 WebSocket"""
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
        """检查连接状态"""
        return self.is_connected and self.websocket is not None
