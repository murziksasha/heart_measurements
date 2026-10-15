"""Versioned schema migrations (PRAGMA user_version)."""

from __future__ import annotations

import sqlite3

MIGRATIONS: list[str] = [
    # v1
    """
    CREATE TABLE patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        gender TEXT CHECK (gender IN ('male','female') OR gender IS NULL),
        birthday TEXT,
        height_cm INTEGER,
        weight_kg INTEGER,
        contact TEXT,
        cloud_member_id INTEGER,
        legacy_ref TEXT UNIQUE,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial TEXT NOT NULL UNIQUE,
        model TEXT NOT NULL DEFAULT 'ER1',
        hw_version INTEGER, fw_version INTEGER, bl_version INTEGER,
        device_type INTEGER, protocol_version INTEGER, branch_code TEXT
    );
    CREATE TABLE recordings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL,
        start_time TEXT NOT NULL,
        duration_s REAL NOT NULL,
        sample_rate INTEGER NOT NULL DEFAULT 250,
        raw_path TEXT, raw_sha256 TEXT,
        pcm_path TEXT, pcm_sha256 TEXT,
        note TEXT NOT NULL DEFAULT '',
        cloud_file_id TEXT,
        legacy_ref TEXT UNIQUE,
        imported_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE (patient_id, device_id, start_time)
    );
    CREATE INDEX ix_recordings_patient ON recordings(patient_id, start_time);
    CREATE TABLE analysis_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
        source TEXT NOT NULL CHECK (source IN ('cloud','local')),
        status TEXT NOT NULL DEFAULT 'done',
        payload TEXT NOT NULL DEFAULT '{}',
        pdf_path TEXT,
        legacy_ref TEXT UNIQUE,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX ix_analysis_recording ON analysis_results(recording_id);
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
    -- No passwords/tokens here: token_ref names an OS keyring entry.
    CREATE TABLE cloud_account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        server_user_id INTEGER,
        token_ref TEXT,
        remember INTEGER NOT NULL DEFAULT 0
    );
    """,
    # v2: ER1 is 125 Hz (v1 data assumed 250 Hz and halved durations)
    """
    UPDATE recordings SET sample_rate = 125, duration_s = duration_s * 2 WHERE sample_rate = 250;
    """,
]

LATEST = len(MIGRATIONS)


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection, target: int = LATEST) -> int:
    v = current_version(conn)
    if v > LATEST:
        raise RuntimeError(f"database version {v} is newer than this app ({LATEST})")
    while v < target:
        script = MIGRATIONS[v]
        v += 1
        conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {v};\nCOMMIT;")
    return v


def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn
