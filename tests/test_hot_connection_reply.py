import asyncio
import json
from unittest.mock import AsyncMock

import pytest
import websockets

from src.core.ws_client import WebSocketClientManager
from src.core.ws_server import NapCatWSServer


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(WebSocketClientManager, "_instance", None)
    return WebSocketClientManager()


@pytest.mark.asyncio
async def test_handler_applies_before_after_and_after_replacement(manager):
    early = await manager.add_connection("early", "early", "ws://127.0.0.1:1", enabled=False)
    first = AsyncMock()
    manager.set_message_handler(first)
    late = await manager.add_connection("late", "late", "ws://127.0.0.1:1", enabled=False)
    assert early._message_handler is first
    assert late._message_handler is first
    second = AsyncMock()
    manager.set_message_handler(second)
    assert early._message_handler is second
    assert late._message_handler is second
    await manager.remove_connection("late")
    replacement = await manager.add_connection("late", "late", "ws://127.0.0.1:1", enabled=False)
    assert replacement._message_handler is second


@pytest.mark.asyncio
async def test_hot_added_bot_action_and_napcat_receipt_round_trip(manager, monkeypatch):
    """真实临时 WS + 模拟 NapCat，覆盖之前遗漏的 Postman 回程，不连接线上 QQ。"""
    monkeypatch.setattr(NapCatWSServer, "_instance", None)
    bridge = NapCatWSServer()
    completed = asyncio.get_running_loop().create_future()
    seen_actions = []

    async def fake_napcat_send(payload):
        action = json.loads(payload)
        seen_actions.append(action)
        await bridge._handle_api_response({
            "status": "ok", "retcode": 0, "echo": action["echo"],
            "data": {"message_id": 123},
        })

    class FakeNapCat:
        send = staticmethod(fake_napcat_send)

    bridge._clients = {FakeNapCat()}

    async def global_handler(conn_id, message):
        await bridge.forward_api_call(conn_id, json.loads(message))

    # 与 main.lifespan 一致：先设置全局回调，之后 API 才热新增连接。
    manager.set_message_handler(global_handler)

    async def bot(ws):
        lifecycle = json.loads(await ws.recv())
        assert lifecycle["post_type"] == "meta_event"
        await ws.send(json.dumps({
            "action": "send_group_msg", "params": {"group_id": 2, "message": "test"},
            "echo": "original-echo",
        }))
        completed.set_result(json.loads(await ws.recv()))
        await ws.wait_closed()

    async with websockets.serve(bot, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        conn = await manager.add_connection("hot", "hot", f"ws://127.0.0.1:{port}", auto_reconnect=False)
        try:
            assert await conn.start()
            receipt = await asyncio.wait_for(completed, timeout=5)
            assert receipt == {"status": "ok", "retcode": 0, "echo": "original-echo",
                               "data": {"message_id": 123}}
            assert len(seen_actions) == 1
            assert seen_actions[0]["echo"].startswith("dp:hot:")
            assert not bridge._pending_api_calls
        finally:
            await conn.disconnect()
