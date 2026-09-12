"""One MVP demo command: live stream or a frozen image through the same pipeline.

  python cv/demo.py --preview
  python cv/demo.py --no-preview --freeze-after 1
  python cv/demo.py --image captures/phaseH_live_raw.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

CV_DIR = Path(__file__).resolve().parent
ROOT = CV_DIR.parent
if str(CV_DIR) not in sys.path:
    sys.path.insert(0, str(CV_DIR))

from live_assess import DEFAULT_URL, run as run_live
from onion_infer import load_detector
from pipeline import save_freeze


def run_image(path: Path, out_dir: Path, imgsz: int, conf: float) -> int:
    frame = cv2.imread(str(path))
    if frame is None:
        print(f"ERROR: cannot read {path}", file=sys.stderr)
        return 1
    model = load_detector()
    stem = "phaseI_" + path.stem[:40]
    pack = save_freeze(model, frame, out_dir, stem=stem, imgsz=imgsz, conf=conf)
    r = pack["report"]
    print(json.dumps({
        "batch_id": r["batch_id"],
        "total_onions": r["total_onions"],
        "good_count": r["good_count"],
        "bad_count": r["bad_count"],
        "good_pct": r["good_pct"],
        "bad_pct": r["bad_pct"],
        "defect_breakdown": r["defect_breakdown"],
        "size_status": r.get("size_status"),
        "unavailable": r.get("unavailable"),
        "html": str(pack["paths"]["html"]),
        "json": str(pack["paths"]["json"]),
    }, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--image", type=Path, default=None)
    p.add_argument("--imgsz", type=int, default=416)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--infer-every", type=int, default=4)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--no-preview", action="store_true")
    p.add_argument("--freeze-after", type=int, default=None)
    p.add_argument("--duration", type=float, default=None)
    p.add_argument("--save-dir", type=Path, default=ROOT / "captures" / "reports")
    args = p.parse_args()
    if args.image:
        return run_image(args.image, args.save_dir, args.imgsz, args.conf)
    preview = False if args.no_preview else True
    print("SPACE freeze (opens HTML report)  S save  Q quit")
    print("stream", args.url)
    return run_live(
        args.url,
        imgsz=args.imgsz,
        infer_every=args.infer_every,
        conf=args.conf,
        preview=preview,
        duration=args.duration,
        save_dir=args.save_dir,
        freeze_after=args.freeze_after,
    )


if __name__ == "__main__":
    raise SystemExit(main())
