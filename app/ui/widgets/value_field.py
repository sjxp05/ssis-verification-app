# '라벨 + 둥근 입력칸' 한 줄짜리 값 입력 위젯
#
# 문서에서 뽑아낸 상수를 보여주고, 사용자가 고칠 수 있게 한다.
# 고쳐진 칸은 파란 테두리, 숫자로 못 읽는 칸은 빨간 테두리로 표시된다.

from __future__ import annotations

import re

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

_NUMBER_RE = re.compile(r"[^0-9.\-]")


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ValueField(QWidget):
    # kind='int' → 216,000 / kind='percent' → 4% / kind='year' → 2026 (쉼표 없음) 로 표시

    valueChanged = pyqtSignal(str, object)  # key, value

    def __init__(
        self,
        key: str,
        label: str,
        value: float | int | str | None = None,
        kind: str = "int",
        label_width: int = 96,
        input_width: int = 92,
        label_bold: bool = False,
        right_align_input: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.key = key
        self.kind = kind
        self._original: float | int | str | None = value

        self._label = QLabel(label)
        self._label.setObjectName("FieldLabel")
        self._label.setFixedWidth(label_width)
        if label_bold:
            # 컨테이너에 스타일시트를 걸면 자식까지 덮어써 버리므로(테두리 사고 참고),
            # 폰트는 QFont로 이 라벨에만 직접 적용한다.
            font = self._label.font()
            font.setBold(True)
            self._label.setFont(font)

        self._input = QLineEdit()
        self._input.setObjectName("FieldInput")
        self._input.setFixedWidth(input_width)
        self._input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._input.textEdited.connect(self._on_text_edited)
        self._input.editingFinished.connect(self._reformat)
        self._input.installEventFilter(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._label)
        if right_align_input:
            # 라벨은 왼쪽에 그대로 두고, 위젯이 넓어진 만큼 생기는 여유 폭을
            # 라벨과 입력칸 사이에 몰아서 입력칸을 오른쪽 끝에 붙인다.
            layout.addStretch(1)
            layout.addWidget(self._input)
            layout.addSpacing(50)  # 셀 오른쪽 끝에 딱 붙지 않도록 약간 띄운다
        else:
            layout.addWidget(self._input)
            layout.addStretch(1)

        self.set_value(value, keep_original=True)

    # --- 표시 형식 --------------------------------------------------------
    def _format(self, value: float | int | str | None) -> str:
        if value is None:
            return ""
        if self.kind == "text":
            return str(value)
        if self.kind == "percent":
            return f"{value:.0%}"
        if self.kind == "year":
            return str(int(value))
        if isinstance(value, float) and not value.is_integer():
            return f"{value:,.2f}"
        return f"{int(value):,}"

    def _plain_format(self, value: float | int | str | None) -> str:
        # 편집 중에는 퍼센트 기호/쉼표 등 표시용 꾸밈을 다 떼고 순수 숫자로 보여준다.
        return self._format(value).replace(",", "").replace("%", "")

    def _parse(self, text: str) -> float | str | None:
        if self.kind == "text":
            stripped = text.strip()
            return stripped or None
        cleaned = _NUMBER_RE.sub("", text)
        if not cleaned:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
        if self.kind == "percent":
            # _format에서 :.0% 로 100배 해서 보여주므로, 파싱할 땐 다시 100으로 나눠
            # 저장 스케일(소수)과 맞춘다. 안 그러면 편집 안 해도 값이 달라져 '수정됨'으로 뜬다.
            number /= 100
        return number

    # --- API -------------------------------------------------------------
    def value(self) -> float | int | str | None:
        parsed = self._parse(self._input.text())
        if self.kind == "text" or parsed is None:
            return parsed
        return int(parsed) if float(parsed).is_integer() else parsed

    def set_value(
        self, value: float | int | str | None, keep_original: bool = False
    ) -> None:
        if keep_original:
            self._original = value
        self._input.setText(self._format(value))
        self._update_state()

    def is_valid(self) -> bool:
        text = self._input.text().strip()
        if text == "":
            return True
        parsed = self._parse(text)
        if parsed is None:
            return False
        # 숫자 칸은 음수도 잘못된 값으로 취급한다 (금액/비율은 음수가 될 수 없음).
        return self.kind == "text" or parsed >= 0

    def is_modified(self) -> bool:
        return self.value() != self._original

    def set_read_only(self, read_only: bool) -> None:
        self._input.setReadOnly(read_only)

    # --- 내부 ------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        if (
            obj is self._input
            and event.type() == QEvent.Type.FocusIn
            and not self._input.isReadOnly()
        ):
            self._input.setText(self._plain_format(self.value()))
        return super().eventFilter(obj, event)

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
