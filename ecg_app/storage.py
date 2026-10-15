"""File housekeeping for the ecg_data layout."""

from __future__ import annotations

import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from .db.repository import Repository


def _safe(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("_")[:40] or "patient"


class TrashError(OSError):
    """Files could not be moved; everything already moved was put back."""

    def __init__(self, path, cause):
        super().__init__(f"{path}: {cause}")
        self.path = path
        self.cause = cause


def move_with_retry(src: Path, dst: Path, attempts: int = 10, delay: float = 0.1, mover=shutil.move) -> None:
    """shutil.move that retries on PermissionError (Windows file locks, AV scanners)."""
    for i in range(attempts):
        try:
            mover(str(src), str(dst))
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def trash_patient_files(repo: Repository, data_dir: Path, patient, mover=shutil.move,
                        attempts: int = 10, delay: float = 0.1) -> Path | None:
    """Move a patient's .er1/.pcm and report files into data_dir/trash/<timestamp>_<patient>/.
    Returns the trash folder, or None when there was nothing to move.
    All-or-nothing: on failure moved files are restored and TrashError is raised."""
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
    moved: list[Path] = []
    for rel in todo:
        src = data_dir / rel
        if not src.exists():  # already moved with its parent folder
            continue
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        try:
            move_with_retry(src, dest / rel, attempts, delay, mover)
        except OSError as e:
            for done in reversed(moved):
                try:
                    shutil.move(str(dest / done), str(data_dir / done))
                except OSError:
                    pass
            shutil.rmtree(dest, ignore_errors=True)
            raise TrashError(src, e) from e
        moved.append(rel)
    pdir = data_dir / "recordings" / str(patient.id)
    if pdir.is_dir() and not any(pdir.iterdir()):
        pdir.rmdir()
    return dest
