"""Entry point: python -m ecg_app"""

from __future__ import annotations

import sys


def main(argv=None) -> int:
    from PySide6.QtWidgets import QApplication

    from .config import app_dir, data_dir, db_path
    from .db.migrations import connect
    from .db.repository import Repository
    from .ui import i18n
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv if argv is None else argv)
    d = data_dir()
    repo = Repository(connect(db_path(d)))
    i18n.set_language(repo.settings.get("ui_language") or repo.settings.get("language"))
    vendor = app_dir() / "Data"
    w = MainWindow(repo, d, db_path(d), vendor if vendor.exists() else None)
    w.show()
    if not repo.patients.list() and vendor.exists():
        w.open_migration()  # first run: offer vendor migration
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
