# Security policy

## Supported versions

Security fixes are provided for the latest published beta or stable release.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose local files, execute
commands, bypass the loopback/session-token boundary, or weaken the USB-only transport model.
Use GitHub's private vulnerability reporting feature for this repository instead.

YFPhoneCam does not intentionally transmit camera frames, logs, device serials, or analytics over
the internet. Network access is limited to user-approved Android Platform-Tools downloads and the
optional GitHub release check.

