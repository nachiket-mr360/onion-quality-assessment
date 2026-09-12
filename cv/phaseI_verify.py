"""Phase I verification through cv.pipeline (same path as demo). No training."""

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

from capture_utils import open_capture
from live_assess import DEFAULT_URL
from onion_infer import load_detector
from pipeline import save_freeze

TEST = ROOT / "data" / "processed" / "yolo" / "images" / "test"
OUT = ROOT / "captures" / "reports"


def summarize(tag, pack):
    r = pack["report"]
    print("====", tag)
    print(json.dumps({
        "total": r["total_onions"],
        "good": r["good_count"],
        "bad": r["bad_count"],
        "good_pct": r["good_pct"],
        "bad_pct": r["bad_pct"],
        "breakdown": r["defect_breakdown"],
        "size": r.get("size_status"),
        "unavailable": r.get("unavailable"),
        "html": str(pack["paths"]["html"]),
        "onions": [
            {k: o.get(k) for k in ("onion_number", "class_name", "confidence", "grade", "review_state", "diameter_mm")}
            for o in r["onions"]
        ],
    }, indent=2))
    return r


def stitch(a, b):
    ha, hb = a.shape[0], b.shape[0]
    h = min(ha, hb)
    a = cv2.resize(a, (int(a.shape[1] * h / ha), h))
    b = cv2.resize(b, (int(b.shape[1] * h / hb), h))
    return np.hstack([a, b])


def main() -> int:
    model = load_detector()
    OUT.mkdir(parents=True, exist_ok=True)

    empty = np.zeros((480, 640, 3), dtype=np.uint8)
    r0 = summarize("EMPTY_FILE", save_freeze(model, empty, OUT, "phaseI_empty"))
    assert r0["total_onions"] == 0 and r0["good_pct"] is None

    healthy = cv2.imread(str(TEST / "onion_sample_001_v2.jpeg"))
    rh = summarize("HEALTHY_FILE", save_freeze(model, healthy, OUT, "phaseI_healthy"))

    rotten = cv2.imread(str(TEST / "onion_sample_r_016_v2.jpeg"))
    rr = summarize("ROTTEN_FILE", save_freeze(model, rotten, OUT, "phaseI_rotten"))

    multi = stitch(healthy, rotten)
    rm = summarize("MULTI_FILE_STITCH_NOT_PHONE", save_freeze(model, multi, OUT, "phaseI_multi"))

    print("REPORT_EXISTS", (OUT / "phaseI_healthy.html").is_file(), (OUT / "phaseI_healthy.json").is_file())

    cap = open_capture(DEFAULT_URL)
    opened = cap.isOpened()
    ok, frame = cap.read() if opened else (False, None)
    cap.release()
    mean = None if frame is None else float(frame.mean())
    print("PHONE_STREAM", {"url": DEFAULT_URL, "opened": opened, "read": ok, "mean": mean})
    if opened and ok and frame is not None:
        rp = summarize("PHONE_LIVE_FRAME", save_freeze(model, frame, OUT, "phaseI_phone"))
        print("PHONE_HAS_ONIONS", rp["total_onions"] > 0)
    else:
        print("PHONE_STREAM_FAILED")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
