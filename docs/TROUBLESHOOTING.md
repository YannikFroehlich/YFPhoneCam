# Troubleshooting

## The phone does not appear

- Use a USB cable that supports data, not charging only.
- Unlock the phone and set its USB mode to file transfer if the manufacturer requires it.
- Revoke and re-accept USB debugging authorizations in Android Developer options.
- Run `scripts\check_setup.py` from a development checkout, or inspect the status line in the app.
- If several devices are attached, explicitly select one. YFPhoneCam never guesses between multiple devices.

## The browser does not open or connect

Press **Start / reconnect**. The server intentionally listens on `127.0.0.1` only, so opening the PC's LAN address is unsupported. A reconnect after unplugging USB is automatic if the original phone tab remains active. A phone displaced by another connection receives `bye/replaced` and intentionally does not reconnect.

## Camera permission or camera switching fails

Grant camera permission to the localhost page in Chrome. When a requested resolution or frame rate is unsupported, Android/Chrome may negotiate a nearby value; the actual value is displayed in the desktop status line. Camera switching is atomic: the previous stream stays active if opening the new camera fails.

## Other applications cannot see YFPhoneCam

- Restart the target application after installation because many apps enumerate cameras only at startup.
- Confirm the installer completed with administrator rights.
- Close all camera clients, then repair or reinstall YFPhoneCam.
- Some applications permit only one process to own a camera at a time.

The virtual-camera status becomes active only when a receiving application has opened the **YFPhoneCam** DirectShow device. This is expected.

## SmartScreen warning

The public beta is intentionally unsigned. Verify the installer SHA-256 against the release asset and download only from the official repository. Signed app and installer binaries are planned before `v1.0.0`.

## Export diagnostics

Choose **File > Export diagnostics**. The ZIP contains versions, connection status, sanitized settings, and rotating text logs. Device serials, camera IDs, session tokens, user paths, and usernames are removed. It never contains camera images and is never uploaded automatically.
