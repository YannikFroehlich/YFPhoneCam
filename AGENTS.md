# AGENTS.md

Guidance for coding agents working on YFPhoneCam.

## Product boundary

YFPhoneCam turns an Android phone into a Windows 10/11 x64 webcam over USB only. Android remains browser-based: Chrome captures JPEG frames and sends them through a WebSocket tunneled by `adb reverse`. The PC server must always bind to `127.0.0.1`; do not add LAN/Wi-Fi transport.

The public beta is English-only, MIT-licensed, and has no telemetry, image recording, or automatic upload. Do not add `pyvirtualcam`; the app sends RGBA frames directly through Unity Capture's permissively licensed shared-memory protocol.

## Commands

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy yfphonecam
.venv\Scripts\python.exe -m pytest
node --check yfphonecam/web/phone/phone.js
.venv\Scripts\python.exe -m yfphonecam
```

Release build:

```powershell
pwsh scripts/fetch_unity_capture.ps1
pwsh scripts/build_release.ps1 -Tag v0.1.0-beta.1
```

## Architecture

- `gui/`: PySide6 Widgets in the process main thread. Preview frames become `QImage` objects only on that thread. `QLocalServer` enforces a single instance.
- `orchestrator.py`: GUI-independent composition root. aiohttp and ADB polling run on the backend asyncio thread in GUI mode.
- `state.py`: lock-guarded state plus three single-slot, drop-oldest queues for compressed, virtual-camera, and preview frames.
- `processing/`: one decoder worker and `FrameProcessor`. It applies zoom, rotation, mirror, and fixed-resolution aspect fit once, then fans the same pixels out to both consumers.
- `server/`: loopback HTTP/WebSocket server. Protocol version is `1`; the binary frame header remains `<IQ` followed by JPEG bytes. Every run uses a random WebSocket session token.
- `virtualcam/`: direct `ctypes` sender for Unity Capture shared memory. The installer registers pinned 32- and 64-bit filters with the display name `YFPhoneCam`.
- `adb.py` and `adb_setup.py`: timeout-checked ADB operations, device polling, and the user-approved, hash-verified official Platform-Tools download.

Settings live in `%LOCALAPPDATA%\YFPhoneCam\settings.toml` and are grouped into `capture`, `image`, `device`, and `app`. Precedence is defaults, file, `YFPHONECAM_*` environment variables, then CLI. Invalid values fall back to documented defaults.

## Invariants

- Never bind the server to `0.0.0.0`.
- Never log session tokens or put device serials/user paths in diagnostics.
- Keep all frame queues bounded at one item; latency is more important than preserving old frames.
- A replaced phone receives `bye/replaced` and must not automatically reconnect.
- Phone camera switching must open the replacement stream before stopping the old stream.
- Rotating logs remain capped at five files of 2 MB each.
- Unity Capture DLLs are fetched from `vendor/unitycapture.json`; never commit release DLLs.
- `yfphonecam/version.py` is the single version source and release tags must be `v` plus that value.
