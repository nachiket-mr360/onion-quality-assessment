"""Phase 10 verification. Not part of the API."""
from __future__ import annotations

import json
import py_compile
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "cv"))
sys.path.insert(0, str(ROOT))

print("A compile")
for p in [ROOT / "backend" / "main.py", ROOT / "backend" / "database.py", ROOT / "cv" / "demo.py"]:
    py_compile.compile(p, doraise=True)
    print(" compile_ok", p.name)

from fastapi.testclient import TestClient  # noqa: E402
from database import save_report  # noqa: E402
import main as api  # noqa: E402

print("B import app", bool(api.app))
api.initialize_database()
api._load_model()
print(" model_loaded", api._state["model_loaded"], api._state["model_error"])

client = TestClient(api.app)

print("C GET /health")
h = client.get("/health")
print(" ", h.status_code, h.json())
assert h.status_code == 200
assert h.json().get("model_loaded") is True

img = ROOT / "captures" / "reports" / "phaseI_healthy_frame.jpg"
print("D POST /assess", img)
with img.open("rb") as f:
    r = client.post("/assess", files={"file": ("phaseI_healthy_frame.jpg", f, "image/jpeg")})
print(" ", r.status_code)
assert r.status_code == 200, r.text
body = r.json()
print("E keys", sorted(k for k in body if k != "onions" and k != "saved"))
assert "batch_id" in body and "total_onions" in body
assert "good_count" in body and "bad_count" in body
print(" batch_id", body["batch_id"])
print(" totals", body["total_onions"], body["good_count"], body["bad_count"], body.get("good_pct"), body.get("bad_pct"))

db = ROOT / "data" / "onion_quality.db"
print("F db exists", db.is_file(), db)
assert db.is_file()

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
n_batch = conn.execute("SELECT COUNT(*) c FROM batches WHERE batch_id=?", (body["batch_id"],)).fetchone()["c"]
print("G batch rows for id", n_batch)
assert n_batch == 1
row = conn.execute("SELECT * FROM batches WHERE batch_id=?", (body["batch_id"],)).fetchone()
onions = conn.execute("SELECT * FROM onion_results WHERE batch_id=?", (body["batch_id"],)).fetchall()
print("H onion_results", len(onions), "api onions", len(body.get("onions") or []))
assert len(onions) == len(body.get("onions") or [])

print("I match")
assert row["batch_id"] == body["batch_id"]
assert row["total_onions"] == body["total_onions"]
assert row["good_count"] == body["good_count"]
assert row["bad_count"] == body["bad_count"]
assert row["good_pct"] == body["good_pct"]
assert row["bad_pct"] == body["bad_pct"]
for api_o, db_o in zip(body["onions"], onions):
    assert db_o["class_name"] == api_o["class_name"]
    assert db_o["class_id"] == api_o["class_id"]
    assert abs(float(db_o["confidence"]) - float(api_o["confidence"])) < 1e-9
    assert db_o["grade"] == api_o["grade"]
    assert db_o["reason"] == api_o["reason"]
    assert db_o["review_state"] == api_o["review_state"]
    print("  onion", db_o["onion_number"], db_o["class_name"], db_o["grade"], db_o["confidence"])

print("J GET /batches")
lb = client.get("/batches")
print(" ", lb.status_code, "n=", len(lb.json()))
assert lb.status_code == 200
assert any(b["batch_id"] == body["batch_id"] for b in lb.json())

print("K GET /batches/{id}")
one = client.get(f"/batches/{body['batch_id']}")
print(" ", one.status_code, "onions", len(one.json().get("onions") or []))
assert one.status_code == 200
assert one.json()["batch_id"] == body["batch_id"]

print("L duplicate save_report")
inserted = save_report(body, body.get("saved") or {})
print("  second insert returned", inserted)
n2 = conn.execute("SELECT COUNT(*) c FROM batches WHERE batch_id=?", (body["batch_id"],)).fetchone()["c"]
n_on = conn.execute("SELECT COUNT(*) c FROM onion_results WHERE batch_id=?", (body["batch_id"],)).fetchone()["c"]
print("  batches", n2, "onions", n_on)
assert inserted is False
assert n2 == 1
assert n_on == len(body["onions"])
conn.close()

print("M demo.py compile already ok")
print("PASS", body["batch_id"])
