"""Compare deleted raw r_021/r_022 blobs (from git HEAD) against everything currently on disk."""
from __future__ import annotations

import hashlib
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLS = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}

DELETED = [
    f"data/raw/rotten/onion_sample_r_02{n}_v{v}.jpeg" for n in (1, 2) for v in (1, 2, 3, 4)
]


def blob_sha(relpath: str) -> str:
    out = subprocess.run(
        ["git", "show", f"HEAD:{relpath}"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    return hashlib.sha256(out).hexdigest()


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


on_disk = defaultdict(list)
for base in ("data/raw", "data/processed/yolo/images"):
    for p in (ROOT / base).rglob("*"):
        if p.suffix.lower() in {".jpeg", ".jpg", ".png"}:
            on_disk[sha(p)].append(str(p.relative_to(ROOT)).replace("\\", "/"))

deleted_hashes = {}
for rel in DELETED:
    d = blob_sha(rel)
    deleted_hashes[rel] = d
    matches = on_disk.get(d, [])
    print(f"{rel}\n   sha={d[:16]}  matches_on_disk={matches}")

print("\n== mutual duplicates among deleted ==")
rev = defaultdict(list)
for rel, d in deleted_hashes.items():
    rev[d].append(rel)
for d, rels in rev.items():
    if len(rels) > 1:
        print(f"  {d[:16]}: {rels}")

print("\n== deleted vs labels_pending (git HEAD) ==")
for rel in DELETED:
    lab = rel.replace("data/raw/", "data/processed/yolo/labels_pending/").replace(".jpeg", ".txt")
    try:
        txt = subprocess.run(
            ["git", "show", f"HEAD:{lab}"], cwd=ROOT, capture_output=True, check=True
        ).stdout.decode()
    except subprocess.CalledProcessError:
        txt = "<absent>"
    print(f"  {lab}: {txt!r}")
