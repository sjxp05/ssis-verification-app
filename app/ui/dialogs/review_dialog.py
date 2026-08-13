# 라벨 검토 화면
#
# 화면 순서가 곧 우선순위다.
#   1. 문구가 바뀐 항목   반드시 골라야 함. 맨 위에 펼쳐서 보여준다.
#   2. 올해 새로 생긴 문구 대개 그냥 두면 된다. 접어 두고 필요할 때만 적는다.
#   3. 표 구조 변경       참고 정보. 접어 둔다.
#
# 자동으로 확정된 항목은 아예 나오지 않는다.
# 후보를 고르면 오른쪽 미리보기가 그 위치로 따라간다. 좌표만 알려주면 담당자가
# 엑셀을 열어 찾아가야 하므로, 주변 몇 칸을 함께 보여줘 화면에서 판단하게 한다.

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from jogyeon_matcher import Decision, MatchItem, MatchReport
from jogyeon_matcher.contracts.schemas import (
    CellLocation,
    LabelRef,
    MatchPath,
    MissingValue,
    Status,
)
from ui.components.button import GhostButton, PrimaryButton
from ui.components.card import Card
from ui.components.scroll_page import centered_scroll_page
from ui.dialogs.review_style import STYLESHEET
from ui.widgets.sheet_preview import SheetPreview, SheetSource
from utils.qss import set_state

FLAG_TEXT = {
    "LOW_MARGIN": "1·2순위 점수가 비슷함",
    "CONTESTED": "다른 문구와 후보가 겹침",
    "NUMERIC_VETO_APPLIED": "숫자가 다름",
    "NUMERIC_EXTRA": "숫자가 덧붙음",
    "ANTONYM_BLOCKED": "뜻이 반대인 표현",
}


# 줄바꿈되는 라벨은 폭이 정해져야 높이가 나오는데, 스크롤 안 중첩 레이아웃에서는
# 그 순서가 보장되지 않아 글자가 잘린다. 폭이 바뀔 때마다 필요한 높이를 직접
# 최소 높이로 박아 레이아웃이 반드시 그만큼 잡게 한다.
class WrapLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def resizeEvent(self, event):  # noqa: N802 (Qt 시그니처)
        super().resizeEvent(event)
        self._sync_height()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt 시그니처)
        super().setText(text)
        self._sync_height()

    def _sync_height(self) -> None:
        if self.width() > 0:
            self.setMinimumHeight(self.heightForWidth(self.width()))


