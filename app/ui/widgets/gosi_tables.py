from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt6.QtGui import QBrush, QColor, QIntValidator
from PyQt6.QtWidgets import QLineEdit, QStyledItemDelegate, QStyle
from resources.styles.theme import SUCCESS, DANGER, WARNING_BG

COMPARE_COLUMNS = [("항목", False, True), ("조견표", True, False), ("고시", True, False), ("결과", False, False)]
PRICE_COLUMNS = [("급여", False, False), ("구분", False, True), ("금액", True, False), ("가산수당", True, False)]
RESULT_COLORS = {"일치": SUCCESS, "불일치": DANGER, "조견표에 없음": WARNING_BG}

def _to_int(value) -> int | None:
    if value is None or isinstance(value, bool): return None
    if isinstance(value, (int, float)): return int(round(value))
    text = str(value).replace(",", "").replace("원", "").strip()
    if not text: return None
    try: return int(round(float(text)))
    except ValueError: return None
    

class PriceEditDelegate(QStyledItemDelegate):
    def __init__(self, minimum=0, maximum=10_000_000, step=100, parent=None):
        super().__init__(parent)
        self._min, self._max, self._step = minimum, maximum, step

    def paint(self, painter, option, index):
        background = index.data(Qt.ItemDataRole.BackgroundRole)
        if background is not None and not (option.state & QStyle.StateFlag.State_Selected):
            painter.fillRect(option.rect, background)
        super().paint(painter, option, index)

    def createEditor(self, parent):
        editor = QLineEdit(parent)
        editor.setObjectName("CellEditor")
        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        editor.setStyleSheet("background-color: #FFFFFF; color: #000000; padding: 0 4px;")
        return editor


    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.UserRole)
        if value is None:
            value = _to_int(index.data(Qt.ItemDataRole.DisplayRole)) or 0
        editor.setText(str(int(value)) if value else "")
        editor.selectAll()

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        if not text:
            model.setData(index, "", Qt.ItemDataRole.EditRole)
            return

        value = _to_int(text)
        if value is None:
            return   
        model.setData(index, min(max(value, self._min), self._max), Qt.ItemDataRole.EditRole)

class GosiBaseTable(QTableWidget):
    rowSelected = pyqtSignal(dict)  # 행 클릭 시 출처(ref) 표시 시스널

    def __init__(self, columns, parent=None):
        super().__init__(0, len(columns), parent)
        self.setObjectName("DataTable")
        self.setHorizontalHeaderLabels([c[0] for c in columns])
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._columns_spec = columns

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        for col, spec in enumerate(columns):
            header.setSectionResizeMode(
                col, QHeaderView.ResizeMode.Stretch if spec[2] else QHeaderView.ResizeMode.ResizeToContents
            )
            
        self.itemSelectionChanged.connect(self._on_selection)

    def _fit_height(self):
        self.resizeRowsToContents()
        height = self.horizontalHeader().height() + 2 * self.frameWidth()
        for row in range(self.rowCount()):
            height += self.rowHeight(row)
        self.setFixedHeight(max(height, 60))

    def _add_row(self, values, ref=None, color=None):
        row = self.rowCount()
        self.insertRow(row)
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if col < len(self._columns_spec) and self._columns_spec[col][1]:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col == 0 and ref:
                item.setData(Qt.ItemDataRole.UserRole, ref)
            if color:
                item.setForeground(color)
            self.setItem(row, col, item)

    def _on_selection(self):
        items = self.selectedItems()
        if not items:
            return
        first = self.item(items[0].row(), 0)
        ref = first.data(Qt.ItemDataRole.UserRole) if first else None
        if ref:
            self.rowSelected.emit(ref)


class CompareTableWidget(GosiBaseTable):
    def __init__(self, parent=None):
        super().__init__(COMPARE_COLUMNS, parent)

    def fill_data(self, compare_data: dict, only_diff: bool = False):
        self.setRowCount(0)
        rows = compare_data.get("행") or []
        for item in rows:
            if only_diff and item["결과"] == "일치":
                continue
            color = QBrush(QColor(RESULT_COLORS.get(item["결과"], "#16212B")))
            self._add_row([
                item["항목"],
                f"{item['조견표']:,}원" if isinstance(item["조견표"], (int, float)) else "—",
                f"{item['고시']:,}원" if isinstance(item["고시"], (int, float)) else "—",
                item["결과"],
            ], item["출처"], None if item["결과"] == "일치" else color)
        self._fit_height()


class PriceTableWidget(GosiBaseTable):
    def __init__(self, parent=None):
        super().__init__(PRICE_COLUMNS, parent)

    def fill_data(self, prices_data: dict):
        self.setRowCount(0)
        for service, items in prices_data.items():
            for key, item in items.items():
                bonus = item.get("가산수당")
                self._add_row([
                    service, key, 
                    f"{item['금액']:,}", 
                    f"{bonus:,}" if bonus else ""
                ], item["출처"])
        self._fit_height()