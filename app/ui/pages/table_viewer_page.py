# 2단계 — 생성된 단가표 화면.
#
# pandas DataFrame 을 엑셀 레이아웃처럼 보여주고,
# 셀을 클릭하면 그 값이 어떻게 나온 값인지 산식을 말풍선으로 띄운다.

from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import QModelIndex, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.card import Card
from ui.components.button import PrimaryButton
from ui.components.tab_bar import SegmentedTabBar
from ui.widgets.dataframe_table import DataFrameTable

TABS = {
    "unit_price": [
        {
            "label": "기본급여 단가표",
            "title": "기본급여 단가표 생성",
            "card_title": "기본급여 단가표 미리보기",
        },
        {
            "label": "추가급여 단가표",
            "title": "추가급여 단가표 생성",
            "card_title": "추가급여 단가표 미리보기",
        },
    ],
    "notice_verify": [
        {
            "label": "결제단가표",
            "title": "결제단가표 생성",
            "card_title": "결제단가표 미리보기",
        },
    ],
}
ACCENT_COLUMNS = ["등급코드", "코드", "항목코드"]
ACTION_TEXT = "Excel 파일로 저장"


class TableViewerPage(QWidget):
    exportRequested = pyqtSignal(int, object)  # tab index, DataFrame
    cellSelected = pyqtSignal(int, QModelIndex)

    def __init__(self, parent: QWidget | None = None, flow: str = "unit_price"):
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._flow = flow

        self._tabs = SegmentedTabBar([tab["label"] for tab in TABS[flow]], flow=flow)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._card = Card()
        self._card_title = QLabel()
        self._card_title.setObjectName("CardTitle")
        self._card_hint = QLabel()
        self._card_hint.setObjectName("CardHint")

        card_head = QHBoxLayout()
        card_head.addWidget(self._card_title)
        card_head.addStretch(1)
        card_head.addWidget(self._card_hint)
        self._card.add_layout(card_head)

        self._stack = QStackedWidget()
        self._tables: list[DataFrameTable] = []
        self._card.add_widget(self._stack)
        self._build_tables(flow)

        self._action = PrimaryButton("")
        self._action.clicked.connect(self._on_export)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.addWidget(self._title)
        header.addWidget(self._subtitle)

        content = QVBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._card, 1)
        content.addWidget(self._action)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(28, 18, 28, 24)
        self._outer.setSpacing(18)
        self._outer.addLayout(header)
        self._outer.addWidget(self._tabs)
        self._outer.addLayout(content, 1)

        self._on_tab_changed(flow, 0)

    # --- API --------------------------------------------------------------
    def set_flow(self, flow: str) -> None:
        # flow가 바뀔 때만 탭바·표를 새로 만든다.
        if flow == self._flow:
            return
        self._flow = flow
        self._build_tabs(flow)
        self._build_tables(flow)
        self._on_tab_changed(flow, 0)

    def set_table(
        self,
        flow: str,
        tab_index: int,
        df: pd.DataFrame,
        formulas: pd.DataFrame | dict | None = None,
    ) -> None:
        self.set_flow(flow)
        self._tables[tab_index].set_dataframe(df, formulas)

    # --- 내부 빌드 ----------------------------------------------------------
    def _build_tabs(self, flow: str) -> None:
        # flow가 바뀔 때만 탭바를 새로 만들어 자리에 갈아 끼운다.
        old_tabs = self._tabs
        new_tabs = SegmentedTabBar([tab["label"] for tab in TABS[flow]], flow=flow)
        new_tabs.currentChanged.connect(self._on_tab_changed)
        self._outer.replaceWidget(old_tabs, new_tabs)
        old_tabs.deleteLater()
        self._tabs = new_tabs

    def _build_tables(self, flow: str) -> None:
        for table in self._tables:
            self._stack.removeWidget(table)
            table.deleteLater()
        self._tables = []

        for index in range(len(TABS[flow])):
            table = DataFrameTable(
                accent_columns=ACCENT_COLUMNS, show_row_numbers=False
            )
            table.cellSelected.connect(
                lambda idx, tab=index: self.cellSelected.emit(tab, idx)
            )
            self._tables.append(table)
            self._stack.addWidget(table)

    def current_dataframe(self) -> pd.DataFrame:
        return self._tables[self._tabs.current()].dataframe()

    def hide_bubbles(self) -> None:
        for table in self._tables:
            table.hide_bubble()

    def reset_tab(self, flow: str = "unit_price", index: int = 0) -> None:
        self._tabs.set_current(index)  # 버튼 상태
        self._on_tab_changed(flow, index)  # 제목·부제·표·저장 버튼 문구

    # --- 동작 -------------------------------------------------------------
    def _on_tab_changed(self, flow: str, index: int) -> None:
        self.hide_bubbles()
        spec = TABS[flow][index]
        self._title.setText(spec["title"])
        self._card_title.setText("단가표 미리보기")
        self._action.setText(ACTION_TEXT)
        self._stack.setCurrentIndex(index)

    def _on_export(self) -> None:
        index = self._tabs.current()
        self.exportRequested.emit(index, self._tables[index].dataframe())
