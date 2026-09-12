"""Phase C smoke: batch assessment on real inference. No training."""

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

TEST_DIR = ROOT / "data" / "processed" / "yolo" / "images" / "test"
SINGLE = TEST_DIR / "onion_sample_001_v2.jpeg"
BAD = TEST_DIR / "onion_sample_d_012_v1.jpeg"
ROTTEN = TEST_DIR / "onion_sample_r_011_v1.jpeg"


def dump(title: str, batch: dict) -> None:
    print("====", title)
    slim = {
        "source": batch.get("source"),
        "raw_detections": batch["raw_detections"],
        "final_onions": batch["final_onions"],
        "total_onions": batch["total_onions"],
        "good_count": batch["good_count"],
        "bad_count": batch["bad_count"],
        "good_pct": batch["good_pct"],
        "bad_pct": batch["bad_pct"],
        "defect_breakdown": batch["defect_breakdown"],
        "unavailable": batch["unavailable"],
        "onions": [
            {
                k: o[k]
                for k in (
                    "onion_number",
                    "class_id",
                    "class_name",
                    "confidence",
                    "grade",
                    "reason",
                    "xyxy",
                    "raw_in_cluster",
                    "cluster_classes",
                )
            }
            for o in batch["onions"]
        ],
    }
    print(json.dumps(slim, indent=2))


def stitch(path_a: Path, path_b: Path) -> np.ndarray:
    a, b = cv2.imread(str(path_a)), cv2.imread(str(path_b))
    if a is None or b is None:
        raise FileNotFoundError(f"stitch sources {path_a} {path_b}")
    h = min(a.shape[0], b.shape[0])
    a = cv2.resize(a, (int(a.shape[1] * h / a.shape[0]), h))
    b = cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h))
    return np.hstack([a, b])


def main() -> int:
    model = load_detector()

    dump("single GOOD " + SINGLE.name, assess_frame(detect(model, SINGLE)))
    dump("BAD overlapping " + BAD.name, assess_frame(detect(model, BAD)))

    frame = stitch(SINGLE, ROTTEN)
    dump("stitched multi-onion 001_v2 + r_011_v1", assess_frame(detect(model, frame)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
