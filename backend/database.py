"""SQLite persistence for existing pipeline report dicts. No recalculation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "onion_quality.db"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(path: Path | None = None) -> Path:
    db = path or DB_PATH
    conn = _connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS batches (
                batch_id TEXT PRIMARY KEY,
                timestamp TEXT,
                title TEXT,
                source TEXT,
                total_onions INTEGER,
                good_count INTEGER,
                bad_count INTEGER,
                good_pct REAL,
                bad_pct REAL,
                calibrated INTEGER,
                size_status TEXT,
                unavailable TEXT,
                html_path TEXT,
                json_path TEXT,
                frame_path TEXT
            );
            CREATE TABLE IF NOT EXISTS onion_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                onion_number INTEGER,
                class_name TEXT,
                class_id INTEGER,
                confidence REAL,
                grade TEXT,
                reason TEXT,
                review_state TEXT,
                diameter_mm REAL,
                measurement_status TEXT,
                xyxy TEXT,
                FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _null(v: Any) -> Any:
    return None if v is None else v


def save_report(report: dict[str, Any], paths: dict[str, Any] | None = None, path: Path | None = None) -> bool:
    """Insert report as-is. Returns True if inserted, False if batch_id already existed."""
    paths = paths or {}
    batch_id = report.get("batch_id")
    if not batch_id:
        raise ValueError("report missing batch_id")

    def _p(key: str) -> str | None:
        v = paths.get(key)
        return None if v is None else str(v)

    conn = _connect(path)
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO batches (
                batch_id, timestamp, title, source,
                total_onions, good_count, bad_count, good_pct, bad_pct,
                calibrated, size_status, unavailable,
                html_path, json_path, frame_path
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                batch_id,
                _null(report.get("timestamp")),
                _null(report.get("title")),
                _null(report.get("source")),
                _null(report.get("total_onions")),
                _null(report.get("good_count")),
                _null(report.get("bad_count")),
                _null(report.get("good_pct")),
                _null(report.get("bad_pct")),
                None if report.get("calibrated") is None else int(bool(report.get("calibrated"))),
                _null(report.get("size_status")),
                _null(report.get("unavailable")),
                _p("html"),
                _p("json"),
                _p("frame"),
            ),
        )
        if cur.rowcount == 0:
            conn.commit()
            return False
        for o in report.get("onions") or []:
            xy = o.get("xyxy")
            conn.execute(
                """
                INSERT INTO onion_results (
                    batch_id, onion_number, class_name, class_id, confidence,
                    grade, reason, review_state, diameter_mm, measurement_status, xyxy
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    batch_id,
                    _null(o.get("onion_number")),
                    _null(o.get("class_name")),
                    _null(o.get("class_id")),
                    _null(o.get("confidence")),
                    _null(o.get("grade")),
                    _null(o.get("reason")),
                    _null(o.get("review_state")),
                    _null(o.get("diameter_mm")),
                    _null(o.get("measurement_status")),
                    None if xy is None else json.dumps(xy),
                ),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_batches(path: Path | None = None) -> list[dict[str, Any]]:
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM batches ORDER BY timestamp DESC, batch_id DESC"
        ).fetchall()
        return [_batch_row(r) for r in rows]
    finally:
        conn.close()


def get_batch(batch_id: str, path: Path | None = None) -> dict[str, Any] | None:
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT * FROM batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if row is None:
            return None
        onions = conn.execute(
            "SELECT * FROM onion_results WHERE batch_id = ? ORDER BY onion_number, id",
            (batch_id,),
        ).fetchall()
        out = _batch_row(row)
        out["onions"] = [_onion_row(o) for o in onions]
        return out
    finally:
        conn.close()


def _batch_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("calibrated") is not None:
        d["calibrated"] = bool(d["calibrated"])
    return d


def _onion_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("xyxy"):
        d["xyxy"] = json.loads(d["xyxy"])
    else:
        d["xyxy"] = None
    return d
