"""Compare prepared labels/images against pending labels and raw sources, byte-wise."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
YOLO = ROOT / "data" / "processed" / "yolo"

pending = {}
for p in (YOLO / "labels_pending").rglob("*.txt"):
    if p.name.lower() != "classes.txt":
        pending[p.stem] = p

diffs = []
same = 0
for split in ("train", "val", "test"):
    for p in sorted((YOLO / "labels" / split).glob("*.txt")):
        src = pending.get(p.stem)
        if src is None:
            diffs.append((split, p.stem, "<no pending source>", p.read_text().strip()))
            continue
        a = p.read_text(encoding="utf-8", errors="replace").strip()
        b = src.read_text(encoding="utf-8", errors="replace").strip()
        if a != b:
            diffs.append((split, p.stem, b, a))
        else:
            same += 1

print(f"identical prepared/pending labels: {same}")
print(f"differences: {len(diffs)}")
for d in diffs:
    print(f"  {d[0]}/{d[1]}\n    pending/corrected: {d[2]!r}\n    prepared        : {d[3]!r}")
