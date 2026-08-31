# 단가표 화면 오른쪽 검증 사이드 패널
#
# - 상단: PASS / FAIL n건 요약 배지
# - 가운데: 전체 오류 목록 (항목을 누르면 표의 해당 셀로 이동)
# - 하단: 선택한 셀(또는 오류 항목)의 상세 설명 — 왜 틀렸는지, 기대/실제, 수정 제안

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.table_validator import CellIssue, ValidationReport
from ui.components.button import GhostButton
from utils.qss import set_state


class ValidationPanel(QFrame):
    # issueActivated(row, column) — 목록에서 오류를 눌렀을 때 (표에서 그 셀을 선택해 달라는 신호)
    issueActivated = Signal(int, str)
    # fixRequested(row, column, value) — 이 셀을 value 로 바꿔 달라는 신호
    fixRequested = Signal(int, str, object)
    # fixAllRequested() — 수정 가능한 오류 전체를 추천값으로 바꿔 달라는 신호
    fixAllRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ValidationPanel")
        self.setFixedWidth(420)

        self._report: ValidationReport | None = None

        self._title = QLabel("검증 결과")
        self._title.setObjectName("ValidationTitle")

        self._fix_all = GhostButton("오류 전체 추천값 적용")
        self._fix_all.clicked.connect(self.fixAllRequested.emit)
        self._fix_all.setVisible(False)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.addWidget(self._title)
        title_row.addStretch(1)
        title_row.addWidget(self._fix_all)

        self._badge = QLabel("검증 대기 중")
        self._badge.setObjectName("ValidationBadge")
        self._badge.setWordWrap(True)

        self._list = QListWidget()
        self._list.setObjectName("IssueList")
        self._list.setWordWrap(True)
        self._list.itemClicked.connect(self._on_item_clicked)

        detail_caption = QLabel("상세")
        detail_caption.setObjectName("ValidationCaption")

        self._detail = QLabel(
            "표의 셀을 누르거나 위 목록의 오류를 선택하면\n자세한 설명이 여기에 표시됩니다."
        )
        self._detail.setObjectName("ValidationDetail")
        self._detail.setWordWrap(True)
        self._detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._detail.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        detail_area = QScrollArea()
        detail_area.setObjectName("ValidationDetailArea")
        detail_area.setWidgetResizable(True)
        detail_area.setFrameShape(QScrollArea.Shape.NoFrame)
        detail_area.setWidget(self._detail)
        detail_area.setMinimumHeight(180)

        # 선택한 셀의 값 수정 영역: 추천값 적용 버튼 + 직접 입력
        self._current_cell: tuple[int, str] | None = None
        self._current_expected = None

        self._apply_button = GhostButton("추천값 적용")
        self._apply_button.clicked.connect(self._on_apply_expected)

        self._input = QLineEdit()
        self._input.setObjectName("FixInput")
        self._input.setPlaceholderText("직접 입력 (숫자)")
        self._input.returnPressed.connect(self._on_apply_custom)
        self._input_button = GhostButton("적용")
        self._input_button.clicked.connect(self._on_apply_custom)

        fix_row = QHBoxLayout()
        fix_row.setContentsMargins(0, 0, 0, 0)
        fix_row.setSpacing(6)
        fix_row.addWidget(self._input, 1)
        fix_row.addWidget(self._input_button)
        fix_row.addWidget(self._apply_button)
        self._fix_area = QWidget()
        self._fix_area.setLayout(fix_row)
        self._fix_area.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(title_row)
        layout.addWidget(self._badge)
        layout.addWidget(self._list, 1)
        layout.addWidget(detail_caption)
        layout.addWidget(detail_area, 1)
        layout.addWidget(self._fix_area)

    # api############################################
    def set_report(self, report: ValidationReport | None) -> None:
        # 탭이 바뀌거나 표가 새로 만들어졌을 때 전체 목록을 바꿈
        self._report = report
        self._list.clear()
        self._detail.setText(
            "표의 셀을 누르거나 위 목록의 오류를 선택하면\n자세한 설명이 여기에 표시됩니다."
        )
        self._current_cell = None
        self._current_expected = None
        self._fix_area.setVisible(False)
        # 자동 수정 가능한 오류(기대값이 있는 셀 오류)가 있을 때만 전체 적용 버튼 표시
        fixable = bool(report) and any(
            not issue.is_table_level() and issue.column and issue.expected is not None
            for issue in (report.issues if report else [])
        )
        self._fix_all.setVisible(fixable)
        self._detail.setText(
            "표의 셀을 누르거나 위 목록의 오류를 선택하면\n자세한 설명이 여기에 표시됩니다."
        )

        if report is None:
            self._set_badge("검증 대기 중", "waiting")
            return
        if report.notice:
            self._set_badge(report.notice, "waiting")
            return

        warn_count = len({row for (row, _c) in report.warn_cells})
        warn_tail = f" · 경고 {warn_count:,}행" if warn_count else ""

        if not report.issues:
            self._set_badge(f"PASS — 발견된 오류가 없습니다 {warn_tail}", "pass")
        else:
            self._set_badge(f"FAIL — 오류 {len(report.issues)}건 {warn_tail}", "fail")
            for issue in report.issues:
                item = QListWidgetItem(issue.title())
                item.setData(Qt.ItemDataRole.UserRole, issue)
                item.setToolTip(issue.detail())
                self._list.addItem(item)

    def show_cell(self, row: int, column: str) -> None:
        # 표에서 셀을 눌렀을 때: 오류 설명 -> 경고(노란 셀) 사유 순으로 보여주고,
        # 부담률·증가율(행 지표)은 오류 유무와 상관없이 항상 맨 끝에 붙인다.
        if self._report is None:
            return
        issues = self._report.issues_at(row, column)
        warn = self._report.warn_cells.get((row, column))
        metric = self._report.metrics.get(row, "")
        header = f"{row + 1}행 · {column}"
        bar = "━" * 24
        tail = f"\n{bar}\n📊 참고 지표\n{metric}" if metric else ""
        self._setup_fix_area(row, column, issues)
        if issues:
            total = len(issues)
            blocks = []
            for k, issue in enumerate(issues, 1):
                label = f"[오류 {k}/{total}] {issue.reason}"
                blocks.append(f"{label}\n{issue.body()}")
            body = f"\n{'·' * 23}\n".join(blocks)
            self._detail.setText(f"{header}\n{bar}\n{body}{tail}")
            self._select_in_list(issues[0])
            return
        self._list.clearSelection()
        if warn:
            self._detail.setText(
                f"{header}\n{bar}\n⚠ {warn}\n" "(값을 확인해 보세요)" f"{tail}"
            )
            return
        self._detail.setText(
            f"{header}\n{bar}\n이 셀에서 발견된 오류는 없습니다.{tail}"
        )

    # --- 값 수정 -----------------------------------------------------------
    def _setup_fix_area(self, row: int, column: str, issues) -> None:
        # 선택한 셀에 대해 '추천값 적용'과 '직접 입력'을 준비한다.
        self._current_cell = (row, column)
        expected = next(
            (issue.expected for issue in issues if issue.expected is not None), None
        )
        self._current_expected = expected
        if expected is not None:
            try:
                self._apply_button.setText(f"추천값 적용 ({int(expected):,})")
            except (TypeError, ValueError):
                self._apply_button.setText(f"추천값 적용 ({expected})")
            self._apply_button.setVisible(True)
        else:
            self._apply_button.setVisible(False)
        self._input.clear()
        self._fix_area.setVisible(True)

    def _on_apply_expected(self) -> None:
        if self._current_cell is None or self._current_expected is None:
            return
        row, column = self._current_cell
        self.fixRequested.emit(row, column, self._current_expected)

    def _on_apply_custom(self) -> None:
        if self._current_cell is None:
            return
        text = self._input.text().strip()
        if not text:
            return
        # 숫자면 숫자로, 아니면 문자 그대로 (등급명·등급구분 같은 문자 셀도 수정 가능)
        # int/float 여부는 set_cell_value가 실제 셀 dtype을 보고 결정하므로 여기서는 자르지 않는다.
        try:
            value = float(text.replace(",", ""))
        except ValueError:
            value = text
        row, column = self._current_cell
        self.fixRequested.emit(row, column, value)

    # 내부####################
    def _set_badge(self, text: str, state: str) -> None:
        self._badge.setText(text)
        set_state(self._badge, "state", state)

    def _select_in_list(self, issue: CellIssue) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) is issue:
                self._list.setCurrentRow(i)
                return

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        if isinstance(data, tuple):
            row, column = data
            self.show_cell(row, column)
            self.issueActivated.emit(row, column)
            return
        issue: CellIssue = item.data(Qt.ItemDataRole.UserRole)
        self._detail.setText(issue.detail())
        if not issue.is_table_level() and issue.column:
            self.issueActivated.emit(issue.row, issue.column)
