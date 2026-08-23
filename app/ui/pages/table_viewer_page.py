# 2단계 — 생성된 단가표 화면.
#
# pandas DataFrame 을 엑셀 레이아웃처럼 보여주고,
# 셀을 클릭하면 그 값이 어떻게 나온 값인지 산식을 말풍선으로 띄운다.
#
# [검증] 표가 들어올 때 services.table_validator 로 검증을 돌려서
#   - 오른쪽 사이드 패널에 전체 오류 목록을 띄우고
#   - 오류가 난 셀은 빨간 배경으로 표시하고 (셀을 누르면 패널에 상세 설명)
#   - 모든 셀 hover 툴팁에 부담률(작년 표를 불러오면 증가율도)을 보여준다.
# 검증 기준값(상한액·부담률·월한도액)은 전부 이전 단계에서 서비스가
# 조견표에서 추출한 values 를 그대로 쓴다 — set_table() 의 values 인자.

from __future__ import annotations
import os
import pandas as pd
from PyQt6.QtCore import QModelIndex, pyqtSignal,Qt,QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QStackedWidget,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from models.dataframe_model import DataFrameModel
from services.table_validator import TableValidator, ValidationReport, read_prev_table
from ui.components.card import Card
from ui.components.button import GhostButton, PrimaryButton
from ui.components.tab_bar import SegmentedTabBar
from ui.widgets.dataframe_table import DataFrameTable
from ui.widgets.validation_panel import ValidationPanel
from utils.qss import set_state

TABS = {
    "unit_price": [
        {
            "label": "기본급여 단가표",
            "title": "기본급여 단가표 생성 및 검증",
            "card_title": "기본급여 단가표 미리보기",
        },
        {
            "label": "추가급여 단가표",
            "title": "추가급여 단가표 생성 및 검증",
            "card_title": "추가급여 단가표 미리보기",
        },
    ],
    "payment_price": [
        {
            "label": "결제단가표",
            "title": "결제단가표 생성 및 검증",
            "card_title": "결제단가표 미리보기",
        },
    ],
}
ACCENT_COLUMNS = ["등급코드", "코드", "항목코드", "등급구분"]
ACTION_TEXT = "Excel 파일로 저장"
_PREV_TEXT = "작년 단가표 불러오기 (증가율)"
_LOAD_TEXT = "단가표 불러오기 (검증)"
_PREV_DONE_TEXT = "✓ 작년 단가표 적용됨"
_LOAD_DONE_TEXT = "✓ 단가표 불러옴"
_ADD_ROW_TEXT = "+"
_DEL_ROW_TEXT = "-"
_PANEL_HIDE_TEXT = ">"
_PANEL_SHOW_TEXT = "<"


