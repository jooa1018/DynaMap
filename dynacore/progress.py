from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .data import CONCEPTS

DB_DIR = Path(os.getenv("DYNAMAP_DB_DIR", Path.home() / ".dynamap"))
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("DYNAMAP_DB_PATH", DB_DIR / "progress.db"))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS concept_progress (
                profile_id TEXT NOT NULL,
                concept_id TEXT NOT NULL,
                mastery REAL NOT NULL DEFAULT 25,
                studied_count INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                confusion INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT,
                last_seen_at TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (profile_id, concept_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                concept_id TEXT,
                correct INTEGER,
                score REAL,
                error_category TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )


def new_profile_id() -> str:
    return "local-" + uuid.uuid4().hex[:12]


def ensure_concept(profile_id: str, concept_id: str) -> None:
    if concept_id not in CONCEPTS:
        return
    with connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO concept_progress(profile_id, concept_id, mastery, updated_at) VALUES(?,?,?,?)",
            (profile_id, concept_id, 25, now_iso()),
        )


def _review_delay(correct: bool, mastery: float) -> timedelta:
    if not correct:
        return timedelta(days=1)
    if mastery >= 80:
        return timedelta(days=14)
    if mastery >= 60:
        return timedelta(days=7)
    if mastery >= 40:
        return timedelta(days=3)
    return timedelta(days=1)


def update_mastery(profile_id: str, concept_id: str, delta: float, correct: Optional[bool] = None, error_category: str = "", payload: Optional[Dict[str, Any]] = None) -> None:
    if concept_id not in CONCEPTS:
        return
    ensure_concept(profile_id, concept_id)
    with connect() as con:
        row = con.execute("SELECT * FROM concept_progress WHERE profile_id=? AND concept_id=?", (profile_id, concept_id)).fetchone()
        mastery = max(0, min(100, float(row["mastery"]) + delta))
        correct_inc = 1 if correct is True else 0
        wrong_inc = 1 if correct is False else 0
        next_review = (datetime.now() + _review_delay(bool(correct), mastery)).isoformat(timespec="seconds") if correct is not None else row["next_review_at"]
        con.execute(
            """
            UPDATE concept_progress
            SET mastery=?, correct_count=correct_count+?, wrong_count=wrong_count+?, next_review_at=?, last_seen_at=?, updated_at=?
            WHERE profile_id=? AND concept_id=?
            """,
            (mastery, correct_inc, wrong_inc, next_review, now_iso(), now_iso(), profile_id, concept_id),
        )
        con.execute(
            "INSERT INTO events(profile_id,event_type,concept_id,correct,score,error_category,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (profile_id, "mastery_update", concept_id, None if correct is None else int(correct), mastery, error_category, json.dumps(payload or {}, ensure_ascii=False), now_iso()),
        )


def mark_studied(profile_id: str, concept_id: str) -> None:
    if concept_id not in CONCEPTS:
        return
    ensure_concept(profile_id, concept_id)
    with connect() as con:
        con.execute(
            "UPDATE concept_progress SET studied_count=studied_count+1, last_seen_at=?, updated_at=?, mastery=MIN(100, mastery+1) WHERE profile_id=? AND concept_id=?",
            (now_iso(), now_iso(), profile_id, concept_id),
        )
        con.execute("INSERT INTO events(profile_id,event_type,concept_id,created_at) VALUES(?,?,?,?)", (profile_id, "studied", concept_id, now_iso()))


def set_confusion(profile_id: str, concept_id: str, value: bool) -> None:
    if concept_id not in CONCEPTS:
        return
    ensure_concept(profile_id, concept_id)
    with connect() as con:
        con.execute("UPDATE concept_progress SET confusion=?, updated_at=? WHERE profile_id=? AND concept_id=?", (1 if value else 0, now_iso(), profile_id, concept_id))
        con.execute("INSERT INTO events(profile_id,event_type,concept_id,payload_json,created_at) VALUES(?,?,?,?,?)", (profile_id, "confusion" if value else "confusion_removed", concept_id, json.dumps({"value": value}), now_iso()))


def log_quiz(profile_id: str, concept_id: str, correct: bool, qtype: str, error_category: str = "", payload: Optional[Dict[str, Any]] = None) -> None:
    update_mastery(profile_id, concept_id, 6 if correct else -10, correct=correct, error_category=error_category, payload=payload)
    with connect() as con:
        con.execute(
            "INSERT INTO events(profile_id,event_type,concept_id,correct,error_category,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (profile_id, f"quiz:{qtype}", concept_id, int(correct), error_category, json.dumps(payload or {}, ensure_ascii=False), now_iso()),
        )


def log_explanation(profile_id: str, concept_id: str, score: float, mode: str, payload: Optional[Dict[str, Any]] = None) -> None:
    delta = (score - 60) / 8
    update_mastery(profile_id, concept_id, delta, correct=score >= 70, error_category="개념 설명", payload=payload)
    with connect() as con:
        con.execute(
            "INSERT INTO events(profile_id,event_type,concept_id,score,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (profile_id, f"explain:{mode}", concept_id, score, json.dumps(payload or {}, ensure_ascii=False), now_iso()),
        )


def get_progress(profile_id: str) -> Dict[str, Dict[str, Any]]:
    init_db()
    with connect() as con:
        rows = con.execute("SELECT * FROM concept_progress WHERE profile_id=?", (profile_id,)).fetchall()
    return {r["concept_id"]: dict(r) for r in rows}


def get_confusion_ids(profile_id: str) -> List[str]:
    progress = get_progress(profile_id)
    return [cid for cid, row in progress.items() if row.get("confusion")]


def due_reviews(profile_id: str, limit: int = 8) -> List[str]:
    now = now_iso()
    with connect() as con:
        rows = con.execute(
            "SELECT concept_id FROM concept_progress WHERE profile_id=? AND next_review_at IS NOT NULL AND next_review_at<=? ORDER BY next_review_at LIMIT ?",
            (profile_id, now, limit),
        ).fetchall()
    return [r["concept_id"] for r in rows if r["concept_id"] in CONCEPTS]


def recent_events(profile_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    with connect() as con:
        rows = con.execute("SELECT * FROM events WHERE profile_id=? ORDER BY id DESC LIMIT ?", (profile_id, limit)).fetchall()
    return [dict(r) for r in rows]


def export_profile(profile_id: str) -> str:
    return json.dumps({"profile_id": profile_id, "progress": get_progress(profile_id), "events": recent_events(profile_id, 500), "exported_at": now_iso()}, ensure_ascii=False, indent=2)


def merge_imported_progress(profile_id: str, data: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    for cid in data.get("studied_concepts", []):
        if cid in CONCEPTS:
            mark_studied(profile_id, cid)
        else:
            warnings.append(f"존재하지 않는 개념 제거: {cid}")
    for cid in data.get("confusion_vault", []):
        if cid in CONCEPTS:
            set_confusion(profile_id, cid, True)
        else:
            warnings.append(f"존재하지 않는 헷갈림 개념 제거: {cid}")
    for cid, val in data.get("mastery", {}).items():
        if cid in CONCEPTS:
            ensure_concept(profile_id, cid)
            with connect() as con:
                con.execute("UPDATE concept_progress SET mastery=?, updated_at=? WHERE profile_id=? AND concept_id=?", (max(0, min(100, float(val))), now_iso(), profile_id, cid))
    return warnings
