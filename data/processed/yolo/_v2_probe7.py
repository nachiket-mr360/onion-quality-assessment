"""Confirm the prepared splits are tracked by git (so a rebuild is recoverable)."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
out = subprocess.run(
    ["git", "ls-files", "data/processed/yolo/images", "data/processed/yolo/labels"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=True,
).stdout.split()

norm = [x.replace("\\", "/") for x in out]
print(f"tracked prepared files: {len(norm)}")
for label, needle in (
    ("images/train", "/images/train/"),
    ("images/val", "/images/val/"),
    ("images/test", "/images/test/"),
    ("labels/train", "/labels/train/"),
    ("labels/val", "/labels/val/"),
    ("labels/test", "/labels/test/"),
):
    print(f"  {label}: {sum(1 for x in norm if needle in x)}")

untracked = subprocess.run(
    ["git", "ls-files", "--others", "data/processed/yolo/images", "data/processed/yolo/labels"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=True,
).stdout.split()
print(f"untracked prepared files: {len(untracked)}")
for x in untracked:
    print(f"  {x}")
