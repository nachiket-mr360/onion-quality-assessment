"""Phase E: grading engine on real inference + marked unit cases. No training."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CV_DIR = Path(__file__).resolve().parent
ROOT = CV_DIR.parent
if str(CV_DIR) not in sys.path:
    sys.path.insert(0, str(CV_DIR))

from batch_assess import assess_frame
from grading import grade_onion
from onion_infer import detect, load_detector

TEST = ROOT / "data" / "processed" / "yolo" / "images" / "test"


def show(title, obj):
    print("====", title)
    print(json.dumps(obj, indent=2, default=str))


def main() -> int:
    print("=== UNIT (not model output) ===")
    for cid, name in [(0, "HEALTHY"), (1, "DAMAGED"), (2, "ROTTEN"), (3, "SPROUTED")]:
        show(f"unit {name}", grade_onion(class_id=cid, class_name=name, confidence=0.9))
    tiny = grade_onion(class_id=0, confidence=0.91, diameter_mm=18.0, size_status="ok")
    assert tiny["grade"] == "GOOD" and tiny["size_used_for_grade"] is False
    show("size present does not flip GOOD", tiny)
    low = grade_onion(class_id=2, confidence=0.31, diameter_mm=None)
    assert low["grade"] == "BAD" and low["review_state"] == "REVIEW_REQUIRED"
    show("low conf ROTTEN still BAD + REVIEW", low)
    no_size = grade_onion(class_id=0, confidence=0.95, diameter_mm=None)
    assert no_size["diameter_mm"] is None
    show("size absent", no_size)

    model = load_detector()
    healthy = assess_frame(detect(model, TEST / "onion_sample_001_v2.jpeg"))
    rotten = assess_frame(detect(model, TEST / "onion_sample_r_016_v2.jpeg"))
    overlap = assess_frame(detect(model, TEST / "onion_sample_d_012_v1.jpeg"))
    show("REAL HEALTHY 001_v2", {
        "raw": healthy["raw_detections"], "final": healthy["final_onions"],
        "onions": healthy["onions"], "good": healthy["good_count"], "bad": healthy["bad_count"],
    })
    show("REAL ROTTEN r_016_v2", {
        "raw": rotten["raw_detections"], "final": rotten["final_onions"],
        "onions": rotten["onions"],
    })
    show("REAL overlap d_012_v1 (DAMAGED image; model class may not be DAMAGED)", {
        "raw": overlap["raw_detections"], "final": overlap["final_onions"],
        "onions": overlap["onions"],
    })

    produced = {o["class_name"] for b in (healthy, rotten, overlap) for o in b["onions"]}
    print("MODEL_CLASSES_SEEN", sorted(produced))
    print("MODEL_LIMITATION_DAMAGED", "DAMAGED" not in produced)
    print("MODEL_LIMITATION_SPROUTED", "SPROUTED" not in produced)
    print("PHASE_C_COUNTS_OK", healthy["final_onions"] == 1 and overlap["raw_detections"] >= overlap["final_onions"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
