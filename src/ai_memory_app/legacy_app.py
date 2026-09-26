from __future__ import annotations

import sys

from .data.database import get_default_db_path, initialize_database


def main() -> int:
    """Launch the preserved AI Memory Manager 1.x PySide6 interface."""
    db_path = get_default_db_path()
    initialize_database(db_path)
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        raise SystemExit("PySide6 is not installed. Run: pip install -r requirements.txt") from exc

    from .data.repository import MemoryRepository
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("AI 個人化記憶管理系統 Legacy")
    repository = MemoryRepository(db_path)
    window = MainWindow(repository)
    window.resize(1180, 760)
    window.show()
    return app.exec()
