"""Phase 2 camera proof: receive a camera/stream and read frames with OpenCV.

This is an infrastructure test. It is not onion detection.

Examples:
  python cv/camera_preview.py --list
  python cv/camera_preview.py --source 0 --frames 20 --save captures/camera_test.jpg
  python cv/camera_preview.py --source 0 --preview
  python cv/camera_preview.py --source http://192.168.0.12:8080/video --preview
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from capture_utils import describe_capture, open_capture

INDEX_PROBE_LIMIT = 5


def list_cameras() -> None:
    print("Probing local camera indexes 0-4 (DirectShow, then default backend)...")
    found = 0
    for index in range(INDEX_PROBE_LIMIT):
        cap = open_capture(str(index))
        opened = cap.isOpened()
        if not opened:
            print(f"index {index}: closed")
            cap.release()
            continue
        ok, frame = cap.read()
        info = describe_capture(cap)
        shape = None if frame is None else tuple(frame.shape)
        print(f"index {index}: opened=True read={ok} {info} shape={shape}")
        cap.release()
        found += 1
    print(f"opened_count={found}")
    if found == 0:
        print(
            "No local camera index opened. "
            "Connect a webcam/phone-as-webcam, or use an IP Webcam URL as --source."
        )


def run_capture(source: str, frames: int, save: Path | None, preview: bool) -> int:
    cap = open_capture(source)
    if not cap.isOpened():
        print(f"ERROR: could not open source {source!r}", file=sys.stderr)
        return 1

    print(f"opened source={source!r} {describe_capture(cap)}")
    read_ok = 0
    last_frame = None
    t0 = time.perf_counter()

    try:
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print(f"ERROR: failed to read frame {i} from {source!r}", file=sys.stderr)
                return 1
            read_ok += 1
            last_frame = frame
            i += 1

            if preview:
                cv2.imshow("Phase 2 camera preview (q to quit)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
            elif i >= frames:
                break
    finally:
        cap.release()
        if preview:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - t0
    fps = (read_ok / elapsed) if elapsed > 0 else 0.0
    print(
        f"frames_read={read_ok} last_shape={None if last_frame is None else tuple(last_frame.shape)} "
        f"elapsed_s={elapsed:.2f} approx_fps={fps:.2f}"
    )
    if save is not None:
        if last_frame is None:
            print(f"ERROR: no frame available to write {save}", file=sys.stderr)
            return 1
        save.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(save), last_frame):
            print(f"ERROR: failed to write {save}", file=sys.stderr)
            return 1
        print(f"saved {save} shape={last_frame.shape}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 OpenCV camera proof")
    parser.add_argument(
        "--source",
        default="0",
        help="Camera index (0) or stream URL (http://IP:8080/video)",
    )
    parser.add_argument("--list", action="store_true", help="Probe local camera indexes and exit")
    parser.add_argument("--frames", type=int, default=15, help="Frames to read in non-preview mode")
    parser.add_argument("--save", type=Path, default=None, help="Optional JPEG path for one frame")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show a live window (interactive). Default is headless read-and-exit.",
    )
    args = parser.parse_args()

    if args.list:
        list_cameras()
        return 0
    if args.frames < 1:
        print("ERROR: --frames must be >= 1", file=sys.stderr)
        return 1
    return run_capture(args.source, args.frames, args.save, args.preview)


if __name__ == "__main__":
    raise SystemExit(main())
