"""Phase 13 integration checks. Not part of the product API."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cv"))
sys.path.insert(0, str(ROOT / "backend"))

IMG = ROOT / "captures" / "reports" / "phaseI_healthy_frame.jpg"
WEIGHTS = ROOT / "runs" / "fresh_yolov8n_293_final" / "weights" / "best.pt"
BASE = "http://127.0.0.1:8000"
DB = ROOT / "data" / "onion_quality.db"


def get(path, timeout=30):
    with urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.headers.get_content_type(), r.read()


def post_assess(img: Path):
    boundary = "----p13"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{img.name}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + img.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = Request(BASE + "/assess", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    t0 = time.perf_counter()
    with urlopen(req, timeout=180) as r:
        raw = r.read()
        dt = time.perf_counter() - t0
        return r.status, json.loads(raw.decode()), dt


print("=== weights", WEIGHTS.is_file(), WEIGHTS)
print("=== image", IMG.is_file(), IMG)

# Test 1 — direct CV
import cv2
from onion_infer import load_detector
from pipeline import freeze_assess, save_freeze

t_load = time.perf_counter()
model = load_detector(WEIGHTS)
print("model_load_s", round(time.perf_counter() - t_load, 2))
frame = cv2.imread(str(IMG))
t_cv = time.perf_counter()
pack = freeze_assess(model, frame)
print("cv_freeze_s", round(time.perf_counter() - t_cv, 2))
rep = pack["report"]
print("CV", {k: rep.get(k) for k in ("batch_id", "total_onions", "good_count", "bad_count", "good_pct", "bad_pct", "calibrated", "size_status")})
print("CV onions", [{k: o.get(k) for k in ("onion_number", "class_id", "class_name", "confidence", "grade", "reason", "review_state", "diameter_mm", "measurement_status")} for o in rep.get("onions") or []])
assert WEIGHTS.name == "best.pt" and "fresh_yolov8n_293_final" in str(WEIGHTS)

# Test 2 health
st, ct, body = get("/health")
health = json.loads(body)
print("HEALTH", st, health)
assert health.get("model_loaded") is True
assert "fresh_yolov8n_293_final" in str(health.get("model_path"))
print("GET /", get("/")[0], get("/docs")[0])

# Test 3 API assess
st, api, dt = post_assess(IMG)
print("API_assess_s", round(dt, 2), "status", st)
print("API", {k: api.get(k) for k in ("batch_id", "total_onions", "good_count", "bad_count", "good_pct", "bad_pct", "calibrated", "size_status", "defect_breakdown")})
print("API saved", api.get("saved"))
assert st == 200
bid = api["batch_id"]
for o in api["onions"]:
    for k in ("onion_number", "class_name", "class_id", "confidence", "grade", "reason", "review_state", "diameter_mm", "measurement_status", "xyxy"):
        assert k in o, k

# Test 4 SQLite
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
brow = conn.execute("SELECT * FROM batches WHERE batch_id=?", (bid,)).fetchone()
orows = conn.execute("SELECT * FROM onion_results WHERE batch_id=?", (bid,)).fetchall()
print("DB batch", dict(brow) if brow else None)
print("DB onions", len(orows))
assert brow is not None
assert brow["total_onions"] == api["total_onions"]
assert brow["good_count"] == api["good_count"]
assert brow["bad_count"] == api["bad_count"]
assert abs(float(brow["good_pct"]) - float(api["good_pct"])) < 1e-6
assert abs(float(brow["bad_pct"]) - float(api["bad_pct"])) < 1e-6
assert len(orows) == len(api["onions"])
for api_o, db_o in zip(api["onions"], orows):
    assert db_o["class_name"] == api_o["class_name"]
    assert db_o["class_id"] == api_o["class_id"]
    assert db_o["grade"] == api_o["grade"]
    assert db_o["reason"] == api_o["reason"]
    assert abs(float(db_o["confidence"]) - float(api_o["confidence"])) < 1e-9

# Test 10 duplicate
from database import save_report
n1 = conn.execute("SELECT COUNT(*) c FROM batches WHERE batch_id=?", (bid,)).fetchone()["c"]
ok = save_report(api, api.get("saved") or {})
n2 = conn.execute("SELECT COUNT(*) c FROM batches WHERE batch_id=?", (bid,)).fetchone()["c"]
n_on = conn.execute("SELECT COUNT(*) c FROM onion_results WHERE batch_id=?", (bid,)).fetchone()["c"]
print("DUP insert_again", ok, "batches", n2, "onions", n_on)
assert ok is False and n2 == 1 and n_on == len(api["onions"])

# Test 5 history
st, _, raw = get("/batches")
batches = json.loads(raw)
assert any(x["batch_id"] == bid for x in batches)
st, _, raw = get("/batches/" + bid)
hist = json.loads(raw)
print("HIST", hist["batch_id"], hist["total_onions"], len(hist.get("onions") or []))
assert hist["total_onions"] == api["total_onions"]
assert hist["good_count"] == api["good_count"]
assert hist["onions"][0]["class_name"] == api["onions"][0]["class_name"]

# Test 6 reports on disk
saved = api["saved"]
html_p = Path(saved["html"])
json_p = Path(saved["json"])
frame_p = Path(saved["frame"])
print("FILES", html_p.is_file(), json_p.is_file(), frame_p.is_file())
jrep = json.loads(json_p.read_text(encoding="utf-8"))
html = html_p.read_text(encoding="utf-8")
assert jrep["batch_id"] == bid
assert jrep["total_onions"] == api["total_onions"]
assert jrep["good_count"] == api["good_count"]
assert bid in html
assert str(api["total_onions"]) in html

# Test 7 media URLs
def media_url(p):
    return "/media/reports/" + Path(p).name

for pth in (html_p, json_p, frame_p):
    url = media_url(pth)
    assert not url.startswith("C:")
    st, ct, body = get(url)
    print("MEDIA", st, url, ct, len(body))
    assert st == 200

# invalid image
try:
    st, api_bad, _ = post_assess  # noqa
except Exception:
    pass
boundary = "----p13"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="x.txt"\r\n'
    f"Content-Type: text/plain\r\n\r\n"
    f"not-an-image\r\n--{boundary}--\r\n"
).encode()
req = Request(BASE + "/assess", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
try:
    urlopen(req, timeout=30)
    print("INVALID unexpected 2xx")
except HTTPError as e:
    print("INVALID", e.code, e.read()[:200])

print("REVIEW in this batch", [o.get("review_state") for o in api["onions"]])
print("PASS", bid)
conn.close()
