"""1단계 — 문서에서 뽑은 상수 확인 화면.

고시 문서를 파싱해 얻은 값을 채워 넣고, 사용자가 눈으로 확인·수정한 뒤
'단가표 생성'을 누르면 값 묶음을 다음 단계로 넘긴다.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.components.card import Card
from ui.components.button import PrimaryButton
from ui.widgets.value_field import ValueField

# 화면 구성 명세 — 항목이 바뀌면 여기만 고치면 된다.
LEFT_FIELDS = [
    ("copay_cap", "본인부담금 상한액", "int"),
    ("base_unit_price", "기본단가", "int"),
]
COPAY_RATES = [
    ("copay_rate_da", "다", "percent"),
    ("copay_rate_ra", "라", "percent"),
    ("copay_rate_ma", "마", "percent"),
    ("copay_rate_ba", "바", "percent"),
]
MONTHLY_LIMIT_COUNT = 8


class ConstantsPage(QWidget):
    generateRequested = pyqtSignal(dict)
    valuesChanged = pyqtSignal()  # 값이 손질되면 이미 만든 단가표는 낡은 것이 된다

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._fields: dict[str, ValueField] = {}

        card = Card("문서 안의 값이 정확한지 확인해 주세요")
        card.setMaximumWidth(760)

        columns = QHBoxLayout()
        columns.setSpacing(40)
        columns.addLayout(self._build_left_column(), 1)
        columns.addLayout(self._build_right_column(), 1)
        card.add_layout(columns)

        self._generate = PrimaryButton("단가표 생성")
        self._generate.clicked.connect(self._on_generate)

        center = QVBoxLayout()
        center.setSpacing(18)
        center.addWidget(card)
        center.addWidget(self._generate)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 26, 28, 26)
        outer.addStretch(1)
        outer.addLayout(center)
        outer.addStretch(2)
        outer.setAlignment(center, Qt.AlignmentFlag.AlignHCenter)

    # --- 구성 -------------------------------------------------------------
    def _build_left_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(12)

        for key, label, kind in LEFT_FIELDS:
            field = ValueField(key, label, kind=kind)
            self._register(field)
            column.addWidget(field)

        column.addSpacing(6)
        rate_title = QLabel("본인부담률")
        rate_title.setObjectName("GroupLabel")

        rate_rows = QVBoxLayout()
        rate_rows.setSpacing(8)
        for key, label, kind in COPAY_RATES:
            field = ValueField(key, label, kind=kind, label_width=20, input_width=68)
            self._register(field)
            rate_rows.addWidget(field)

        rate_block = QHBoxLayout()
        rate_block.setSpacing(10)
        rate_block.addWidget(rate_title, 0, Qt.AlignmentFlag.AlignTop)
        rate_block.addLayout(rate_rows)
        rate_block.addStretch(1)

        column.addLayout(rate_block)
        column.addStretch(1)
        return column

    def _build_right_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(10)

        title = QLabel("월 한도액")
        title.setObjectName("GroupLabel")

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for i in range(MONTHLY_LIMIT_COUNT):
            key = f"monthly_limit_{i + 1}"
            field = ValueField(
                key, f"{i + 1}구간", kind="int", label_width=44, input_width=104
            )
            self._register(field)
            grid.addWidget(field, i, 0)

        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch(1)

        column.addLayout(header)
        column.addLayout(grid)
        column.addStretch(1)
        return column

    def _register(self, field: ValueField) -> None:
        self._fields[field.key] = field
        field.valueChanged.connect(lambda *_: self.valuesChanged.emit())

    # --- API --------------------------------------------------------------
    def set_values(self, values: dict[str, float | int | None]) -> None:
        """파서가 뽑아낸 값을 화면에 채운다."""
        for key, value in values.items():
            if key in self._fields:
                self._fields[key].set_value(value, keep_original=True)

    def values(self) -> dict[str, float | int | None]:
        return {key: field.value() for key, field in self._fields.items()}

    def invalid_keys(self) -> list[str]:
        return [key for key, field in self._fields.items() if not field.is_valid()]

    def modified_keys(self) -> list[str]:
        return [key for key, field in self._fields.items() if field.is_modified()]

    # --- 동작 -------------------------------------------------------------
    def _on_generate(self) -> None:
        if self.invalid_keys():
            return  # 잘못된 칸은 빨간 테두리로 이미 표시돼 있다
        self.generateRequested.emit(self.values())