class TableViewerPage(QWidget):
    exportRequested = pyqtSignal(int, object)  # tab index, DataFrame
    cellSelected = pyqtSignal(int, QModelIndex)

    def __init__(self, parent: QWidget | None = None, flow: str = "unit_price"):
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._flow = flow
        self._validator = TableValidator()
        self._values: dict | None = None  # 서비스에서 추출한 상수 (검증 기준)
        self._reports: dict[int, ValidationReport] = {}  # 탭별 검증 결과
        self._prev_tables: dict[int, pd.DataFrame] = {}  # 탭별 작년 표 (증가율용)
        self._loaded_names: dict[int, str] = {}  # 탭별 '단가표 불러오기' 파일명
        self._prev_names: dict[int, str] = {}  # 탭별 작년 표 파일명 (버튼 표시용)
        self._loaded_names: dict[int, str] = {}  # 탭별 '단가표 불러오기' 파일명
        self._original_tables: dict[int, tuple] = {}  # 불러오기 전 원래 표 (취소 시 복원용)
        self._basic_reference: pd.DataFrame | None = None  # 결제단가 검증 기준(기본급여 표)
        self._tabs = SegmentedTabBar([tab["label"] for tab in TABS[flow]], flow=flow)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._card = Card()
        self._card_title = QLabel()
        self._card_title.setObjectName("CardTitle")
        self._card_hint = QLabel()
        self._card_hint.setObjectName("CardHint")

        self._prev_button = GhostButton(_PREV_TEXT)
        self._prev_button.clicked.connect(self._on_load_prev)

        self._load_button = GhostButton(_LOAD_TEXT)
        self._load_button.clicked.connect(self._on_load_table)

        self._add_row_button = GhostButton(_ADD_ROW_TEXT)
        self._add_row_button.setObjectName("RowButton")
        self._add_row_button.setFixedWidth(28)
        self._add_row_button.clicked.connect(self._on_add_row)

        self._del_row_button = GhostButton(_DEL_ROW_TEXT)
        self._del_row_button.setObjectName("RowButton")
        self._del_row_button.setFixedWidth(28)
        self._del_row_button.clicked.connect(self._on_del_row)

        self._panel_button = GhostButton(_PANEL_HIDE_TEXT)
        self._panel_button.clicked.connect(self._toggle_panel)

        card_head = QHBoxLayout()
        card_head.addWidget(self._card_title)
        card_head.addStretch(1)
        card_head.addWidget(self._card_hint)
        card_head.addWidget(self._add_row_button)
        card_head.addWidget(self._del_row_button)  
        card_head.addWidget(self._load_button)
        card_head.addWidget(self._prev_button)
        card_head.addWidget(self._panel_button)
        self._card.add_layout(card_head)

        self._stack = QStackedWidget()
        self._tables: list[DataFrameTable] = []
        self._card.add_widget(self._stack)
        self._build_tables(flow)

        self._panel = ValidationPanel()
        self._panel.issueActivated.connect(self._on_issue_activated)
        self._panel.fixRequested.connect(self._on_fix_requested)
        self._panel.fixAllRequested.connect(self._on_fix_all)

        self._action = PrimaryButton("")
        self._action.clicked.connect(self._on_export)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.addWidget(self._title)
        header.addWidget(self._subtitle)

        # 표(왼쪽) + 검증 패널(오른쪽)
        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(self._card, 1)
        left.addWidget(self._action)

        content = QHBoxLayout()
        content.setSpacing(16)
        content.addLayout(left, 1)
        content.addWidget(self._panel)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(28, 18, 28, 24)
        self._outer.setSpacing(18)
        self._outer.addLayout(header)
        self._outer.addWidget(self._tabs)
        self._outer.addLayout(content, 1)

        self._on_tab_changed(flow, 0)

    # --- API --------------------------------------------------------------
    def set_flow(self, flow: str) -> None:
        # flow가 바뀔 때만 탭바·표를 새로 만든다.
        if flow == self._flow:
            return
        self._flow = flow
        self._reports.clear()
        self._prev_tables.clear()
        self._prev_names.clear()
        self._loaded_names.clear()
        self._original_tables.clear()
        self._build_tabs(flow)
        self._build_tables(flow)
        self._on_tab_changed(flow, 0)

    def set_values(self, values: dict | None) -> None:
        # 검증 기준이 되는 서비스 추출값. set_table 보다 먼저(또는 함께) 넣는다.
        self._values = values

    def set_reference_table(self, df: pd.DataFrame | None) -> None:
        # 결제단가 검증 기준이 되는 기본급여 단가표
        self._basic_reference = df

    def set_table(
        self,
        flow: str,
        tab_index: int,
        df: pd.DataFrame,
        formulas: pd.DataFrame | dict | None = None,
        values: dict | None = None,
    ) -> None:
        self.set_flow(flow)
        if values is not None:
            self._values = values
        self._tables[tab_index].set_dataframe(df, formulas)
        self._run_validation(tab_index)
        self._loaded_names.pop(tab_index, None)
        self._original_tables.pop(tab_index, None)
        self._update_load_button()
        self._run_validation(tab_index)

    # --- 내부 빌드 ----------------------------------------------------------
    def _build_tabs(self, flow: str) -> None:
        # flow가 바뀔 때만 탭바를 새로 만들어 자리에 갈아 끼운다.
        old_tabs = self._tabs
        new_tabs = SegmentedTabBar([tab["label"] for tab in TABS[flow]], flow=flow)
        new_tabs.currentChanged.connect(self._on_tab_changed)
        self._outer.replaceWidget(old_tabs, new_tabs)
        old_tabs.deleteLater()
        self._tabs = new_tabs

    def _build_tables(self, flow: str) -> None:
        for splitter in getattr(self,"_splitters",[]):
            self._stack.removeWidget(splitter)
            splitter.deleteLater()
        self._tables = []
        self._splitters:list[QSplitter]=[]
        self._prev_views:list[DataFrameModel]=[]
        self._reports.clear()
        self._prev_tables.clear()
        self._prev_names.clear()

        for index in range(len(TABS[flow])):
            table = DataFrameTable(
                accent_columns=ACCENT_COLUMNS, show_row_numbers=False
            )
            table.cellSelected.connect(
                lambda idx, tab=index: self._on_cell_selected(tab, idx)
            )
            table.model().cellEdited.connect(
                lambda row, col, tab=index: self._on_cell_edited(tab, row, col)
            )
            self._tables.append(table)

            #작년 단가표 패널 평소 숨어있지만 불러오면 스플릿으로 나타남
            prev_view = DataFrameTable(
                accent_columns=ACCENT_COLUMNS, show_row_numbers=False
            )
            prev_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            prev_view.setVisible(False)

            # 스크롤 동기화
            self._link_scrollbars(table, prev_view)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setObjectName("TableSplitter")
            splitter.setChildrenCollapsible(False)
            splitter.addWidget(table)
            splitter.addWidget(prev_view)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 1)

            self._prev_views.append(prev_view)
            self._splitters.append(splitter)
            self._stack.addWidget(splitter)

    @staticmethod
    def _link_scrollbars(a: QAbstractItemView, b: QAbstractItemView) -> None:
        # 세로·가로 스크롤을 양방향으로 묶는다.
        for bar_a, bar_b in (
            (a.verticalScrollBar(), b.verticalScrollBar()),
            (a.horizontalScrollBar(), b.horizontalScrollBar()),
        ):
            bar_a.valueChanged.connect(bar_b.setValue)
            bar_b.valueChanged.connect(bar_a.setValue)

    def current_dataframe(self) -> pd.DataFrame:
        return self._tables[self._tabs.current()].dataframe()

    def hide_bubbles(self) -> None:
        for table in self._tables:
            table.hide_bubble()
        for view in getattr(self,"_prev_views",[]):
            view.hide_bubble()

    def reset_tab(self, flow: str = "unit_price", index: int = 0) -> None:
        self._tabs.set_current(index)  # 버튼 상태
        self._on_tab_changed(flow, index)  # 제목·부제·표·저장 버튼 문구

    def reset(self) -> None:
        # 사업년도가 바뀌면 불러왔던 단가표(검증용/작년)는 다른 연도 것이므로 모두 초기화
        self._reports.clear()
        self._loaded_names.clear()
        self._prev_names.clear()
        self._prev_tables.clear()
        self._original_tables.clear()
        for tab in range(len(self._tables)):
            self._hide_prev_split(tab)
        self._update_prev_button()
        self._update_load_button()
        self._update_panel_button()

    # --- 검증 -------------------------------------------------------------
    def _model_of(self, tab_index: int) -> DataFrameModel:
        # DataFrameTable.model() 은 DataFrameModel 을 그대로 돌려준다
        return self._tables[tab_index].model()

    def _run_validation(self, tab_index: int) -> None:
        df = self._tables[tab_index].dataframe()
        report = self._validator.validate(
            self._flow,
            tab_index,
            df,
            self._values,
            prev_df=self._prev_tables.get(tab_index),
            basic_df=self._basic_reference,
        )
        self._reports[tab_index] = report

        # 셀 강조 + 툴팁 지표를 모델에 주입
        issue_cells = {
            key: " / ".join(issue.reason for issue in issues)
            for key, issues in report.cells.items()
        }
        self._model_of(tab_index).set_annotations(
            issue_cells, report.metrics, report.warn_cells
        )
        if tab_index == self._tabs.current():
            self._panel.set_report(report)
        self._update_panel_button()

    def _on_cell_selected(self, tab: int, index: QModelIndex) -> None:
        # 기존 산식 말풍선 동작은 DataFrameTable 안에서 그대로 돌고,
        # 여기서는 패널에 셀 상세(오류 설명 또는 지표)를 띄운다.
        report = self._reports.get(tab)
        if report is not None and index.isValid():
            df = self._tables[tab].dataframe()
            if 0 <= index.column() < len(df.columns):
                self._panel.show_cell(index.row(), str(df.columns[index.column()]))
        self.cellSelected.emit(tab, index)

    def _on_issue_activated(self, row: int, column: str) -> None:
        # 패널 목록에서 오류를 눌렀을 때: 표에서 그 셀을 선택하고 화면에 보이게 스크롤
        tab = self._tabs.current()
        table = self._tables[tab]
        df = table.dataframe()
        if column not in df.columns:
            return
        index = self._model_of(tab).index(row, int(df.columns.get_loc(column)))
        table.setCurrentIndex(index)
        table.scrollTo(index)
        self._panel.show_cell(row, column)

    def _on_add_row(self) -> None:
        # 선택한 행 바로 아래에 행을 삽입한다
        tab = self._tabs.current()
        table = self._tables[tab]
        model = self._model_of(tab)
        df = model.dataframe()

        current = table.currentIndex()
        at = current.row() + 1 if current.isValid() else None  # 선택 행 바로 아래

        row = model.add_row({}, at=at)
        table.scrollTo(model.index(row, 0))
        table.setCurrentIndex(model.index(row, 0))
        self._run_validation(tab)

    def _on_del_row(self) -> None:
        # 선택한 행을 삭제한다 (확인창 후) 엑셀 저장에도 반영됨
        tab = self._tabs.current()
        table = self._tables[tab]
        model = self._model_of(tab)
        current = table.currentIndex()
        if not current.isValid():
            QMessageBox.information(self, "행 삭제", "삭제할 행의 셀을 먼저 선택해 주세요.")
            return
        row = current.row()
        df = model.dataframe()
        name = str(df.iloc[row].get("등급명", "") or "").strip() or "(빈 행)"
        answer = QMessageBox.question(
            self, "행 삭제",
            f"{row + 1}행을 삭제할까요?\n등급명: {name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if model.remove_row(row):
            self._run_validation(tab)

    def _on_cell_edited(self, tab: int, row: int, column: str) -> None:
        # 더블클릭 편집으로 값이 바뀌면 즉시 재검증하고 상세를 갱신
        self._run_validation(tab)
        self._panel.show_cell(row, column)

    def _on_fix_requested(self, row: int, column: str, value) -> None:
        # 패널의 '추천값 적용'/'직접 입력' — 셀 값을 바꾸고 즉시 재검증한다.
        # DataFrame 자체가 바뀌므로 엑셀 저장 시 수정된 값이 그대로 나간다.
        tab = self._tabs.current()
        if not self._model_of(tab).set_cell_value(row, column, value):
            return
        self._run_validation(tab)
        self._panel.show_cell(row, column)

    def _on_fix_all(self) -> None:
        # 수정 가능한 오류(기대값이 있는 셀 오류)를 전부 추천값으로 바꾼다.
        tab = self._tabs.current()
        model = self._model_of(tab)
        for _ in range(5):
            report = self._reports.get(tab)
            if report is None:
                return
            seen: set[tuple[int, str]] = set()
            fixes = []
            for issue in report.issues:
                if issue.is_table_level() or not issue.column or issue.expected is None:
                    continue
                key = (issue.row, issue.column)
                if key in seen:
                    continue
                seen.add(key)
                fixes.append((issue.row, issue.column, issue.expected))
            if not fixes:
                break
            for row, column, value in fixes:
                model.set_cell_value(row, column, value)
            self._run_validation(tab)
 
        # 추천값이 없어 자동으로 못 고친 오류 안내
        # (행 삭제로 인한 행 개수·소득형 결손, 등급구분 중복, 등급명 형식 등)
        report = self._reports.get(tab)
        remaining = list(report.issues) if report is not None else []
        if remaining:
            listed = "\n".join(f" · {issue.title()}" for issue in remaining[:8])
            more = f"\n · … 외 {len(remaining) - 8}건" if len(remaining) > 8 else ""
            QMessageBox.information(
                self, "직접 수정이 필요한 오류",
                "다음 오류는 추천값이 없어 자동으로 고칠 수 없습니다.\n"
                "행 추가/삭제, 등급명·등급구분 수정은 원본 파일을 직접 고친 뒤\n"
                "다시 불러와 주세요.\n\n"
                f"{listed}{more}",
            )

    def _on_load_table(self) -> None:
        # 외부 단가표(엑셀)를 현재 탭에 불러와서 바로 검증한다.
        tab = self._tabs.current()
 
        if tab in self._loaded_names:
            # 적용 취소: 불러오기 전 표로 복원
            df, formulas = self._original_tables.pop(tab, (None, None))
            self._loaded_names.pop(tab, None)
            if df is not None:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    self._tables[tab].set_dataframe(df, formulas)
                    self._run_validation(tab)
                finally:
                    QApplication.restoreOverrideCursor()
            self._update_load_button()
            return
 
        path, _ = QFileDialog.getOpenFileName(
            self, "검증할 단가표 선택", "", "Excel 파일 (*.xlsx *.xls)"
        )
        if not path:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            try:
                df = read_prev_table(path)
            except Exception as error:
                QMessageBox.warning(self, "불러오기 실패", f"단가표를 읽지 못했습니다:\n{error}")
                return
            # 취소 시 되돌릴 수 있게 현재(생성된) 표를 저장해 둔다
            model = self._model_of(tab)
            self._original_tables[tab] = (model.dataframe().copy(), model._formulas)
            self._loaded_names[tab] = os.path.basename(path)
            self._tables[tab].set_dataframe(df, None)
            self._update_load_button()
            self._run_validation(tab)
        finally:
            QApplication.restoreOverrideCursor()
 
    def _on_load_prev(self) -> None:
        # 작년 단가표를 불러오면 등급구분으로 짝지어 증가율을 툴팁에 덧붙인다.
        # 이미 적용된 상태에서 다시 누르면 적용 취소(증가율 제거).
        tab = self._tabs.current()
 
        if tab in self._prev_names:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self._prev_tables.pop(tab, None)
                self._prev_names.pop(tab, None)
                self._hide_prev_split(tab)
                self._update_prev_button()
                self._run_validation(tab)  # 증가율 지표가 빠진 상태로 재계산
                return
            finally:
                QApplication.restoreOverrideCursor()
 
        path, _ = QFileDialog.getOpenFileName(
            self, "작년 단가표 선택", "", "Excel 파일 (*.xlsx *.xls)"
        )
        if not path:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            try:
                self._prev_tables[tab] = read_prev_table(path)
            except Exception as error:  # 형식이 다른 파일 등
                QMessageBox.warning(self, "불러오기 실패", f"작년 단가표를 읽지 못했습니다:\n{error}")
                return
            self._prev_names[tab] = os.path.basename(path)
            self._show_prev_split(tab)
            self._update_prev_button()
            self._run_validation(tab)
        finally:
            QApplication.restoreOverrideCursor()

    #작년단가표 스플릿 뷰
    def _show_prev_split(self,tab:int)->None:
        df=self._prev_tables.get(tab)
        if df is None:
            return
        self._prev_views[tab].set_dataframe(df,None)
        self._prev_views[tab].setVisible(True)
        splitter=self._splitters[tab]
        QTimer.singleShot(0, lambda: splitter.setSizes([1, 1]))

    def _hide_prev_split(self,tab:int)->None:
        self._prev_views[tab].hide_bubble()
        self._prev_views[tab].setVisible(False)

    def _toggle_panel(self) -> None:
        # 검증 패널 접기/펼치기 — 접으면 표가 화면 전체 폭을 쓴다
        self._panel.setVisible(not self._panel.isVisible())
        self._update_panel_button()

    def _update_panel_button(self) -> None:
        if self._panel.isVisible():
            self._panel_button.setText(_PANEL_HIDE_TEXT)
            return
        # 접힌 동안에도 오류가 있으면 버튼에 개수를 보여줘서 놓치지 않게 한다
        report = self._reports.get(self._tabs.current())
        count = len(report.issues) if report is not None else 0
        if count:
            self._panel_button.setText(f"{_PANEL_SHOW_TEXT} (오류 {count}건)")
        else:
            self._panel_button.setText(_PANEL_SHOW_TEXT)
 
    def _update_prev_button(self) -> None:
        # 현재 탭에 작년 단가표가 불러와져 있으면 버튼을 '적용됨' 상태(초록)로 바꾼다.
        name = self._prev_names.get(self._tabs.current())
        if name:
            self._prev_button.setText(_PREV_DONE_TEXT)
            self._prev_button.setToolTip(f"불러온 파일: {name}\n다시 누르면 다른 파일로 교체합니다.")
            set_state(self._prev_button, "state", "loaded")
            self._card_hint.setText(f"오른쪽: 작년 · {os.path.splitext(name)[0][:20]}")
        else:
            self._prev_button.setText(_PREV_TEXT)
            self._prev_button.setToolTip("")
            set_state(self._prev_button, "state", "")
            self._card_hint.setText("")

    def _update_load_button(self) -> None:
        # 현재 탭에 외부 단가표가 불러와져 있으면 초록 '불러옴' 상태로 바꾼다.
        name = self._loaded_names.get(self._tabs.current())
        if name:
            self._load_button.setText(_LOAD_DONE_TEXT)
            self._load_button.setToolTip(f"불러온 파일: {name}\n다시 누르면 원래 표로 되돌립니다.")
            set_state(self._load_button, "state", "loaded")
        else:
            self._load_button.setText(_LOAD_TEXT)
            self._load_button.setToolTip("")
            set_state(self._load_button, "state", "")

    # --- 동작 -------------------------------------------------------------
    def _on_tab_changed(self, flow: str, index: int) -> None:
        self.hide_bubbles()
        spec = TABS[flow][index]
        self._title.setText(spec["title"])
        self._card_title.setText(spec["card_title"])
        self._action.setText(ACTION_TEXT)
        self._stack.setCurrentIndex(index)
        self._update_prev_button()
        self._update_load_button()
        self._update_panel_button()
        self._panel.set_report(self._reports.get(index))

    def _on_export(self) -> None:
        index = self._tabs.current()
        self.exportRequested.emit(index, self._tables[index].dataframe())