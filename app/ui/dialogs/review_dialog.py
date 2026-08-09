# 라벨 검토 화면
#
# 자동으로 확정하지 못한 항목만 보여준다. 완전일치·규칙파서로 끝난 항목은
# 목록에 나오지 않는다.
#
# 후보마다 점수 분해와 플래그를 함께 띄운다. 담당자가 고르는 근거라서다.
# 4번째 선택지인 직접 입력은 top-3 가 전부 틀렸을 때의 탈출구다.

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from jogyeon_matcher import Decision, MatchItem, MatchReport, Status

FLAG_TEXT = {
    "LOW_MARGIN": "1·2순위 점수차 작음",
    "CONTESTED": "다른 라벨과 후보 경합",
    "NUMERIC_VETO_APPLIED": "숫자 불일치",
    "ANTONYM_BLOCKED": "반의어 충돌",
}


# 검토 항목 하나. top-3 라디오 + 직접 입력.
class _ItemCard(QGroupBox):
    def __init__(self, item: MatchItem, parent=None):
        title = f"{item.input_label.raw}"
        if item.input_label.location:
            title += f"   ({item.input_label.location.sheet} {item.input_label.location.a1})"
        super().__init__(title, parent)
        self.item = item
        self.setObjectName("ReviewCard")

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        if item.flags:
            badges = " · ".join(FLAG_TEXT.get(f, f) for f in item.flags)
            warning = QLabel(f"⚠ {badges}")
            warning.setObjectName("ReviewFlag")
            layout.addWidget(warning)

        if item.status is Status.UNMATCHED:
            note = QLabel("자동으로 찾지 못했습니다. 아래에 직접 입력해 주세요.")
            note.setObjectName("ReviewNote")
            layout.addWidget(note)

        self.group = QButtonGroup(self)
        for candidate in item.candidates:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            radio = QRadioButton(f"{candidate.rank}.  {candidate.base_label}")
            radio.setProperty("rank", candidate.rank)
            radio.setProperty("label", candidate.base_label)
            self.group.addButton(radio)
            row_layout.addWidget(radio, 1)

            detail = (
                f"점수 {candidate.final:.3f}  "
                f"(BM25 {candidate.bm25:.2f} / 임베딩 {candidate.embedding:.2f})"
            )
            if candidate.base_location:
                detail += f"   {candidate.base_location.sheet} {candidate.base_location.a1}"
            if candidate.flags:
                detail += "   ⚠ " + ", ".join(FLAG_TEXT.get(f, f) for f in candidate.flags)
            score = QLabel(detail)
            score.setObjectName("ReviewScore")
            row_layout.addWidget(score)
            layout.addWidget(row)

        manual_row = QWidget()
        manual_layout = QHBoxLayout(manual_row)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        self.manual_radio = QRadioButton("직접 입력")
        self.group.addButton(self.manual_radio)
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("올해 조견표에 있는 문구를 그대로 적어 주세요")
        # textEdited 는 직접 타이핑에만 반응해서 붙여넣기·자동 채움을 놓친다.
        # 내용이 들어오면 무조건 직접 입력으로 돌려야 담당자가 적은 값이 버려지지 않는다.
        self.manual_edit.textChanged.connect(
            lambda text: self.manual_radio.setChecked(True) if text.strip() else None
        )
        manual_layout.addWidget(self.manual_radio)
        manual_layout.addWidget(self.manual_edit, 1)
        layout.addWidget(manual_row)

        # 후보가 있으면 1순위를 기본 선택. 없으면 직접 입력으로 유도한다.
        if item.candidates:
            self.group.buttons()[0].setChecked(True)
        else:
            self.manual_radio.setChecked(True)

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


class ReviewDialog(QDialog):
    def __init__(self, report: MatchReport, parent=None):
        super().__init__(parent)
        self.report = report
        self.setWindowTitle("조견표 라벨 확인")
        self.resize(940, 720)

        root = QVBoxLayout(self)

        summary = report.summary
        head = QLabel(
            f"{report.baseline_file} → {report.target_file}\n"
            f"전체 {summary.total_labels}건 중 자동 확인 {summary.auto_passed}건, "
            f"확인 필요 {summary.needs_review}건, 찾지 못함 {summary.unmatched}건"
        )
        head.setObjectName("ReviewSummary")
        root.addWidget(head)

        for alert in report.structural_alerts:
            banner = QLabel(
                f"{'🚫' if alert.fatal else '⚠'} [{alert.sheet}] {alert.detail}"
            )
            banner.setObjectName("ReviewAlertFatal" if alert.fatal else "ReviewAlert")
            banner.setWordWrap(True)
            root.addWidget(banner)

        for anomaly in report.value_anomalies:
            banner = QLabel(f"⚠ 값 검증 — {anomaly.detail}")
            banner.setObjectName("ReviewAlert")
            banner.setWordWrap(True)
            root.addWidget(banner)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        self._cards = [_ItemCard(item) for item in report.review_items]
        for card in self._cards:
            holder_layout.addWidget(card)
        if not self._cards:
            done = QLabel("확인이 필요한 항목이 없습니다. 모든 라벨을 자동으로 찾았습니다.")
            done.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(done)
        holder_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def decisions(self) -> list[Decision]:
        return [card.decision(self.report.run_id) for card in self._cards]

    # 작년 문구 -> 담당자가 확정한 올해 문구
    def resolved_labels(self) -> dict[str, str]:
        out = {}
        for decision in self.decisions():
            chosen = decision.selected_label or decision.manual_input
            if chosen:
                out[decision.input_label] = chosen
        return out
