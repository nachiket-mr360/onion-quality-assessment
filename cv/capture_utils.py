"""Shared camera opening helpers for Phase 2 infrastructure proofs."""

from __future__ import annotations

import cv2


def parse_source(source: str) -> int | str:
    source = source.strip()
    if source.isdigit():
        return int(source)
    return source


def open_capture(source: str) -> cv2.VideoCapture:
    parsed = parse_source(source)
    if isinstance(parsed, int):
        cap = cv2.VideoCapture(parsed, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap
        cap.release()
        return cv2.VideoCapture(parsed)
    return cv2.VideoCapture(parsed)


def describe_capture(cap: cv2.VideoCapture) -> str:
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    return f"{width}x{height} fps_prop={fps:.2f}"
