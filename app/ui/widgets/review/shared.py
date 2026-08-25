from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pandas as pd
from utils import xlsx_scan
from utils.qss import set_state

RADIUS = 3
ROW_HEIGHT = 24


def _column_name(index: int) -> str:
    # 0 -> A, 25 -> Z, 26 -> AA
    name, index = "", index + 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _window(center: int, size: int) -> list[int]:
    start = max(0, center - RADIUS)
    return list(range(start, min(size, start + RADIUS * 2 + 1)))


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:,}"
    return str(value)


# 조견표의 특정 셀 주변을 엑셀처럼 잘라서 보여주는 위젯
#
# 좌표(인정조사 B2)만 알려주면 담당자가 실제 파일을 열어 찾아가야 한다.
# 주변 몇 칸을 함께 보여주면 "여기가 맞다"를 화면에서 바로 판단할 수 있다.
#
# 시트 전체는 200행이 넘어 통째로 띄우면 오히려 못 찾는다. 대상 셀 기준으로
# 위아래·좌우 RADIUS 칸만 잘라 낸다.
class SheetPreview(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._caption = QLabel(title)
        self._caption.setObjectName("PreviewCaption")
        layout.addWidget(self._caption)

        self._table = QTableWidget()
        self._table.setObjectName("PreviewTable")
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.verticalHeader().setHighlightSections(False)
        self._table.setFixedHeight(ROW_HEIGHT * (RADIUS * 2 + 1) + 30)
        layout.addWidget(self._table)

        self._empty = QLabel()
        self._empty.setObjectName("PreviewEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(False)
        layout.addWidget(self._empty)

    def set_title(self, text: str) -> None:
        self._caption.setText(text)

    def show_message(self, text: str) -> None:
        self._table.setVisible(False)
        self._empty.setText(text)
        self._empty.setVisible(True)

    def show_cell(self, frame: pd.DataFrame, row: int, column: int) -> None:
        self._empty.setVisible(False)
        self._table.setVisible(True)

        rows = _window(row, frame.shape[0])
        columns = _window(column, frame.shape[1])

        self._table.clear()
        self._table.setRowCount(len(rows))
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels([_column_name(c) for c in columns])
        self._table.setVerticalHeaderLabels([str(r + 1) for r in rows])

        for y, r in enumerate(rows):
            for x, c in enumerate(columns):
                item = QTableWidgetItem(_text(frame.iat[r, c]))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if r == row and c == column:
                    item.setBackground(Qt.GlobalColor.yellow)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self._table.setItem(y, x, item)

        target = self._table.item(rows.index(row), columns.index(column))
        if target is not None:
            self._table.scrollToItem(
                target, QAbstractItemView.ScrollHint.PositionAtCenter
            )


class SheetSource:
    """미리보기에 필요한 시트만 그때그때 읽어 캐시한다.

    매칭이 끝나면 워크북을 버리므로 미리보기용 데이터가 남아 있지 않다.
    리포트에 시트를 통째로 실으면 계약이 무거워지고 메모리를 오래 붙들게 되므로,
    화면이 실제로 펼쳐질 때 해당 시트 하나만 읽는다.
    """

    def __init__(self, path=None):
        self.path = path
        self._cache: dict[str, pd.DataFrame | None] = {}

    def sheet(self, name: str) -> pd.DataFrame | None:
        if self.path is None:
            return None
        if name not in self._cache:
            try:
                # 서식만 남은 빈 행이 시트 끝까지 부풀어 있는 파일 방어 —
                # 값이 있는 마지막 행까지만 읽는다 (탐지 실패 시 전체 읽기).
                cap = xlsx_scan.true_row_counts(self.path).get(name)
                self._cache[name] = pd.read_excel(
                    self.path,
                    sheet_name=name,
                    engine="openpyxl",
                    header=None,
                    **({"nrows": cap} if cap else {}),
                )
            except Exception:
                self._cache[name] = None
        return self._cache[name]


def render(view: SheetPreview, source: SheetSource, location, side: str) -> None:
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
def banner(text: str, state: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("ReviewBanner")
    set_state(frame, "state", state)

    layout = QHBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    label = WrapLabel(text)
    label.setObjectName("ReviewBannerText")
    layout.addWidget(label)
    return frame


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("ReviewSectionTitle")
    return label
