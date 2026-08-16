# 1단계 — 문서에서 뽑은 상수 확인 화면.
#
# 고시 문서를 파싱해 얻은 값을 채워 넣고, 사용자가 눈으로 확인·수정한 뒤
# '단가표 생성'을 누르면 값 묶음을 다음 단계로 넘긴다.
#
# UploadPage가 넘겨주는 values는 페이지(탭)별 dict의 list다. 필드를 미리
# 정해두지 않고, 받은 dict 구조를 그대로 보고 ValueField를 만든다:
#   - 값이 문자/숫자면            -> key - ValueField 한 쌍
#   - 값이 dict(중첩)이면        -> 상위 key는 그룹 라벨로만 쓰고
#                                    하위 key - ValueField 들을 나열

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox
)

import pandas as pd
from pathlib import Path
from services.table_writer import TableWriter
from ui.components.card import Card
from ui.components.button import PrimaryButton, GhostButton 
from ui.components.tab_bar import SegmentedTabBar
from ui.widgets.value_field import ValueField
from utils.qss import set_state

# 단가표 생성 상태
WAITING, FILLED, BUSY, READY, FAILED = "waiting", "filled", "busy", "ready", "failed"

_GENERATE_TEXT = "단가표 생성"
_NEXT_TEXT = "다음 단계로  →"
_BUSY_TEXT = "⟳  단가표를 생성하는 중..."
_LOADING_TEXT = "⟳  불러오는 중..."


GROUP_GRID_COLUMNS = 6
# 라벨이 길어 기본 4열로는 잘리는 그룹은 여기서 열 수를 따로 지정한다.
GROUP_COLUMN_OVERRIDES = {"추가급여 월한도액": 3}
# value_field를 셀 오른쪽에 붙여서 정렬할 그룹
GROUP_RIGHT_ALIGN = {"추가급여 월한도액"}

# '인정조사' 탭(0번 페이지)에서 한 줄에 나란히 둘 최상위 스칼라 키 묶음
PAGE1_ROW_GROUPS = [
    ("사업년도", "차수"),
    ("기본단가", "A값", "인정조사 본인부담금 상한액"),
]

# 쉼표 없이 연도 그대로 표시할 키
YEAR_KEYS = {"사업년도"}
# '본인부담률' 그룹 안에서 퍼센티지로 표시할 구간('다'~'바')
PERCENT_GRADES = {"다", "라", "마", "바"}

TABS = {
    "unit_price": [
        {
            "label": "인정조사",
            "title": "문서 안의 값이 정확한지 확인해 주세요",
            "card_title": "인정조사",
        },
        {
            "label": "종합조사/산정특례",
            "title": "문서 안의 값이 정확한지 확인해 주세요",
            "card_title": "종합조사/산정특례",
        },
    ],
    "notice_verify": [],
}


class _TableWriteSignals(QObject):
    finished = pyqtSignal(int, object)  # generation, Tables
    failed = pyqtSignal(int, str)  # generation, 사유


# 단가표 생성기를 GUI 스레드 밖에서 돌린다.
class _TableWriteTask(QRunnable):
    def __init__(
        self,
        table_writer: TableWriter,
        values: dict[str, str | int | float],
        flow_key: str,
        generation: int,
    ) -> None:
        super().__init__()
        self.signals = _TableWriteSignals()
        self._table_writer = table_writer
        self._values = values
        self._flow_key = flow_key
        self._generation = generation

    def run(self) -> None:
        try:
            if self._flow_key == "unit_price":
                tables = self._table_writer.write_basic_add_tables(
                    values=self._values,
                )
            else:
                tables = self._table_writer.write_payment_table(
                    service_prices=self._values,
                    basic_df=None,  # TODO: 여기에 기본급여 단가표 혹은 단가표 엑셀파일의 path를 넣어줄 것
                )
        except Exception as error:
            self.signals.failed.emit(
                self._generation, str(error) or type(error).__name__
            )
        else:
            self.signals.finished.emit(self._generation, tables)


