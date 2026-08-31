# 조견표 라벨 대조 결과 검토 화면

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from jogyeon_matcher import Decision, MatchReport

from ui.components.button import GhostButton, PrimaryButton
from ui.components.scroll_page import centered_scroll_page

from ui.widgets.review.shared import *
from ui.widgets.review.collapsible import Collapsible
from ui.widgets.review.review_cards import ChangedCard, MissingCard
from ui.widgets.review.new_label_card import NewLabelCard


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
        self.resize(1120, 820)

        self._baseline = SheetSource(baseline_path)
        self._target = SheetSource(target_path)
        self._cards: list[ChangedCard] = []
        self._new_cards: list[NewLabelCard] = []

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
            "단가표를 만들려면 아래 값을 먼저 확정해 주세요."
            if blocked
            else "단가표를 만드는 데 필요한 값을 모두 확인했습니다."
        )
        title.setObjectName("PageTitle")
        column.addWidget(title)

        summary = self.report.summary
        subtitle = WrapLabel(
            f"현재 파일  {self.report.target_file}\n"
            f"대조 파일  {self.report.baseline_file}\n"
            f"문구 {summary.total_labels}개 중 {summary.auto_passed}개는 변하지 않았습니다."
        )
        subtitle.setObjectName("PageSubtitle")
        column.addWidget(subtitle)

        for alert in [a for a in alerts if a.fatal]:
            column.addWidget(banner(f"[{alert.sheet}] {alert.detail}", "danger"))

        # 1. 확정하지 않으면 단가표를 못 만드는 것 — 유일하게 붙잡는 구간
        if missing:
            column.addWidget(
                banner(
                    f"{' · '.join(blocked)}를 만들 수 없습니다. "
                    f"아래 {len(missing)}개 값을 현재 파일의 어느 문구로 읽을지 정해 주세요.",
                    "danger",
                )
            )
            column.addWidget(section_title(f"확정이 필요한 값  {len(missing)}건"))
            for value in missing:
                column.addWidget(
                    banner(
                        f"[{value.sheet}] '{value.label}' — {value.reason}\n"
                        f"이 문구로 «{value.produces}» 을(를) 읽습니다.",
                        "warn",
                    )
                )
                card = MissingCard(value, self._baseline, self._target)
                self._cards.append(card)
                column.addWidget(card)
        else:
            column.addWidget(
                banner(
                    "기본급여·추가급여 단가표를 만들 수 있습니다. "
                    "아래는 참고 사항이므로 확인하지 않아도 됩니다.",
                    "info",
                )
            )

        # 2~4. 넘겨도 되는 것들은 전부 접어 둔다
        if changed:
            section = Collapsible(
                f"참고 · 문구가 바뀐 항목  {len(changed)}건",
                "단가표 값을 읽는 데 사용되지 않는 문구이므로 확인하지 않아도 됩니다.",
            )
            for item in changed:
                card = ChangedCard(item, self._baseline, self._target)
                self._cards.append(card)
                section.add(card)
            column.addWidget(section)

        if new_labels:
            section = Collapsible(
                f"참고 · 현재 파일에 새로 생긴 문구  {len(new_labels)}건",
                "대조 파일에 없던 문구입니다. 문구를 누르면 조견표에서 어디인지 볼 수 있습니다.",
            )
            self._new_cards = [NewLabelCard(item, self._target) for item in new_labels]
            for card in self._new_cards:
                section.add(card)
            column.addWidget(section)

        others = [a for a in alerts if not a.fatal]
        if others or anomalies:
            section = Collapsible(
                f"참고 · 표 구조·값 변화  {len(others) + len(anomalies)}건",
                "값을 읽는 위치가 달라졌을 수 있으므로 다음 화면에서 값이 맞는지 확인해 주세요.",
            )
            for anomaly in anomalies:
                section.add(banner(f"[{anomaly.sheet}] {anomaly.detail}", "warn"))
            for alert in others:
                section.add(banner(f"[{alert.sheet}] {alert.detail}", "warn"))
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
