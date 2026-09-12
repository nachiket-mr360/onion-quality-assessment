"""Live MJPEG → YOLO → overlap merge → GOOD/BAD overlay. CPU-friendly.

Stream URL is an argument / ONION_STREAM_URL. Not a permanent hardcoded IP.

Keys (preview): q quit | space freeze/unfreeze | s save snapshot
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

import cv2
import numpy as np

CV_DIR = Path(__file__).resolve().parent
ROOT = CV_DIR.parent
if str(CV_DIR) not in sys.path:
    sys.path.insert(0, str(CV_DIR))

from batch_assess import assess_frame
from capture_utils import describe_capture, open_capture
from onion_infer import detect, load_detector
from pipeline import freeze_assess
from report import write_report

DEFAULT_URL = os.environ.get("ONION_STREAM_URL", "http://192.168.167.38:8080/video")
GOOD_COLOR = (40, 180, 60)
BAD_COLOR = (40, 40, 220)
TEXT = (255, 255, 255)


def annotate(frame: np.ndarray, batch: dict, extra: str) -> np.ndarray:
    vis = frame.copy()
    for o in batch.get("onions") or []:
        x1, y1, x2, y2 = [int(v) for v in o["xyxy"]]
        color = GOOD_COLOR if o["grade"] == "GOOD" else BAD_COLOR
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        label = f"#{o['onion_number']} {o['class_name']} {o['confidence']:.2f} {o['grade']}"
        cv2.putText(vis, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    h, _w = vis.shape[:2]
    bar = [
        extra,
        f"onions={batch.get('total_onions', 0)} GOOD={batch.get('good_count', 0)} "
        f"BAD={batch.get('bad_count', 0)}  raw={batch.get('raw_detections', 0)}",
        "space=freeze  s=save  q=quit",
    ]
    y = 24
    for line in bar:
        cv2.putText(vis, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT, 2)
        y += 22
    return vis


def run(
    url: str,
    *,
    imgsz: int,
    infer_every: int,
    conf: float,
    preview: bool,
    duration: float | None,
    save_dir: Path,
    freeze_after: int | None,
) -> int:
    save_dir.mkdir(parents=True, exist_ok=True)
    print(f"opening stream {url!r}")
    cap = open_capture(url)
    if not cap.isOpened():
        print(f"ERROR: stream unavailable: {url}", file=sys.stderr)
        return 2
    print("opened", describe_capture(cap))

    weights = ROOT / "runs" / "baseline_yolov8n" / "weights" / "best.pt"
    if not weights.is_file():
        print(f"ERROR: model unavailable: {weights}", file=sys.stderr)
        cap.release()
        return 3
    model = load_detector(weights)
    print("model loaded", weights)

    last_batch: dict = {
        "onions": [],
        "total_onions": 0,
        "good_count": 0,
        "bad_count": 0,
        "raw_detections": 0,
    }
    frozen = False
    frozen_frame = None
    n_read = 0
    n_infer = 0
    infer_ms = []
    t_start = time.perf_counter()
    t_disp = t_start
    disp_n = 0

    try:
        while True:
            if duration is not None and (time.perf_counter() - t_start) >= duration:
                break
            ok, frame = cap.read()
            if not ok or frame is None:
                print("ERROR: connection lost or invalid frame", file=sys.stderr)
                return 4
            n_read += 1
            disp_n += 1

            if not frozen and (n_read % max(1, infer_every) == 0):
                t0 = time.perf_counter()
                raw = detect(model, frame, conf=conf, imgsz=imgsz, device="cpu")
                last_batch = assess_frame(raw)
                infer_ms.append((time.perf_counter() - t0) * 1000)
                n_infer += 1

            if freeze_after is not None and n_infer >= freeze_after and not frozen:
                frozen = True
                frozen_frame = frame.copy()
                pack = freeze_assess(model, frozen_frame, conf=conf, imgsz=imgsz)
                last_batch = pack["batch"]
                paths = write_report(pack["report"], save_dir)
                print("AUTO_FREEZE report", paths["html"])
                try:
                    webbrowser.open(paths["html"].as_uri())
                except Exception as e:
                    print("could not open report in browser:", e)
                print(json.dumps({
                    "total_onions": last_batch["total_onions"],
                    "good_count": last_batch["good_count"],
                    "bad_count": last_batch["bad_count"],
                    "good_pct": last_batch["good_pct"],
                    "bad_pct": last_batch["bad_pct"],
                    "raw_detections": last_batch["raw_detections"],
                    "calibrated": last_batch.get("calibrated"),
                    "size_status": last_batch.get("size_status"),
                    "onions": [
                        {k: o.get(k) for k in (
                            "onion_number", "class_name", "confidence", "grade", "reason",
                            "review_state", "diameter_mm", "raw_in_cluster",
                        )}
                        for o in last_batch["onions"]
                    ],
                }, indent=2))
                snap = save_dir / "phaseF_freeze.jpg"
                cv2.imwrite(str(snap), annotate(frozen_frame, last_batch, "FROZEN"))
                print("saved", snap)
                if not preview:
                    break

            now = time.perf_counter()
            fps = disp_n / max(1e-6, now - t_disp)
            if now - t_disp > 1.5:
                t_disp = now
                disp_n = 0
            avg_inf = sum(infer_ms[-5:]) / len(infer_ms[-5:]) if infer_ms else 0
            mode = "FROZEN" if frozen else "LIVE"
            extra = f"{mode} display~{fps:.1f}fps infer~{avg_inf:.0f}ms n_infer={n_infer} imgsz={imgsz}"
            vis = annotate(frozen_frame if frozen and frozen_frame is not None else frame, last_batch, extra)

            if preview:
                cv2.imshow("Onion live assess (q quit)", vis)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord(" "):
                    frozen = not frozen
                    if frozen:
                        frozen_frame = frame.copy()
                        pack = freeze_assess(model, frozen_frame, conf=conf, imgsz=imgsz)
                        last_batch = pack["batch"]
                        paths = write_report(pack["report"], save_dir)
                        print("FREEZE report", paths["html"])
                        try:
                            webbrowser.open(paths["html"].as_uri())
                        except Exception as e:
                            print("could not open report in browser:", e)
                        print("FREEZE", json.dumps({
                            "total": last_batch["total_onions"],
                            "good": last_batch["good_count"],
                            "bad": last_batch["bad_count"],
                            "pct": (last_batch["good_pct"], last_batch["bad_pct"]),
                            "size": last_batch.get("size_status"),
                        }))
                    else:
                        frozen_frame = None
                        print("LIVE")
                if key == ord("s"):
                    p = save_dir / f"phaseF_snap_{int(time.time())}.jpg"
                    cv2.imwrite(str(p), vis)
                    print("saved", p)
    finally:
        cap.release()
        if preview:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - t_start
    print(
        f"done reads={n_read} infers={n_infer} elapsed={elapsed:.1f}s "
        f"avg_infer_ms={sum(infer_ms)/len(infer_ms) if infer_ms else 0:.0f}"
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Live onion assess from MJPEG URL")
    p.add_argument("--url", default=DEFAULT_URL, help="MJPEG URL (or env ONION_STREAM_URL)")
    p.add_argument("--imgsz", type=int, default=416)
    p.add_argument("--infer-every", type=int, default=4)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--no-preview", action="store_true")
    p.add_argument("--duration", type=float, default=None)
    p.add_argument("--freeze-after", type=int, default=None, help="auto-freeze after N inferences")
    p.add_argument("--save-dir", type=Path, default=ROOT / "captures")
    args = p.parse_args()
    preview = True if args.preview else False if args.no_preview else sys.stdout.isatty()
    return run(
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
