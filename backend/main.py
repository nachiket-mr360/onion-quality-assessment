"""Phase 9: FastAPI around cv.pipeline.freeze_assess / save_freeze.

Does not reimplement detection, grading, size, or report math.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
CV_DIR = ROOT / "cv"
BACKEND_DIR = Path(__file__).resolve().parent
for p in (str(BACKEND_DIR), str(CV_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from batch_assess import assess_frame  # noqa: E402
from capture_utils import open_capture  # noqa: E402
from database import get_batch, initialize_database, list_batches, save_report  # noqa: E402
from onion_infer import detect, load_detector  # noqa: E402
from pipeline import save_freeze  # noqa: E402

def _path_from_env(name: str, default: Path) -> Path:
    raw = (os.environ.get(name) or "").strip()
    return Path(raw) if raw else default


APPROVED_WEIGHTS = _path_from_env(
    "MODEL_PATH", ROOT / "runs" / "fresh_yolov8n_293_final" / "weights" / "best.pt"
)
REPORT_DIR = _path_from_env("REPORT_DIR", ROOT / "captures" / "reports")
FRONTEND_DIR = _path_from_env("FRONTEND_DIR", ROOT / "frontend")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

_state: dict[str, Any] = {
    "model": None,
    "model_loaded": False,
    "model_error": None,
    "weights": str(APPROVED_WEIGHTS),
}


def _load_model() -> None:
    try:
        if not APPROVED_WEIGHTS.is_file():
            raise FileNotFoundError(f"checkpoint not found: {APPROVED_WEIGHTS}")
        _state["model"] = load_detector(APPROVED_WEIGHTS)
        _state["model_loaded"] = True
        _state["model_error"] = None
    except Exception as exc:
        _state["model"] = None
        _state["model_loaded"] = False
        _state["model_error"] = f"{type(exc).__name__}: {exc}"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    _load_model()
    yield
    _release_stream()
    _state["model"] = None


app = FastAPI(
    title="Onion Quality Assessment API",
    description="Thin wrapper around the existing freeze-frame CV pipeline.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if _state["model_loaded"] else "degraded",
        "backend": "running",
        "model_loaded": bool(_state["model_loaded"]),
        "model_path": _state["weights"],
        "model_error": _state["model_error"],
    }


class CameraAddress(BaseModel):
    address: str = Field(..., min_length=1, max_length=200)


def _normalize_ipwebcam_url(address: str) -> str:
    raw = (address or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="invalid address")
    lower = raw.lower()
    if lower.startswith(("file:", "javascript:", "data:", "ftp:")):
        raise HTTPException(status_code=400, detail="invalid address")
    if raw.startswith("http://") or raw.startswith("https://"):
        url = raw
    else:
        host = raw.split("/")[0]
        if ":" not in host or " " in host:
            raise HTTPException(status_code=400, detail="invalid address")
        url = "http://" + host
    if "/video" not in url.rstrip("/").split("?", 1)[0]:
        url = url.rstrip("/") + "/video"
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="invalid address")
    return url


_UNREACHABLE = (
    "Unable to connect to mobile camera. Check that the phone and laptop are on the same Wi-Fi network and that IP Webcam is running."
)
_live_lock = threading.Lock()
_pump_lock = threading.Lock()
_pump: dict[str, Any] = {
    "url": None,
    "cap": None,
    "thread": None,
    "stop": threading.Event(),
    "frame": None,
    "jpeg": None,
    "ok": False,
}


def _release_stream() -> None:
    _stop_pump()


def _stop_pump() -> None:
    with _pump_lock:
        _pump["stop"].set()
        th = _pump.get("thread")
        cap = _pump.get("cap")
    if th is not None and th is not threading.current_thread():
        th.join(timeout=2.0)
    with _pump_lock:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        _pump["cap"] = None
        _pump["thread"] = None
        _pump["url"] = None
        _pump["frame"] = None
        _pump["jpeg"] = None
        _pump["ok"] = False
        _pump["stop"] = threading.Event()


def _pump_loop(url: str, stop: threading.Event, cap: cv2.VideoCapture) -> None:
    last_jpeg_t = 0.0
    while not stop.is_set():
        ok, frame = cap.read()
        if not ok or frame is None or getattr(frame, "size", 0) == 0:
            time.sleep(0.02)
            continue
        now = time.perf_counter()
        jpeg = None
        if now - last_jpeg_t >= 0.08:
            enc_ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if enc_ok:
                jpeg = bytes(buf)
                last_jpeg_t = now
        with _pump_lock:
            _pump["frame"] = frame
            _pump["ok"] = True
            if jpeg is not None:
                _pump["jpeg"] = jpeg


def _ensure_pump(url: str) -> None:
    with _pump_lock:
        th = _pump.get("thread")
        if _pump.get("url") == url and th is not None and th.is_alive() and _pump.get("cap") is not None:
            return
    _stop_pump()
    if not _tcp_reachable(url):
        raise HTTPException(status_code=502, detail=_UNREACHABLE)
    cap = open_capture(url)
    if not cap.isOpened():
        try:
            cap.release()
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=_UNREACHABLE)
    stop = threading.Event()
    th = threading.Thread(target=_pump_loop, args=(url, stop, cap), daemon=True)
    with _pump_lock:
        _pump["url"] = url
        _pump["cap"] = cap
        _pump["stop"] = stop
        _pump["thread"] = th
        _pump["frame"] = None
        _pump["jpeg"] = None
        _pump["ok"] = False
    th.start()


def _cached_frame(url: str, *, wait_s: float = 2.0) -> np.ndarray:
    _ensure_pump(url)
    deadline = time.perf_counter() + wait_s
    while time.perf_counter() < deadline:
        with _pump_lock:
            if _pump.get("url") == url and _pump.get("frame") is not None:
                return _pump["frame"].copy()
        time.sleep(0.03)
    raise HTTPException(status_code=502, detail=_UNREACHABLE)


def _cached_jpeg(url: str, *, wait_s: float = 2.0) -> bytes:
    _ensure_pump(url)
    deadline = time.perf_counter() + wait_s
    while time.perf_counter() < deadline:
        with _pump_lock:
            jpeg = _pump.get("jpeg")
            if _pump.get("url") == url and jpeg:
                return jpeg
        time.sleep(0.03)
    raise HTTPException(status_code=502, detail=_UNREACHABLE)


def _tcp_reachable(url: str, timeout_s: float = 2.0) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _live_onions(frame: np.ndarray) -> dict[str, Any]:
    raw = detect(_state["model"], frame, conf=0.25, imgsz=416, device="cpu")
    batch = assess_frame(raw)
    onions = []
    for o in batch.get("onions") or []:
        onions.append(
            {
                "onion_number": o.get("onion_number"),
                "class_id": o.get("class_id"),
                "class_name": o.get("class_name"),
                "confidence": o.get("confidence"),
                "xyxy": list(o.get("xyxy") or []),
                "grade": o.get("grade"),
                "reason": o.get("reason"),
                "review_state": o.get("review_state"),
            }
        )
    return {
        "ok": True,
        "live": True,
        "onions": onions,
        "total_onions": batch.get("total_onions", len(onions)),
        "good_count": batch.get("good_count", 0),
        "bad_count": batch.get("bad_count", 0),
    }


def _report_payload(pack: dict[str, Any]) -> dict[str, Any]:
    report = pack["report"]
    paths = pack.get("paths") or {}
    try:
        save_report(report, paths)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"database persistence failed: {type(exc).__name__}: {exc}",
        ) from exc
    payload = dict(report)
    payload["saved"] = {
        "html": str(paths["html"]) if paths.get("html") else None,
        "json": str(paths["json"]) if paths.get("json") else None,
        "frame": str(paths["frame"]) if paths.get("frame") else None,
    }
    return payload


def _decode_image(data: bytes) -> np.ndarray:
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None or getattr(frame, "size", 0) == 0:
        raise HTTPException(status_code=400, detail="invalid image: could not decode upload")
    return frame


@app.post("/assess")
async def assess(file: UploadFile = File(...)) -> JSONResponse:
    if not _state["model_loaded"] or _state["model"] is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "model not loaded",
                "model_error": _state["model_error"],
            },
        )
    data = await file.read()
    frame = _decode_image(data)
    stem = f"OQA-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    try:
        pack = save_freeze(_state["model"], frame, REPORT_DIR, stem=stem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"assessment failed: {type(exc).__name__}: {exc}",
        ) from exc

    return JSONResponse(content=_report_payload(pack))


@app.post("/camera/test")
def camera_test(body: CameraAddress) -> dict[str, Any]:
    url = _normalize_ipwebcam_url(body.address)
    try:
        _cached_frame(url)
    except HTTPException as exc:
        if exc.status_code == 400:
            raise
        return {
            "ok": False,
            "state": "CAMERA UNREACHABLE",
            "stream_url": url,
            "message": exc.detail if isinstance(exc.detail, str) else _UNREACHABLE,
        }
    return {
        "ok": True,
        "state": "CAMERA CONNECTED",
        "stream_url": url,
    }


@app.get("/camera/snapshot")
def camera_snapshot(address: str) -> Response:
    url = _normalize_ipwebcam_url(address)
    jpeg = _cached_jpeg(url)
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/camera/assess")
def camera_assess(body: CameraAddress) -> JSONResponse:
    if not _state["model_loaded"] or _state["model"] is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "model not loaded", "model_error": _state["model_error"]},
        )
    url = _normalize_ipwebcam_url(body.address)
    frame = _cached_frame(url)
    stem = f"OQA-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    try:
        pack = save_freeze(_state["model"], frame, REPORT_DIR, stem=stem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"assessment failed: {type(exc).__name__}: {exc}",
        ) from exc
    return JSONResponse(content=_report_payload(pack))


@app.post("/camera/live")
def camera_live(body: CameraAddress) -> JSONResponse:
    """Throttled visual detection only. Does not write reports or SQLite."""
    if not _state["model_loaded"] or _state["model"] is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "model not loaded", "model_error": _state["model_error"]},
        )
    url = _normalize_ipwebcam_url(body.address)
    if not _live_lock.acquire(blocking=False):
        return JSONResponse(content={"ok": True, "live": True, "busy": True, "onions": []})
    try:
        frame = _cached_frame(url)
        payload = _live_onions(frame)
        payload["busy"] = False
        payload["width"] = int(frame.shape[1])
        payload["height"] = int(frame.shape[0])
        return JSONResponse(content=payload)
    finally:
        _live_lock.release()


@app.post("/live")
async def live_frame(file: UploadFile = File(...)) -> JSONResponse:
    """Laptop/webcam JPEG live pass. No report, no database."""
    if not _state["model_loaded"] or _state["model"] is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "model not loaded", "model_error": _state["model_error"]},
        )
    if not _live_lock.acquire(blocking=False):
        return JSONResponse(content={"ok": True, "live": True, "busy": True, "onions": []})
    try:
        data = await file.read()
        frame = _decode_image(data)
        payload = _live_onions(frame)
        payload["busy"] = False
        return JSONResponse(content=payload)
    finally:
        _live_lock.release()


@app.get("/batches")
def batches() -> list[dict[str, Any]]:
    return list_batches()


@app.get("/batches/{batch_id}")
def batch_detail(batch_id: str) -> dict[str, Any]:
    row = get_batch(batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return row


@app.get("/")
def frontend_index() -> FileResponse:
    page = FRONTEND_DIR / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="frontend not found")
    return FileResponse(page)


app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
app.mount("/media/reports", StaticFiles(directory=str(REPORT_DIR)), name="report_media")
