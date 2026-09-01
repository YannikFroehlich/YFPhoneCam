from __future__ import annotations

from pathlib import Path

from aiohttp import web

from .context import CONTEXT_KEY

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_CONTENT_TYPES = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
}


def _serve_file(relative_path: str):
    file_path = WEB_DIR / relative_path
    content_type = _CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")

    async def handler(request: web.Request) -> web.Response:
        return web.Response(body=file_path.read_bytes(), content_type=content_type, charset="utf-8")

    return handler


async def phone_index(request: web.Request) -> web.Response:
    file_path = WEB_DIR / "phone" / "index.html"
    response = web.Response(body=file_path.read_bytes(), content_type="text/html", charset="utf-8")
    response.set_cookie(
        "yfphonecam_session",
        request.app[CONTEXT_KEY].session_token,
        httponly=True,
        samesite="Strict",
        path="/",
    )
    return response


async def api_status(request: web.Request) -> web.Response:
    return web.json_response(request.app[CONTEXT_KEY].state.snapshot())


async def api_config(request: web.Request) -> web.Response:
    settings = request.app[CONTEXT_KEY].settings
    return web.json_response(
        {
            "protocol": 1,
            "width": settings.capture.width,
            "height": settings.capture.height,
            "fps": settings.capture.fps,
            "jpeg_quality": settings.capture.jpeg_quality,
            "camera_id": settings.capture.camera_id,
        }
    )


def register_routes(app: web.Application) -> None:
    app.router.add_get("/", phone_index)
    app.router.add_get("/phone.js", _serve_file("phone/phone.js"))
    app.router.add_get("/phone.css", _serve_file("phone/phone.css"))

    app.router.add_get("/status", _serve_file("status/index.html"))
    app.router.add_get("/status.js", _serve_file("status/status.js"))

    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/config", api_config)
