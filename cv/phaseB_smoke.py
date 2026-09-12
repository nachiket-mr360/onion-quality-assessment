"""Phase B smoke: real inference on prepared test images. Does not train or write labels."""

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

from grading import grade_class, worst_class
from onion_infer import detect, load_detector

TEST_DIR = ROOT / "data" / "processed" / "yolo" / "images" / "test"
SAMPLES = [
    "onion_sample_001_v2.jpeg",
    "onion_sample_d_012_v1.jpeg",
    "onion_sample_r_011_v1.jpeg",
    "onion_sample_011_v1.jpeg",
    "onion_sample_r_016_v2.jpeg",
]


def main() -> int:
    print("=== grading unit ===")
    assert grade_class("HEALTHY")[0] == "GOOD"
    assert grade_class("DAMAGED")[0] == "BAD"
    assert grade_class("ROTTEN")[0] == "BAD"
    assert grade_class("SPROUTED")[0] == "BAD"
    assert worst_class(["HEALTHY", "DAMAGED", "ROTTEN"]) == "ROTTEN"
    assert worst_class(["SPROUTED", "DAMAGED"]) == "SPROUTED"
    print("priority OK")

    model = load_detector()
    print("weights", ROOT / "runs" / "baseline_yolov8n" / "weights" / "best.pt")

    for name in SAMPLES:
        path = TEST_DIR / name
        out = detect(model, path)
        print("---", name)
        print(json.dumps({k: out[k] for k in ("n_detections", "detections", "summary")}, indent=2))

    # Multi-onion: stitch two real test images; still real YOLO, not fake boxes.
    a = cv2.imread(str(TEST_DIR / SAMPLES[0]))
    b = cv2.imread(str(TEST_DIR / SAMPLES[2]))
    if a is None or b is None:
        print("ERROR: could not read stitch sources")
        return 1
    h = min(a.shape[0], b.shape[0])
    a = cv2.resize(a, (int(a.shape[1] * h / a.shape[0]), h))
    b = cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h))
    stitched = np.hstack([a, b])
    out = detect(model, stitched)
    print("--- stitched two test frames (multi-onion check)")
    print(json.dumps({k: out[k] for k in ("n_detections", "detections", "summary")}, indent=2))
    print("multi_n", out["n_detections"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
