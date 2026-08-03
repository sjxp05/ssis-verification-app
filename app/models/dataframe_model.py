# pandas DataFrame 을 QTableView 에 붙이기 위한 모델
#
# - 숫자 컬럼은 천단위 콤마 + 우측 정렬
# - accent_columns 로 지정한 컬럼은 파란 글씨 (등급코드 등)
# - 셀마다 산식 문자열을 따로 들고 있다가 말풍선에 넘겨준다

from __future__ import annotations

from typing import Any

import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from resources.styles import theme


class DataFrameModel(QAbstractTableModel):
    def __init__(
        self,
        df: pd.DataFrame | None = None,
        formulas: pd.DataFrame | dict[tuple[int, int], str] | None = None,
        accent_columns: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()
        self._formulas = formulas if formulas is not None else {}
        self._accent = set(accent_columns or [])

    # --- 데이터 교체 ------------------------------------------------------
    def set_dataframe(
        self,
        df: pd.DataFrame,
        formulas: pd.DataFrame | dict[tuple[int, int], str] | None = None,
    ) -> None:
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self._formulas = formulas if formulas is not None else {}
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    # --- 기본 구현 --------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._df.index)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._df.columns)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int
    ):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        column = self._df.columns[index.column()]
        value = self._df.iat[index.row(), index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(value)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            flag = (
                Qt.AlignmentFlag.AlignRight
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                else Qt.AlignmentFlag.AlignLeft
            )
            return int(flag | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.ForegroundRole and column in self._accent:
            return QColor(theme.ACCENT)

        if role == Qt.ItemDataRole.ToolTipRole:
            return self.formula_at(index) or None

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # --- 산식 -------------------------------------------------------------
    def formula_at(self, index: QModelIndex) -> str:
        if not index.isValid():
            return ""
        row, col = index.row(), index.column()
        if isinstance(self._formulas, pd.DataFrame):
            if row < len(self._formulas.index) and col < len(self._formulas.columns):
                value = self._formulas.iat[row, col]
                return "" if pd.isna(value) else str(value)
            return ""
        column = str(self._df.columns[col])
        return str(
            self._formulas.get((row, col))
            or self._formulas.get((row, column))
            or self._formulas.get(column)
            or ""
        )

    def cell_label(self, index: QModelIndex) -> str:
        # 말풍선 제목에 쓸 '행 · 컬럼' 라벨.
        if not index.isValid():
            return ""
        return f"{index.row() + 1}행 · {self._df.columns[index.column()]}"

    # --- 내부 -------------------------------------------------------------
    @staticmethod
    def _display(value: Any) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, bool):
            return "예" if value else "아니오"
        if isinstance(value, int):
            return f"{value:,}"
        if isinstance(value, float):
            return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"
        return str(value)
