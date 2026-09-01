from __future__ import annotations

import numpy as np

from yfphonecam.config import CaptureSettings, ImageSettings
from yfphonecam.processing.frame_processor import FrameProcessor


def _quadrants() -> np.ndarray:
    frame = np.zeros((4, 6, 3), dtype=np.uint8)
    frame[:2, :3] = (10, 0, 0)
    frame[:2, 3:] = (20, 0, 0)
    frame[2:, :3] = (30, 0, 0)
    frame[2:, 3:] = (40, 0, 0)
    return frame


def test_output_resolution_is_fixed_for_every_rotation() -> None:
    capture = CaptureSettings(width=12, height=8)
    for rotation in (0, 90, 180, 270):
        result = FrameProcessor.process(_quadrants(), capture, ImageSettings(rotation=rotation))
        assert result.shape == (8, 12, 3)


def test_quarter_turn_is_letterboxed() -> None:
    result = FrameProcessor.process(
        _quadrants(), CaptureSettings(width=12, height=8), ImageSettings(rotation=90)
    )
    assert np.all(result[:, :3] == 0)
    assert np.all(result[:, -3:] == 0)


def test_horizontal_mirror_swaps_sides() -> None:
    capture = CaptureSettings(width=6, height=4)
    result = FrameProcessor.process(_quadrants(), capture, ImageSettings(mirror=True))
    assert tuple(result[0, 0]) == (20, 0, 0)
    assert tuple(result[0, -1]) == (10, 0, 0)


def test_zoom_crops_the_center() -> None:
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    frame[2:6, 2:6] = 255
    result = FrameProcessor.process(
        frame, CaptureSettings(width=8, height=8), ImageSettings(zoom=2.0)
    )
    assert np.all(result == 255)
