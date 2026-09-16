"""Dump pending labels for the newly annotated groups."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PENDING = ROOT / "data" / "processed" / "yolo" / "labels_pending"
NEW = ("s_019", "s_020", "s_021", "s_022", "s_023", "d_021")

for p in sorted(PENDING.rglob("*.txt")):
    if p.name == "classes.txt":
        continue
    if any(k in p.stem for k in NEW):
        print(f"{p.parent.name}/{p.stem}: {p.read_text(encoding='utf-8').strip()!r}")