# 여백은 QSS padding 이 아니라 레이아웃으로 준다.
# wordWrap 라벨에 QSS padding 을 주면 Qt 가 높이 계산에서 그 여백을 빠뜨린다.
def _banner(text: str, state: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("ReviewBanner")
    set_state(frame, "state", state)

    layout = QHBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    label = WrapLabel(text)
    label.setObjectName("ReviewBannerText")
    layout.addWidget(label)
    return frame


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("ReviewSectionTitle")
    return label


# 접었다 펴는 구획. 기본은 접힘 — 열지 않아도 되는 정보라는 뜻이다.
class _Collapsible(QWidget):
    def __init__(self, title: str, hint: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._title = title
        self._toggle = QToolButton()
        self._toggle.setObjectName("ReviewToggle")
        self._toggle.setText(f"▸  {title}")
        self._toggle.setCheckable(True)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self._on_toggle)
        layout.addWidget(self._toggle)

        self._body = QWidget()
        self.body_layout = QVBoxLayout(self._body)
        self.body_layout.setContentsMargins(0, 0, 0, 6)
        self.body_layout.setSpacing(8)
        self._body.setVisible(False)
        layout.addWidget(self._body)

        if hint:
            note = WrapLabel(hint)
            note.setObjectName("ReviewSectionHint")
            self.body_layout.addWidget(note)

    def _on_toggle(self, opened: bool) -> None:
        self._toggle.setText(f"{'▾' if opened else '▸'}  {self._title}")
        self._body.setVisible(opened)

    def add(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)


# 작년 / 올해 미리보기 한 쌍
class _PreviewPair(QWidget):
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
        _render(self.left, self._baseline, location, "대조")

    def show_target(self, location: CellLocation | None) -> None:
        _render(self.right, self._target, location, "현재")


def _render(view: SheetPreview, source: SheetSource, location, side: str) -> None:
    if location is None:
        view.set_title(f"{side} 조견표")
        view.show_message("보여줄 위치가 없습니다")
        return
    view.set_title(f"{side} 조견표   {location.sheet} {location.a1}")
    frame = source.sheet(location.sheet)
    if frame is None:
        view.show_message("시트를 읽지 못했습니다")
        return
    view.show_cell(frame, location.row, location.column)


# 문구가 바뀐 항목 하나. top-3 중에서 고르거나 직접 적는다.
class _ChangedCard(Card):
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
            self.add_widget(_banner("  ·  ".join(FLAG_TEXT[f] for f in flags), "warn"))

        message = (
            "현재 파일에서 이 문구에 해당하는 것을 골라 주세요."
            if item.candidates
            else "현재 파일에서 비슷한 문구를 찾지 못했습니다."
        )
        self.add_widget(_banner(message, "info"))

        self._locations: dict[int, CellLocation | None] = {}
        self.group = QButtonGroup(self)
        for candidate in item.candidates:
            self._locations[candidate.rank] = candidate.base_location
            self.add_widget(self._candidate_row(candidate))
        self.add_widget(self._manual_row())

        self._preview = _PreviewPair(baseline, target)
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
class _MissingCard(_ChangedCard):
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


# 올해 새로 생긴 문구 하나. 적지 않으면 아무 일도 일어나지 않는다.
class _NewLabelCard(QWidget):
    def __init__(self, item: MatchItem, target: SheetSource, parent=None):
        super().__init__(parent)
        self.item = item
        self._target = target
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        location = item.input_label.location
        head = QWidget()
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(10)

        self._toggle = QToolButton()
        self._toggle.setObjectName("ReviewToggle")
        self._toggle.setCheckable(True)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setText(
            f"▸  {item.input_label.raw}"
            + (f"   ({location.sheet} {location.a1})" if location else "")
        )
        self._toggle.clicked.connect(self._on_toggle)
        head_layout.addWidget(self._toggle, 1)

        self.edit = QLineEdit()
        self.edit.setObjectName("FieldInput")
        self.edit.setPlaceholderText(
            "필요하면 대조 파일에서 대응하는 문구를 적어 주세요"
        )
        self.edit.setMaximumWidth(320)
        head_layout.addWidget(self.edit)
        layout.addWidget(head)

        self._preview = SheetPreview("현재 파일")
        self._preview.setVisible(False)
        layout.addWidget(self._preview)

    def _on_toggle(self, opened: bool) -> None:
        text = self._toggle.text()
        self._toggle.setText(("▾" if opened else "▸") + text[1:])
        self._preview.setVisible(opened)
        if opened and not self._loaded:
            self._loaded = True
            _render(self._preview, self._target, self.item.input_label.location, "현재")

    def decision(self, run_id: str) -> Decision | None:
        text = self.edit.text().strip()
        if not text:
            return None
        return Decision(
            run_id=run_id,
            item_id=self.item.item_id,
            action="manual_input",
            input_label=self.item.input_label.raw,
            manual_input=text,
        )


class ReviewDialog(QDialog):
    def __init__(
        self,
        report: MatchReport,
        baseline_path: Path | None = None,
        target_path: Path | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.report = report
        self.setWindowTitle("조견표 라벨 확인")
        self.setObjectName("PageBody")
        # app.qss 는 건드리지 않고 이 화면에만 스타일을 얹는다
        self.setStyleSheet(STYLESHEET)
        self.resize(1120, 820)

        self._baseline = SheetSource(baseline_path)
        self._target = SheetSource(target_path)
        self._cards: list[_ChangedCard] = []
        self._new_cards: list[_NewLabelCard] = []

        page, column = centered_scroll_page(1020)
        self._fill(column)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(page, 1)
        root.addWidget(self._footer())

    def _fill(self, column: QVBoxLayout) -> None:
        missing = self.report.missing_values
        changed = self.report.changed_items
        new_labels = self.report.new_labels
        alerts = self.report.structural_alerts
        anomalies = self.report.value_anomalies

        blocked = self.report.blocked_tables
        title = WrapLabel(
            "단가표를 만들려면 아래 값을 먼저 확정해 주세요"
            if blocked
            else "단가표를 만드는 데 필요한 값은 모두 확인됐습니다"
        )
        title.setObjectName("PageTitle")
        column.addWidget(title)

        summary = self.report.summary
        subtitle = WrapLabel(
            f"현재 파일  {self.report.baseline_file}\n"
            f"대조 파일  {self.report.target_file}\n"
            f"문구 {summary.total_labels}개 중 {summary.auto_passed}개는 그대로였습니다."
        )
        subtitle.setObjectName("PageSubtitle")
        column.addWidget(subtitle)

        for alert in [a for a in alerts if a.fatal]:
            column.addWidget(_banner(f"[{alert.sheet}] {alert.detail}", "danger"))

        # 1. 확정하지 않으면 단가표를 못 만드는 것 — 유일하게 붙잡는 구간
        if missing:
            column.addWidget(
                _banner(
                    f"{' · '.join(blocked)}를 만들 수 없습니다. "
                    f"아래 {len(missing)}개 값을 현재 파일의 어느 문구로 읽을지 정해 주세요.",
                    "danger",
                )
            )
            column.addWidget(_section_title(f"확정이 필요한 값  {len(missing)}건"))
            for value in missing:
                column.addWidget(
                    _banner(
                        f"[{value.sheet}] '{value.label}' — {value.reason}\n"
                        f"이 문구로 «{value.produces}» 을(를) 읽습니다.",
                        "warn",
                    )
                )
                card = _MissingCard(value, self._baseline, self._target)
                self._cards.append(card)
                column.addWidget(card)
        else:
            column.addWidget(
                _banner(
                    "기본급여·추가급여 단가표를 만들 수 있습니다. "
                    "아래는 참고 사항이니 넘기셔도 됩니다.",
                    "info",
                )
            )

        # 2~4. 넘겨도 되는 것들은 전부 접어 둔다
        if changed:
            section = _Collapsible(
                f"참고 · 문구가 바뀐 항목  {len(changed)}건",
                "단가표 값을 읽는 데는 쓰이지 않는 문구입니다. 확인하지 않아도 됩니다.",
            )
            for item in changed:
                card = _ChangedCard(item, self._baseline, self._target)
                self._cards.append(card)
                section.add(card)
            column.addWidget(section)

        if new_labels:
            section = _Collapsible(
                f"참고 · 현재 파일에 새로 생긴 문구  {len(new_labels)}건",
                "대조 파일에 없던 문구입니다. 문구를 누르면 조견표에서 어디인지 볼 수 있습니다.",
            )
            self._new_cards = [_NewLabelCard(item, self._target) for item in new_labels]
            for card in self._new_cards:
                section.add(card)
            column.addWidget(section)

        others = [a for a in alerts if not a.fatal]
        if others or anomalies:
            section = _Collapsible(
                f"참고 · 표 구조·값 변화  {len(others) + len(anomalies)}건",
                "값을 읽는 위치가 달라졌을 수 있으니, 다음 화면에서 값이 맞는지 확인해 주세요.",
            )
            for anomaly in anomalies:
                section.add(_banner(f"[{anomaly.sheet}] {anomaly.detail}", "warn"))
            for alert in others:
                section.add(_banner(f"[{alert.sheet}] {alert.detail}", "warn"))
            column.addWidget(section)

        column.addStretch(1)

    def _footer(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ReviewFooter")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(10)

        cancel = GhostButton("취소하고 돌아가기")
        cancel.clicked.connect(self.reject)
        confirm = PrimaryButton(
            "확정하고 값 읽기  →" if self.report.missing_values else "값 읽기 시작  →"
        )
        confirm.clicked.connect(self.accept)

        layout.addWidget(cancel)
        layout.addStretch(1)
        layout.addWidget(confirm)
        return bar

    def decisions(self) -> list[Decision]:
        made = [card.decision(self.report.run_id) for card in self._cards]
        made += [
            d for d in (c.decision(self.report.run_id) for c in self._new_cards) if d
        ]
        return made

    # 작년 문구 -> 담당자가 확정한 올해 문구
    def resolved_labels(self) -> dict[str, str]:
        out = {}
        for decision in self.decisions():
            chosen = decision.selected_label or decision.manual_input
            if chosen:
                out[decision.input_label] = chosen
        return out
