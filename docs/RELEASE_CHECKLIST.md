# Public beta release checklist

The `v0.1.0-beta.1` release stays in draft until every automated and manual item below has evidence attached to the release issue.

## Automated gates

- [ ] `python -m ruff check .`
- [ ] `python -m ruff format --check .`
- [ ] `python -m mypy yfphonecam`
- [ ] `python -m pytest`
- [ ] JavaScript syntax checks for both browser files
- [ ] Source version exactly matches the Git tag
- [ ] Runtime and development dependencies install with `--require-hashes`
- [ ] Both Unity Capture DLLs match `vendor/unitycapture.json`
- [ ] PyInstaller `onedir` build succeeds and the frozen `--version` command exits successfully
- [ ] Inno Setup build succeeds
- [ ] Installer, SHA-256 file, and CycloneDX SBOM are attached to a draft release

## Clean-VM installer matrix

Run every row on fresh, fully patched x64 virtual machines without Python or Android Studio installed.

| Scenario | Windows 10 | Windows 11 |
| --- | --- | --- |
| New installation and optional desktop shortcut | [ ] | [ ] |
| UAC rejection leaves the machine unchanged | [ ] | [ ] |
| In-place upgrade keeps settings | [ ] | [ ] |
| Forced filter-registration failure rolls installation back | [ ] | [ ] |
| Uninstall deregisters both filters and removes managed app data | [ ] | [ ] |
| App launches and the guided ADB download succeeds | [ ] | [ ] |
| Camera enumerates as `YFPhoneCam` in 32- and 64-bit clients | [ ] | [ ] |

## Compatibility matrix

Test the preview, camera output, every rotation, mirror, and at least two zoom levels. Record the versions used.

| Client | 720p30 | 1080p30 | Reconnect | Pixel match |
| --- | --- | --- | --- | --- |
| OBS Studio | [ ] | [ ] | [ ] | [ ] |
| Zoom | [ ] | [ ] | [ ] | [ ] |
| Microsoft Teams | [ ] | [ ] | [ ] | [ ] |
| Discord | [ ] | [ ] | [ ] | [ ] |
| Chromium browser | [ ] | [ ] | [ ] | [ ] |

- [ ] At least two Android manufacturers tested
- [ ] One older and one current supported Android/Chrome combination tested
- [ ] Unsupported 60 FPS cleanly reports the negotiated fallback

## Endurance and privacy

- [ ] Stream `1280×720 @ 30 FPS` for 30 minutes with stable memory usage
- [ ] Confirm all three frame queues remain bounded at one item
- [ ] Recover automatically after at least 20 USB disconnect/reconnect cycles
- [ ] Confirm preview and virtual-camera frames are pixel-identical for all transforms
- [ ] Confirm logs rotate at five files of at most 2 MB each
- [ ] Inspect diagnostics ZIP: no serials, session tokens, user paths, usernames, or images
- [ ] Confirm no telemetry and no network listener outside `127.0.0.1`

## Publication

- [ ] Review MIT and all third-party notices against the final SBOM
- [ ] Document the unsigned SmartScreen warning in release notes
- [ ] Confirm install succeeds without Python, Platform-Tools, or Android Studio preinstalled
- [ ] Publish the draft release
- [ ] Change the GitHub repository from private to public only after the published assets have been re-downloaded and checksum-verified
