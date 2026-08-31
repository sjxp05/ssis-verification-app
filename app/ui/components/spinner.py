# 회전하는 로딩 스피너

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class Spinner(QWidget):
    def __init__(self, size: int = 24, color: str = "#1a3a5c", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor(color)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.hide()

    def _rotate(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def start(self) -> None:
        self.show()
        self._timer.start(80)

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(self._color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        rect = QRectF(4, 4, self.width() - 8, self.height() - 8)
        painter.drawArc(rect, self._angle * 16, 270 * 16)
