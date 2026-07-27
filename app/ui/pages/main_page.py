"""메인 화면 — 어떤 작업을 할지 고른다.

버튼 목록은 models.flows.FLOWS 에서 온다. 흐름이 늘어나면 이 파일은
고칠 필요가 없다.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from models.flows import FLOWS, FlowSpec
from ui.components.scroll_page import centered_scroll_page


class FlowButton(QFrame):
    """제목 + 설명 두 줄짜리 큼직한 선택 버튼."""

    clicked = pyqtSignal(object)  # FlowSpec

    def __init__(self, spec: FlowSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FlowButton")
        self._spec = spec
        self.setEnabled(spec.enabled)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if spec.enabled
            else Qt.CursorShape.ArrowCursor
        )

        title = QLabel(spec.menu_title)
        title.setObjectName("FlowButtonTitle")
        description = QLabel(spec.menu_description)
        description.setObjectName("FlowButtonDesc")
        description.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addWidget(description)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self.isEnabled()
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self._spec)
        super().mouseReleaseEvent(event)


class MainPage(QWidget):
    """flowRequested(FlowSpec) — 사용자가 작업을 골랐을 때."""

    flowRequested = pyqtSignal(object)  # FlowSpec

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageBody")

        page, column = centered_scroll_page(620)

        title = QLabel("무엇을 하시겠어요?")
        title.setObjectName("PageTitle")
        subtitle = QLabel("작업을 고르면 필요한 문서를 안내해 드립니다.")
        subtitle.setObjectName("PageSubtitle")

        column.addStretch(1)
        column.addWidget(title)
        column.addWidget(subtitle)
        column.addSpacing(10)
        for spec in FLOWS:
            button = FlowButton(spec)
            button.clicked.connect(self.flowRequested.emit)
            column.addWidget(button)
        column.addStretch(2)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
