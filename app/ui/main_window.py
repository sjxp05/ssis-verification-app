# 메인 윈도우: 헤더 + 단계 표시줄 + 페이지 스택

from __future__ import annotations

from datetime import date
from typing import Callable
from enum import IntEnum

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

from models.dto import ConstantValues
from models.flows import FlowSpec
from ui.components.header import HeaderBar
from ui.components.step_indicator import StepIndicator
from ui.pages.constants_page import ConstantsPage
from ui.pages.main_page import MainPage
from ui.pages.constants_page import ConstantsPage
from ui.pages.table_viewer_page import TableViewerPage
from ui.pages.upload_page import UploadPage, ValueExtractor

STEPS = ["조견표 업로드", "단가 정보 확인", "단가표 생성 및 저장"]


class Screen(IntEnum):
    HOME = 0
    UPLOAD = 1
    CONSTANTS = 2
    TABLES = 3

    @property
    def step(self) -> int:
        # 단계 표시줄에서 이 화면이 몇 번째 단계인지, 메인 화면은 -1
        return -1 if self is Screen.HOME else int(self) - 1

    @classmethod
    def for_step(cls, step: int) -> Screen:
        return cls(step + 1)


# table_builder(values) -> {탭 인덱스: (DataFrame, 산식)}
TableBuilder = Callable[[ConstantValues], dict[int, tuple[pd.DataFrame, object]]]


