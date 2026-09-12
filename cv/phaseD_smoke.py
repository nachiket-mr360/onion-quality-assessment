"""Phase D smoke: ArUco calibration + diameter. Not field evidence if synthetic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

CV_DIR = Path(__file__).resolve().parent
ROOT = CV_DIR.parent
if str(CV_DIR) not in sys.path:
    sys.path.insert(0, str(CV_DIR))

from batch_assess import assess_frame
from onion_infer import detect, load_detector
from size_measure import (
    DEFAULT_MARKER_MM,
    detect_aruco_scale,
    make_test_calibration_image,
    measure_onion,
)

OUT = ROOT / "captures"
TEST_IMG = ROOT / "data" / "processed" / "yolo" / "images" / "test" / "onion_sample_001_v2.jpeg"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    img, meta = make_test_calibration_image()
    artifact = OUT / "phaseD_SYNTHETIC_calibration_test.png"
    cv2.imwrite(str(artifact), img)
    print("TEST_ARTIFACT", artifact)
    print("META", json.dumps(meta, indent=2))

    scale = detect_aruco_scale(img, marker_mm=meta["marker_mm"])
    print("CAL", json.dumps({k: scale[k] for k in scale if k != "foo"}, indent=2, default=float))
    meas = measure_onion(img, meta["onion_xyxy"], marker_mm=meta["marker_mm"], scale=scale)
    print("MEAS", json.dumps(meas, indent=2))
    err_ppm = abs(scale["pixels_per_mm"] - meta["expected_pixels_per_mm"])
    err_mm = abs(meas["diameter_mm"] - meta["expected_diameter_mm"])
    print("err_ppm", err_ppm, "err_mm", err_mm)
    ok_math = err_ppm < 0.05 and err_mm < 0.5
    print("math_ok", ok_math)

    blank = np.full((200, 200, 3), 220, dtype=np.uint8)
    no_cal = measure_onion(blank, [10, 10, 110, 110])
    print("NO_CAL", json.dumps(no_cal, indent=2))
    fake_mm = no_cal["diameter_mm"] is not None
    print("invented_mm", fake_mm)

    # Real onion image has no marker → must not invent mm; still has pixel size.
    model = load_detector()
    batch = assess_frame(detect(model, TEST_IMG))
    xyxy = batch["onions"][0]["xyxy"] if batch["onions"] else None
    real = measure_onion(cv2.imread(str(TEST_IMG)), xyxy)
    print("REAL_TEST_NO_MARKER", json.dumps(real, indent=2))
    print("real_invented_mm", real["diameter_mm"] is not None)

    # Printable marker for Nachiket (50 mm outer square).
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = np.zeros((600, 600), dtype=np.uint8)
    cv2.aruco.generateImageMarker(dictionary, 0, 600, marker, 1)
    printable = OUT / "phaseD_print_aruco_4x4_id0_50mm.png"
    cv2.imwrite(str(printable), marker)
    print("PRINTABLE", printable)
    print("PRINT_INSTRUCTIONS: print this PNG so the BLACK SQUARE is 50 mm on each side. Place it in the same plane as the onion, fully visible, not covered. Capture one still with phone camera.")
    return 0 if ok_math and not fake_mm else 1


if __name__ == "__main__":
    raise SystemExit(main())
