# 문구가 바뀐 항목 하나. top-3 중에서 고르거나 직접 적는다.
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QWidget,
)

from jogyeon_matcher.contracts.schemas import (
    CellLocation,
    Decision,
    LabelRef,
    MatchItem,
    MatchPath,
    MissingValue,
    Status,
)
from ui.components.card import Card
from ui.widgets.sheet_preview import SheetPreview, SheetSource, render

from ui.widgets.review.shared import banner

FLAG_TEXT = {
    "LOW_MARGIN": "1·2순위 점수가 비슷함",
    "CONTESTED": "다른 문구와 후보가 겹침",
    "NUMERIC_VETO_APPLIED": "숫자가 다름",
    "NUMERIC_EXTRA": "숫자가 덧붙음",
    "ANTONYM_BLOCKED": "뜻이 반대인 표현",
}


class PreviewPair(QWidget):
    def __init__(self, baseline: SheetSource, target: SheetSource, parent=None):
        super().__init__(parent)
        self._baseline, self._target = baseline, target

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)
        self.left = SheetPreview("대조 파일")
        self.right = SheetPreview("현재 파일")
        layout.addWidget(self.left, 1)
        layout.addWidget(self.right, 1)

    def show_baseline(self, location: CellLocation | None) -> None:
        render(self.left, self._baseline, location, "대조")

    def show_target(self, location: CellLocation | None) -> None:
        render(self.right, self._target, location, "현재")


class ChangedCard(Card):
    def __init__(
        self,
        item: MatchItem,
        baseline: SheetSource,
        target: SheetSource,
        parent: QWidget | None = None,
        title: str = "",
    ):
        location = item.input_label.location
        where = f"대조 파일 {location.sheet} {location.a1}" if location else ""
        super().__init__(
            title or f"대조 파일 문구  {item.input_label.raw}", where, parent
        )
        self.item = item
        self.body_layout.setSpacing(10)

        flags = [f for f in item.flags if f in FLAG_TEXT]
        if flags:
            self.add_widget(banner("  ·  ".join(FLAG_TEXT[f] for f in flags), "warn"))

        message = (
            "현재 파일에서 이 문구에 해당하는 것을 골라 주세요."
            if item.candidates
            else "현재 파일에서 비슷한 문구를 찾지 못했습니다."
        )
        self.add_widget(banner(message, "info"))

        self._locations: dict[int, CellLocation | None] = {}
        self.group = QButtonGroup(self)
        for candidate in item.candidates:
            self._locations[candidate.rank] = candidate.base_location
            self.add_widget(self._candidate_row(candidate))
        self.add_widget(self._manual_row())

        self._preview = PreviewPair(baseline, target)
        self.add_widget(self._preview)
        self._preview.show_baseline(location)

        self.group.buttonClicked.connect(self._on_choice)
        if item.candidates:
            self.group.buttons()[0].setChecked(True)
            self._preview.show_target(self._locations.get(1))
        else:
            self.manual_radio.setChecked(True)
            self._preview.show_target(None)

    def _on_choice(self, button) -> None:
        rank = button.property("rank")
        self._preview.show_target(self._locations.get(rank) if rank else None)

    def _candidate_row(self, candidate) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        radio = QRadioButton(f"{candidate.rank}.  {candidate.base_label}")
        radio.setObjectName("ReviewChoice")
        radio.setCursor(Qt.CursorShape.PointingHandCursor)
        radio.setProperty("rank", candidate.rank)
        radio.setProperty("label", candidate.base_label)
        self.group.addButton(radio)
        layout.addWidget(radio, 1)

        detail = f"유사도 {candidate.final:.2f}"
        if candidate.base_location:
            detail += f"   현재 파일 {candidate.base_location.sheet} {candidate.base_location.a1}"
        flags = [FLAG_TEXT[f] for f in candidate.flags if f in FLAG_TEXT]
        if flags:
            detail += "   ⚠ " + ", ".join(flags)

        score = QLabel(detail)
        score.setObjectName("ReviewScore")
        layout.addWidget(score)
        return row

    def _manual_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.manual_radio = QRadioButton("직접 입력")
        self.manual_radio.setObjectName("ReviewChoice")
        self.manual_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group.addButton(self.manual_radio)

        self.manual_edit = QLineEdit()
        self.manual_edit.setObjectName("FieldInput")
        self.manual_edit.setPlaceholderText("현재 파일에 적힌 문구를 그대로")
        # textEdited 는 붙여넣기를 놓친다. 내용이 들어오면 무조건 직접 입력으로 돌려야
        # 담당자가 적은 값이 버려지지 않는다.
        self.manual_edit.textChanged.connect(
            lambda text: self.manual_radio.setChecked(True) if text.strip() else None
        )

        layout.addWidget(self.manual_radio)
        layout.addWidget(self.manual_edit, 1)
        return row

    def decision(self, run_id: str) -> Decision:
        checked = self.group.checkedButton()
        if checked is self.manual_radio or checked is None:
            return Decision(
                run_id=run_id,
                item_id=self.item.item_id,
                action="manual_input",
                input_label=self.item.input_label.raw,
                manual_input=self.manual_edit.text().strip() or None,
            )
        return Decision(
            run_id=run_id,
            item_id=self.item.item_id,
            action="select_candidate",
            input_label=self.item.input_label.raw,
            selected_label=checked.property("label"),
            selected_rank=checked.property("rank"),
        )


# 못 읽는 값 하나. 이걸 확정해야 단가표를 만들 수 있다.
class MissingCard(ChangedCard):
    def __init__(
        self,
        missing: MissingValue,
        baseline: SheetSource,
        target: SheetSource,
        parent: QWidget | None = None,
    ):
        item = MatchItem(
            item_id=f"missing-{missing.sheet}-{missing.label}",
            input_label=LabelRef(
                missing.label, missing.label, missing.baseline_location
            ),
            status=Status.UNMATCHED,
            match_path=MatchPath.HYBRID,
            candidates=missing.candidates,
        )
        super().__init__(
            item, baseline, target, parent, title=f"필요한 값  {missing.label}"
        )
