# YFPhoneCam

YFPhoneCam turns an Android phone into a Windows webcam over a USB cable. The phone camera runs in Chrome, frames travel through an `adb reverse` tunnel, and the Windows application provides a live preview plus a DirectShow camera named **YFPhoneCam**.

> [!IMPORTANT]
> `0.1.0-beta.1` is an unsigned Windows 10/11 x64 beta. Windows SmartScreen may show an unrecognized-app warning until signed releases have built reputation.

## Highlights

- USB-only transport; the local server binds to `127.0.0.1` and does not expose the camera on Wi-Fi.
- Desktop controls for camera selection, 640×480/720p/1080p, 15/30/60 FPS, JPEG quality, 1–4× zoom, rotation, and mirroring.
- A single processed frame is sent to both the Qt preview and virtual camera.
- Guided Android Platform-Tools setup with explicit SDK terms acceptance, HTTPS download, size limit, SHA-256 verification, and safe ZIP extraction.
- No account, telemetry, image recording, cloud service, or automatic upload.
- Local rotating logs and a manually initiated, redacted diagnostics export.

## How it works

```text
Android Chrome -> getUserMedia -> JPEG/WebSocket
                    | adb reverse over USB
Windows service -> newest-frame queue -> decoder -> image processing
                                           |-> Qt preview
                                           `-> Unity Capture shared memory -> DirectShow apps
```

Chrome treats `localhost` as a secure context for camera access. `adb reverse` makes the PC's loopback server available as `http://localhost:<port>` on the phone without LAN transport or a certificate. A random session token is created for every run and required by the WebSocket.

## Installing the beta

1. Download `YFPhoneCam-Setup-0.1.0-beta.1.exe` from the matching GitHub Release.
2. Optionally compare it with the published SHA-256 file.
3. Run the installer as administrator. It installs the app and registers the 32- and 64-bit virtual-camera filters as **YFPhoneCam**.
4. Start YFPhoneCam and follow the Android Platform-Tools assistant.
5. Enable Android Developer options and USB debugging, connect the phone, and accept its authorization prompt.
6. Select **YFPhoneCam** as the camera in OBS, Zoom, Teams, Discord, or a browser.

Python, Android Studio, and Platform-Tools are not bundled in the installer. If ADB is unavailable, the setup assistant can download the pinned official Google archive only after the user accepts the Android SDK terms.

See [docs/INSTALLATION.md](docs/INSTALLATION.md) and [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed guidance.

## Development

Requirements: Windows 10/11 x64, Python 3.13, Node.js for the JavaScript syntax check, and optionally Inno Setup 6 for an installer build.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy yfphonecam
node --check yfphonecam/web/phone/phone.js
.venv\Scripts\python.exe -m yfphonecam
```

For headless diagnostics:

```powershell
.venv\Scripts\python.exe -m yfphonecam --headless --fps 15 --jpeg-quality 60
```

Runtime settings are stored at `%LOCALAPPDATA%\YFPhoneCam\settings.toml`. Precedence is defaults, configuration file, `YFPHONECAM_*` environment variables, then CLI options. [config.example.toml](config.example.toml) documents every group.

## Building a release

Release builds fetch the two Unity Capture filter DLLs from the commit pinned in `vendor/unitycapture.json` and verify both SHA-256 hashes. They are not stored in Git. The app uses a small MIT-licensed Python sender adapted from Unity Capture's zlib-licensed public shared-memory protocol; `pyvirtualcam` is not used.

```powershell
pwsh scripts/fetch_unity_capture.ps1
pwsh scripts/build_release.ps1
```

PyInstaller creates an `onedir` application and Inno Setup turns it into one installer. The tag must exactly match `v` plus the version in [yfphonecam/version.py](yfphonecam/version.py).

## Security and privacy

The HTTP server listens only on loopback. Camera frames are kept in memory, stale work is dropped, and nothing is saved unless the user explicitly exports diagnostics; that export never includes images. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

YFPhoneCam is released under the [MIT License](LICENSE). Bundled third-party components keep their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
