"""Single freeze-frame path: detect → merge → grade → optional size → report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from batch_assess import assess_frame
from onion_infer import detect
from report import build_report, write_report
from size_measure import detect_aruco_scale, measure_onion


def attach_size(frame: np.ndarray, batch: dict[str, Any]) -> dict[str, Any]:
    scale = detect_aruco_scale(frame)
    onions = []
    for o in batch.get("onions") or []:
        m = measure_onion(frame, o["xyxy"], scale=scale)
        item = dict(o)
        item["diameter_mm"] = m["diameter_mm"]
        item["size_status"] = m["measurement_status"]
        item["size_used_for_grade"] = False
        onions.append(item)
    out = dict(batch)
    out["onions"] = onions
    out["calibrated"] = bool(scale.get("calibrated"))
    out["pixels_per_mm"] = scale.get("pixels_per_mm")
    out["size_status"] = scale.get("measurement_status")
    return out


def freeze_assess(model, frame: np.ndarray, *, conf: float = 0.25, imgsz: int = 416) -> dict[str, Any]:
    if frame is None or getattr(frame, "size", 0) == 0:
        raise ValueError("invalid frame")
    raw = detect(model, frame, conf=conf, imgsz=imgsz, device="cpu")
    batch = attach_size(frame, assess_frame(raw))
    report = build_report(batch)
    return {"batch": batch, "report": report}


def save_freeze(
    model,
    frame: np.ndarray,
    out_dir: Path,
    stem: str,
    **kwargs,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pack = freeze_assess(model, frame, **kwargs)
    paths = write_report(pack["report"], out_dir, stem=stem)
    jpg = out_dir / f"{stem}_frame.jpg"
    cv2.imwrite(str(jpg), frame)
    pack["paths"] = {**paths, "frame": jpg}
    return pack
