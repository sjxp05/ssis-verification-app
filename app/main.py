# 실행 진입점

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from services.table_writer import TableWriter
from services.jogyeon_value_extractor import ValueExtractor
from resources.styles import theme
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    try:
        app.setStyleSheet(theme.load_stylesheet())
    except theme.StylesheetError as error:
        QMessageBox.warning(None, "스타일 오류", str(error))
    window = MainWindow(value_extractor=ValueExtractor(), table_writer=TableWriter())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
