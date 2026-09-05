from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import secrets
import struct
from typing import Any

from aiohttp import WSMsgType, web

from ..config import CaptureSettings
from ..decode import jpeg_dimensions
from ..version import PROTOCOL_VERSION
from .context import CONTEXT_KEY, ServerContext

log = logging.getLogger(__name__)

_FRAME_HEADER = struct.Struct("<IQ")
_PING_INTERVAL_S = 5.0
_MAX_MESSAGE_SIZE = 8 * 1024 * 1024
_MAX_CAMERAS = 16


async def _send_json(ws: web.WebSocketResponse, msg_type: str, **payload: Any) -> None:
    await ws.send_str(json.dumps({"type": msg_type, **payload}, separators=(",", ":")))


async def _ping_loop(ws: web.WebSocketResponse) -> None:
    try:
        while not ws.closed:
            await asyncio.sleep(_PING_INTERVAL_S)
            if not ws.closed:
                await _send_json(ws, "ping")
    except (asyncio.CancelledError, ConnectionResetError):
        pass


def _validated_int(value: Any, minimum: int, maximum: int, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _validated_float(value: Any, minimum: float, maximum: float, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _validated_range(value: Any, minimum: float, maximum: float) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key in ("min", "max"):
        if key in value:
            result[key] = _validated_float(value[key], minimum, maximum, key)
    if result.get("min", minimum) > result.get("max", maximum):
        raise ValueError("capability minimum cannot exceed maximum")
    return result


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    context = request.app[CONTEXT_KEY]
    expected_token = context.session_token
    provided_token = request.query.get("token", "") or request.cookies.get("yfphonecam_session", "")
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        raise web.HTTPForbidden(text="Invalid YFPhoneCam session token")

    ws = web.WebSocketResponse(max_msg_size=_MAX_MESSAGE_SIZE, autoping=True)
    await ws.prepare(request)
    state = context.state

    previous_ws = context.current_ws
    if previous_ws is not None and not previous_ws.closed:
        with contextlib.suppress(Exception):
            await _send_json(previous_ws, "bye", reason="replaced")
            await previous_ws.close(code=1000, message=b"replaced")
    context.current_ws = ws

    ping_task = asyncio.create_task(_ping_loop(ws))
    log.info("Phone WebSocket connected")
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await _handle_text(msg.data, ws, context)
            elif msg.type == WSMsgType.BINARY:
                _handle_binary(msg.data, state)
            elif msg.type == WSMsgType.ERROR:
                log.warning("Phone WebSocket error: %s", ws.exception())
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        ping_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ping_task
        if context.current_ws is ws:
            context.current_ws = None
            state.mark_phone_disconnected()
        log.info("Phone WebSocket disconnected")
    return ws


async def _handle_text(raw: str, ws: web.WebSocketResponse, context: ServerContext) -> None:
    state = context.state
    try:
        message = json.loads(raw)
        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Ignoring invalid phone message: %s", exc)
        await _send_json(ws, "error", code="invalid-message", message=str(exc))
        return

    msg_type = message.get("type")
    try:
        if msg_type == "hello":
            protocol = _validated_int(message.get("protocol"), 1, PROTOCOL_VERSION, "protocol")
            width = _validated_int(message.get("width"), 160, 3840, "width")
            height = _validated_int(message.get("height"), 120, 2160, "height")
            fps = _validated_float(message.get("fps"), 1, 120, "fps")
            browser = {
                "name": str(message.get("browser", "Chrome"))[:64],
                "user_agent": str(message.get("userAgent", ""))[:512],
            }
            state.mark_phone_connected(width, height, fps, protocol, browser)
            await _send_json(
                ws,
                "hello-ack",
                protocol=PROTOCOL_VERSION,
                sessionId=context.session_id,
                status="ok",
            )
            await send_phone_configuration(context, state.capture_settings)

        elif msg_type == "capabilities":
            raw_cameras = message.get("cameras", [])
            if not isinstance(raw_cameras, list):
                raise ValueError("cameras must be a list")
            cameras: list[dict[str, str]] = []
            for item in raw_cameras[:_MAX_CAMERAS]:
                if not isinstance(item, dict):
                    continue
                device_id = str(item.get("id", ""))[:512]
                if not device_id:
                    continue
                cameras.append(
                    {
                        "id": device_id,
                        "label": str(item.get("label", "Camera"))[:128],
                        "facing": str(item.get("facing", "unknown"))[:32],
                    }
                )
            raw_capture = message.get("capture", {})
            if not isinstance(raw_capture, dict):
                raise ValueError("capture capabilities must be an object")
            capture_capabilities = {
                "width": _validated_range(raw_capture.get("width"), 160, 7680),
                "height": _validated_range(raw_capture.get("height"), 120, 4320),
                "frameRate": _validated_range(raw_capture.get("frameRate"), 1, 240),
            }
            state.set_phone_capabilities(cameras, capture_capabilities)

        elif msg_type == "configured":
            request_id = str(message.get("requestId", ""))[:64]
            if not request_id or request_id != context.pending_config_request:
                raise ValueError("configured response has an unknown requestId")
            context.pending_config_request = None
            if message.get("ok") and isinstance(message.get("actual"), dict):
                actual = message["actual"]
                state.mark_phone_connected(
                    _validated_int(actual.get("width"), 160, 3840, "width"),
                    _validated_int(actual.get("height"), 120, 2160, "height"),
                    _validated_float(actual.get("fps"), 1, 120, "fps"),
                    PROTOCOL_VERSION,
                )
            elif not message.get("ok"):
                log.warning("Phone rejected configuration: %s", message.get("error", "unknown"))

        elif msg_type == "stats":
            avg_encode_ms = message.get("avgEncodeMs")
            state.update_client_stats(
                captured=_validated_int(
                    message.get("capturedFrames", 0), 0, 2**31 - 1, "capturedFrames"
                ),
                sent=_validated_int(message.get("sentFrames", 0), 0, 2**31 - 1, "sentFrames"),
                dropped=_validated_int(
                    message.get("droppedFrames", 0), 0, 2**31 - 1, "droppedFrames"
                ),
                dropped_busy=_validated_int(
                    message.get("droppedBusyFrames", 0), 0, 2**31 - 1, "droppedBusyFrames"
                ),
                dropped_backpressure=_validated_int(
                    message.get("droppedBackpressureFrames", 0),
                    0,
                    2**31 - 1,
                    "droppedBackpressureFrames",
                ),
                avg_encode_ms=_validated_float(avg_encode_ms, 0, 10_000, "avgEncodeMs")
                if isinstance(avg_encode_ms, (int, float))
                else None,
                buffered_amount=_validated_int(
                    message.get("bufferedAmount", 0), 0, 2**31 - 1, "bufferedAmount"
                ),
                capture_mode=str(message.get("captureMode", ""))[:32] or None,
            )
        elif msg_type == "pong":
            return
        else:
            log.debug("Ignoring unknown phone message type: %s", msg_type)
    except ValueError as exc:
        log.warning("Rejected %s message: %s", msg_type, exc)
        await _send_json(ws, "error", code="invalid-fields", message=str(exc))


def _handle_binary(data: bytes, state: Any) -> None:
    if len(data) <= _FRAME_HEADER.size or len(data) > _MAX_MESSAGE_SIZE:
        return
    _sequence, _timestamp_ms = _FRAME_HEADER.unpack_from(data, 0)
    jpeg = data[_FRAME_HEADER.size :]
    if len(jpeg) < 4 or jpeg[:2] != b"\xff\xd8" or jpeg[-2:] != b"\xff\xd9":
        return
    dimensions = jpeg_dimensions(jpeg)
    if dimensions is None or dimensions[0] > 3840 or dimensions[1] > 2160:
        return
    state.submit_jpeg(jpeg)


async def send_phone_configuration(
    target: web.Application | ServerContext, capture: CaptureSettings
) -> bool:
    context = target[CONTEXT_KEY] if isinstance(target, web.Application) else target
    ws = context.current_ws
    if ws is None or ws.closed:
        return False
    request_id = secrets.token_hex(8)
    context.pending_config_request = request_id
    await _send_json(
        ws,
        "configure",
        requestId=request_id,
        deviceId=capture.camera_id,
        width=capture.width,
        height=capture.height,
        fps=capture.fps,
        jpegQuality=capture.jpeg_quality,
    )
    return True


async def close_phone_session(app: web.Application, reason: str = "stopped") -> None:
    ws = app[CONTEXT_KEY].current_ws
    if ws is None or ws.closed:
        return
    with contextlib.suppress(Exception):
        await _send_json(ws, "bye", reason=reason)
        await ws.close(code=1000, message=reason.encode("utf-8"))


async def shutdown_websocket(app: web.Application) -> None:
    await close_phone_session(app, "shutdown")
