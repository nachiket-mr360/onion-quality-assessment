"""Frozen-frame batch assessment. No tracking. No YOLO.

Raw detections from onion_infer are clustered by box overlap so one
physical onion is not counted twice. Class inside a cluster uses locked
defect priority, not highest confidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from grading import CLASS_NAMES, PRIORITY, grade_onion

DEFAULT_IOU = 0.45


def _iou_xyxy(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _parent(parents: list[int], i: int) -> int:
    while parents[i] != i:
        parents[i] = parents[parents[i]]
        i = parents[i]
    return i


def cluster_detections(
    detections: Sequence[dict[str, Any]],
    iou_threshold: float = DEFAULT_IOU,
) -> list[list[dict[str, Any]]]:
    n = len(detections)
    parents = list(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if _iou_xyxy(detections[i]["xyxy"], detections[j]["xyxy"]) >= iou_threshold:
                pi, pj = _parent(parents, i), _parent(parents, j)
                if pi != pj:
                    parents[pj] = pi
    buckets: dict[int, list[dict[str, Any]]] = {}
    for i, det in enumerate(detections):
        buckets.setdefault(_parent(parents, i), []).append(det)
    return list(buckets.values())


def resolve_cluster(cluster: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not cluster:
        raise ValueError("empty cluster")
    winner = max(cluster, key=lambda d: PRIORITY.get(str(d["class_name"]).upper(), -1))
    name = str(winner["class_name"]).upper()
    conf = float(winner["confidence"])
    graded = grade_onion(class_id=int(winner["class_id"]), class_name=name, confidence=conf)
    same = [d for d in cluster if str(d["class_name"]).upper() == name]
    box_src = max(
        same,
        key=lambda d: (d["xyxy"][2] - d["xyxy"][0]) * (d["xyxy"][3] - d["xyxy"][1]),
    )
    confs = [float(d["confidence"]) for d in cluster]
    return {
        "class_id": graded["class_id"],
        "class_name": graded["class_name"],
        "confidence": graded["confidence"],
        "confidence_max_in_cluster": max(confs),
        "xyxy": list(box_src["xyxy"]),
        "grade": graded["grade"],
        "reason": graded["reason"],
        "review_state": graded["review_state"],
        "diameter_mm": graded["diameter_mm"],
        "size_used_for_grade": False,
        "raw_in_cluster": len(cluster),
        "cluster_classes": [str(d["class_name"]) for d in cluster],
    }


def _pct(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(100.0 * part / total, 2)


def assess_frame(
    raw_result: dict[str, Any],
    iou_threshold: float = DEFAULT_IOU,
) -> dict[str, Any]:
    raw = list(raw_result.get("detections") or [])
    clusters = cluster_detections(raw, iou_threshold=iou_threshold)
    onions: list[dict[str, Any]] = []
    for i, cluster in enumerate(clusters, start=1):
        item = resolve_cluster(cluster)
        item["onion_number"] = i
        onions.append(item)

    total = len(onions)
    good = sum(1 for o in onions if o["grade"] == "GOOD")
    bad = sum(1 for o in onions if o["grade"] == "BAD")
    breakdown = {name: 0 for name in CLASS_NAMES.values()}
    breakdown.update(Counter(o["class_name"] for o in onions))

    return {
        "source": raw_result.get("source"),
        "raw_detections": len(raw),
        "final_onions": total,
        "onions": onions,
        "total_onions": total,
        "good_count": good,
        "bad_count": bad,
        "good_pct": _pct(good, total),
        "bad_pct": _pct(bad, total),
        "defect_breakdown": breakdown,
        "iou_threshold": iou_threshold,
        "unavailable": None if total else "no onions detected in this frame",
    }
