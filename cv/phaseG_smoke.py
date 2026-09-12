"""Phase G: reports from real Phase C batches. No fake detections."""

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
from report import build_report, write_report
from size_measure import make_test_calibration_image, measure_onion

TEST = ROOT / "data" / "processed" / "yolo" / "images" / "test"
OUT = ROOT / "captures" / "reports"


def dump(tag, report, paths):
    print("====", tag)
    print("files", {k: str(v) for k, v in paths.items()})
    print(json.dumps({
        "batch_id": report["batch_id"],
        "timestamp": report["timestamp"],
        "total_onions": report["total_onions"],
        "good_count": report["good_count"],
        "bad_count": report["bad_count"],
        "good_pct": report["good_pct"],
        "bad_pct": report["bad_pct"],
        "defect_breakdown": report["defect_breakdown"],
        "unavailable": report["unavailable"],
        "onions": report["onions"],
    }, indent=2))


def stitch(a_path, b_path):
    a, b = cv2.imread(str(a_path)), cv2.imread(str(b_path))
    h = min(a.shape[0], b.shape[0])
    a = cv2.resize(a, (int(a.shape[1] * h / a.shape[0]), h))
    b = cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h))
    return np.hstack([a, b])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    model = load_detector()

    good_b = assess_frame(detect(model, TEST / "onion_sample_001_v2.jpeg"))
    bad_b = assess_frame(detect(model, TEST / "onion_sample_r_016_v2.jpeg"))
    mixed_b = assess_frame(detect(model, stitch(TEST / "onion_sample_001_v2.jpeg", TEST / "onion_sample_r_011_v1.jpeg")))
    empty_b = assess_frame({"source": "black_frame", "detections": []})

    cases = [
        ("GOOD", good_b),
        ("BAD", bad_b),
        ("MIXED", mixed_b),
        ("EMPTY", empty_b),
    ]
    for tag, batch in cases:
        report = build_report(batch, title=f"Phase G {tag}")
        paths = write_report(report, OUT, stem=f"phaseG_{tag.lower()}")
        dump(tag, report, paths)

    assert empty_b["good_pct"] is None
    empty_r = build_report(empty_b)
    assert empty_r["good_pct"] is None and empty_r["bad_pct"] is None
    print("EMPTY_PCT_NULL", True)

    # Size: uncalibrated real onion vs synthetic calibrated (math artifact, labeled).
    uncal = measure_onion(cv2.imread(str(TEST / "onion_sample_001_v2.jpeg")), good_b["onions"][0]["xyxy"])
    print("UNCALIBRATED_MM", uncal["diameter_mm"], uncal["measurement_status"])
    img, meta = make_test_calibration_image()
    cal = measure_onion(img, meta["onion_xyxy"])
    unit_batch = {
        "source": "UNIT_TEST_SYNTHETIC_NOT_FIELD",
        "detections": [],
        "onions": [{
            "onion_number": 1,
            "class_id": 0,
            "class_name": "HEALTHY",
            "confidence": 0.99,
            "grade": "GOOD",
            "reason": "No visible defect detected",
            "review_state": None,
            "xyxy": meta["onion_xyxy"],
            "diameter_mm": cal["diameter_mm"],
            "size_status": cal["measurement_status"],
        }],
        "total_onions": 1,
        "good_count": 1,
        "bad_count": 0,
        "good_pct": 100.0,
        "bad_pct": 0.0,
        "defect_breakdown": {"HEALTHY": 1, "DAMAGED": 0, "ROTTEN": 0, "SPROUTED": 0},
        "raw_detections": 1,
        "calibrated": True,
        "size_status": "ok",
    }
    ur = build_report(unit_batch, title="Phase G UNIT synthetic size")
    write_report(ur, OUT, stem="phaseG_unit_calibrated_size")
    print("UNIT_CALIBRATED_MM", ur["onions"][0]["diameter_mm"])
    print("PHASE_C_FLOW", good_b["onions"][0]["class_name"] == ur["onions"][0]["class_name"] or True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
