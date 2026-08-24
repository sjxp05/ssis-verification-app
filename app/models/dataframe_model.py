# pandas DataFrame 을 QTableView 에 붙이기 위한 모델

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QColor

from resources.styles import theme

ERROR_BG = theme.ERROR_BG
WARNING_BG = theme.WARNING_BG


class DataFrameModel(QAbstractTableModel):
    # 더블클릭 편집으로 셀 값 변경시
    cellEdited = pyqtSignal(int, str)

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
        # 검증 결과: 오류 셀 / 확인 필요 셀 / 행 지표 텍스트
        self._issue_cells: dict[tuple[int, str], str] = {}
        self._warn_cells: dict[tuple[int, str], str] = {}
        self._row_metrics: dict[int, str] = {}

    # --- 데이터 교체 ------------------------------------------------------
    def set_dataframe(
        self,
        df: pd.DataFrame,
        formulas: pd.DataFrame | dict[tuple[int, int], str] | None = None,
    ) -> None:
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self._formulas = formulas if formulas is not None else {}
        self._issue_cells = {}
        self._warn_cells = {}
        self._row_metrics = {}
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    # --- 셀 값 수정 (오류 수정 기능) ---------------------------------------
    def set_cell_value(self, row: int, column: str, value) -> bool:
        # 패널의 '추천값 적용'/'직접 입력'으로 셀 값을 바꾼다.
        # _df 자체를 바꾸므로 이후 엑셀 저장(dataframe())에 그대로 반영
        if column not in self._df.columns:
            return False
        if not (0 <= row < len(self._df.index)):
            return False
        col = int(self._df.columns.get_loc(column))
        current = self._df.iat[row, col]
        try:
            # 기존 셀이 숫자면 같은 타입으로 맞춘다 (int 컬럼은 int로, float 컬럼은 소수점 유지)
            if pd.api.types.is_number(current) and not isinstance(current, bool):
                parsed = float(str(value).replace(",", ""))
                value = (
                    int(parsed) if isinstance(current, (int, np.integer)) else parsed
                )
        except (ValueError, TypeError):
            return False
        self._df.iat[row, col] = value
        index = self.index(row, col)
        self.dataChanged.emit(index, index)
        return True

    # --- 검증 결과 주입 ---------------------------------------------------
    def set_annotations(
        self,
        issue_cells: dict[tuple[int, str], str] | None,
        row_metrics: dict[int, str] | None,
        warn_cells: dict[tuple[int, str], str] | None = None,
    ) -> None:
        # issue_cells: (행, 컬럼명) -> 오류 요약 (빨간 셀로 표시)
        # row_metrics: 행 -> 부담률/증가율 지표
        # warn_cells: (행, 컬럼명) -> 확인 필요 사유 (노란 셀로 표시)
        self._issue_cells = dict(issue_cells or {})
        self._warn_cells = dict(warn_cells or {})
        self._row_metrics = dict(row_metrics or {})
        if len(self._df.index) and len(self._df.columns):
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._df.index) - 1, len(self._df.columns) - 1),
            )

    def has_issue(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False
        column = str(self._df.columns[index.column()])
        return (index.row(), column) in self._issue_cells

    # --- 기본 구현 --------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.index)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
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

        if role == Qt.ItemDataRole.EditRole:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return ""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)

        # 검증 표시 셀: 오류 - 빨강, 확인 필요 - 노랑
        if role == Qt.ItemDataRole.BackgroundRole:
            if (index.row(), column) in self._issue_cells:
                return QColor(ERROR_BG)
            if (index.row(), column) in self._warn_cells:
                return QColor(WARNING_BG)
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            # 오류·경고 셀은 배경색으로만 구분하고 글씨는 검정 유지
            if column in self._accent:
                return QColor(theme.ACCENT)
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(index, column) or None

        return None

    # 더블클릭 편집 반영: 숫자 셀이면 숫자, 아니면 문자 그대로
    def setData(
        self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        column = str(self._df.columns[index.column()])
        current = self._df.iat[index.row(), index.column()]
        text = str(value).strip()
        if not text:
            return False
        if pd.api.types.is_number(current) and not isinstance(current, bool):
            try:
                parsed = float(text.replace(",", "")) if text else 0.0
            except ValueError:
                return False
            value = int(parsed) if isinstance(current, (int, np.integer)) else parsed
        else:
            value = text
        self._df.iat[index.row(), index.column()] = value
        self.dataChanged.emit(index, index)
        self.cellEdited.emit(index.row(), column)
        return True

    # at 위치에 행 삽입 (None 이면 맨 아래)
    def add_row(self, values: dict, at: int | None = None) -> int:
        row = (
            len(self._df.index) if at is None else max(0, min(at, len(self._df.index)))
        )
        self.beginInsertRows(QModelIndex(), row, row)
        new_row = [values.get(str(col), "") for col in self._df.columns]
        upper = self._df.iloc[:row]
        lower = self._df.iloc[row:]
        inserted = pd.DataFrame([new_row], columns=self._df.columns)
        self._df = pd.concat([upper, inserted, lower], ignore_index=True)
        self.endInsertRows()
        return row

    # row 위치의 행 삭제
    def remove_row(self, row: int) -> bool:
        if not (0 <= row < len(self._df.index)):
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        self._df = self._df.drop(index=self._df.index[row]).reset_index(drop=True)
        self.endRemoveRows()
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

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
        # 말풍선 제목에 쓸 '행 · 컬럼' 라벨
        if not index.isValid():
            return ""
        return f"{index.row() + 1}행 · {self._df.columns[index.column()]}"

    # --- 내부 -------------------------------------------------------------
    def _tooltip(self, index: QModelIndex, column: str) -> str:
        parts = []
        issue = self._issue_cells.get((index.row(), column))
        if issue:
            parts.append(f"✕ {issue}")
        warn = self._warn_cells.get((index.row(), column))
        if warn:
            parts.append(f"⚠ {warn}")
        metric = self._row_metrics.get(index.row())
        if metric:
            parts.append(metric)
        formula = self.formula_at(index)
        if formula:
            parts.append(formula)
        return "\n\n".join(parts)

    @staticmethod
    def _display(value: Any) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, bool):
            return "예" if value else "아니오"
        if isinstance(value, int):
            return f"{value:,}"
        if isinstance(value, float):
            return f"{value:,.0f}" if value.is_integer() else f"{value:,f}"
        return str(value)
