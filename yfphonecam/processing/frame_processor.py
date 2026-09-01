from __future__ import annotations

import cv2
import numpy as np

from ..config import CaptureSettings, ImageSettings


class FrameProcessor:
    """Apply display-space transforms and produce a fixed-size BGR frame."""

    @staticmethod
    def process(
        frame: np.ndarray,
        capture: CaptureSettings,
        image: ImageSettings,
    ) -> np.ndarray:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("expected a BGR image with shape (height, width, 3)")

        transformed = FrameProcessor._rotate(frame, image.rotation)
        if image.mirror:
            transformed = cv2.flip(transformed, 1)
        transformed = FrameProcessor._zoom(transformed, image.zoom)
        return FrameProcessor._fit(transformed, capture.width, capture.height)

    @staticmethod
    def _rotate(frame: np.ndarray, rotation: int) -> np.ndarray:
        if rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        if rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        if rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    @staticmethod
    def _zoom(frame: np.ndarray, zoom: float) -> np.ndarray:
        zoom = min(4.0, max(1.0, float(zoom)))
        if zoom <= 1.0:
            return frame
        height, width = frame.shape[:2]
        crop_width = max(1, round(width / zoom))
        crop_height = max(1, round(height / zoom))
        left = (width - crop_width) // 2
        top = (height - crop_height) // 2
        return frame[top : top + crop_height, left : left + crop_width]

    @staticmethod
    def _fit(frame: np.ndarray, target_width: int, target_height: int) -> np.ndarray:
        source_height, source_width = frame.shape[:2]
        scale = min(target_width / source_width, target_height / source_height)
        width = max(1, round(source_width * scale))
        height = max(1, round(source_height * scale))
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        resized = cv2.resize(frame, (width, height), interpolation=interpolation)
        canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        left = (target_width - width) // 2
        top = (target_height - height) // 2
        canvas[top : top + height, left : left + width] = resized
        return canvas
