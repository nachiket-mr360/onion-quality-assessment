"""Physical size from a calibrated reference. Independent of YOLO grading.

A bounding-box width in pixels is never treated as millimetres.
Scale comes only from a detected ArUco marker of known printed size.
"""

from __future__ import annotations

from typing import Any, Sequence

import cv2
import numpy as np

ARUCO_DICT_NAME = "DICT_4X4_50"
DEFAULT_MARKER_ID = 0
# Printed outer black-square side length the user should measure with a ruler.
DEFAULT_MARKER_MM = 50.0


def _detector():
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    params = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(dictionary, params)


def _marker_side_px(corners: np.ndarray) -> float:
    pts = corners.reshape(-1, 2)
    sides = [float(np.linalg.norm(pts[i] - pts[(i + 1) % 4])) for i in range(4)]
    return float(sum(sides) / 4.0)


def detect_aruco_scale(
    image: np.ndarray,
    marker_mm: float = DEFAULT_MARKER_MM,
    marker_id: int = DEFAULT_MARKER_ID,
) -> dict[str, Any]:
    """Return pixels_per_mm if the expected marker is found. Never invent a scale."""
    if image is None or image.size == 0:
        return {
            "calibrated": False,
            "pixels_per_mm": None,
            "marker_side_px": None,
            "marker_mm": marker_mm,
            "measurement_status": "no_image",
        }
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    corners, ids, _ = _detector().detectMarkers(gray)
    if ids is None or len(ids) == 0:
        return {
            "calibrated": False,
            "pixels_per_mm": None,
            "marker_side_px": None,
            "marker_mm": marker_mm,
            "measurement_status": "reference_not_detected",
        }
    ids_flat = ids.flatten().tolist()
    if marker_id not in ids_flat:
        return {
            "calibrated": False,
            "pixels_per_mm": None,
            "marker_side_px": None,
            "marker_mm": marker_mm,
            "found_ids": ids_flat,
            "measurement_status": "expected_marker_id_not_found",
        }
    if marker_mm <= 0:
        return {
            "calibrated": False,
            "pixels_per_mm": None,
            "marker_side_px": None,
            "marker_mm": marker_mm,
            "measurement_status": "invalid_marker_mm",
        }
    idx = ids_flat.index(marker_id)
    side_px = _marker_side_px(corners[idx])
    ppm = side_px / float(marker_mm)
    if ppm <= 0:
        return {
            "calibrated": False,
            "pixels_per_mm": None,
            "marker_side_px": side_px,
            "marker_mm": marker_mm,
            "measurement_status": "invalid_scale",
        }
    return {
        "calibrated": True,
        "pixels_per_mm": ppm,
        "marker_side_px": side_px,
        "marker_mm": float(marker_mm),
        "marker_id": marker_id,
        "aruco_dict": ARUCO_DICT_NAME,
        "measurement_status": "ok",
    }


def diameter_from_xyxy(xyxy: Sequence[float]) -> dict[str, float]:
    x1, y1, x2, y2 = [float(v) for v in xyxy]
    w, h = abs(x2 - x1), abs(y2 - y1)
    return {
        "bbox_width_px": w,
        "bbox_height_px": h,
        # Approximate onion diameter = mean of bbox sides (not a fitted circle).
        "diameter_px": (w + h) / 2.0,
    }


def measure_onion(
    image: np.ndarray | None,
    xyxy: Sequence[float] | None,
    marker_mm: float = DEFAULT_MARKER_MM,
    marker_id: int = DEFAULT_MARKER_ID,
    scale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calibrated mm if reference found; otherwise diameter_mm is None."""
    cal = scale if scale is not None else detect_aruco_scale(
        image, marker_mm=marker_mm, marker_id=marker_id
    )
    out: dict[str, Any] = {
        "diameter_mm": None,
        "diameter_cm": None,
        "diameter_px": None,
        "calibrated": bool(cal.get("calibrated")),
        "pixels_per_mm": cal.get("pixels_per_mm"),
        "measurement_status": cal.get("measurement_status"),
        "marker_mm": cal.get("marker_mm"),
    }
    if xyxy is None:
        out["measurement_status"] = "no_bbox"
        return out
    geom = diameter_from_xyxy(xyxy)
    out.update(geom)
    if not cal.get("calibrated") or not cal.get("pixels_per_mm"):
        if out["measurement_status"] in (None, "ok"):
            out["measurement_status"] = "not_calibrated"
        return out
    ppm = float(cal["pixels_per_mm"])
    mm = geom["diameter_px"] / ppm
    out["diameter_mm"] = round(mm, 2)
    out["diameter_cm"] = round(mm / 10.0, 3)
    out["measurement_status"] = "ok"
    return out


def make_test_calibration_image(
    marker_side_px: int = 200,
    marker_mm: float = 50.0,
    onion_box_px: int = 160,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Synthetic TEST ARTIFACT only — proves pixel/mm math. Not field evidence."""
    pad = 40
    canvas_w = pad * 3 + marker_side_px + onion_box_px
    canvas_h = pad * 2 + max(marker_side_px, onion_box_px)
    img = np.full((canvas_h, canvas_w, 3), 240, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = np.zeros((marker_side_px, marker_side_px), dtype=np.uint8)
    cv2.aruco.generateImageMarker(dictionary, DEFAULT_MARKER_ID, marker_side_px, marker, 1)
    marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    img[pad : pad + marker_side_px, pad : pad + marker_side_px] = marker_bgr
    ox = pad * 2 + marker_side_px
    oy = pad
    cv2.rectangle(img, (ox, oy), (ox + onion_box_px, oy + onion_box_px), (40, 80, 180), -1)
    expected_ppm = marker_side_px / marker_mm
    expected_mm = onion_box_px / expected_ppm
    meta = {
        "test_artifact": True,
        "marker_side_px": marker_side_px,
        "marker_mm": marker_mm,
        "onion_xyxy": [ox, oy, ox + onion_box_px, oy + onion_box_px],
        "expected_pixels_per_mm": expected_ppm,
        "expected_diameter_mm": expected_mm,
    }
    return img, meta
