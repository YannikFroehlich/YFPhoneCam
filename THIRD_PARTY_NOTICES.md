# Third-party notices

YFPhoneCam is licensed under the MIT License. The distributable application also uses the
following third-party components. Their complete license texts are copied into the installer's
`licenses` directory during the release build.

| Component | Purpose | License |
| --- | --- | --- |
| Python | Runtime | Python Software Foundation License |
| aiohttp | Local HTTP/WebSocket server | Apache-2.0 |
| NumPy | Frame buffers | BSD-3-Clause |
| OpenCV / opencv-python | JPEG decoding and image processing | Apache-2.0 |
| Qt for Python / PySide6 | Desktop user interface | LGPL-3.0-only or commercial |
| Unity Capture filter | DirectShow virtual camera | MIT |
| Unity Capture shared-memory sender interface | Frame transfer protocol | zlib |

## Unity Capture

YFPhoneCam interoperates with the Unity Capture filter and adapts the shared-memory sender
interface published by Bernhard Schelling:

- https://github.com/schellingb/UnityCapture at commit `3ed54c325e0ad71afcf4f246c07e5e17b3d7f2d2`
- Copyright (c) 2018 Bernhard Schelling
- Based on UnityCam, copyright (c) 2016 MHD Yamen Saraiji

The filter binaries are fetched from a pinned upstream revision and hash-verified by the release
workflow. They are registered under the custom display name `YFPhoneCam` without modifying the
filter.

## Android SDK Platform-Tools

Android SDK Platform-Tools are **not distributed with YFPhoneCam**. When required, the user can
accept Google's SDK terms and download an official archive directly from Google through the
first-run assistant. Beta `0.1.0-beta.1` pins Platform-Tools `37.0.1` with SHA-256
`45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99`. See
https://developer.android.com/tools/releases/platform-tools.

## pyvirtualcam

YFPhoneCam does not distribute or import `pyvirtualcam`. Earlier development versions used it,
but it was removed before the public beta to keep the YFPhoneCam codebase under the MIT License.
