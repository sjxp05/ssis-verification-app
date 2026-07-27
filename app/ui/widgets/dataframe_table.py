# dataframe을 엑셀처럼 표 형식으로 보여주는 위젯
# 셀을 누르면 옆에 산식 말풍선이 뜬다.

from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from models.dataframe_model import DataFrameModel
from ui.widgets.formula_bubble import FormulaBubble


class DataFrameTable(QTableView):
    # set_dataframe(df, formulas) 로 데이터를 넣는다.

    cellSelected = pyqtSignal(QModelIndex)

    def __init__(
        self,
        accent_columns: list[str] | None = None,
        show_row_numbers: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("DataTable")

        self._model = DataFrameModel(accent_columns=accent_columns)
        self.setModel(self._model)

        self._bubble = FormulaBubble(self)

        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setWordWrap(False)
        self.setCornerButtonEnabled(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.verticalHeader().setVisible(show_row_numbers)
        self.verticalHeader().setDefaultSectionSize(34)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setMinimumSectionSize(70)
        self.horizontalHeader().setFixedHeight(38)

        self.clicked.connect(self._on_clicked)
        self.verticalScrollBar().valueChanged.connect(self.hide_bubble)
        self.horizontalScrollBar().valueChanged.connect(self.hide_bubble)

    # --- API -------------------------------------------------------------
    def set_dataframe(
        self,
        df: pd.DataFrame,
        formulas: pd.DataFrame | dict | None = None,
    ) -> None:
        self.hide_bubble()
        self._model.set_dataframe(df, formulas)
        self.clearSelection()

    def dataframe(self) -> pd.DataFrame:
        return self._model.dataframe()

    def hide_bubble(self) -> None:
        self._bubble.hide()

    # --- 내부 ------------------------------------------------------------
    def _on_clicked(self, index: QModelIndex) -> None:
        self.cellSelected.emit(index)
        formula = self._model.formula_at(index)
        if not formula:
            self.hide_bubble()
            return

        rect = self.visualRect(index)
        anchor = rect.translated(
            self.viewport().mapToGlobal(rect.topLeft()) - rect.topLeft()
        )
        self._bubble.show_beside(
            anchor,
            title=self._model.cell_label(index),
            formula=formula,
        )

    # --- 이벤트 ----------------------------------------------------------
    def resizeEvent(self, event):  # noqa: N802
        self.hide_bubble()
        super().resizeEvent(event)

    def hideEvent(self, event):  # noqa: N802
        self.hide_bubble()
        super().hideEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bubble()
            return
        super().keyPressEvent(event)
