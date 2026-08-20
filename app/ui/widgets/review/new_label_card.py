# 올해 새로 생긴 문구 하나. 적지 않으면 아무 일도 일어나지 않는다.

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from jogyeon_matcher.contracts.schemas import Decision, MatchItem
from ui.widgets.review.shared import SheetPreview, SheetSource, render


class NewLabelCard(QWidget):
    def __init__(self, item: MatchItem, target: SheetSource, parent=None):
        super().__init__(parent)
        self.item = item
        self._target = target
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        location = item.input_label.location
        head = QWidget()
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(10)

        self._toggle = QToolButton()
        self._toggle.setObjectName("ReviewToggle")
        self._toggle.setCheckable(True)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setText(
            f"▸  {item.input_label.raw}"
            + (f"   ({location.sheet} {location.a1})" if location else "")
        )
        self._toggle.clicked.connect(self._on_toggle)
        head_layout.addWidget(self._toggle, 1)

        self.edit = QLineEdit()
        self.edit.setObjectName("FieldInput")
        self.edit.setPlaceholderText(
            "필요하면 대조 파일에서 대응하는 문구를 적어 주세요"
        )
        self.edit.setMaximumWidth(320)
        head_layout.addWidget(self.edit)
        layout.addWidget(head)

        self._preview = SheetPreview("현재 파일")
        self._preview.setVisible(False)
        layout.addWidget(self._preview)

    def _on_toggle(self, opened: bool) -> None:
        text = self._toggle.text()
        self._toggle.setText(("▾" if opened else "▸") + text[1:])
        self._preview.setVisible(opened)
        if opened and not self._loaded:
            self._loaded = True
            render(self._preview, self._target, self.item.input_label.location, "현재")

    def decision(self, run_id: str) -> Decision | None:
        text = self.edit.text().strip()
        if not text:
            return None
        return Decision(
            run_id=run_id,
            item_id=self.item.item_id,
            action="manual_input",
            input_label=self.item.input_label.raw,
            manual_input=text,
        )
