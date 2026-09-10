"""Launch LabelImg on one raw class folder. Does not modify data/raw images."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLASSES = ROOT / "data" / "processed" / "yolo" / "classes.txt"
LABELS = ROOT / "data" / "processed" / "yolo" / "labels_pending"
ALLOWED = ("healthy", "damaged", "rotten", "sprouted")


def main() -> int:
    parser = argparse.ArgumentParser(description="Open LabelImg on one data/raw class folder")
    parser.add_argument("folder", choices=ALLOWED, help="Class folder under data/raw")
    args = parser.parse_args()

    image_dir = RAW / args.folder
    save_dir = LABELS / args.folder
    save_dir.mkdir(parents=True, exist_ok=True)

    if not image_dir.is_dir():
        print(f"ERROR: missing {image_dir}", file=sys.stderr)
        return 1
    if not CLASSES.is_file():
        print(f"ERROR: missing {CLASSES}", file=sys.stderr)
        return 1

    exe = shutil.which("labelImg") or shutil.which("labelImg.exe")
    if exe:
        cmd = [exe, str(image_dir), str(CLASSES), str(save_dir)]
    else:
        cmd = [sys.executable, "-m", "labelImg", str(image_dir), str(CLASSES), str(save_dir)]

    print("NOTE: set LabelImg format to YOLO before saving.")
    print("NOTE: do not write labels into data/raw.")
    print("running", cmd)
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
