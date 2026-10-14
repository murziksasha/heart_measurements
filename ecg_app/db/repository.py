"""Thin repository layer over sqlite3 for ecg_app models."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, fields
from typing import Optional, TypeVar

from ..core.models import AnalysisResult, CloudAccount, Device, Patient, Recording

T = TypeVar("T")


def _row_to(cls: type[T], row: Optional[sqlite3.Row]) -> Optional[T]:
    if row is None:
        return None
    names = {f.name for f in fields(cls)}
    return cls(**{k: row[k] for k in row.keys() if k in names})


class _Base:
    table = ""
    model: type = object
    key_skip = ("id", "created_at", "imported_at")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _values(self, obj) -> dict:
        d = asdict(obj)
        return {k: v for k, v in d.items() if k not in self.key_skip or (k != "id" and v is not None)}

    def add(self, obj):
        d = self._values(obj)
        cols = ",".join(d)
        q = ",".join("?" * len(d))
        with self.conn:
            cur = self.conn.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({q})", list(d.values()))
        return self.get(cur.lastrowid)

    def update(self, obj):
        if obj.id is None:
            raise ValueError("update requires id")
        d = self._values(obj)
        sets = ",".join(f"{k}=?" for k in d)
        with self.conn:
            self.conn.execute(f"UPDATE {self.table} SET {sets} WHERE id=?", [*d.values(), obj.id])
        return self.get(obj.id)

    def delete(self, id_: int) -> None:
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.table} WHERE id=?", (id_,))

    def get(self, id_: int):
        return _row_to(self.model, self.conn.execute(f"SELECT * FROM {self.table} WHERE id=?", (id_,)).fetchone())

    def list(self, where: str = "", params=(), order: str = "id"):
        sql = f"SELECT * FROM {self.table} {('WHERE ' + where) if where else ''} ORDER BY {order}"
        return [_row_to(self.model, r) for r in self.conn.execute(sql, params)]

    def by(self, column: str, value):
        return _row_to(self.model, self.conn.execute(
            f"SELECT * FROM {self.table} WHERE {column}=?", (value,)).fetchone())


class Patients(_Base):
    table, model = "patients", Patient


class Devices(_Base):
    table, model = "devices", Device


class Recordings(_Base):
    table, model = "recordings", Recording

    def for_patient(self, patient_id: int):
        return self.list("patient_id=?", (patient_id,), "start_time")


class AnalysisResults(_Base):
    table, model = "analysis_results", AnalysisResult

    def _values(self, obj):
        d = super()._values(obj)
        d["payload"] = json.dumps(d.get("payload") or {}, ensure_ascii=False)
        return d

    def get(self, id_):
        r = super().get(id_)
        return self._fix(r)

    def list(self, *a, **k):
        return [self._fix(r) for r in super().list(*a, **k)]

    def by(self, column, value):
        return self._fix(super().by(column, value))

    @staticmethod
    def _fix(r):
        if r is not None and isinstance(r.payload, str):
            r.payload = json.loads(r.payload)
        return r

    def for_recording(self, recording_id: int):
        return self.list("recording_id=?", (recording_id,))


class CloudAccounts(_Base):
    table, model = "cloud_account", CloudAccount

    def get(self, id_):
        r = super().get(id_)
        if r is not None:
            r.remember = bool(r.remember)
        return r


class Settings:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, key: str, default=None):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set(self, key: str, value) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                              (key, json.dumps(value, ensure_ascii=False)))


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.patients = Patients(conn)
        self.devices = Devices(conn)
        self.recordings = Recordings(conn)
        self.analysis = AnalysisResults(conn)
        self.accounts = CloudAccounts(conn)
        self.settings = Settings(conn)
