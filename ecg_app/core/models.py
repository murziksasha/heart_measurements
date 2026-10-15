from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Patient:
    name: str
    gender: Optional[str] = None  # "male" | "female" | None
    birthday: Optional[str] = None  # ISO date
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    contact: Optional[str] = None
    cloud_member_id: Optional[int] = None
    legacy_ref: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class Device:
    serial: str
    model: str = "ER1"
    hw_version: Optional[int] = None
    fw_version: Optional[int] = None
    bl_version: Optional[int] = None
    device_type: Optional[int] = None
    protocol_version: Optional[int] = None
    branch_code: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Recording:
    patient_id: int
    start_time: str  # ISO local datetime
    duration_s: float
    sample_rate: int = 125
    device_id: Optional[int] = None
    raw_path: Optional[str] = None  # relative to data dir
    raw_sha256: Optional[str] = None
    pcm_path: Optional[str] = None
    pcm_sha256: Optional[str] = None
    note: str = ""
    cloud_file_id: Optional[str] = None
    legacy_ref: Optional[str] = None
    imported_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class AnalysisResult:
    recording_id: int
    source: str  # "cloud" | "local"
    payload: dict = field(default_factory=dict)
    pdf_path: Optional[str] = None
    status: str = "done"
    legacy_ref: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class CloudAccount:
    """Credentials are never stored here; token_ref points to the OS keyring entry."""

    email: str
    server_user_id: Optional[int] = None
    token_ref: Optional[str] = None
    remember: bool = False
    id: Optional[int] = None
