# Installation

## Supported system

YFPhoneCam `0.1.0-beta.1` supports 64-bit Windows 10 and Windows 11 and an Android phone with a current Chromium-based browser. USB debugging is required. iOS, macOS, Linux, Wi-Fi streaming, and an Android APK are outside this beta.

## Install YFPhoneCam

1. Download the installer and its `.sha256` file from the same GitHub Release.
2. In PowerShell, optionally verify it with `Get-FileHash .\YFPhoneCam-Setup-0.1.0-beta.1.exe -Algorithm SHA256`.
3. Run the installer and accept the administrator prompt. The elevation is needed to install and register the DirectShow camera for the whole machine.
4. Keep **Launch YFPhoneCam** selected on the final page.

The beta is unsigned, so SmartScreen can warn that the publisher is unknown. Download only from this project's GitHub Releases page and verify the checksum.

## Configure Android Platform-Tools

YFPhoneCam first searches `PATH`, `ANDROID_HOME`, `ANDROID_SDK_ROOT`, the usual Android SDK directory, and its managed app-data directory. If ADB is absent, the assistant offers two choices:

- select an existing `adb.exe`; or
- open and accept Google's Android SDK terms, then download the pinned official Platform-Tools archive.

The managed copy is stored under `%LOCALAPPDATA%\YFPhoneCam\platform-tools`. It is not part of the installer.

## Connect the phone

1. Enable Android Developer options (usually by tapping **Build number** seven times).
2. Enable **USB debugging**.
3. Connect a data-capable USB cable.
4. Unlock the phone and accept **Allow USB debugging?**. Choosing **Always allow from this computer** makes reconnects smoother.
5. Select the device in YFPhoneCam if more than one authorized Android device is attached.
6. Press **Start / reconnect**. Chrome opens the local phone page and asks for camera permission.

Keep the Chrome tab visible and prevent the phone from sleeping while streaming. Android can pause camera capture in a backgrounded tab.

## Uninstall

Use **Installed apps > YFPhoneCam > Uninstall**. The uninstaller deregisters both virtual-camera filters and removes YFPhoneCam's managed settings, Platform-Tools, and logs. Diagnostics archives saved elsewhere remain yours.
