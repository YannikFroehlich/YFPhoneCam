from __future__ import annotations

from aiohttp import web

from ..config import Settings
from ..state import AppState
from .context import CONTEXT_KEY, ServerContext
from .routes import register_routes
from .ws_handler import shutdown_websocket, websocket_handler


def create_app(
    settings: Settings,
    state: AppState,
    session_token: str,
    session_id: str,
) -> web.Application:
    app = web.Application()
    app[CONTEXT_KEY] = ServerContext(settings, state, session_token, session_id)

    register_routes(app)
    app.router.add_get("/ws", websocket_handler)
    app.on_shutdown.append(shutdown_websocket)

    return app
