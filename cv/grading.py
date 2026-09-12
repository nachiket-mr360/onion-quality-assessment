"""Onion GOOD/BAD grading — business logic only. No YOLO / no I/O.

Locked mapping:
  0 HEALTHY  -> GOOD
  1 DAMAGED  -> BAD
  2 ROTTEN   -> BAD
  3 SPROUTED -> BAD

If several class predictions apply to one assessment, pick the worst:
  ROTTEN > SPROUTED > DAMAGED > HEALTHY
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

CLASS_NAMES = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}
GRADE_BY_CLASS = {
    "HEALTHY": "GOOD",
    "DAMAGED": "BAD",
    "ROTTEN": "BAD",
    "SPROUTED": "BAD",
}
# Higher = worse / higher priority.
PRIORITY = {"ROTTEN": 3, "SPROUTED": 2, "DAMAGED": 1, "HEALTHY": 0}

REASON_BY_CLASS = {
    "HEALTHY": "No visible defect detected",
    "DAMAGED": "Visible damage detected",
    "ROTTEN": "Visible rot detected",
    "SPROUTED": "Visible sprouting detected",
}

# Not a third grade. Flag only; GOOD/BAD still comes from class.
LOW_CONFIDENCE = 0.50


def class_name_from_id(class_id: int) -> str:
    if class_id not in CLASS_NAMES:
        raise ValueError(f"unknown class_id {class_id}; locked set is {CLASS_NAMES}")
    return CLASS_NAMES[class_id]


def grade_class(class_name: str) -> tuple[str, str]:
    """Return (GOOD|BAD, reason) for a locked class name."""
    key = class_name.upper()
    if key not in GRADE_BY_CLASS:
        raise ValueError(f"unknown class {class_name!r}; locked set is {list(GRADE_BY_CLASS)}")
    grade = GRADE_BY_CLASS[key]
    return grade, REASON_BY_CLASS[key]


def grade_detection(class_id: int, class_name: str | None = None) -> dict[str, Any]:
    name = class_name_from_id(class_id) if class_name is None else class_name.upper()
    if CLASS_NAMES.get(class_id) and class_name is not None and name != CLASS_NAMES[class_id]:
        raise ValueError(f"class_id {class_id} is {CLASS_NAMES[class_id]}, not {class_name}")
    if class_name is not None:
        expected_id = next((i for i, n in CLASS_NAMES.items() if n == name), None)
        if expected_id is None:
            raise ValueError(f"unknown class_name {class_name!r}")
        if class_id != expected_id:
            raise ValueError(f"class_id {class_id} does not match class_name {class_name}")
    return grade_onion(class_id=class_id, class_name=name, confidence=None)


def grade_onion(
    *,
    class_id: int,
    confidence: float | None = None,
    class_name: str | None = None,
    diameter_mm: float | None = None,
    size_status: str | None = None,
    low_confidence: float = LOW_CONFIDENCE,
) -> dict[str, Any]:
    """Final GOOD/BAD from class only. Size is never used to change grade."""
    name = class_name_from_id(class_id) if class_name is None else str(class_name).upper()
    if name not in GRADE_BY_CLASS:
        raise ValueError(f"unknown class {name!r}")
    if CLASS_NAMES[class_id] != name:
        raise ValueError(f"class_id {class_id} is {CLASS_NAMES[class_id]}, not {name}")
    grade, reason = grade_class(name)
    review = None
    if confidence is not None and float(confidence) < low_confidence:
        review = "REVIEW_REQUIRED"
    return {
        "class_id": class_id,
        "class_name": name,
        "confidence": None if confidence is None else float(confidence),
        "grade": grade,
        "reason": reason,
        "review_state": review,
        "priority": PRIORITY[name],
        "diameter_mm": diameter_mm,
        "size_used_for_grade": False,
        "size_status": size_status,
    }


def worst_class(class_names: Iterable[str]) -> str | None:
    names = [n.upper() for n in class_names]
    if not names:
        return None
    return max(names, key=lambda n: PRIORITY[n] if n in PRIORITY else -1)


def summarize_grades(detections: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate one frozen frame. No tracking."""
    if not detections:
        return {
            "n": 0,
            "good": 0,
            "bad": 0,
            "worst_class": None,
            "frame_grade": None,
        }
    names = [str(d["class_name"]) for d in detections]
    worst = worst_class(names)
    good = sum(1 for d in detections if d.get("grade") == "GOOD")
    bad = sum(1 for d in detections if d.get("grade") == "BAD")
    return {
        "n": len(detections),
        "good": good,
        "bad": bad,
        "worst_class": worst,
        "frame_grade": GRADE_BY_CLASS[worst] if worst else None,
    }
