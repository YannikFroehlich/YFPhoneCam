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

## Branching and releases

Day-to-day work happens on `develop`; `main` only receives finished, release-ready changes.

1. Commit and push to `develop` (directly or via PR). Every push runs CI (lint, type check,
   tests, JS syntax check).
2. Bump `__version__` in [`yfphonecam/version.py`](yfphonecam/version.py) as part of the change
   that should ship next.
3. Merge or push `develop` into `main`. CI runs again, and if it passes, a second job tags the
   commit `v<version>` (skipped if that tag already exists, so a merge without a version bump is a
   no-op).
4. The new tag triggers the `Release` workflow, which builds the installer, generates its
   checksum and SBOM, and publishes a draft GitHub Release with the installer `.exe` attached.
   Review and publish the draft manually.
