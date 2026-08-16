# 메인 윈도우: 헤더 + 단계 표시줄 + 페이지 스택

from __future__ import annotations

from pathlib import Path
from enum import IntEnum

import pandas as pd
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

from services.table_writer import TableWriter
from services import recent_files

from models.dto import ConstantValues
from models.flows import FlowSpec, UNIT_PRICE, NOTICE_VERIFY, PAYMENT_PRICE

from ui.components.header import HeaderBar
from ui.components.step_indicator import StepIndicator
from ui.dialogs.review_flow import LabelReviewFlow
from ui.pages.constants_page import ConstantsPage
from ui.pages.main_page import MainPage
from ui.pages.table_viewer_page import TableViewerPage
from ui.pages.upload_page import UploadPage, ValueExtractor
from ui.pages.gosi_constants_page import GosiConstantsPage

from utils.appdata import user_data_dir
from utils.date import yearConfig

STEPS = ["조견표 업로드", "단가 정보 확인", "단가표 생성 및 저장"]



class Screen(IntEnum):
    HOME = 0
    UPLOAD = 1
    CONSTANTS = 2
    TABLES = 3

    @property
    def step(self) -> int:
        # 단계 표시줄에서 이 화면이 몇 번째 단계인지 표현, 메인 화면은 -1
        return -1 if self is Screen.HOME else int(self) - 1

    @classmethod
    def for_step(cls, step: int) -> Screen:
        return cls(step + 1)


