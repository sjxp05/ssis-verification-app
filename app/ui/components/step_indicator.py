# 진행 단계 표시줄 (조견표 업로드 > 단가 정보 확인 > 단가표 생성)
#
# 이미 지나온 단계는 눌러서 되돌아갈 수 있다.
# 아직 도달하지 못한 단계는 눌러도 반응하지 않는다.

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

DONE, CURRENT, TODO = "done", "current", "todo"


def _repolish(widget: QWidget) -> None:
    # 동적 property 변경 후 QSS 다시 적용
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class _StepChip(QFrame):
    clicked = pyqtSignal(int)  # 0-based 단계 번호

    def __init__(self, index: int, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StepChip")
        self._index = index
        self._navigable = False

        self._mark = QLabel(str(index + 1))
        self._mark.setObjectName("StepMark")
        self._mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._text = QLabel(text)
        self._text.setObjectName("StepText")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 14, 6)
        layout.setSpacing(8)
        layout.addWidget(self._mark)
        layout.addWidget(self._text)

        self.set_state(TODO)

    def set_state(self, state: str) -> None:
        self._mark.setText("✓" if state == DONE else str(self._index + 1))
        for widget in (self, self._mark, self._text):
            widget.setProperty("state", state)
            _repolish(widget)

    def set_navigable(self, navigable: bool) -> None:
        # 되돌아갈 수 있는 단계인지 여부. 커서와 hover 표시가 달라진다.
        self._navigable = navigable
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if navigable
            else Qt.CursorShape.ArrowCursor
        )
        self.setProperty("navigable", "true" if navigable else "false")
        _repolish(self)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt 시그니처)
        if self._navigable and event.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit(self._index)
        super().mouseReleaseEvent(event)


class StepIndicator(QFrame):
    # steps = ["조견표 업로드", "단가 정보 확인", "단가표 생성 및 저장"]
    #
    # stepClicked(index) — 이미 도달한 단계를 눌렀을 때만 발생

    stepClicked = pyqtSignal(int)

    def __init__(self, steps: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StepBar")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(6)

        self._chips: list[_StepChip] = []
        for i, label in enumerate(steps):
            if i:
                arrow = QLabel("›")
                arrow.setObjectName("StepArrow")
                layout.addWidget(arrow)
            chip = _StepChip(i, label, self)
            chip.clicked.connect(self.stepClicked.emit)
            self._chips.append(chip)
            layout.addWidget(chip)
        layout.addStretch(1)

        self._current = 0
        self._max_reached = 0
        self.set_current(0)

    # --- API -------------------------------------------------------------
    def set_current(self, index: int) -> None:
        # index 이전 단계는 done, 해당 단계는 current, 이후는 todo
        self._current = index
        self._max_reached = max(self._max_reached, index)
        self._refresh()

    def current(self) -> int:
        return self._current

    def max_reached(self) -> int:
        return self._max_reached

    def set_max_reached(self, index: int) -> None:
        # 앞 단계를 다시 잠글 때 사용 (되돌아가서 값을 고쳤을 때 등)
        self._max_reached = max(index, self._current)
        self._refresh()

    # --- 내부 ------------------------------------------------------------
    def _refresh(self) -> None:
        for i, chip in enumerate(self._chips):
            state = (
                DONE if i < self._current else CURRENT if i == self._current else TODO
            )
            chip.set_state(state)
            chip.set_navigable(i != self._current and i <= self._max_reached)
