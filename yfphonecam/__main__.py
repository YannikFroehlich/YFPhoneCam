from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import replace

from .config import Settings, load_settings, validate_settings
from .logging_setup import setup_logging
from .version import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="YFPhoneCam",
        description="Use an Android phone as a USB-only Windows webcam.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--headless", action="store_true", help="Run without the desktop UI.")
    parser.add_argument("--gui-smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help="Preferred localhost server port.")
    parser.add_argument("--width", type=int, choices=(640, 1280, 1920))
    parser.add_argument("--height", type=int, choices=(480, 720, 1080))
    parser.add_argument("--fps", type=int, choices=(15, 30, 60))
    parser.add_argument("--jpeg-quality", type=int, choices=range(40, 96), metavar="40-95")
    parser.add_argument("--device-serial", help="ADB serial of the Android device to use.")
    parser.add_argument("--adb-path", help="Path to adb.exe.")
    parser.add_argument(
        "--no-auto-launch", action="store_true", help="Do not open the phone page automatically."
    )
    parser.add_argument("--no-preview", action="store_true", help=argparse.SUPPRESS)
    return parser


def _apply_cli(settings: Settings, args: argparse.Namespace) -> Settings:
    capture = settings.capture
    device = settings.device
    app = settings.app

    if args.width is not None:
        capture = replace(capture, width=args.width)
    if args.height is not None:
        capture = replace(capture, height=args.height)
    if args.fps is not None:
        capture = replace(capture, fps=args.fps)
    if args.jpeg_quality is not None:
        capture = replace(capture, jpeg_quality=args.jpeg_quality)
    if args.device_serial is not None:
        device = replace(device, serial=args.device_serial)
    if args.adb_path is not None:
        device = replace(device, adb_path=args.adb_path)
    if args.no_auto_launch:
        app = replace(app, auto_launch_phone_browser=False)
    if args.port is not None:
        app = replace(app, port=args.port)

    return replace(settings, capture=capture, device=device, app=app)


def _run_headless(settings: Settings) -> int:
    # Keep the native backend out of lightweight CLI paths and let the GUI own
    # its Qt-before-backend import order.
    from .orchestrator import Orchestrator

    try:
        asyncio.run(Orchestrator(settings).run_forever())
    except KeyboardInterrupt:
        return 0
    except Exception:
        logging.getLogger(__name__).exception(
            "YFPhoneCam stopped because of an unrecoverable error"
        )
        return 1
    return 0


def _run_gui_smoke_test() -> int:
    """Load Qt and create its platform integration for release-build verification."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(["YFPhoneCam", "--gui-smoke-test"])
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    setup_logging()
    settings = validate_settings(_apply_cli(load_settings(), args))

    if args.gui_smoke_test:
        return _run_gui_smoke_test()

    if args.headless:
        return _run_headless(settings)

    try:
        from .gui.app import run_gui
    except ImportError as exc:
        logging.getLogger(__name__).error("The desktop UI could not be loaded: %s", exc)
        print(
            "The desktop UI could not be loaded. Reinstall YFPhoneCam or use --headless.",
            file=sys.stderr,
        )
        return 1
    return run_gui(settings)


if __name__ == "__main__":
    raise SystemExit(main())