class ConstantsPage(QWidget):
    # tablesReady(dict): 단가표 생성이 끝나 다음 단계로 넘어가도 된다는 신호
    tablesReady = pyqtSignal(object)
    valuesChanged = pyqtSignal()  # 값이 수정되면 이미 만든 단가표는 낡은 것이 된다
    valuesKept = (
        pyqtSignal()
    )  # 값 수정했다가 취소한 경우 바뀌지 않은 것으로 처리, 단가표 페이지로 정상적 이동 가능

    def __init__(
        self,
        table_writer: TableWriter | None = None,
        parent: QWidget | None = None,
        flow: str = "unit_price",
    ):
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._fields: dict[str, ValueField] = {}

        self._flow = flow

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        self._table_writer = table_writer
        self._pool = QThreadPool.globalInstance()

        self._tabs = SegmentedTabBar([tab["label"] for tab in TABS[flow]], flow=flow)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._card = Card()

        self._stack = QStackedWidget()  # 값이 오기 전까지는 비어 있다
        self._card.add_widget(self._stack)

        self._is_table_generated = False  # 단가표 최초 생성 했는지 여부
        self._tables: dict | None = None
        self._generation = 0
        self._state = WAITING

        self._next = PrimaryButton(_GENERATE_TEXT)
        self._next.setEnabled(False)
        self._next.clicked.connect(self._on_next)

        self._hint = QLabel()
        self._hint.setObjectName("GenerateHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)

        self._export_button=GhostButton("수정된 조견표 저장")
        self._export_button.clicked.connect(self._on_export_jogyeon)
        self._export_button.setVisible(self._flow == "unit_price")
        self._export_src: Path |None=None
        self._export_cells: dict[str,tuple[str,int,int]]={}

        content = QVBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._card, 1)
        content.addWidget(self._next)
        content.addWidget(self._hint)

        #수정된 조견표 저장버튼
        # 탭 + 조견표 저장 버튼을 한 줄에 (탭 왼쪽, 버튼 오른쪽)
        self._tabs_row = QHBoxLayout()
        self._tabs_row.addWidget(self._tabs)
        self._tabs_row.addStretch(1)
        self._tabs_row.addWidget(self._export_button)

        content = QVBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._card, 1)
        content.addWidget(self._next)
        content.addWidget(self._hint)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(28, 18, 28, 24)
        self._outer.setSpacing(18)
        self._outer.addWidget(self._title)
        self._outer.addLayout(self._tabs_row)
        self._outer.addLayout(content, 1)

        self._on_tab_changed(flow, 0)
        self._set_state(WAITING)

    # --- 구성 -------------------------------------------------------------
    def _group_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("GroupLabel")
        return label

    def _infer_kind(self, key: str, value: object) -> str:
        if key in YEAR_KEYS:
            return "year"
        # bool은 int의 하위 타입이라 먼저 걸러낸다.
        if not isinstance(value, bool) and isinstance(value, (int, float)):
            return "int"
        return "text"  # 숫자가 아닌 값이면 그대로 표시

    def _make_field(
        self, key: str, label: str, value: object, kind: str | None = None, **kwargs
    ) -> ValueField:
        field = ValueField(
            key, label, value=value, kind=kind or self._infer_kind(key, value), **kwargs
        )
        self._register(field)
        return field

    def _add_group_fields(self, column: QVBoxLayout, key: str, values: dict) -> None:
        # 상위 key는 그룹 라벨로만 쓰고, 하위 key들을 그리드로 나열한다.
        column.addWidget(self._group_label(key))
        columns = GROUP_COLUMN_OVERRIDES.get(key, GROUP_GRID_COLUMNS)
        metrics = QFontMetrics(self.font())
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        for i, (sub_key, sub_value) in enumerate(values.items()):
            # 라벨 폭을 텍스트 길이에 맞춰 잡아서 긴 라벨이 잘리지 않게 한다.
            label_width = metrics.horizontalAdvance(sub_key) + 8
            is_percent = "본인부담률" in key and sub_key in PERCENT_GRADES
            field = self._make_field(
                f"{key}.{sub_key}",
                sub_key,
                sub_value,
                kind="percent" if is_percent else None,
                label_width=label_width,
                input_width=92,
                right_align_input=key in GROUP_RIGHT_ALIGN,
            )
            # 정렬 없이 그대로 셀을 채우게 둔다 — 라벨은 왼쪽에 고정되고,
            # right_align_input이 켜진 필드는 남는 폭을 이용해 입력칸만 오른쪽에 붙는다.
            grid.addWidget(field, i // columns, i % columns)
        column.addLayout(grid)

    def _row_groups_for(self, index: int) -> list[tuple[str, ...]]:
        # unit_price 흐름의 키 구성을 기준으로 정한 묶음이라 첫 번째 flow에만 적용
        # 두 번째 flow는 어떤 값이 들어올지 미정
        if self._flow == "unit_price" and index == 0:
            return PAGE1_ROW_GROUPS
        return []

    def _add_scalar_row(
        self, column: QVBoxLayout, keys: tuple[str, ...], values: dict
    ) -> None:
        row = QHBoxLayout()
        row.setSpacing(24)
        bold_font = self.font()
        bold_font.setBold(True)
        metrics = QFontMetrics(bold_font)
        for key in keys:
            # 라벨 폭을 텍스트 길이에 맞춰 줄여서 입력칸이 바로 붙게 한다.
            label_width = metrics.horizontalAdvance(key) + 4
            field = self._make_field(
                key,
                key,
                values[key],
                label_width=label_width,
                input_width=140,
                label_bold=True,
            )
            row.addWidget(field)
        row.addStretch(1)
        column.addLayout(row)

    def _build_page(self, index: int, values: dict) -> QWidget:
        column = QVBoxLayout()
        column.setSpacing(14)

        group_of: dict[str, tuple[str, ...]] = {
            key: group for group in self._row_groups_for(index) for key in group
        }
        handled: set[str] = set()

        for key, value in values.items():
            if key in handled:
                continue
            if isinstance(value, dict):
                self._add_group_fields(column, key, value)
                continue
            group = group_of.get(key)
            if group and all(
                k in values and not isinstance(values[k], dict) for k in group
            ):
                self._add_scalar_row(column, group, values)
                handled.update(group)
                continue
            field = self._make_field(
                key, key, value, label_width=220, input_width=140, label_bold=True
            )
            column.addWidget(field)

        column.addStretch(1)

        # 스타일시트 없는 선택자는 자식 위젯(FieldInput 테두리 등)까지 덮어써 버리므로
        # 반드시 objectName + ID 선택자로 범위를 한정한다.
        body = QWidget()
        body.setLayout(column)
        body.setObjectName("ConstantsScrollBody")
        body.setStyleSheet("QWidget#ConstantsScrollBody { background: transparent; }")

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setObjectName("ConstantsScrollArea")
        area.setStyleSheet(
            "QScrollArea#ConstantsScrollArea { background: transparent; border: none; }"
        )
        viewport = area.viewport()
        viewport.setObjectName("ConstantsScrollViewport")
        viewport.setStyleSheet(
            "QWidget#ConstantsScrollViewport { background: transparent; }"
        )
        area.setWidget(body)
        return area

    def _rebuild_pages(self, pages: list[dict]) -> None:
        self._fields.clear()
        while self._stack.count():
            widget = self._stack.widget(0)
            self._stack.removeWidget(widget)
            widget.deleteLater()

        for index, page_values in enumerate(pages):
            self._stack.addWidget(self._build_page(index, page_values))

        self._on_tab_changed(self._flow, self._tabs.current())

        # 새로 받은 값이므로 이전에 만든 단가표는 낡은 것으로 친다.
        self._is_table_generated = False
        self._tables = None
        self._refresh_state()

    def _build_tabs(self, flow: str) -> None:
        # flow가 바뀔 때만 탭바를 새로 만들어 자리에 갈아 끼운다.
        old_tabs = self._tabs
        new_tabs = SegmentedTabBar([tab["label"] for tab in TABS[flow]], flow=flow)
        new_tabs.currentChanged.connect(self._on_tab_changed)
        self._outer.replaceWidget(old_tabs, new_tabs)
        old_tabs.deleteLater()
        self._tabs = new_tabs

    def _register(self, field: ValueField) -> None:
        self._fields[field.key] = field
        field.valueChanged.connect(lambda *_: self._on_field_changed())

    def _on_field_changed(self) -> None:
        if self._is_table_generated and self.modified_keys() == []:
            self.valuesKept.emit()
        else:
            self.valuesChanged.emit()
        self._refresh_state()

    # --- 조견표 수정한 것 저장 -----------------------------------------------
    def set_export_source(self,src_path,cell_map)->None:
        self._export_src=src_path
        self._export_cells=cell_map or {}

    def _collect_changed(self) -> dict[str, object]:
        return {
            key: field.value()
            for key, field in self._fields.items()
            if field.is_modified() and field.is_valid()
        }

    def _on_export_jogyeon(self)->None:
        changed=self._collect_changed()
        if not changed:
            QMessageBox.information(self,"안내","수정된 값이 없습니다.")
            return
        if self._export_src is None:
            QMessageBox.warning(self,"안내","원본 조견표 정보를 찾을 수 없습니다.\n조견표를 다시 업로드해 주세요.")
            return
        path,_=QFileDialog.getSaveFileName(
            self,"수정된 조견표 저장",
            str(Path(self._export_src).with_stem(Path(self._export_src).stem+"_수정본")),
            "Excel (*.xlsx)")

        if not path:
            return
        from services.jogyeon_exporter import export_modified_jogyeon
        try:
            skipped=export_modified_jogyeon(
                self._export_src,path,self._export_cells,changed
            )
        except Exception as error:
            QMessageBox.critical(self,"저장 실패",str(error))
            return

        if skipped:
            detail = "\n".join(f"· {k}\n   {reason}" for k, reason in skipped)
            QMessageBox.warning(
                self, "일부 값 미반영",
                f"조견표를 저장했지만 다음 값은 반영되지 않았습니다:\n\n{detail}")
        else:
            QMessageBox.information(self, "완료", "수정된 조견표를 저장했습니다.")

    # --- API --------------------------------------------------------------
    def set_flow(self, flow: str) -> None:
        # flow가 바뀔 때만 탭바를 새로 만들고, 이전 흐름에서 만든 필드를 비운다.
        if flow == self._flow:
            return
        self._flow = flow
        self._build_tabs(flow)
        self._rebuild_pages([])
        self._export_button.setVisible(flow=="unit_price")

    def set_values(self, values: dict | list[dict]) -> None:
        # value_extractor는 탭 개수에 맞춰 dict의 list를 돌려준다 —
        # dict 하나가 탭 하나에 해당하므로 각각 페이지를 새로 만든다.
        # 단순 dict가 오면(예: 값 초기화) 이미 만들어진 필드에 값만 채운다.
        if isinstance(values, list):
            self._rebuild_pages(values)
            return
        for key, value in values.items():
            if key in self._fields:
                self._fields[key].set_value(value, keep_original=True)
        self._refresh_state()

    def values(self) -> dict:
        return {key: field.value() for key, field in self._fields.items()}

    def invalid_keys(self) -> list[str]:
        return [key for key, field in self._fields.items() if not field.is_valid()]

    def modified_keys(self) -> list[str]:
        return [key for key, field in self._fields.items() if field.is_modified()]

    # --- 동작 -------------------------------------------------------------
    def _on_tab_changed(self, flow: str, index: int) -> None:
        spec = (
            TABS[flow][index] if 0 <= index < len(TABS[flow]) else TABS["unit_price"][0]
        )
        self._title.setText(spec["title"])
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)

    def _commit_original_values(self) -> None:
        # 생성에 사용한 값을 새 기본값으로 삼아, 수정 표시(파란 테두리)를 지운다.
        for field in self._fields.values():
            field.set_value(field.value(), keep_original=True)

    def _start_table_write(self, values: dict[str, str | int | float]) -> None:
        if self._table_writer is None:
            # 생성기를 안 붙인 경우: 상수 확인까지만 하고 READY 로 넘어간다
            self._tables = {}
            self._is_table_generated = True
            self._commit_original_values()
            self._set_state(READY)
            return

        self._set_state(BUSY)
        self._generation += 1
        task = _TableWriteTask(self._table_writer, values, self._flow, self._generation)
        task.signals.finished.connect(self._on_table_complete)
        task.signals.failed.connect(self._on_table_failed)
        self._pool.start(task)

    def _on_table_complete(self, generation: int, tables: dict) -> None:
        if generation != self._generation:
            return  # 생성 중에 값이 바뀐 경우: 결과가 낡은 값이므로 버린다
        self._tables = tables
        self._is_table_generated = True
        self._commit_original_values()
        self._set_state(READY)

    def _on_table_failed(self, generation: int, reason: str) -> None:
        if generation != self._generation:
            return
        self._tables = None
        self._set_state(FAILED, reason)

    def _on_next(self) -> None:
        if self._state in (FILLED, FAILED):
            # '단가표 생성' 버튼: 값이 다 채워졌거나 생성이 실패해 재시도하는 경우
            self._start_table_write(self.values())
        elif self._state == READY and self._tables is not None:
            # '다음 단계로' 버튼: 표를 화면에 채우는 동안(느림) 버튼만 잠깐 회색으로 보여준다.
            # 상태(FSM)는 그대로 READY 로 두고, 순수 UI만 바꿨다가 화면 전환 후 되돌린다.
            self._next.setEnabled(False)
            self._next.setText(_LOADING_TEXT)
            self._next.repaint()  # 바로 이어지는 무거운 작업 전에 강제로 다시 그려서 보이게 한다
            self.tablesReady.emit(self._tables)

    def reset_next_button(self) -> None:
        # TableViewerPage로 넘어간 뒤 호출: 로딩 표시로 바꿨던 버튼 모양을 되돌린다.
        if self._state == READY:
            self._next.setEnabled(True)
            self._next.setText(_NEXT_TEXT)

    # --- 내부 -------------------------------------------------------------
    def _refresh_state(self) -> None:
        if self._state == BUSY:
            return  # 생성 중엔 값이 바뀌어도 상태를 그대로 둔다
        if not self._fields or self.invalid_keys():
            self._set_state(WAITING)
        elif self._is_table_generated and self.modified_keys() == []:
            self._set_state(READY)
        else:
            self._set_state(FILLED)

    def _set_state(self, state: str, reason: str = "") -> None:
        self._state = state
        busy = state == BUSY
        for field in self._fields.values():
            field.set_read_only(busy)

        self._next.setEnabled(state in (FILLED, READY, FAILED))
        self._next.setText(
            _BUSY_TEXT if busy else _NEXT_TEXT if state == READY else _GENERATE_TEXT
        )

        if state == WAITING:
            self._hint.setText(
                "값을 불러오는 중입니다."
                if not self._fields
                else "잘못된 값이 있어 단가표를 생성할 수 없습니다. 빨간 테두리 칸을 확인해 주세요."
            )
        elif state == FILLED:
            self._hint.setText("값을 확인했다면 '단가표 생성'을 눌러 주세요.")
        elif state == BUSY:
            self._hint.setText("단가표를 생성하고 있습니다. 잠시만 기다려 주세요.")
        elif state == READY:
            self._hint.setText(
                "단가표를 생성했습니다. 다음 화면에서 확인할 수 있습니다."
            )
        else:
            self._hint.setText(
                f"단가표를 생성하지 못했습니다: {reason}\n값을 확인한 뒤 다시 시도해 주세요."
            )

        set_state(self._hint, "state", state)
        self._hint.setVisible(True)
