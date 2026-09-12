"""Phase 9: FastAPI around cv.pipeline.freeze_assess / save_freeze.

Does not reimplement detection, grading, size, or report math.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from urllib.request import urlopen
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

from capture_utils import describe_capture, open_capture  # noqa: E402
from database import get_batch, initialize_database, list_batches, save_report  # noqa: E402
from onion_infer import load_detector  # noqa: E402
from pipeline import save_freeze  # noqa: E402

APPROVED_WEIGHTS = ROOT / "runs" / "fresh_yolov8n_293_final" / "weights" / "best.pt"
REPORT_DIR = ROOT / "captures" / "reports"
FRONTEND_DIR = ROOT / "frontend"

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


def _probe_camera_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="invalid address")
    try:
        urlopen(f"{parsed.scheme}://{parsed.netloc}/", timeout=5)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to mobile camera. Check that the phone and laptop are on the same Wi-Fi network and that IP Webcam is running.",
        ) from exc


def _grab_stream_frame(url: str) -> np.ndarray:
    _probe_camera_host(url)
    cap = open_capture(url)
    try:
        if not cap.isOpened():
            raise HTTPException(
                status_code=502,
                detail="Unable to connect to mobile camera. Check that the phone and laptop are on the same Wi-Fi network and that IP Webcam is running.",
            )
        ok, frame = cap.read()
        if not ok or frame is None or getattr(frame, "size", 0) == 0:
            raise HTTPException(
                status_code=502,
                detail="Unable to connect to mobile camera. Check that the phone and laptop are on the same Wi-Fi network and that IP Webcam is running.",
            )
        return frame
    finally:
        cap.release()


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
        _probe_camera_host(url)
    except HTTPException as exc:
        if exc.status_code == 400:
            raise
        return {
            "ok": False,
            "state": "CAMERA UNREACHABLE",
            "stream_url": url,
            "message": exc.detail,
        }
    cap = open_capture(url)
    try:
        if not cap.isOpened():
            return {
                "ok": False,
                "state": "CAMERA UNREACHABLE",
                "stream_url": url,
                "message": "Unable to connect to mobile camera. Check that the phone and laptop are on the same Wi-Fi network and that IP Webcam is running.",
            }
        ok, frame = cap.read()
        if not ok or frame is None:
            return {
                "ok": False,
                "state": "CAMERA UNREACHABLE",
                "stream_url": url,
                "message": "Unable to connect to mobile camera. Check that the phone and laptop are on the same Wi-Fi network and that IP Webcam is running.",
            }
        return {
            "ok": True,
            "state": "CAMERA CONNECTED",
            "stream_url": url,
            "info": describe_capture(cap),
        }
    finally:
        cap.release()


@app.get("/camera/snapshot")
def camera_snapshot(address: str) -> Response:
    url = _normalize_ipwebcam_url(address)
    frame = _grab_stream_frame(url)
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="could not encode frame")
    return Response(content=bytes(buf), media_type="image/jpeg")


@app.post("/camera/assess")
def camera_assess(body: CameraAddress) -> JSONResponse:
    if not _state["model_loaded"] or _state["model"] is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "model not loaded", "model_error": _state["model_error"]},
        )
    url = _normalize_ipwebcam_url(body.address)
    frame = _grab_stream_frame(url)
    stem = f"OQA-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    try:
        pack = save_freeze(_state["model"], frame, REPORT_DIR, stem=stem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"assessment failed: {type(exc).__name__}: {exc}",
        ) from exc
    return JSONResponse(content=_report_payload(pack))


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
