"""Read-only overlay of existing trial YOLO boxes. Does not modify labels or raw images."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LABELS = ROOT / "data" / "processed" / "yolo" / "labels_pending"
OUT = ROOT / "captures" / "phase4_visual_check"

NAMES = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}
FOLDER_CLASS = {
    "healthy": 0,
    "damaged": 1,
    "rotten": 2,
    "sprouted": 3,
}

TRIAL = [
    ("healthy", "onion_sample_001_v2"),
    ("healthy", "onion_sample_002_v1"),
    ("healthy", "onion_sample_002_v2"),
    ("healthy", "onion_sample_002_v3"),
    ("healthy", "onion_sample_002_v4"),
    ("damaged", "onion_sample_d_001_v2"),
    ("damaged", "onion_sample_d_001_v3"),
    ("damaged", "onion_sample_d_003_v1"),
    ("damaged", "onion_sample_d_004_v1"),
    ("rotten", "onion_sample_r_001_v1"),
    ("rotten", "onion_sample_r_002_v2"),
    ("rotten", "onion_sample_r_003_v1"),
    ("sprouted", "onion_sample_s_001_v1"),
    ("sprouted", "onion_sample_s_001_v2"),
    ("sprouted", "onion_sample_s_001_v4"),
]


def yolo_to_xyxy(line: str, w: int, h: int) -> tuple[int, int, int, int, int]:
    parts = line.split()
    cls = int(float(parts[0]))
    xc, yc, bw, bh = map(float, parts[1:5])
    x1 = int(round((xc - bw / 2) * w))
    y1 = int(round((yc - bh / 2) * h))
    x2 = int(round((xc + bw / 2) * w))
    y2 = int(round((yc + bh / 2) * h))
    return cls, x1, y1, x2, y2


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for folder, stem in TRIAL:
        img_path = RAW / folder / f"{stem}.jpeg"
        lab_path = LABELS / folder / f"{stem}.txt"
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"MISSING_IMAGE {img_path}")
            continue
        if not lab_path.is_file():
            print(f"MISSING_LABEL {lab_path}")
            continue
        h, w = img.shape[:2]
        vis = img.copy()
        text = lab_path.read_text(encoding="utf-8").strip()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        area_img = w * h
        print(f"\n{stem} folder={folder} size={w}x{h} lines={len(lines)}")
        for i, ln in enumerate(lines):
            cls, x1, y1, x2, y2 = yolo_to_xyxy(ln, w, h)
            bw, bh = x2 - x1, y2 - y1
            area = max(bw, 0) * max(bh, 0)
            clip = x1 <= 1 or y1 <= 1 or x2 >= w - 2 or y2 >= h - 2
            print(
                f"  box{i} cls={cls}/{NAMES.get(cls,'?')} folder_cls={FOLDER_CLASS[folder]} "
                f"xyxy=({x1},{y1},{x2},{y2}) area_frac={area/area_img:.3f} edge_clip={clip} line={ln}"
            )
            color = (0, 255, 0) if cls == FOLDER_CLASS[folder] else (0, 0, 255)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 4)
            cv2.putText(
                vis,
                f"{cls}:{NAMES.get(cls,'?')}",
                (max(x1, 5), max(y1 - 10, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )
        cv2.putText(vis, stem, (10, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        out_path = OUT / f"{stem}.jpg"
        cv2.imwrite(str(out_path), vis)
        thumb = cv2.resize(vis, (320, 240))
        thumbs.append(thumb)

    if thumbs:
        rows = []
        for i in range(0, len(thumbs), 5):
            chunk = thumbs[i : i + 5]
            while len(chunk) < 5:
                chunk.append(np.zeros_like(chunk[0]))
            rows.append(np.hstack(chunk))
        sheet = np.vstack(rows)
        sheet_path = OUT / "contact_sheet.jpg"
        cv2.imwrite(str(sheet_path), sheet)
        print(f"\ncontact_sheet {sheet_path} overlays={len(thumbs)}")


if __name__ == "__main__":
    main()
