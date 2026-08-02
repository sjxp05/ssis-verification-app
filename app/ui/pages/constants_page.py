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

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.card import Card
from ui.components.button import PrimaryButton
from ui.components.tab_bar import SegmentedTabBar
from ui.widgets.value_field import ValueField

GROUP_GRID_COLUMNS = 4
# 라벨이 길어 기본 4열로는 잘리는 그룹은 여기서 열 수를 따로 지정한다.
GROUP_COLUMN_OVERRIDES = {"추가급여 월한도액": 3}
# value_field를 셀 오른쪽에 붙여서 정렬할 그룹
GROUP_RIGHT_ALIGN = {"추가급여 월한도액"}

# '인정조사' 탭(0번 페이지)에서 한 줄에 나란히 둘 최상위 스칼라 키 묶음
PAGE1_ROW_GROUPS = [
    ("사업연도", "차수"),
    ("기본단가", "A값", "인정조사 본인부담금 상한액"),
]

TABS = [
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
]


class ConstantsPage(QWidget):
    generateRequested = pyqtSignal(dict)
    valuesChanged = pyqtSignal()  # 값이 수정되면 이미 만든 단가표는 낡은 것이 된다
    valuesKept = (
        pyqtSignal()
    )  # 값 수정했다가 취소한 경우 바뀌지 않은 것으로 처리, 단가표 페이지로 정상적 이동 가능

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._fields: dict[str, ValueField] = {}

        self._title = QLabel()
        self._title.setObjectName("PageTitle")

        self._tabs = SegmentedTabBar([tab["label"] for tab in TABS])
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._card = Card()
        self._card_title = QLabel()
        self._card_title.setObjectName("CardTitle")

        card_head = QHBoxLayout()
        card_head.addWidget(self._card_title)
        card_head.addStretch(1)
        self._card.add_layout(card_head)

        self._stack = QStackedWidget()  # 값이 오기 전까지는 비어 있다
        self._card.add_widget(self._stack)

        self._is_table_generated = False  # 단가표 최초 생성 했는지 여부
        self._generate = PrimaryButton("단가표 생성")
        self._generate.clicked.connect(self._on_generate)

        content = QVBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._card, 1)
        content.addWidget(self._generate)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 18, 28, 24)
        outer.setSpacing(18)
        outer.addWidget(self._title)
        outer.addWidget(self._tabs)
        outer.addLayout(content, 1)

        self._on_tab_changed("", 0)

    # --- 구성 -------------------------------------------------------------
    def _group_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("GroupLabel")
        return label

    def _infer_kind(self, value: object) -> str:
        # bool은 int의 하위 타입이라 먼저 걸러낸다.
        if not isinstance(value, bool) and isinstance(value, (int, float)):
            return "int"
        return "text"  # 숫자가 아닌 값("면제", "20,000 원" 등)은 그대로 표시

    def _make_field(self, key: str, label: str, value: object, **kwargs) -> ValueField:
        field = ValueField(
            key, label, value=value, kind=self._infer_kind(value), **kwargs
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
            field = self._make_field(
                f"{key}.{sub_key}",
                sub_key,
                sub_value,
                label_width=label_width,
                input_width=92,
                right_align_input=key in GROUP_RIGHT_ALIGN,
            )
            # 정렬 없이 그대로 셀을 채우게 둔다 — 라벨은 왼쪽에 고정되고,
            # right_align_input이 켜진 필드는 남는 폭을 이용해 입력칸만 오른쪽에 붙는다.
            grid.addWidget(field, i // columns, i % columns)
        column.addLayout(grid)

    def _row_groups_for(self, index: int) -> list[tuple[str, ...]]:
        if index == 0:
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

        self._on_tab_changed("", self._tabs.current())

    def _register(self, field: ValueField) -> None:
        self._fields[field.key] = field
        field.valueChanged.connect(
            lambda *_: (
                self.valuesKept.emit()
                if self._is_table_generated and self.modified_keys() == []
                else self.valuesChanged.emit()
            )
        )

    # --- API --------------------------------------------------------------
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

    def values(self) -> dict:
        return {key: field.value() for key, field in self._fields.items()}

    def invalid_keys(self) -> list[str]:
        return [key for key, field in self._fields.items() if not field.is_valid()]

    def modified_keys(self) -> list[str]:
        return [key for key, field in self._fields.items() if field.is_modified()]

    # --- 동작 -------------------------------------------------------------
    def _on_tab_changed(self, _flow: str, index: int) -> None:
        spec = TABS[index] if 0 <= index < len(TABS) else TABS[0]
        self._title.setText(spec["title"])
        self._card_title.setText(spec["card_title"])
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)

    def _on_generate(self) -> None:
        if self.invalid_keys():
            return  # 잘못된 칸은 빨간 테두리로 이미 표시돼 있다
        self._is_table_generated = True
        self.generateRequested.emit(self.values())