class MainWindow(QMainWindow):
    tablesRequested = pyqtSignal(dict)  # table_builder 를 안 넣었을 때 밖으로 넘김
    # uploadRequested = pyqtSignal()
    # homeRequested = pyqtSignal()

    def __init__(
        self,
        value_extractor: ValueExtractor | None = None,
        table_builder: TableBuilder | None = None,
    ):
        super().__init__()
        self.setWindowTitle("조견표 → 단가표 생성")
        self.resize(1180, 820)
        self.table_builder = table_builder
        self._flow: FlowSpec | None = None
        self._table_count = 0

        today = date.today()
        self._header = HeaderBar(
            "조견표 → 단가표 생성",
            f"🕐 {today.year}. {today.month}. {today.day}.",
        )

        self._header.backRequested.connect(self.go_home)

        # 흐름마다 단계 문구가 달라서 StepIndicator 는 통째로 갈아 끼운다.
        self._step_holder = QWidget()
        self._step_layout = QVBoxLayout(self._step_holder)
        self._step_layout.setContentsMargins(0, 0, 0, 0)
        self._step_layout.setSpacing(0)
        self._steps: StepIndicator | None = None

        self.main_page = MainPage()
        self.main_page.flowRequested.connect(self.start_flow)

        self.upload_page = UploadPage(value_extractor)
        self.upload_page.valuesReady.connect(self._on_values_ready)

        self.constants_page = ConstantsPage()
        self.constants_page.generateRequested.connect(self._on_generate)
        self.constants_page.valuesChanged.connect(self._on_values_changed)

        self.table_viewer_page = TableViewerPage()
        self.table_viewer_page.exportRequested.connect(self._on_export)

        self._stack = QStackedWidget()
        for page in (
            self.main_page,
            self.upload_page,
            self.constants_page,
            self.table_viewer_page,
        ):
            self._stack.addWidget(page)

        root = QWidget()
        root.setObjectName("Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._step_holder)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        self.go_home()

        # 헤더의 '메인으로'는 단계 이동이 아니라 이 흐름에서 나가는 동작이다.
        # self._header.backRequested.connect(self.homeRequested.emit)

        # self._steps = StepIndicator(STEPS)
        # self._steps.stepClicked.connect(self._on_step_clicked)

        # self.constants_page = ConstantsPage()
        # self.constants_page.generateRequested.connect(self._on_generate)
        # self.constants_page.valuesChanged.connect(self._on_values_changed)

        # self.table_viewer_page = TableViewerPage()
        # self.table_viewer_page.exportRequested.connect(self._on_export)

        # self._stack = QStackedWidget()
        # self._stack.addWidget(self.constants_page)
        # self._stack.addWidget(self.table_viewer_page)

        # root = QWidget()
        # root.setObjectName("Root")
        # layout = QVBoxLayout(root)
        # layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(0)
        # layout.addWidget(self._header)
        # layout.addWidget(self._steps)
        # layout.addWidget(self._stack, 1)
        # self.setCentralWidget(root)

        # self.go_to_step(1)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 시그니처)
        # 메인 창을 닫을 때 셀에 표시되는 말풍선을 항상 숨김
        self.table_viewer_page.hide_bubbles()
        super().closeEvent(event)

    # --- 화면 전환 --------------------------------------------------------
    def go_home(self) -> None:
        # 메인 화면으로. 진행 중이던 흐름은 그대로 두었다가 다시 들어오면 이어간다.
        self.table_viewer_page.hide_bubbles()
        self._stack.setCurrentIndex(Screen.HOME)
        self._header.set_title("사회보장정보원 단가표 생성 앱")
        self._header.set_back_visible(False)
        self._step_holder.setVisible(False)

    def start_flow(self, flow: FlowSpec) -> None:
        # 메인 화면에서 작업을 골랐을 때
        changed = self._flow is None or self._flow.key != flow.key
        self._flow = flow
        if changed:
            self._reset_flow(flow)
        self._header.set_title(flow.window_title)
        self._header.set_back_visible(True)
        self._step_holder.setVisible(True)
        self.go_to_step(self._steps.current() if self._steps else 0)

    def go_to_step(self, step: int) -> None:
        # 0 = 문서 업로드, step 1 = 단가 정보 확인, step 2 = 단가표 생성
        if self._steps is None or self._flow is None:
            return
        step = max(0, min(step, len(self._flow.steps) - 1))
        self.table_viewer_page.hide_bubbles()
        if step == Screen.TABLES.step:
            self.table_viewer_page.reset_tab()  # 마지막 단계는 항상 첫 탭부터
        self._stack.setCurrentIndex(Screen.for_step(step))
        self._steps.set_current(step)

    # --- 흐름 준비 --------------------------------------------------------
    def _reset_flow(self, flow: FlowSpec) -> None:
        # 다른 작업을 고르면 앞선 작업의 흔적을 지운다.
        self._install_steps(flow)
        self.upload_page.set_flow(flow)
        self.constants_page.set_values(dict.fromkeys(self.constants_page.values()))
        for index in range(self._table_count):
            self.table_viewer_page.set_table(index, pd.DataFrame())
        self._table_count = 0

    def _install_steps(self, flow: FlowSpec) -> None:
        if self._steps is not None:
            self._step_layout.removeWidget(self._steps)
            self._steps.deleteLater()
        self._steps = StepIndicator(list(flow.steps))
        self._steps.stepClicked.connect(self.go_to_step)
        self._step_layout.addWidget(self._steps)

    def _on_step_clicked(self, index: int) -> None:
        # 스텝바에서 이미 지나온 단계를 눌렀을 때
        if index == 0:
            # 조견표 업로드 화면은 이 창 밖에 있음 -> 바깥에서 처리하도록 넘긴다
            self.uploadRequested.emit()
            return
        self.go_to_step(index)

    def mousePressEvent(self, event):  # noqa: N802 (Qt 시그니처)
        # 빈 곳을 누르면 입력칸에서 포커스(깜빡이는 커서)를 뗀다.
        #
        # 입력칸·버튼처럼 클릭을 직접 받는 위젯이 아니면 이벤트가 여기까지 올라온다.
        # 포커스가 풀리면서 ValueField 의 editingFinished 가 걸려 숫자도 다시 포맷된다.
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            focused.clearFocus()
        self.table_viewer_page.hide_bubbles()  # 표 바깥을 누르면 말풍선도 닫는다
        super().mousePressEvent(event)

    def set_extracted_values(self, values: dict) -> None:
        self.constants_page.set_values(values)

    def set_tables(self, tables: dict[int, tuple[pd.DataFrame, object]]) -> None:
        for index in range(self._table_count):
            if index not in tables:
                self.table_viewer_page.set_table(index, pd.DataFrame())
        for index, (df, formulas) in tables.items():
            self.table_viewer_page.set_table(index, df, formulas)
        self._table_count = max(tables, default=-1) + 1

    # --- 동작 -------------------------------------------------------------
    def _on_values_ready(self, values: ConstantValues) -> None:
        # 업로드 화면에서 문서를 다 읽었을 때.
        self.constants_page.set_values(values)
        self.go_to_step(Screen.CONSTANTS.step)

    def _on_values_changed(self) -> None:
        # 상수를 고치면 이미 만든 단가표는 낡은 값이므로 3단계를 다시 잠근다.
        if self._steps is not None:
            self._steps.set_max_reached(Screen.CONSTANTS.step)

    def _on_generate(self, values: dict) -> None:
        if self.table_builder is None:
            self.tablesRequested.emit(values)
        else:
            self.set_tables(self.table_builder(values))
        self.go_to_step(Screen.TABLES.step)

    def _on_export(self, tab_index: int, df: pd.DataFrame) -> None:
        if df.empty:
            QMessageBox.information(self, "저장", "저장할 내용이 없습니다.")
            return
        if self._flow is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "표 저장",
            self._flow.export_name(tab_index),
            "Excel 파일 (*.xlsx)",
        )
        if not path:
            return
        try:
            df.to_excel(path, index=False)
        except PermissionError:
            QMessageBox.warning(
                self,
                "저장 실패",
                "파일이 다른 프로그램에서 열려 있는 것 같습니다.\n"
                "엑셀에서 닫은 뒤 다시 시도해 주세요.",
            )
        except ModuleNotFoundError:
            QMessageBox.warning(
                self,
                "저장 실패",
                "엑셀 저장에 필요한 openpyxl 이 설치되어 있지 않습니다.",
            )
        except OSError as error:
            QMessageBox.warning(
                self, "저장 실패", f"파일을 저장하지 못했습니다.\n{error}"
            )
        else:
            QMessageBox.information(self, "저장 완료", f"{path} 에 저장했습니다.")
