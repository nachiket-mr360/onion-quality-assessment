from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8000"
IMG = ROOT / "captures" / "reports" / "phaseI_healthy_frame.jpg"
DB = ROOT / "data" / "onion_quality.db"


def get(path):
    with urlopen(BASE + path, timeout=30) as r:
        return r.status, r.read()


print("GET /", get("/")[0])
st, body = get("/health")
print("GET /health", st, body.decode())
print("GET /docs", get("/docs")[0])

conn = sqlite3.connect(str(DB))
n_before = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
print("batches_before", n_before)

boundary = "----live"
raw = IMG.read_bytes()
body = (
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"live.jpg\"\r\n"
    f"Content-Type: image/jpeg\r\n\r\n"
).encode() + raw + f"\r\n--{boundary}--\r\n".encode()
req = Request(BASE + "/live", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
t0 = time.perf_counter()
with urlopen(req, timeout=120) as r:
    live = json.loads(r.read().decode())
print("POST /live", round(time.perf_counter() - t0, 2), "s", {k: live.get(k) for k in ("ok", "live", "busy", "total_onions", "good_count", "bad_count")})
print("onions", [{k: o.get(k) for k in ("class_name", "confidence", "grade", "xyxy")} for o in live.get("onions") or []])
assert live.get("live") is True
assert "saved" not in live
assert live.get("onions")

n_after = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
print("batches_after_live", n_after)
assert n_after == n_before, "live must not insert batches"

req2 = Request(BASE + "/assess", data=body, method="POST")
req2.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
with urlopen(req2, timeout=120) as r:
    assess = json.loads(r.read().decode())
print("POST /assess", assess.get("batch_id"), assess.get("total_onions"), assess.get("saved"))
n_assess = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
print("batches_after_assess", n_assess)
assert n_assess == n_before + 1
assert assess.get("saved")
conn.close()
print("OK")
