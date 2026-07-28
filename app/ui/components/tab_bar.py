# 기본급여 / 추가급여 등 세그먼트 탭

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedTabBar(QWidget):
    # 탭을 고르면 currentChanged(index) 발생

    currentChanged = pyqtSignal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for i, label in enumerate(labels):
            button = QPushButton(label)
            button.setObjectName("Tab")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(button, i)
            layout.addWidget(button)
        layout.addStretch(1)

        self._group.idClicked.connect(self.currentChanged.emit)
        self.set_current(0)

    def set_current(self, index: int) -> None:
        button = self._group.button(index)
        if button:
            button.setChecked(True)

    def current(self) -> int:
        return self._group.checkedId()
