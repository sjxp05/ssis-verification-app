# 메인 화면 (기본급여단가표/결제단가표 중 어떤 작업을 할지 선택)
#
# 버튼 목록은 models.flows.FLOWS 에서 import하기 때문에 흐름이 늘어나도 이 파일은 고칠 필요 X

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton
from models.flows import FLOWS, FlowSpec
from ui.components.scroll_page import centered_scroll_page
from ui.widgets.value_field import ValueField
from utils.date import yearConfig


class FlowCard(QFrame):
    clicked = pyqtSignal(FlowSpec)

    def __init__(self, flow: FlowSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MenuCard")
        self._flow = flow
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        top_line = QFrame()
        top_line.setObjectName("CardTopLine")
        top_line.setFixedHeight(2)

        line_layout = QHBoxLayout()
        line_layout.setContentsMargins(0, 0, 0, 0)

        line_layout.addStretch(1)
        line_layout.addWidget(top_line, 8)
        line_layout.addStretch(1)

        layout.addLayout(line_layout)

        content_wrapper = QWidget()
        content_wrapper.setObjectName("MenuCardContent")
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(28, 24, 28, 28)
        content_layout.setSpacing(16)

        # 1. 상단 아이콘, 화살표
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_label = QLabel(self._get_icon())
        icon_label.setObjectName("MenuIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        arrow_label = QLabel("→")
        arrow_label.setObjectName("MenuArrow")
        
        header_layout.addWidget(icon_label)
        header_layout.addStretch()
        header_layout.addWidget(arrow_label)

        # 2. 카드 제목, 설명
        title = QLabel(flow.menu_title)
        title.setObjectName("MenuTitle")
        
        desc = QLabel(flow.menu_description)
        desc.setObjectName("MenuDesc")
        desc.setWordWrap(True)
        desc.setMinimumHeight(45) # 텍스트 길이에 상관없이 카드 높이 맞춤

        # 3. Steps 안내
        steps_layout = QVBoxLayout()
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(8)
        
        for i, step_text in enumerate(flow.steps):
            step_row = QHBoxLayout()
            step_row.setContentsMargins(0, 0, 0, 0)
            
            badge = QLabel(str(i + 1))
            badge.setObjectName("StepBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            text = QLabel(step_text)
            text.setObjectName("MenuStepText")
            
            step_row.addWidget(badge)
            step_row.addWidget(text)
            step_row.addStretch()
            steps_layout.addLayout(step_row)

        # 4. 시작하기 버튼
        self.start_btn = QPushButton("시작하기 ›")
        self.start_btn.setObjectName("MenuStartBtn")
        self.start_btn.clicked.connect(lambda: self.clicked.emit(self._flow))

        if getattr(flow, "stub", False):
            self.start_btn.setEnabled(False)
            self.start_btn.setText("준비 중")


        # 5. 카드 전체 레이아웃 조립
        content_layout.addLayout(header_layout)
        content_layout.addWidget(title)
        content_layout.addWidget(desc)
        content_layout.addSpacing(4)
        content_layout.addLayout(steps_layout)
        content_layout.addStretch() # 버튼을 항상 맨 밑으로
        content_layout.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(content_wrapper)

    def _get_icon(self) -> str:
        # 메뉴 이름에 따라 이모지(아이콘) 다르게 배정
        if "대조" in self._flow.menu_title:
            return "✔️"
        elif "결제단가표" in self._flow.menu_title:
            return "📶"
        return "📄"


class MainPage(QWidget):
    # flowRequested(FlowSpec) — 사용자가 작업을 골랐을 때
    # yearChanged() — 사업년도를 바꿨을 때 (업로드 화면의 파일을 새로 고쳐야 함)

    flowRequested = pyqtSignal(FlowSpec)  # FlowSpec
    yearChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageBody")

        # 1. 헤더 (타이틀 & 서브타이틀)
        title = QLabel("무엇을 하시겠어요?")
        title.setObjectName("MainTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("기존에 업로드했던 문서는 각 메뉴의 파일 업로드 페이지에서 자동 연동할 수 있습니다.")
        subtitle.setObjectName("MainSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 2. 사업년도 필드
        year_container = QFrame()
        year_container.setObjectName("YearSelectorBox")
        year_layout = QHBoxLayout(year_container)
        year_layout.setContentsMargins(24, 10, 24, 10)
        year_layout.setSpacing(10)

        self.year_field = ValueField(
            key="system_year",
            label="사업년도",
            value=yearConfig.SYSTEM_YEAR,
            kind="year",
        )

        self.year_field.valueChanged.connect(
            lambda _key, value: yearConfig.set_system_year(value)
        )

        year_layout.addWidget(self.year_field)

        # 3. 카드
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(24)
        for flow in FLOWS:
            card = FlowCard(flow)
            card.clicked.connect(self.flowRequested.emit)
            cards_layout.addWidget(card)

        # 4. 인포박스
        info_box = QFrame()
        info_box.setObjectName("MainInfoBox")
        info_layout = QHBoxLayout(info_box)
        info_layout.setContentsMargins(20, 16, 20, 16)
        
        info_icon = QLabel("ⓘ")
        info_icon.setObjectName("InfoIcon")
        
        info_text = QLabel(
            "세 메뉴는 독립적으로 실행 가능합니다. 각 메뉴의 파일 업로드 페이지에서 '작업기록 불러오기'를 통해 동일 사업년도의 이전 파일을 자동으로 연동할 수 있습니다."
            " 단, 저장 경로를 변경할 경우 연동이 지원되지 않으며, 사용자가 업로드한 원본 파일의 내용은 프로그램에 별도로 수집되지 않습니다."
        )
        info_text.setObjectName("InfoText")
        info_text.setWordWrap(True)
        
        info_layout.addWidget(info_icon)
        info_layout.addWidget(info_text, 1)

        # 5. 전체 화면 가운데 정렬 조립
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(30)

        year_wrapper = QHBoxLayout()
        year_wrapper.addStretch(1)
        year_wrapper.addWidget(year_container)
        year_wrapper.addStretch(1)
        layout.addLayout(year_wrapper)

        layout.addSpacing(20)

        cards_container = QHBoxLayout()
        cards_container.addStretch(1)
        cards_container.addLayout(cards_layout)
        cards_container.addStretch(1)
        layout.addLayout(cards_container)
        
        layout.addSpacing(40)
        
        info_container = QHBoxLayout()
        info_container.addStretch(1)
        info_container.addWidget(info_box)
        info_container.addStretch(1)
        layout.addLayout(info_container)
        
        layout.addStretch(1)


    def _on_year_changed(self, _key: str, value: object) -> None:
        yearConfig.set_system_year(value)
        self.yearChanged.emit()
