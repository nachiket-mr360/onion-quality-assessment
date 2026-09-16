"""Check whether raw/sprouted s_02x images correspond to the deleted rotten r_021/r_022 files."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
YOLO = ROOT / "data" / "processed" / "yolo"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(d: Path):
    out = {}
    for p in sorted(d.rglob("*")):
        if p.suffix.lower() in {".jpeg", ".jpg", ".png"}:
            out[sha(p)] = out.get(sha(p), []) + [str(p.relative_to(ROOT)).replace("\\", "/")]
    return out


h = collect(YOLO / "images")
for p in sorted(RAW.rglob("*")):
    if p.suffix.lower() in {".jpeg", ".jpg", ".png"}:
        d = sha(p)
        if d in h:
            print(f"{p.relative_to(ROOT)}  ==  {h[d]}")