class MainWindow(QMainWindow):
    # uploadRequested = pyqtSignal()
    # homeRequested = pyqtSignal()

    def __init__(
        self,
        value_extractor: ValueExtractor | None = None,
        table_writer: TableWriter | None = None,
    ):
        super().__init__()
        self.setWindowTitle("조견표 → 단가표 생성")
        self.resize(1180, 820)
        self._flow: FlowSpec | None = None
        self._table_count = 0
        # 업로드 화면에서 파일이 바뀌어 2,3단계를 잠갔을 때, 되돌릴 max_reached 값
        self._locked_max_reached: int | None = None

        self._header = HeaderBar(
            "조견표 → 단가표 생성",
            yearConfig.get_formatted_date(),
        )

        self._header.backRequested.connect(self.go_home)

        self._step_holder = QWidget()
        self._step_layout = QVBoxLayout(self._step_holder)
        self._step_layout.setContentsMargins(0, 0, 0, 0)
        self._step_layout.setSpacing(0)
        self._steps: StepIndicator | None = None

        self.main_page = MainPage()
        self.main_page.flowRequested.connect(self.start_flow)
        self.main_page.yearChanged.connect(self._on_year_changed)

        # 값을 읽기 전에 작년 조견표와 문구를 대조시킨다
        self._label_review = LabelReviewFlow(self)
        self.upload_page = UploadPage(value_extractor, self._label_review.run)
        self.upload_page.valuesReady.connect(self._on_values_ready)
        self.upload_page.filesDiverged.connect(self._on_upload_files_diverged)

        self.constants_page = ConstantsPage(table_writer)
        self.constants_page.tablesReady.connect(self._on_tables_ready)
        self.constants_page.valuesChanged.connect(self._on_values_changed)
        self.constants_page.valuesKept.connect(self._on_values_kept)

        self.notice_page = GosiConstantsPage(
            table_writer=table_writer, flow=NOTICE_VERIFY.key
        )
        self.notice_page.tablesReady.connect(self._on_tables_ready)
        self.notice_page.valuesChanged.connect(self._on_values_changed)
        self.notice_page.valuesKept.connect(self._on_values_kept)

        self.table_viewer_page = TableViewerPage()
        self.table_viewer_page.exportRequested.connect(self._on_export)

        self._stack = QStackedWidget()
        for page in (
            self.main_page,
            self.upload_page,
            self.constants_page,
            self.table_viewer_page,
            self.notice_page,
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

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 시그니처)
        # 메인 창을 닫을 때 셀에 표시되는 말풍선을 항상 숨김
        self.table_viewer_page.hide_bubbles()
        super().closeEvent(event)

    def moveEvent(self, event) -> None:  # noqa: N802 (Qt 시그니처)
        # 창을 옮기면 말풍선 위치가 어긋나므로 항상 숨김
        self.table_viewer_page.hide_bubbles()
        super().moveEvent(event)

    # 2단계(값 확인)
    def _constants_page(self) -> QWidget:
        if self._flow is not None and self._flow.key in (NOTICE_VERIFY.key, PAYMENT_PRICE.key):
            return self.notice_page
        return self.constants_page

    def _page_for_step(self, step: int) -> QWidget:
        # 스택에 넣은 순서가 아니라 단계로 화면 선택
        if step == Screen.UPLOAD.step:
            return self.upload_page
        if step == Screen.CONSTANTS.step:
            return self._constants_page()
        return self.table_viewer_page

    def _on_year_changed(self) -> None:
        # 사업년도를 바꾸면 업로드 화면에 남아 있던 파일은 다른 연도 것이므로 새로 고른다.
        self.upload_page.reset()

    def go_home(self) -> None:
        # 메인 화면으로. 진행 중이던 흐름은 그대로 두었다가 다시 들어오면 이어간다.
        self.table_viewer_page.hide_bubbles()
        self._stack.setCurrentWidget(self.main_page)
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
            # 고시 검증 화면에는 modified_keys 가 없으므로 있을 때만 물어보
            modified_keys = getattr(self._constants_page(), "modified_keys", None)
            if modified_keys is not None and modified_keys() != []:
                self.table_viewer_page.reset_tab(self._flow.key, 0)

        self._stack.setCurrentWidget(self._page_for_step(step))
        self._steps.set_current(step)

    # --- 흐름 준비 --------------------------------------------------------
    def _reset_flow(self, flow: FlowSpec) -> None:
        # 다른 작업을 고르면 앞선 작업의 흔적을 지운다.
        self._install_steps(flow)
        self.upload_page.set_flow(flow)

        if flow.key in (NOTICE_VERIFY.key, PAYMENT_PRICE.key):
            self.notice_page.set_flow(flow.key)
        else:
            self.constants_page.set_flow(flow.key)

        if flow.key in (UNIT_PRICE.key, PAYMENT_PRICE.key):
            self.table_viewer_page.set_flow(flow.key)
            self._table_count = 0

    def _install_steps(self, flow: FlowSpec) -> None:
        if self._steps is not None:
            self._step_layout.removeWidget(self._steps)
            self._steps.deleteLater()
        self._steps = StepIndicator(list(flow.steps))
        self._steps.stepClicked.connect(self.go_to_step)
        self._step_layout.addWidget(self._steps)
        self._locked_max_reached = None

    def mousePressEvent(self, event):
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            focused.clearFocus()
        self.table_viewer_page.hide_bubbles()
        super().mousePressEvent(event)

    def set_extracted_values(self, values: dict) -> None:
        self.constants_page.set_values(values)

    def set_tables(self, tables: dict[int, tuple[pd.DataFrame, object]]) -> None:
        # 검증 기준값: 사용자가 확인·수정을 마친 최종 상수 (단가표 생성에 쓴 값과 동일)
        # 고시 검증 화면의 values() 는 출처까지 담은 중첩 dict이므로 return_values()로 평탄화한 dict 반환
        page = self._constants_page()
        flat_values = (
            page.return_values() if hasattr(page, "return_values") else page.values()
        )
        self.table_viewer_page.set_values(flat_values)
        basic_ref = getattr(page, "_basic_df", None)
        self.table_viewer_page.set_reference_table(basic_ref)
        for index in range(self._table_count):
            if index not in tables:
                self.table_viewer_page.set_table(self._flow.key, index, pd.DataFrame())
        for index, (df, formulas) in tables.items():
            self.table_viewer_page.set_table(self._flow.key, index, df, formulas)
        self._table_count = max(tables, default=-1) + 1

    # --- 동작 -------------------------------------------------------------
    def _on_values_ready(self, values: ConstantValues) -> None:
        upload_files = self.upload_page.files()
        # 업로드 화면에서 문서를 다 읽었을 때
        if self._flow.key in (NOTICE_VERIFY.key, PAYMENT_PRICE.key):
            self.notice_page.clear()

            reference_dict = {}
            raw_data = values if isinstance(values, list) else [values]

            # 데이터 평평하게 펴기
            for tab in raw_data:
                for key, val in tab.items():
                    if isinstance(val, dict):
                        for sub_key, sub_val in val.items():
                            reference_dict[f"{key}.{sub_key}"] = sub_val
                    else:
                        reference_dict[key] = val
            self.notice_page.set_reference(reference_dict)

            # 슬롯 파일 받아오기
            upload_files = self.upload_page.files()
            gosi_file = upload_files.get("guide")
            jogyeon_file = upload_files.get("jogyeon")
            table_file = upload_files.get("basic_unit_price")

            if table_file and hasattr(table_file, "path"):
                self.notice_page.set_unit_price_path(table_file.path)

            if jogyeon_file and hasattr(jogyeon_file, "path"):
                self.notice_page.set_sheet_path(jogyeon_file.path)

            if gosi_file and hasattr(gosi_file, "path"):
                self.notice_page.load_notice(gosi_file.path)

        else:
            self.constants_page.set_values(values)
        self.go_to_step(Screen.CONSTANTS.step)

    def _on_upload_files_diverged(self, diverged: bool) -> None:
        # 업로드 화면에서 파일이 원래 추출에 쓰인 파일과 달라졌을 때: 2,3단계 이동을 막는다.
        # 원래 파일로 되돌아오면 막았던 만큼 다시 풀어 준다 (2,3단계 값은 그대로 남아 있음).
        if self._steps is None:
            return
        if diverged:
            if self._locked_max_reached is None:
                self._locked_max_reached = self._steps.max_reached()
            self._steps.set_max_reached(Screen.UPLOAD.step)
        elif self._locked_max_reached is not None:
            self._steps.set_max_reached(self._locked_max_reached)
            self._locked_max_reached = None

    def _on_values_changed(self) -> None:
        # 상수를 고치면 이미 만든 단가표는 낡은 값이므로 3단계를 다시 잠근다.
        if self._steps is not None:
            self._steps.set_max_reached(Screen.CONSTANTS.step)

    def _on_values_kept(self) -> None:
        if self._steps is not None:
            self._steps.set_max_reached(Screen.TABLES.step)

    # 상수 확인 화면에서 단가표 생성을 마치고 '다음 단계로'를 눌렀을 때
    def _on_tables_ready(self, tables: dict) -> None:
        if self._flow.key == NOTICE_VERIFY.key:
            self._on_gosi_prices_confirmed(tables)
            return
        self.set_tables(tables)
        self.go_to_step(Screen.TABLES.step)
        self._constants_page().reset_next_button()

    def _on_gosi_prices_confirmed(self, prices: dict) -> None:
        # 고시 검증 2단계에서 '다음 단계로' 버튼을 눌렀을 때 실행됨
        QMessageBox.information(
            self, "검증 완료", "확인이 완료되었습니다. 메인 화면으로 돌아갑니다."
        )
        self.go_home()

    def _on_export(self, tab_index: int, df: pd.DataFrame) -> None:
        if df.empty:
            QMessageBox.information(self, "저장", "저장할 내용이 없습니다.")
            return
        if self._flow is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "표 저장",
            str(
                user_data_dir()
                / str(yearConfig.SYSTEM_YEAR)
                / (
                    str(yearConfig.SYSTEM_YEAR)
                    + "_"
                    + self._flow.export_name(tab_index)
                )
            ),
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
            if self._flow.key == UNIT_PRICE.key:
                if tab_index == 0:
                    # flow 1에서 생성한 기본급여 단가표를 저장하면 flow 2가 나중에 자동으로 불러올 수 있도록 캐시에 경로 기록
                    recent_files.set_recent_path(
                        yearConfig.SYSTEM_YEAR, "basic_unit_price", Path(path)
                    )
                elif tab_index == 1:
                    # 생성한 추가급여 단가표의 저장 위치 캐싱
                    recent_files.set_recent_path(
                        yearConfig.SYSTEM_YEAR, "add_unit_price", Path(path)
                    )
            elif self._flow.key == PAYMENT_PRICE.key:
                if tab_index == 0:
                    # 생성한 결제단가표의 저장 위치 캐싱
                    recent_files.set_recent_path(
                        yearConfig.SYSTEM_YEAR, "payment_unit_price", Path(path)
                    )
