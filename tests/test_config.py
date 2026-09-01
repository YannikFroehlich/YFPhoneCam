from __future__ import annotations

from dataclasses import replace

from yfphonecam.config import Settings, load_settings, save_settings, validate_settings


def test_invalid_values_fall_back_to_documented_defaults() -> None:
    invalid = Settings(
        capture=replace(Settings().capture, width=10, fps=500, jpeg_quality=2),
        image=replace(Settings().image, zoom=9, rotation=45),
        app=replace(Settings().app, port=80, last_update_check=-1),
    )

    actual = validate_settings(invalid)

    assert actual.capture.width == 1280
    assert actual.capture.fps == 30
    assert actual.capture.jpeg_quality == 80
    assert actual.image.zoom == 1.0
    assert actual.image.rotation == 0
    assert actual.app.port == 8000
    assert actual.app.last_update_check == 0


def test_grouped_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.toml"
    expected = Settings(
        capture=replace(Settings().capture, width=1920, height=1080, camera_id="rear"),
        image=replace(Settings().image, zoom=2.3, rotation=270, mirror=True),
        device=replace(Settings().device, serial="device-1", adb_path="C:/tools/adb.exe"),
        app=replace(Settings().app, update_check_enabled=False),
    )

    save_settings(expected, path)

    assert load_settings(path) == expected


def test_environment_overrides_file(monkeypatch, tmp_path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text("[capture]\nfps = 15\n", encoding="utf-8")
    monkeypatch.setenv("YFPHONECAM_FPS", "60")

    assert load_settings(path).capture.fps == 60
