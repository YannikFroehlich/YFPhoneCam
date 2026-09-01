from __future__ import annotations

from dataclasses import dataclass

from aiohttp import web

from ..config import Settings
from ..state import AppState


@dataclass
class ServerContext:
    settings: Settings
    state: AppState
    session_token: str
    session_id: str
    current_ws: web.WebSocketResponse | None = None
    pending_config_request: str | None = None


CONTEXT_KEY = web.AppKey("yfphonecam.context", ServerContext)
