# Contributing to YFPhoneCam

Thank you for helping improve YFPhoneCam.

## Development setup

YFPhoneCam targets Windows 10/11 x64 and Python 3.13.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy yfphonecam
```

Run the application from source with:

```powershell
.\.venv\Scripts\python.exe -m yfphonecam
```

Please keep the server bound to loopback only and preserve the USB-only transport guarantee.
New dependencies must have a license compatible with the project's MIT distribution and must be
added to `THIRD_PARTY_NOTICES.md`.

## Pull requests

- Keep changes focused and include tests for observable behavior.
- Do not commit generated installers, virtual environments, ADB binaries, logs, device serials,
  or session tokens.
- Update the user-facing documentation when behavior changes.
