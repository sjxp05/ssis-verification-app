from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QApplication
)

from services import gosi_verifier
from services.table_writer import TableWriter
from ui.components.card import Card
from ui.components.button import GhostButton, PrimaryButton
from ui.components.tab_bar import SegmentedTabBar
from utils.qss import set_state

# 결제단가표 생성 상태 — ConstantsPage 와 같은 이름을 쓴다.
WAITING, FILLED, BUSY, READY, FAILED = "waiting", "filled", "busy", "ready", "failed"

_GENERATE_TEXT = "결제단가표 생성"
_NEXT_TEXT = "다음 단계로  →"
_BUSY_TEXT = "⟳  결제단가표를 생성하는 중..."
_LOADING_TEXT = "⟳  불러오는 중..."
_OPEN_TEXT = "고시 파일 불러오기"
_OPEN_DONE_TEXT = "✓ {name}"
_ONLY_DIFF_ON = "다른 것만 보기"
_ONLY_DIFF_OFF = "전체 보기"
_DOC_HIDE_TEXT = "고시 원문 접기"
_DOC_SHOW_TEXT = "고시 원문 펼치기"

TABS = {
    "notice_verify": [
        {
            "label": "월 한도액",
            "title": "고시와 조견표의 월한도액 정보가 맞는지 확인해 주세요.",
            "card_title": "월 한도액 대조",
        },
        {
            "label": "서비스 단가",
            "title": "서비스별 단가가 맞는지 확인해 주세요.",
            "card_title": "서비스 단가 확인",
        },
    ],
}

# 탭별로 원문 패널에 보여줄 장(章). 비우면 문서 전체를 보여준다.
TAB_CHAPTERS = {0: ("제2장",), 1: ("제3장", "제4장")}

# 표 열 구성. (제목, 오른쪽 정렬, 남는 폭을 가져갈 열)
COMPARE_COLUMNS = [("항목", False, True), ("조견표", True, False),
                   ("고시", True, False), ("결과", False, False)]
PRICE_COLUMNS = [("급여", False, False), ("구분", False, True),
                 ("금액", True, False), ("가산수당", True, False)]

# 대조 결과 색. 실제 팔레트가 QSS 에 있으면 그쪽 값으로 맞춘다.
RESULT_COLORS = {"일치": "#0E6F63", "불일치": "#B23A2B", "조견표에 없음": "#96620F"}

# 고시 원문 패널 HTML. 스타일시트 없는 선택자가 자식 위젯을 덮어쓰지 않도록
# 원문은 QTextBrowser 안에서만 쓰이는 인라인 HTML 로 그린다.
_DOC_CSS = """
body { font-family:'바탕','Batang',serif; font-size:11pt; color:#16212B; }
p { margin:0 0 8px 0; }
p.chapter { font-size:13pt; font-weight:bold; margin:16px 0 10px 0; }
p.item { font-weight:bold; margin-top:12px; }
p.body { color:#4B5B69; font-size:10pt; }
table { border-collapse:collapse; margin:6px 0 14px 0; }
td { border:1px solid #CBD5DC; padding:4px 7px; }
td.head { background:#EDF1F3; font-weight:bold; }
td.hit { background:#FFE07A; }
"""


class _TableWriteSignals(QObject):
    finished = pyqtSignal(int, object)  # generation, Tables
    failed = pyqtSignal(int, str)  # generation, 사유


class _TableWriteTask(QRunnable):
    """결제단가표 생성기를 GUI 스레드 밖에서 돌린다."""

    def __init__(self, table_writer: TableWriter, service_prices: dict,
                 generation: int) -> None:
        super().__init__()
        self.signals = _TableWriteSignals()
        self._table_writer = table_writer
        self._service_prices = service_prices
        self._generation = generation

    def run(self) -> None:
        try:
            tables = self._table_writer.write_payment_table(
                service_prices=self._service_prices,
                basic_df=None,  # TODO: 기본급여 단가표(또는 단가표 엑셀 path)를 넣을 것
            )
        except Exception as error:
            self.signals.failed.emit(self._generation,
                                     str(error) or type(error).__name__)
        else:
            self.signals.finished.emit(self._generation, tables)


