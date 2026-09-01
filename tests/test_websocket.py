from __future__ import annotations

import asyncio
import struct

import cv2
import numpy as np
import pytest
from aiohttp import WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer

from yfphonecam.config import Settings
from yfphonecam.server.app import create_app
from yfphonecam.state import AppState


@pytest.fixture
async def web_client():
    settings = Settings()
    state = AppState(settings.capture, settings.image)
    app = create_app(settings, state, session_token="test-session-token", session_id="session-1")
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        yield client, state
    finally:
        await client.close()


async def _connect(client: TestClient):
    return await client.ws_connect("/ws?token=test-session-token")


@pytest.mark.asyncio
async def test_websocket_requires_session_token(web_client) -> None:
    client, _state = web_client
    with pytest.raises(WSServerHandshakeError) as error:
        await client.ws_connect("/ws")
    assert error.value.status == 403


@pytest.mark.asyncio
async def test_hello_and_configuration_round_trip(web_client) -> None:
    client, state = web_client
    ws = await _connect(client)
    await ws.send_json(
        {
            "type": "hello",
            "protocol": 1,
            "width": 1280,
            "height": 720,
            "fps": 30,
            "browser": "Chrome",
            "userAgent": "test-agent",
        }
    )

    acknowledgement = await ws.receive_json()
    configuration = await ws.receive_json()
    assert acknowledgement["type"] == "hello-ack"
    assert acknowledgement["protocol"] == 1
    assert configuration["type"] == "configure"
    assert configuration["width"] == 1280

    await ws.send_json(
        {
            "type": "configured",
            "requestId": configuration["requestId"],
            "ok": True,
            "actual": {"width": 640, "height": 480, "fps": 30},
        }
    )
    for _ in range(20):
        await asyncio.sleep(0.01)
        if state.snapshot()["resolution"] == [640, 480]:
            break
    assert state.snapshot()["resolution"] == [640, 480]
    await ws.close()


@pytest.mark.asyncio
async def test_invalid_message_is_rejected_without_disconnect(web_client) -> None:
    client, _state = web_client
    ws = await _connect(client)
    await ws.send_str("not json")
    response = await ws.receive_json()
    assert response["type"] == "error"
    assert not ws.closed
    await ws.close()


@pytest.mark.asyncio
async def test_binary_frame_enters_single_slot_queue(web_client) -> None:
    client, state = web_client
    ws = await _connect(client)
    ok1, encoded1 = cv2.imencode(".jpg", np.zeros((2, 3, 3), dtype=np.uint8))
    ok2, encoded2 = cv2.imencode(".jpg", np.ones((2, 3, 3), dtype=np.uint8))
    assert ok1 and ok2
    jpeg1 = encoded1.tobytes()
    jpeg2 = encoded2.tobytes()
    await ws.send_bytes(struct.pack("<IQ", 1, 100) + jpeg1)
    await ws.send_bytes(struct.pack("<IQ", 2, 200) + jpeg2)
    for _ in range(20):
        await asyncio.sleep(0.01)
        if not state.jpeg_queue.empty():
            break
    assert state.jpeg_queue.get_nowait() == jpeg2
    await ws.close()


@pytest.mark.asyncio
async def test_new_phone_replaces_old_without_reconnect_loop(web_client) -> None:
    client, _state = web_client
    first = await _connect(client)
    second = await _connect(client)
    message = await first.receive_json()
    assert message == {"type": "bye", "reason": "replaced"}
    await second.close()
