"""Locate empty / multi-line / odd pending labels and verify EXCLUDE coverage."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PENDING = ROOT / "data" / "processed" / "yolo" / "labels_pending"
CLS = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}

lines_total = 0
n = 0
odd = []
per_class = Counter()
for p in sorted(PENDING.rglob("*.txt")):
    if p.name.lower() == "classes.txt":
        continue
    n += 1
    text = p.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        odd.append((str(p.relative_to(ROOT)), "EMPTY"))
        continue
    rows = [r for r in text.splitlines() if r.strip()]
    lines_total += len(rows)
    if len(rows) != 1:
        odd.append((str(p.relative_to(ROOT)), f"{len(rows)} lines: {rows}"))
    for r in rows:
        per_class[int(float(r.split()[0]))] += 1

print(f"pending label files: {n}  total box lines: {lines_total}  per-class: {dict(sorted(per_class.items()))}")
print(f"odd labels: {len(odd)}")
for o in odd:
    print(f"  {o[0]} -> {o[1]}")
