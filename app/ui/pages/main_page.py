# 메인 화면 (기본급여단가표/결제단가표 중 어떤 작업을 할지 선택)
#
# 버튼 목록은 models.flows.FLOWS 에서 import하기 때문에 흐름이 늘어나도 이 파일은 고칠 필요 X

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from models.flows import FLOWS, FlowSpec
from ui.components.scroll_page import centered_scroll_page
from ui.widgets.value_field import ValueField
from utils.date import yearConfig


class FlowButton(QFrame):
    # 작업 선택 버튼 (제목 + 설명 두 줄)

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
    # flowRequested(FlowSpec) — 사용자가 작업을 골랐을 때
    # yearChanged() — 사업년도를 바꿨을 때 (업로드 화면의 파일을 새로 고쳐야 함)

    flowRequested = pyqtSignal(object)  # FlowSpec
    yearChanged = pyqtSignal()

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

        column.addSpacing(10)
        year_field = ValueField(
            key="system_year",
            label="사업년도",
            value=yearConfig.SYSTEM_YEAR,
            kind="year",
        )
        year_field.valueChanged.connect(self._on_year_changed)
        column.addWidget(year_field, 0, Qt.AlignmentFlag.AlignHCenter)

        column.addStretch(2)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

    def _on_year_changed(self, _key: str, value: object) -> None:
        yearConfig.set_system_year(value)
        self.yearChanged.emit()
