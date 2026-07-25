"""메인 윈도우 — 헤더 + 단계 표시줄 + 페이지 스택."""

from __future__ import annotations

from datetime import date
from typing import Callable

import pandas as pd
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.header import HeaderBar
from ui.components.step_indicator import StepIndicator
from ui.pages.constants_page import ConstantsPage
from ui.pages.table_viewer_page import TableViewerPage

STEPS = ["조견표 업로드", "단가 정보 확인", "단가표 생성 및 저장"]

# table_builder(values) -> {탭 인덱스: (DataFrame, 산식)}
TableBuilder = Callable[[dict], dict[int, tuple[pd.DataFrame, object]]]


class MainWindow(QMainWindow):
    tablesRequested = pyqtSignal(dict)  # table_builder 를 안 넣었을 때 밖으로 넘김
    uploadRequested = pyqtSignal()  # 스텝바에서 '조견표 업로드'로 되돌아갈 때
    homeRequested = pyqtSignal()  # 헤더의 '메인으로'

    def __init__(self, table_builder: TableBuilder | None = None):
        super().__init__()
        self.setWindowTitle("조견표 → 단가표 생성")
        self.resize(1180, 820)
        self.table_builder = table_builder

        today = date.today()
        self._header = HeaderBar(
            "조견표 → 단가표 생성",
            f"🕐 {today.year}. {today.month}. {today.day}.",
        )
        # 헤더의 '메인으로'는 단계 이동이 아니라 이 흐름에서 나가는 동작이다.
        self._header.backRequested.connect(self.homeRequested.emit)

        self._steps = StepIndicator(STEPS)
        self._steps.stepClicked.connect(self._on_step_clicked)

        self.constants_page = ConstantsPage()
        self.constants_page.generateRequested.connect(self._on_generate)
        self.constants_page.valuesChanged.connect(self._on_values_changed)

        self.table_viewer_page = TableViewerPage()
        self.table_viewer_page.exportRequested.connect(self._on_export)

        self._stack = QStackedWidget()
        self._stack.addWidget(self.constants_page)
        self._stack.addWidget(self.table_viewer_page)

        root = QWidget()
        root.setObjectName("Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._steps)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        self.go_to_step(1)

    # --- 화면 전환 --------------------------------------------------------
    def go_to_step(self, step: int) -> None:
        """step 1 = 단가 정보 확인, step 2 = 단가표 생성."""
        self.table_viewer_page.hide_bubbles()
        if step == 2:
            self.table_viewer_page.reset_tab()  # 3단계는 항상 기본급여 탭부터
        self._stack.setCurrentIndex(step - 1)
        self._steps.set_current(step)  # 0번(조견표 업로드)은 이미 끝난 단계

    def _on_step_clicked(self, index: int) -> None:
        """스텝바에서 이미 지나온 단계를 눌렀을 때."""
        if index == 0:
            # 조견표 업로드 화면은 이 창 밖에 있다 — 바깥에서 처리하도록 넘긴다
            self.uploadRequested.emit()
            return
        self.go_to_step(index)

    def _on_values_changed(self) -> None:
        """상수를 고치면 이미 만든 단가표는 낡은 값이므로 3단계를 다시 잠근다."""
        self._steps.set_max_reached(1)

    def mousePressEvent(self, event):  # noqa: N802 (Qt 시그니처)
        """빈 곳을 누르면 입력칸에서 포커스(깜빡이는 커서)를 뗀다.

        입력칸·버튼처럼 클릭을 직접 받는 위젯이 아니면 이벤트가 여기까지 올라온다.
        포커스가 풀리면서 ValueField 의 editingFinished 가 걸려 숫자도 다시 포맷된다.
        """
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            focused.clearFocus()
        self.table_viewer_page.hide_bubbles()  # 표 바깥을 누르면 말풍선도 닫는다
        super().mousePressEvent(event)

    def set_extracted_values(self, values: dict) -> None:
        self.constants_page.set_values(values)

    def set_tables(self, tables: dict[int, tuple[pd.DataFrame, object]]) -> None:
        for index, (df, formulas) in tables.items():
            self.table_viewer_page.set_table(index, df, formulas)

    # --- 동작 -------------------------------------------------------------
    def _on_generate(self, values: dict) -> None:
        if self.table_builder is None:
            self.tablesRequested.emit(values)
        else:
            self.set_tables(self.table_builder(values))
        self.go_to_step(2)

    def _on_export(self, tab_index: int, df: pd.DataFrame) -> None:
        if df.empty:
            QMessageBox.information(self, "저장", "저장할 내용이 없습니다.")
            return

        default_name = (
            "기본급여_단가표.xlsx"
            if tab_index == 0
            else "추가급여_단가표.xlsx" if tab_index == 1 else "결제급여_단가표.xlsx"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "단가표 저장", default_name, "Excel 파일 (*.xlsx)"
        )
        if not path:
            return
        try:
            df.to_excel(path, index=False)
        except Exception as error:  # openpyxl 미설치, 권한 등
            QMessageBox.warning(
                self, "저장 실패", f"파일을 저장하지 못했습니다.\n{error}"
            )
            return
        QMessageBox.information(self, "저장 완료", f"{path} 에 저장했습니다.")
