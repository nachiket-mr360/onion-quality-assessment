"""Phase 14 non-physical validation. No training. Uses existing test split + pipeline."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

CV_DIR = Path(__file__).resolve().parent
ROOT = CV_DIR.parent
if str(CV_DIR) not in sys.path:
    sys.path.insert(0, str(CV_DIR))

from batch_assess import assess_frame
from grading import CLASS_NAMES, LOW_CONFIDENCE
from onion_infer import detect, load_detector
from pipeline import freeze_assess, save_freeze
from report import build_report, write_report
from size_measure import detect_aruco_scale, make_test_calibration_image, measure_onion

TEST = ROOT / "data" / "processed" / "yolo" / "images" / "test"
LABELS = ROOT / "data" / "processed" / "yolo" / "labels" / "test"
OUT = ROOT / "captures" / "reports"
SUM_PATH = ROOT / "captures" / "reports" / "phase14_test_summary.json"
WEIGHTS = ROOT / "runs" / "fresh_yolov8n_293_final" / "weights" / "best.pt"

NAMES = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}


def gt_class(stem: str) -> str | None:
    p = LABELS / f"{stem}.txt"
    if not p.is_file():
        return None
    line = p.read_text(encoding="utf-8").strip().split()
    if not line:
        return None
    return NAMES.get(int(line[0]))


def stitch(a, b):
    h = min(a.shape[0], b.shape[0])
    a = cv2.resize(a, (int(a.shape[1] * h / a.shape[0]), h))
    b = cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h))
    return np.hstack([a, b])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    images = sorted(
        p for p in TEST.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    model = load_detector(WEIGHTS)
    per_image = []
    pred_vs_gt = []
    fail_cats = Counter()
    n_dets = 0
    n_review = 0
    class_pred = Counter()

    for path in images:
        raw = detect(model, path, conf=0.25, imgsz=640, device="cpu")
        batch = assess_frame(raw)
        n_dets += raw["n_detections"]
        gtc = gt_class(path.stem)
        preds = [d["class_name"] for d in raw["detections"]]
        for d in raw["detections"]:
            class_pred[d["class_name"]] += 1
            if d.get("review_state") == "REVIEW_REQUIRED":
                n_review += 1
        top = None
        if raw["detections"]:
            top = max(raw["detections"], key=lambda d: d["confidence"])
        mismatch = False
        if gtc and top and top["class_name"] != gtc:
            mismatch = True
            fail_cats[f"pred_{top['class_name']}_gt_{gtc}"] += 1
        if raw["n_detections"] == 0:
            fail_cats["no_detection"] += 1
        elif raw["n_detections"] > 1:
            fail_cats["multi_box"] += 1
        per_image.append(
            {
                "image": path.name,
                "gt_class": gtc,
                "n_detections": raw["n_detections"],
                "final_onions": batch["final_onions"],
                "predictions": [
                    {
                        "class_name": d["class_name"],
                        "confidence": round(float(d["confidence"]), 4),
                        "grade": d["grade"],
                        "review_state": d["review_state"],
                    }
                    for d in raw["detections"]
                ],
                "top_class": None if top is None else top["class_name"],
                "top_conf": None if top is None else round(float(top["confidence"]), 4),
                "mismatch_vs_label": mismatch,
            }
        )
        pred_vs_gt.append((gtc, None if top is None else top["class_name"]))

    by_gt = Counter(g for g, _ in pred_vs_gt if g)
    match_by_gt = Counter()
    for g, p in pred_vs_gt:
        if g and p == g:
            match_by_gt[g] += 1

    # Size
    img, meta = make_test_calibration_image()
    cal = measure_onion(img, meta["onion_xyxy"])
    size_ok = (
        cal["calibrated"]
        and cal["diameter_mm"] is not None
        and abs(cal["diameter_mm"] - meta["expected_diameter_mm"]) < 0.05
    )
    real_img = cv2.imread(str(images[0]))
    uncal = measure_onion(real_img, [10, 10, 110, 110])
    no_ref = uncal["diameter_mm"] is None and uncal["measurement_status"] == "reference_not_detected"

    # Batch + report using first healthy-like, first rotten, first sprouted if present
    def first_with(prefix: str):
        for p in images:
            if p.name.startswith(prefix):
                return p
        return None

    healthy_p = first_with("onion_sample_0") or images[0]
    damaged_p = first_with("onion_sample_d_")
    rotten_p = first_with("onion_sample_r_")
    sprouted_p = first_with("onion_sample_s_")

    h_img = cv2.imread(str(healthy_p))
    r_img = cv2.imread(str(rotten_p)) if rotten_p else None
    multi = stitch(h_img, r_img) if r_img is not None else h_img
    pack = save_freeze(model, multi, OUT, "phase14_batch")
    report = pack["report"]
    html_ok = pack["paths"]["html"].is_file()
    json_ok = pack["paths"]["json"].is_file()
    frame_ok = pack["paths"]["frame"].is_file()
    values_match = (
        report["total_onions"] == pack["batch"]["total_onions"]
        and report["good_count"] == pack["batch"]["good_count"]
        and report["bad_count"] == pack["batch"]["bad_count"]
        and report["defect_breakdown"] == pack["batch"]["defect_breakdown"]
    )

    # Edge cases
    edges = {}
    try:
        freeze_assess(model, None)
        edges["invalid_frame"] = "did_not_raise"
    except (ValueError, TypeError, AttributeError) as e:
        edges["invalid_frame"] = f"raised {type(e).__name__}: {e}"

    empty = np.zeros((240, 320, 3), dtype=np.uint8)
    empty_pack = freeze_assess(model, empty)
    edges["empty_black"] = {
        "total_onions": empty_pack["report"]["total_onions"],
        "unavailable": empty_pack["report"]["unavailable"],
        "good_pct": empty_pack["report"]["good_pct"],
        "size_status": empty_pack["report"].get("size_status"),
    }

    junk = np.full((100, 100, 3), 128, dtype=np.uint8)
    junk_pack = freeze_assess(model, junk)
    edges["nonsensical_gray"] = {
        "total_onions": junk_pack["report"]["total_onions"],
        "unavailable": junk_pack["report"]["unavailable"],
    }

    scale = detect_aruco_scale(h_img)
    edges["no_aruco_on_real_test_image"] = {
        "calibrated": scale["calibrated"],
        "measurement_status": scale["measurement_status"],
        "pixels_per_mm": scale["pixels_per_mm"],
    }

    low_conf_example = next(
        (
            row
            for row in per_image
            for d in row["predictions"]
            if d["confidence"] < LOW_CONFIDENCE
        ),
        None,
    )
    edges["low_confidence_observed_on_test"] = bool(low_conf_example)
    edges["low_confidence_example"] = None
    if low_conf_example:
        edges["low_confidence_example"] = {
            "image": low_conf_example["image"],
            "predictions": low_conf_example["predictions"],
        }

    summary = {
        "note": "Observational run on existing TEST split. Not a replacement for official evaluation metrics.",
        "weights": str(WEIGHTS),
        "n_test_images": len(images),
        "n_detections": n_dets,
        "n_review_required": n_review,
        "class_prediction_counts": dict(class_pred),
        "gt_image_counts": dict(by_gt),
        "top1_match_vs_label_file": {k: match_by_gt.get(k, 0) for k in by_gt},
        "obvious_failure_categories": dict(fail_cats),
        "per_image": per_image,
        "size": {
            "synthetic_calibrated": {
                "ok_math": size_ok,
                "diameter_mm": cal["diameter_mm"],
                "expected_mm": meta["expected_diameter_mm"],
                "pixels_per_mm": cal["pixels_per_mm"],
                "status": cal["measurement_status"],
            },
            "real_test_image_no_marker": {
                "diameter_mm": uncal["diameter_mm"],
                "status": uncal["measurement_status"],
                "unavailable_as_expected": no_ref,
            },
        },
        "batch_report": {
            "stem": "phase14_batch",
            "html": html_ok,
            "json": json_ok,
            "frame": frame_ok,
            "values_match_batch": values_match,
            "total_onions": report["total_onions"],
            "good_count": report["good_count"],
            "bad_count": report["bad_count"],
            "good_pct": report["good_pct"],
            "bad_pct": report["bad_pct"],
            "defect_breakdown": report["defect_breakdown"],
            "calibrated": report.get("calibrated"),
            "size_status": report.get("size_status"),
            "sources": {
                "healthy_like": healthy_p.name,
                "damaged": None if damaged_p is None else damaged_p.name,
                "rotten": None if rotten_p is None else rotten_p.name,
                "sprouted": None if sprouted_p is None else sprouted_p.name,
            },
        },
        "edges": edges,
        "official_eval_reminder": (
            "Training val curves in runs/fresh_yolov8n_293_final/results.csv remain the project's recorded metrics. "
            "This file is a Phase 14 observational dump, not a new accuracy claim."
        ),
    }
    SUM_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "per_image"}, indent=2))
    print("WROTE", SUM_PATH)
    print("IMAGES", len(images), "DETS", n_dets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
