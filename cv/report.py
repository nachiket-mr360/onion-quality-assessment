"""Digital quality report from Phase C batch output. No YOLO / no invented stats."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from grading import CLASS_NAMES


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_report(
    batch: dict[str, Any],
    *,
    batch_id: str | None = None,
    title: str = "Onion quality assessment",
) -> dict[str, Any]:
    onions = list(batch.get("onions") or [])
    total = int(batch.get("total_onions") or len(onions))
    good = int(batch.get("good_count") or 0)
    bad = int(batch.get("bad_count") or 0)
    breakdown = {name: 0 for name in CLASS_NAMES.values()}
    breakdown.update(batch.get("defect_breakdown") or {})
    rows = []
    for o in onions:
        rows.append(
            {
                "onion_number": o.get("onion_number"),
                "class_name": o.get("class_name"),
                "class_id": o.get("class_id"),
                "confidence": o.get("confidence"),
                "grade": o.get("grade"),
                "reason": o.get("reason"),
                "review_state": o.get("review_state"),
                "diameter_mm": o.get("diameter_mm"),
                "measurement_status": o.get("size_status") or o.get("measurement_status"),
                "xyxy": o.get("xyxy"),
            }
        )
    unavailable = batch.get("unavailable")
    if total <= 0:
        unavailable = unavailable or "no onions detected in this frame"
    return {
        "batch_id": batch_id or f"OQA-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}",
        "title": title,
        "timestamp": _now_iso(),
        "source": batch.get("source"),
        "total_onions": total,
        "good_count": good,
        "bad_count": bad,
        "good_pct": batch.get("good_pct") if total > 0 else None,
        "bad_pct": batch.get("bad_pct") if total > 0 else None,
        "defect_breakdown": breakdown,
        "onions": rows,
        "raw_detections": batch.get("raw_detections"),
        "calibrated": batch.get("calibrated"),
        "size_status": batch.get("size_status"),
        "unavailable": unavailable,
    }


def _fmt_pct(v) -> str:
    return "unavailable" if v is None else f"{v:.2f}%"


def _fmt_mm(v) -> str:
    return "unavailable" if v is None else f"{v:.2f} mm"


def report_html(report: dict[str, Any]) -> str:
    rows = []
    for o in report["onions"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(o['onion_number']))}</td>"
            f"<td>{html.escape(str(o['class_name']))}</td>"
            f"<td>{html.escape('' if o['confidence'] is None else f'{o['confidence']:.3f}')}</td>"
            f"<td>{html.escape(str(o['grade']))}</td>"
            f"<td>{html.escape(str(o['reason'] or ''))}</td>"
            f"<td>{html.escape(str(o['review_state'] or ''))}</td>"
            f"<td>{html.escape(_fmt_mm(o['diameter_mm']))}</td>"
            f"<td>{html.escape(str(o['measurement_status'] or 'n/a'))}</td>"
            "</tr>"
        )
    onion_table = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="8">No onions detected — percentages unavailable</td></tr>'
    )
    bd = report["defect_breakdown"]
    warn = (
        f"<p class='warn'>{html.escape(report['unavailable'])}</p>"
        if report.get("unavailable")
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{html.escape(report['title'])} {html.escape(report['batch_id'])}</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 24px; color: #111; }}
h1 {{ margin-bottom: 4px; }}
.meta, .summary, table {{ width: 100%; }}
.cards {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.card {{ border: 1px solid #ccc; padding: 12px 16px; min-width: 120px; }}
.good {{ border-color: #2a8; }}
.bad {{ border-color: #c44; }}
table {{ border-collapse: collapse; margin-top: 16px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
th {{ background: #f4f4f4; }}
.warn {{ color: #a40; }}
.foot {{ color: #666; font-size: 12px; margin-top: 24px; }}
</style></head><body>
<h1>{html.escape(report['title'])}</h1>
<p class="meta">Batch ID <b>{html.escape(report['batch_id'])}</b><br/>
Timestamp {html.escape(report['timestamp'])}<br/>
Source {html.escape(str(report.get('source') or 'frozen frame'))}<br/>
Onions assessed <b>{report['total_onions']}</b></p>
{warn}
<div class="cards">
<div class="card good">GOOD<br/><b>{report['good_count']}</b><br/>{_fmt_pct(report['good_pct'])}</div>
<div class="card bad">BAD<br/><b>{report['bad_count']}</b><br/>{_fmt_pct(report['bad_pct'])}</div>
<div class="card">HEALTHY<br/><b>{bd.get('HEALTHY', 0)}</b></div>
<div class="card">DAMAGED<br/><b>{bd.get('DAMAGED', 0)}</b></div>
<div class="card">ROTTEN<br/><b>{bd.get('ROTTEN', 0)}</b></div>
<div class="card">SPROUTED<br/><b>{bd.get('SPROUTED', 0)}</b></div>
</div>
<table>
<thead><tr><th>#</th><th>Class</th><th>Conf</th><th>Grade</th><th>Reason</th><th>Review</th><th>Diameter</th><th>Size status</th></tr></thead>
<tbody>
{onion_table}
</tbody></table>
<p class="foot">GOOD/BAD from visible class only. Diameter only if ArUco calibration succeeded.
RGB cannot detect hidden rot. Generated from Phase C batch assessment — not sample data.</p>
</body></html>
"""


def write_report(report: dict[str, Any], out_dir: Path, stem: str | None = None) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or report["batch_id"]
    html_path = out_dir / f"{stem}.html"
    json_path = out_dir / f"{stem}.json"
    html_path.write_text(report_html(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"html": html_path, "json": json_path}
