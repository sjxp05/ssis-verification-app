# '라벨 + 둥근 입력칸' 한 줄짜리 값 입력 위젯
#
# 문서에서 뽑아낸 상수를 보여주고, 사용자가 고칠 수 있게 한다.
# 고쳐진 칸은 파란 테두리, 숫자로 못 읽는 칸은 빨간 테두리로 표시된다.

from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

_NUMBER_RE = re.compile(r"[^0-9.\-]")


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ValueField(QWidget):
    # kind='int' → 216,000 / kind='percent' → 4% 로 표시

    valueChanged = pyqtSignal(str, object)  # key, value

    def __init__(
        self,
        key: str,
        label: str,
        value: float | int | None = None,
        kind: str = "int",
        label_width: int = 96,
        input_width: int = 92,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.key = key
        self.kind = kind
        self._original: float | int | None = value

        self._label = QLabel(label)
        self._label.setObjectName("FieldLabel")
        self._label.setFixedWidth(label_width)

        self._input = QLineEdit()
        self._input.setObjectName("FieldInput")
        self._input.setFixedWidth(input_width)
        self._input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._input.textEdited.connect(self._on_text_edited)
        self._input.editingFinished.connect(self._reformat)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._label)
        layout.addWidget(self._input)
        layout.addStretch(1)

        self.set_value(value, keep_original=True)

    # --- 표시 형식 --------------------------------------------------------
    def _format(self, value: float | int | None) -> str:
        if value is None:
            return ""
        if self.kind == "percent":
            return f"{value:g}%"
        if isinstance(value, float) and not value.is_integer():
            return f"{value:,.2f}"
        return f"{int(value):,}"

    def _parse(self, text: str) -> float | None:
        cleaned = _NUMBER_RE.sub("", text)
        if not cleaned:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
        return number

    # --- API -------------------------------------------------------------
    def value(self) -> float | int | None:
        number = self._parse(self._input.text())
        if number is None:
            return None
        return int(number) if float(number).is_integer() else number

    def set_value(self, value: float | int | None, keep_original: bool = False) -> None:
        if keep_original:
            self._original = value
        self._input.setText(self._format(value))
        self._update_state()

    def is_valid(self) -> bool:
        return (
            self._input.text().strip() == ""
            or self._parse(self._input.text()) is not None
        )

    def is_modified(self) -> bool:
        return self.value() != self._original

    def set_read_only(self, read_only: bool) -> None:
        self._input.setReadOnly(read_only)

    # --- 내부 ------------------------------------------------------------
    def _on_text_edited(self, _text: str) -> None:
        self._update_state()
        self.valueChanged.emit(self.key, self.value())

    def _reformat(self) -> None:
        if self.is_valid():
            self.set_value(self.value())

    def _update_state(self) -> None:
        self._input.setProperty("invalid", "true" if not self.is_valid() else "false")
        self._input.setProperty("modified", "true" if self.is_modified() else "false")
        _repolish(self._input)
