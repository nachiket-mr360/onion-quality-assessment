"""Phase 2 YOLO inference proof using a standard pretrained model.

This is an infrastructure test only. It is NOT the onion quality model.
Do not treat COCO class labels as onion condition classes.

Examples:
  python cv/yolo_proof.py --source captures/camera_test.jpg --save captures/yolo_test.jpg
  python cv/yolo_proof.py --source 0 --frames 5 --save captures/yolo_camera.jpg
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
from ultralytics import YOLO

from capture_utils import describe_capture, open_capture, parse_source

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ROOT / "models" / "yolov8n.pt"


def load_model(weights: Path) -> YOLO:
    weights.parent.mkdir(parents=True, exist_ok=True)
    print(f"loading YOLO weights={weights}")
    return YOLO(str(weights))


def annotate(result) -> tuple:
    plotted = result.plot()
    names = result.names
    rows = []
    if result.boxes is not None and len(result.boxes) > 0:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            rows.append((names.get(cls_id, str(cls_id)), conf))
    return plotted, rows


def run_on_image(model: YOLO, source: Path, save: Path | None, preview: bool) -> int:
    if not source.exists():
        print(f"ERROR: image not found: {source}", file=sys.stderr)
        return 1
    results = model.predict(source=str(source), verbose=False)
    result = results[0]
    plotted, rows = annotate(result)
    print(f"image={source} detections={len(rows)}")
    for name, conf in rows:
        print(f"  {name} conf={conf:.3f}")
    if save is not None:
        save.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(save), plotted):
            print(f"ERROR: failed to write {save}", file=sys.stderr)
            return 1
        print(f"saved {save}")
    if preview:
        cv2.imshow("Phase 2 YOLO proof (q to quit)", plotted)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return 0


def run_on_capture(model: YOLO, source: str, frames: int, save: Path | None, preview: bool) -> int:
    cap = open_capture(source)
    if not cap.isOpened():
        print(f"ERROR: could not open source {source!r}", file=sys.stderr)
        return 1
    print(f"opened source={source!r} {describe_capture(cap)}")
    saved = False
    read_ok = 0
    t0 = time.perf_counter()
    try:
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print(f"ERROR: failed to read frame {i} from {source!r}", file=sys.stderr)
                return 1
            results = model.predict(source=frame, verbose=False)
            plotted, rows = annotate(results[0])
            read_ok += 1
            i += 1
            print(f"frame={i} detections={len(rows)}")
            for name, conf in rows[:8]:
                print(f"  {name} conf={conf:.3f}")
            if save is not None and not saved:
                save.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(save), plotted):
                    print(f"ERROR: failed to write {save}", file=sys.stderr)
                    return 1
                print(f"saved {save}")
                saved = True
            if preview:
                cv2.imshow("Phase 2 YOLO proof (q to quit)", plotted)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            elif i >= frames:
                break
    finally:
        cap.release()
        if preview:
            cv2.destroyAllWindows()
    elapsed = time.perf_counter() - t0
    fps = (read_ok / elapsed) if elapsed > 0 else 0.0
    print(f"frames_read={read_ok} elapsed_s={elapsed:.2f} approx_processing_fps={fps:.2f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 pretrained YOLO inference proof")
    parser.add_argument(
        "--source",
        required=True,
        help="Image path, camera index (0), or stream URL",
    )
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS, help="YOLO weights path")
    parser.add_argument("--frames", type=int, default=5, help="Camera frames in non-preview mode")
    parser.add_argument("--save", type=Path, default=None, help="Optional annotated JPEG path")
    parser.add_argument("--preview", action="store_true", help="Show a window")
    args = parser.parse_args()

    print("NOTE: pretrained COCO YOLO is an infrastructure test, not the onion model.")
    model = load_model(args.weights)

    parsed = parse_source(args.source)
    source_path = Path(args.source)
    if isinstance(parsed, str) and source_path.exists() and source_path.is_file():
        return run_on_image(model, source_path, args.save, args.preview)
    return run_on_capture(model, args.source, args.frames, args.save, args.preview)


if __name__ == "__main__":
    raise SystemExit(main())