class GosiConstantsPage(QWidget):
    # tablesReady(dict): 결제단가표 생성이 끝나 다음 단계로 넘어가도 된다는 신호
    tablesReady = pyqtSignal(object)
    valuesChanged = pyqtSignal()  # 다른 고시를 불러오면 이미 만든 표는 낡은 것이 된다
    valuesKept = pyqtSignal()  # 같은 고시를 다시 불러온 경우

    def __init__(
        self,
        table_writer: TableWriter | None = None,
        parent: QWidget | None = None,
        flow: str = "notice_verify",
    ):
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._flow = flow
        self._table_writer = table_writer
        self._pool = QThreadPool.globalInstance()

        self._reference: dict = {}  # 조견표에서 파싱한 평평한 딕셔너리
        self._result: dict | None = None  # gosi_reader.read_gosi() 결과
        self._path: str | None = None
        self._tables: dict | None = None
        self._generation = 0
        self._state = WAITING
        self._only_diff = False

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._tabs = SegmentedTabBar([tab["label"] for tab in TABS[flow]], flow=flow)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._card = Card()
        self._card_title = QLabel()
        self._card_title.setObjectName("CardTitle")
        self._card_hint = QLabel()
        self._card_hint.setObjectName("CardHint")

        self._diff_button = GhostButton(_ONLY_DIFF_ON)
        self._diff_button.clicked.connect(self._toggle_only_diff)
        self._doc_button = GhostButton(_DOC_HIDE_TEXT)
        self._doc_button.clicked.connect(self._toggle_document)

        card_head = QHBoxLayout()
        card_head.addWidget(self._card_title)
        card_head.addStretch(1)
        card_head.addWidget(self._card_hint)
        card_head.addWidget(self._diff_button)
        card_head.addWidget(self._doc_button)
        self._card.add_layout(card_head)

        # 왼쪽 고시 원문 — 탭이 바뀌어도 하나를 계속 쓰고 내용만 갈아 끼운다.
        self._doc = QTextBrowser()
        self._doc.setObjectName("NoticeDocument")
        self._doc.setOpenExternalLinks(False)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_compare_panel())
        self._stack.addWidget(self._build_price_panel())

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._doc)
        self._splitter.addWidget(self._stack)
        self._splitter.setSizes([1, 1])
        self._card.add_widget(self._splitter)

        self._next = PrimaryButton(_GENERATE_TEXT)
        self._next.setEnabled(False)
        self._next.clicked.connect(self._on_next)

        self._hint = QLabel()
        self._hint.setObjectName("GenerateHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.addWidget(self._title)
        header.addWidget(self._subtitle)

        content = QVBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._card, 1)
        content.addWidget(self._next)
        content.addWidget(self._hint)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(28, 18, 28, 24)
        self._outer.setSpacing(18)
        # TODO: 스텝 인디케이터는 상위 화면에서 붙인다 (여기서는 자리만 비워 둠)
        self._outer.addLayout(header)
        self._outer.addWidget(self._tabs)
        self._outer.addLayout(content, 1)

        self._on_tab_changed(flow, 0)
        self._set_state(WAITING)

    # --- API --------------------------------------------------------------
    def set_flow(self, flow: str) -> None:
        # 이 페이지는 notice_verify 전용이라 흐름이 바뀌면 값만 비운다.
        if flow != self._flow:
            self._flow = flow
            self.clear()

    def set_reference(self, values: dict | None) -> None:
        """조견표에서 파싱한 평평한 딕셔너리. 고시를 읽기 전에 넣어 둔다."""
        self._reference = values or {}
        if self._result:
            self._result["대조"] = gosi_verifier.compare_with_reference(
                self._result["월한도액"], self._reference)
            self._fill_all()
            self._refresh_state()

    def load_notice(self, path: str) -> None:
        """고시 파일을 읽어 화면을 채운다. UploadPage 가 파일을 고른 뒤 부른다."""
        same = path == self._path
        try:
            result = gosi_verifier.read_gosi(path, self._reference)
        except Exception as error:  # hwpx 가 아니거나 파일이 손상된 경우
            QMessageBox.warning(self, "불러오기 실패",
                                f"고시를 읽지 못했습니다:\n{error}")
            return
        self._result = result
        self._path = path
        self._tables = None
        self._fill_all()
        (self.valuesKept if same else self.valuesChanged).emit()
        self._refresh_state()

    def clear(self) -> None:
        self._result = None
        self._path = None
        self._tables = None
        self._fill_all()
        self._set_state(WAITING)

    def values(self) -> dict:
        """결제단가표로 넘길 단가 dict. TableWriter 의 service_prices 인자.

        월 한도액은 조견표가 기준이라 여기 포함하지 않는다.
        """
        return (self._result or {}).get("단가", {})

    def compare_result(self) -> dict:
        return (self._result or {}).get("대조") or {}

    def issues(self) -> list:
        return (self._result or {}).get("검증") or []

    def reset_next_button(self) -> None:
        # 다음 화면으로 넘어간 뒤 호출: 로딩 표시로 바꿨던 버튼 모양을 되돌린다.
        if self._state == READY:
            self._next.setEnabled(True)
            self._next.setText(_NEXT_TEXT)

    # --- 내부 빌드 ----------------------------------------------------------
    def _new_table(self, columns) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setObjectName("ParsedTable")
        table.setHorizontalHeaderLabels([c[0] for c in columns])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        for col, spec in enumerate(columns):
            header.setSectionResizeMode(
                col, QHeaderView.ResizeMode.Stretch if spec[2]
                else QHeaderView.ResizeMode.ResizeToContents)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.itemSelectionChanged.connect(lambda t=table: self._on_row_selected(t))
        table.setProperty("columns", columns)
        return table

    @staticmethod
    def _fit_height(table: QTableWidget) -> None:
        """행 수만큼 표 높이를 늘려 안쪽 스크롤이 생기지 않게 한다."""
        table.resizeRowsToContents()
        height = table.horizontalHeader().height() + 2 * table.frameWidth()
        for row in range(table.rowCount()):
            height += table.rowHeight(row)
        table.setFixedHeight(max(height, 60))

    def _section(self, title: str, widget: QWidget) -> QWidget:
        label = QLabel(title)
        label.setObjectName("GroupLabel")
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        box.addWidget(label)
        box.addWidget(widget)
        holder = QWidget()
        holder.setLayout(box)
        return holder

    def _scroll(self, widgets) -> QScrollArea:
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(14)
        for widget in widgets:
            column.addWidget(widget)
        column.addStretch(1)

        # 스타일시트 없는 선택자는 자식 위젯까지 덮어써 버리므로
        # 반드시 objectName + ID 선택자로 범위를 한정한다.
        body = QWidget()
        body.setLayout(column)
        body.setObjectName("NoticeScrollBody")
        body.setStyleSheet("QWidget#NoticeScrollBody { background: transparent; }")

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setObjectName("NoticeScrollArea")
        area.setStyleSheet(
            "QScrollArea#NoticeScrollArea { background: transparent; border: none; }")
        viewport = area.viewport()
        viewport.setObjectName("NoticeScrollViewport")
        viewport.setStyleSheet(
            "QWidget#NoticeScrollViewport { background: transparent; }")
        area.setWidget(body)
        return area

    def _build_compare_panel(self) -> QWidget:
        self._compare_summary = QLabel()
        self._compare_summary.setObjectName("CompareSummary")
        self._compare_summary.setWordWrap(True)
        self._compare_table = self._new_table(COMPARE_COLUMNS)
        return self._scroll([
            self._compare_summary,
            self._section("조견표 ↔ 고시", self._compare_table),
        ])

    def _build_price_panel(self) -> QWidget:
        self._price_table = self._new_table(PRICE_COLUMNS)
        self._issue_label = QLabel()
        self._issue_label.setObjectName("FindingDetail")
        self._issue_label.setWordWrap(True)
        return self._scroll([
            self._section("고시에서 읽은 단가 (결제단가표로 전달)", self._price_table),
            self._section("검증", self._issue_label),
        ])

    # --- 화면 채우기 --------------------------------------------------------
    def _fill_all(self) -> None:
        name = os.path.basename(self._path) if self._path else None
        self._subtitle.setText(
            f"{name} · 조견표 항목 {len(self._reference)}개" if name
            else "고시 파일을 불러오면 조견표와 대조한 결과가 표시됩니다.")

        self._fill_compare_table()
        self._fill_price_table()
        self._render_document()

    def _row(self, table: QTableWidget, values, ref=None, color=None) -> None:
        row = table.rowCount()
        table.insertRow(row)
        columns = table.property("columns") or []
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if col < len(columns) and columns[col][1]:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)
            if col == 0 and ref:
                # 행을 누르면 원문 어디로 갈지 첫 칸에 담아 둔다.
                item.setData(Qt.ItemDataRole.UserRole, ref)
            if color:
                item.setForeground(color)
            table.setItem(row, col, item)

    def _fill_compare_table(self) -> None:
        from PyQt6.QtGui import QBrush, QColor

        self._compare_table.setRowCount(0)
        compare = self.compare_result()
        rows = compare.get("행") or []

        if not rows:
            self._compare_summary.setText(
                "대조할 값이 없습니다. 고시와 조견표를 모두 불러와 주세요.")
            self._fit_height(self._compare_table)
            return

        wrong = compare["불일치"] + compare["조견표에 없음"]
        self._compare_summary.setText(
            f"전체 {len(rows)}항목 · 일치 {compare['일치']} · "
            f"불일치 {compare['불일치']} · 조견표에 없음 {compare['조견표에 없음']}")
        set_state(self._compare_summary, "state", "fail" if wrong else "pass")

        for item in rows:
            if self._only_diff and item["결과"] == "일치":
                continue
            color = QBrush(QColor(RESULT_COLORS.get(item["결과"], "#16212B")))
            self._row(self._compare_table, [
                item["항목"],
                _won(item["조견표"]) if item["조견표"] is not None else "—",
                _won(item["고시"]),
                item["결과"],
            ], item["출처"], None if item["결과"] == "일치" else color)
        self._fit_height(self._compare_table)

    def _fill_price_table(self) -> None:
        self._price_table.setRowCount(0)
        for service, items in (self._result or {}).get("단가", {}).items():
            for key, item in items.items():
                bonus = item.get("가산수당")
                self._row(self._price_table,
                          [service, key, _won(item["금액"]),
                           _won(bonus) if bonus else ""],
                          item["출처"])
        self._fit_height(self._price_table)

        issues = self.issues()
        self._issue_label.setText(
            "\n\n".join(f"[{i['항목']}] {i['메시지']}" for i in issues)
            + f"\n\n{gosi_verifier.FIX_GUIDE}" if issues
            else "고시 안에서의 검증은 모두 통과했습니다.")

    # --- 고시 원문 패널 ------------------------------------------------------
    def _visible_blocks(self) -> list[dict]:
        """현재 탭에서 원문 패널에 보여줄 블록만 고른다."""
        blocks = (self._result or {}).get("블록") or []
        chapters = TAB_CHAPTERS.get(self._tabs.current())
        if not chapters:
            return list(blocks)
        return [b for b in blocks
                if any(c in (b["문맥"].get("장") or "") for c in chapters)]

    def _render_document(self, highlight: dict | None = None) -> None:
        """원문을 HTML 로 그린다. highlight 가 있으면 그 칸만 강조한다.

        문서가 100블록 남짓이라 강조할 때마다 통째로 다시 그려도 충분히 빠르고,
        조각을 골라 고치는 것보다 상태가 단순하다.
        """
        if not self._result:
            self._doc.setHtml(f"<style>{_DOC_CSS}</style>"
                              "<p class='body'>고시 파일을 불러오면 원문이 표시됩니다.</p>")
            return

        target = ((highlight["표번호"], highlight["행"]) if highlight else None)
        parts = [f"<style>{_DOC_CSS}</style>"]
        for block in self._visible_blocks():
            if block["종류"] == "문단":
                parts.append(f"<p class='{_para_class(block['글'])}'>"
                             f"{_escape(block['글'])}</p>")
                continue
            parts.append("<table>")
            for r, row in enumerate(block["격자"]):
                hit = target == (block["표번호"], r)
                parts.append("<tr>")
                for c, text in enumerate(row):
                    css = "head" if r == 0 else "hit" if hit else ""
                    anchor = (f"<a name='{_anchor(block['표번호'], r)}'></a>"
                              if hit and c == 0 else "")
                    parts.append(f"<td class='{css}'>{anchor}{_escape(text)}</td>")
                parts.append("</tr>")
            parts.append("</table>")

        self._doc.setHtml("".join(parts))
        if target:
            self._doc.scrollToAnchor(_anchor(*target))

    # --- 동작 -------------------------------------------------------------
    def _on_tab_changed(self, flow: str, index: int) -> None:
        spec = (TABS[flow][index] if 0 <= index < len(TABS[flow])
                else TABS["notice_verify"][0])
        self._title.setText(spec["title"])
        self._card_title.setText(spec["card_title"])
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
        self._diff_button.setVisible(index == 0)  # 대조 탭에서만 쓰는 버튼
        self._render_document()

    def _on_row_selected(self, table: QTableWidget) -> None:
        # 선택한 행의 출처로 원문을 스크롤하고 그 행을 강조한다.
        items = table.selectedItems()
        if not items:
            return
        first = table.item(items[0].row(), 0)
        ref = first.data(Qt.ItemDataRole.UserRole) if first else None
        if ref:
            if not self._splitter.widget(0).isVisible():
                self._toggle_document()
            self._render_document(ref)

    def _toggle_only_diff(self) -> None:
        self._only_diff = not self._only_diff
        self._diff_button.setText(_ONLY_DIFF_OFF if self._only_diff
                                  else _ONLY_DIFF_ON)
        set_state(self._diff_button, "state", "loaded" if self._only_diff else "")
        self._fill_compare_table()

    def _toggle_document(self) -> None:
        shown = self._doc.isVisible()
        self._doc.setVisible(not shown)
        self._doc_button.setText(_DOC_SHOW_TEXT if shown else _DOC_HIDE_TEXT)

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "고시 파일 선택", "", "한글 문서 (*.hwpx)")
        if path:
            self.load_notice(path)

    def _on_next(self) -> None:
        if self._state in (FILLED, FAILED):
            self._start_table_write(self.values())
        elif self._state == READY and self._tables is not None:
            # 표를 화면에 채우는 동안(느림) 버튼만 잠깐 회색으로 보여준다.
            # 상태(FSM)는 READY 로 두고 순수 UI만 바꿨다가 화면 전환 후 되돌린다.
            self._next.setEnabled(False)
            self._next.setText(_LOADING_TEXT)
            self._next.repaint()
            self.tablesReady.emit(self._tables)

    def _start_table_write(self, service_prices: dict) -> None:
        if self._table_writer is None:
            # 생성기를 안 붙인 경우: 값 확인까지만 하고 READY 로 넘어간다.
            self._tables = {}
            self._set_state(READY)
            return
        self._set_state(BUSY)
        self._generation += 1
        task = _TableWriteTask(self._table_writer, service_prices, self._generation)
        task.signals.finished.connect(self._on_table_complete)
        task.signals.failed.connect(self._on_table_failed)
        self._pool.start(task)

    def _on_table_complete(self, generation: int, tables: dict) -> None:
        if generation != self._generation:
            return  # 생성 중에 다른 고시를 불러온 경우: 낡은 결과라 버린다
        self._tables = tables
        self._set_state(READY)

    def _on_table_failed(self, generation: int, reason: str) -> None:
        if generation != self._generation:
            return
        self._tables = None
        self._set_state(FAILED, reason)

    # --- 상태 -------------------------------------------------------------
    def _refresh_state(self) -> None:
        if self._state == BUSY:
            return  # 생성 중엔 상태를 그대로 둔다
        if not self.values() or self.issues():
            # 단가를 못 읽었거나 단가 자체가 이상하면 넘기지 않는다.
            self._set_state(WAITING)
        elif self._tables is not None:
            self._set_state(READY)
        else:
            self._set_state(FILLED)

    def _set_state(self, state: str, reason: str = "") -> None:
        self._state = state
        busy = state == BUSY

        self._next.setEnabled(state in (FILLED, READY, FAILED))
        self._next.setText(_BUSY_TEXT if busy else _NEXT_TEXT if state == READY
                           else _GENERATE_TEXT)

        compare = self.compare_result()
        wrong = compare.get("불일치", 0) + compare.get("조견표에 없음", 0)

        if state == WAITING:
            if not self._result:
                self._hint.setText("고시 파일을 불러오면 값과 대조 결과가 표시됩니다.")
            else:
                self._hint.setText(
                    f"고시에서 읽은 단가에 문제가 {len(self.issues())}건 있어 "
                    "결제단가표를 만들 수 없습니다. '서비스 단가' 탭을 확인해 주세요.")
        elif state == FILLED:
            self._hint.setText(
                "단가를 확인했다면 '결제단가표 생성'을 눌러 주세요."
                + (f" (조견표와 다른 항목 {wrong}건은 조견표 쪽을 확인해 주세요.)"
                   if wrong else ""))
        elif state == BUSY:
            self._hint.setText("결제단가표를 생성하고 있습니다. 잠시만 기다려 주세요.")
        elif state == READY:
            self._hint.setText("결제단가표를 생성했습니다. 다음 화면에서 확인할 수 있습니다.")
        else:
            self._hint.setText(f"결제단가표를 생성하지 못했습니다: {reason}\n"
                               "값을 확인한 뒤 다시 시도해 주세요.")

        set_state(self._hint, "state", state)
        self._hint.setVisible(True)


# --- 표시 헬퍼 -------------------------------------------------------------

def _won(value) -> str:
    if isinstance(value, int):
        return f"{value:,}원"
    if isinstance(value, float):
        return f"{value:g}"
    return "—" if value is None else str(value)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _anchor(table_no: int, row: int) -> str:
    return f"cell-{table_no}-{row}"


def _para_class(text: str) -> str:
    if gosi_verifier._CHAPTER.match(text):
        return "chapter"
    if gosi_verifier._ITEM.match(text):
        return "item"
    return "body"
