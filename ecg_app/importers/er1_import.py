"""Import ER1 R files (folder or USB drive) into the new data layout."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from ..core import er1_format as er1
from ..core.models import Device, Recording
from ..db.repository import Repository

R_NAME = re.compile(r"^(?:(\d{8,12}))?R(\d{14})$")


@dataclass
class ImportResult:
    imported: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def find_r_files(folder: Path) -> list[Path]:
    folder = Path(folder)
    try:
        return sorted(p for p in folder.iterdir() if p.is_file() and R_NAME.match(p.name))
    except OSError:
        return []


def candidate_roots() -> list[Path]:
    if sys.platform.startswith("win"):
        return [Path(f"{c}:/") for c in string.ascii_uppercase[3:] if os.path.exists(f"{c}:/")]
    roots = []
    for base in ("/media", "/run/media", "/mnt", "/Volumes"):
        b = Path(base)
        if b.is_dir():
            for p in b.rglob("*"):
                if p.is_dir() and len(p.relative_to(b).parts) <= 2:
                    roots.append(p)
    return roots


def detect_er1_drives(roots: Optional[Iterable[Path]] = None) -> list[Path]:
    """Return mounted volumes whose root holds ER1 R files."""
    return [r for r in (roots if roots is not None else candidate_roots()) if find_r_files(r)]


def import_r_files(repo: Repository, data_dir: Path, files: Iterable[Path], patient_id: int,
                   serial: Optional[str] = None,
                   progress: Optional[Callable[[int, int, str], None]] = None,
                   cancelled: Callable[[], bool] = lambda: False) -> ImportResult:
    files = list(files)
    res = ImportResult()
    data_dir = Path(data_dir)
    for i, f in enumerate(files):
        if cancelled():
            break
        if progress:
            progress(i, len(files), f.name)
        m = R_NAME.match(f.name)
        try:
            raw = f.read_bytes()
            er1.parse_trailer(raw)
            hdr = er1.parse_header(raw)
            stamp = m[2] if m else hdr.start.strftime("%Y%m%d%H%M%S")
            sn = (m[1] if m and m[1] else None) or serial or "unknown"
            ref = f"er1:{sn}:{stamp}"
            if repo.recordings.by("legacy_ref", ref) or repo.recordings.by("legacy_ref", f"vendor:rec:{sn}:{stamp}"):
                res.skipped.append(f.name)
                continue
            pcm = er1.decode_to_bytes(raw)
            dev = repo.devices.by("serial", sn) or repo.devices.add(Device(serial=sn))
            rel = Path("recordings") / str(patient_id)
            (data_dir / rel).mkdir(parents=True, exist_ok=True)
            raw_rel, pcm_rel = rel / f"{sn}_{stamp}.er1", rel / f"{sn}_{stamp}.pcm"
            shutil.copy2(f, data_dir / raw_rel)
            (data_dir / pcm_rel).write_bytes(pcm)
            start = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[8:10]}:{stamp[10:12]}:{stamp[12:14]}"
            repo.recordings.add(Recording(
                patient_id=patient_id, device_id=dev.id, start_time=start,
                duration_s=len(pcm) / 2 / er1.SAMPLE_RATE,
                raw_path=raw_rel.as_posix(), raw_sha256=hashlib.sha256(raw).hexdigest(),
                pcm_path=pcm_rel.as_posix(), pcm_sha256=hashlib.sha256(pcm).hexdigest(),
                legacy_ref=ref))
            res.imported.append(f.name)
        except (er1.ER1FormatError, OSError, AttributeError) as e:
            res.errors.append(f"{f.name}: {e}")
    if progress:
        progress(len(files), len(files), "")
    return res
