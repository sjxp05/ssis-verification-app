from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.review.shared import WrapLabel


# 접었다 펴는 구획. 기본은 접힘 — 열지 않아도 되는 정보라는 뜻이다.
class Collapsible(QWidget):
    def __init__(self, title: str, hint: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._title = title
        self._toggle = QToolButton()
        self._toggle.setObjectName("ReviewToggle")
        self._toggle.setText(f"▸  {title}")
        self._toggle.setCheckable(True)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self._on_toggle)
        layout.addWidget(self._toggle)

        self._body = QWidget()
        self.body_layout = QVBoxLayout(self._body)
        self.body_layout.setContentsMargins(0, 0, 0, 6)
        self.body_layout.setSpacing(8)
        self._body.setVisible(False)
        layout.addWidget(self._body)

        if hint:
            note = WrapLabel(hint)
            note.setObjectName("ReviewSectionHint")
            self.body_layout.addWidget(note)

    def _on_toggle(self, opened: bool) -> None:
        self._toggle.setText(f"{'▾' if opened else '▸'}  {self._title}")
        self._body.setVisible(opened)

    def add(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)
