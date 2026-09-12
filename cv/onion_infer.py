"""Real YOLOv8 onion detection. Returns boxes/classes/conf only.

Grading lives in cv.grading — do not put GOOD/BAD rules here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from ultralytics import YOLO

_CV = Path(__file__).resolve().parent
if str(_CV) not in sys.path:
    sys.path.insert(0, str(_CV))

from grading import CLASS_NAMES, grade_onion, summarize_grades

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ROOT / "runs" / "fresh_yolov8n_293_final" / "weights" / "best.pt"


def load_detector(weights: Path | str | None = None, device: str = "cpu") -> YOLO:
    path = Path(weights) if weights else DEFAULT_WEIGHTS
    if not path.is_file():
        raise FileNotFoundError(f"checkpoint not found: {path}")
    model = YOLO(str(path))
    model.to(device)
    return model


def _xyxy(box) -> list[float]:
    xy = box.xyxy[0].tolist()
    return [float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3])]


def detect(
    model: YOLO,
    source: str | Path | np.ndarray,
    *,
    conf: float = 0.25,
    imgsz: int = 640,
    device: str = "cpu",
) -> dict[str, Any]:
    """Run YOLO on one image/frame. Multiple onions = multiple boxes."""
    results = model.predict(
        source=source,
        conf=conf,
        imgsz=imgsz,
        device=device,
        verbose=False,
        save=False,
    )
    result = results[0]
    names = result.names or CLASS_NAMES
    detections: list[dict[str, Any]] = []
    boxes = result.boxes
    if boxes is not None:
        for i, box in enumerate(boxes):
            class_id = int(box.cls[0])
            class_name = str(names.get(class_id, CLASS_NAMES.get(class_id, str(class_id))))
            conf = float(box.conf[0])
            graded = grade_onion(class_id=class_id, class_name=class_name, confidence=conf)
            detections.append(
                {
                    "onion_id": i + 1,
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": conf,
                    "xyxy": _xyxy(box),
                    "grade": graded["grade"],
                    "reason": graded["reason"],
                    "review_state": graded["review_state"],
                }
            )
    summary = summarize_grades(detections)
    return {
        "source": None if isinstance(source, np.ndarray) else str(source),
        "n_detections": len(detections),
        "detections": detections,
        "summary": summary,
        "speed_ms": getattr(result, "speed", None),
    }


def detect_image(path: str | Path, **kwargs) -> dict[str, Any]:
    model = kwargs.pop("model", None)
    weights = kwargs.pop("weights", None)
    if model is None:
        model = load_detector(weights)
    return detect(model, Path(path), **kwargs)
