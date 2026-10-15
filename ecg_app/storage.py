"""File housekeeping for the ecg_data layout."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from .db.repository import Repository


def _safe(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("_")[:40] or "patient"


def trash_patient_files(repo: Repository, data_dir: Path, patient) -> Path | None:
    """Move a patient's .er1/.pcm and report files into data_dir/trash/<timestamp>_<patient>/.
    Returns the trash folder, or None when there was nothing to move."""
    data_dir = Path(data_dir)
    rels: list[Path] = []
    for r in repo.recordings.for_patient(patient.id):
        rels += [Path(p) for p in (r.raw_path, r.pcm_path) if p]
        rels.append(Path("reports") / str(r.id))
        rels += [Path(a.pdf_path) for a in repo.analysis.for_recording(r.id) if a.pdf_path]
    todo = [p for p in dict.fromkeys(rels) if (data_dir / p).exists()]
    if not todo:
        return None
    dest = data_dir / "trash" / f"{datetime.now():%Y%m%d_%H%M%S}_{patient.id}_{_safe(patient.name)}"
    for rel in todo:
        src = data_dir / rel
        if not src.exists():  # already moved with its parent folder
            continue
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest / rel))
    pdir = data_dir / "recordings" / str(patient.id)
    if pdir.is_dir() and not any(pdir.iterdir()):
        pdir.rmdir()
    return dest
