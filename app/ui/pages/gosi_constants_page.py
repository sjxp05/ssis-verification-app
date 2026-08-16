from __future__ import annotations
import os
import copy
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)
import pandas as pd

from services import gosi_verifier, recent_files
from services.table_writer import TableWriter
from ui.components.card import Card
from ui.components.button import GhostButton, PrimaryButton
from ui.components.tab_bar import SegmentedTabBar
from utils.qss import set_state
from ui.widgets.gosi_panel import GosiDocumentViewer
from ui.widgets.gosi_tables import (
    CompareTableWidget,
    PriceTableWidget,
    PriceEditDelegate,
    _to_int,
)

WAITING, FILLED, BUSY, READY, FAILED = "waiting", "filled", "busy", "ready", "failed"

_GENERATE_TEXT = "결제단가표 생성"
_NEXT_TEXT = "다음 단계로  →"
_BUSY_TEXT = "⟳  결제단가표를 생성하는 중..."
_LOADING_TEXT = "⟳  불러오는 중..."

_ONLY_DIFF_ON = "불일치만 보기"
_ONLY_DIFF_OFF = "전체 보기"
_DOC_HIDE_TEXT = "고시 원문 접기"
_DOC_SHOW_TEXT = "고시 원문 펼치기"

TABS = {
    "notice_verify": {
        "label": "조견표 대조",
        "title": "고시와 조견표의 값이 맞는지 확인해 주세요.",
        "card_title": "조견표 ↔ 고시 대조",
    },
    "payment_price": {
        "label": "서비스 단가",
        "title": "서비스별 단가가 맞는지 확인해주세요.",
        "card_title": "서비스 단가 확인",
    },
}


TAB_CHAPTERS = {0: ("제2장", "제3장", "부"), 1: ("제3장", "제4장")}
COMPARE_COLUMNS = [
    ("항목", False, True),
    ("조견표", True, False),
    ("고시", True, False),
    ("결과", False, False),
]
PRICE_COLUMNS = [
    ("급여", False, False),
    ("구분", False, True),
    ("금액", True, False),
    ("가산수당", True, False),
]
RESULT_COLORS = {"일치": "#2F855A", "불일치": "#C53030", "조견표에 없음": "#96620F"}

EDITABLE_PRICE_COLS = (2, 3)  # 금액(2열), 가산수당(3열)


class _TableWriteSignals(QObject):
    finished = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)


class _TableWriteTask(QRunnable):
    def __init__(
        self, table_writer: TableWriter, service_prices: dict, basic_df, generation: int
    ) -> None:
        super().__init__()
        self.signals = _TableWriteSignals()
        self._table_writer = table_writer
        self._service_prices = service_prices
        self._basic_df = basic_df
        self._generation = generation

    def run(self) -> None:
        try:
            tables = self._table_writer.write_payment_table(
                service_prices=self._service_prices,
                basic_df=self._basic_df,
            )
        except Exception as error:
            self.signals.failed.emit(
                self._generation, str(error) or type(error).__name__
            )
        else:
            self.signals.finished.emit(self._generation, tables)


class GosiConstantsPage(QWidget):
    # 단가표 생성 생략 -> 값 확인이 끝났음을 메인 윈도우에 알림
    tablesReady = pyqtSignal(object)
    valuesChanged = pyqtSignal()
    valuesKept = pyqtSignal()

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
        self._tables = None
        self._generation = 0

        self._reference: dict = {}
        self._result: dict | None = None
        self._path: str | None = None
        self._unit_price_path: str | None = None
        self._sheet_path: str | None = None
        self._only_diff = False
        self._tab_index = 0
        self._doc_sizes: list[int] | None = None
        self._state = WAITING
        self._price_overrides: dict[tuple[str, str, str], int] = {}

        self._build_ui()
        self._on_tab_changed()
        self._set_state(WAITING)

    def _build_ui(self):
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

        self._diff_button = GhostButton(_ONLY_DIFF_ON)
        self._diff_button.clicked.connect(self._toggle_only_diff)
        self._doc_button = GhostButton(_DOC_HIDE_TEXT)
        self._doc_button.clicked.connect(self._toggle_document)

        for b in (self._diff_button, self._doc_button):
            b.setFixedSize(130, 32)

        card_head = QHBoxLayout()
        card_head.addWidget(self._card_title)
        card_head.addStretch(1)
        card_head.addWidget(self._card_hint)
        card_head.addWidget(self._diff_button)
        card_head.addWidget(self._doc_button)
        self._card.add_layout(card_head)

        self._doc = GosiDocumentViewer()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_compare_panel())
        self._stack.addWidget(self._build_price_panel())

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._doc)
        self._splitter.addWidget(self._stack)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)
        self._card.add_widget(self._splitter)

        self._next = PrimaryButton(_NEXT_TEXT)
        self._next.setEnabled(False)
        self._next.clicked.connect(self._on_next)

        self._hint = QLabel()
        self._hint.setObjectName("GenerateHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header = QVBoxLayout()
        header.addWidget(self._title)
        header.addWidget(self._subtitle)

        content = QVBoxLayout()
        content.addWidget(self._card, 1)
        content.addWidget(self._next)
        content.addWidget(self._hint)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(28, 18, 28, 24)
        self._outer.setSpacing(18)
        self._outer.addLayout(header)
        self._outer.addLayout(content, 1)

    # --- API --------------------------------------------------------------
    # 데이터 반환 함수
    def return_values(self) -> dict:
        formatted = {}

        for service, items in self._prices().items():
            if not isinstance(items, dict):
                continue

            for key, item in items.items():
                if not isinstance(item, dict):
                    continue

                amount = _to_int(item.get("금액"))
                if amount is not None:
                    formatted[f"{service}.{key}"] = amount

        return formatted

    def _prices(self) -> dict:
        raw = (self._result or {}).get("단가") or {}
        if not self._price_overrides:
            return raw

        merged = copy.deepcopy(raw)
        for (service, key, col_name), value in self._price_overrides.items():
            if service not in merged:
                merged[service] = {}
            if key not in merged[service]:
                merged[service][key] = {}
            merged[service][key][col_name] = value
        return merged

    def set_reference(self, values: dict | None) -> None:
        self._reference = values or {}
        if self._result:
            self._result["대조"] = gosi_verifier.compare_with_reference(
                self._result["월한도액"], self._reference
            )
            self._fill_all()
            self._refresh_state()

    def set_unit_price_path(self, path: str) -> None:
        self._unit_price_path = path

    def set_sheet_path(self, path: str) -> None:
        self._sheet_path = path

    def load_notice(self, path: str) -> None:
        try:
            result = gosi_verifier.read_gosi(path, self._reference, self._flow)
        except Exception as error:
            QMessageBox.warning(
                self, "불러오기 실패", f"고시를 읽지 못했습니다:\n{error}"
            )
            return
        
        self._result = result
        self._path = path
        self._price_overrides.clear()
        self._tables = None
        self._generation += 1
        self._fill_all()
        self._refresh_state()

    def values(self) -> dict:
        return (self._result or {}).get("단가", {})

    def issues(self) -> list:
        return (self._result or {}).get("검증") or []

    def set_flow(self, flow: str) -> None:
        if flow != self._flow:
            self._flow = flow
            self.clear()
            self._on_tab_changed()

    def clear(self) -> None:
        self._result = None
        self._path = None
        self._reference = {}
        self._unit_price_path = None
        self._sheet_path = None
        # 이미 만들어 둔 표와 돌고 있던 생성 작업은 낡은 값이므로 함께 버린다.
        self._tables = None
        self._generation += 1
        self._only_diff = False
        self._price_overrides.clear()
        self._diff_button.setText(_ONLY_DIFF_ON)
        set_state(self._diff_button, "state", "")
        self._fill_all()
        self._set_state(WAITING)

    # --- 내부 빌드 및 채우기 로직 (간소화) --------------------------------------

    def _section(self, title: str, widget: QWidget) -> QWidget:
        label = QLabel(title)
        label.setObjectName("GroupLabel")
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(label)
        box.addWidget(widget)
        holder = QWidget()
        holder.setLayout(box)
        return holder

    def _scroll(self, widgets) -> QScrollArea:
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            column.addWidget(widget)
        column.addStretch(1)

        body = QWidget()
        body.setLayout(column)
        body.setObjectName("NoticeScrollBody")
        body.setStyleSheet("background-color: transparent;")

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setObjectName("NoticeScrollArea")
        area.viewport().setObjectName("NoticeScrollViewport")
        area.setStyleSheet("background-color: transparent;")
        area.setWidget(body)
        return area

    def _build_compare_panel(self) -> QWidget:
        self._compare_summary = QLabel()
        self._compare_summary.setObjectName("CompareSummary")
        self._compare_summary.setWordWrap(True)

        self._compare_table = CompareTableWidget()
        self._compare_table.rowSelected.connect(self._doc.render_document)

        self._skipped_label = QLabel()
        self._skipped_label.setObjectName("FindingDetail")
        self._skipped_label.setWordWrap(True)
        return self._scroll(
            [
                self._compare_summary,
                self._section("조견표 ↔ 고시", self._compare_table),
                self._section(
                    "고시에 없어 대조하지 않은 조견표 항목", self._skipped_label
                ),
            ]
        )

    def _build_price_panel(self) -> QWidget:
        self._price_table = PriceTableWidget()
        self._price_table.rowSelected.connect(self._doc.render_document)
        self._price_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )

        self._price_delegate = PriceEditDelegate(0, 10_000_000, 100, self)
        for col in EDITABLE_PRICE_COLS:
            self._price_table.setItemDelegateForColumn(col, self._price_delegate)

        self._price_table.itemChanged.connect(self._on_item_changed)
        self._price_table.setToolTip("금액/가산수당 셀을 더블클릭하면 수정 가능합니다.")

        self._issue_label = QLabel()
        self._issue_label.setObjectName("FindingDetail")
        self._issue_label.setWordWrap(True)
        return self._scroll(
            [
                self._section(
                    "고시에서 읽은 단가 (결제단가표로 전달)", self._price_table
                ),
                self._section("검증", self._issue_label),
            ]
        )

    def _fill_all(self) -> None:
        if self._path:
            name = os.path.basename(self._path)
            self._subtitle.setText(
                f"{name}  ·  조견표에서 읽은 항목 {len(self._reference)}개"
            )
        else:
            self._subtitle.setText(
                "고시 파일을 불러오면 대조 결과가 여기에 표시됩니다."
            )

        compare_data = (self._result or {}).get("대조") or {}
        self._compare_table.fill_data(compare_data, self._only_diff)

        self._price_table.blockSignals(True)
        self._price_table.fill_data(self._prices())

        for row in range(self._price_table.rowCount()):
            for col in EDITABLE_PRICE_COLS:
                item = self._price_table.item(row, col)
                if item:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    keys = self._row_keys(row)
                    if (
                        keys
                        and (keys[0], keys[1], PRICE_COLUMNS[col][0])
                        in self._price_overrides
                    ):
                        item.setBackground(QBrush(QColor("#FFE79D")))
                        item.setToolTip("수정한 값입니다.")

        self._price_table.blockSignals(False)

        self._doc.set_blocks(
            (self._result or {}).get("블록", []),
            chapters=TAB_CHAPTERS.get(self._tab_index, ()),
        )

        self._update_summary_labels(compare_data)

    def _update_summary_labels(self, compare_data: dict) -> None:
        rows = compare_data.get("행") or []
        matched = compare_data.get("일치", 0)
        mismatched = compare_data.get("불일치", 0)
        absent = compare_data.get("조견표에 없음", 0)

        if rows:
            self._compare_summary.setText(
                f"전체 {len(rows)}항목  ·  일치 {matched}  ·  "
                f"불일치 {mismatched}  ·  조견표에 없음 {absent}"
            )
            set_state(
                self._compare_summary,
                "state",
                "fail" if (mismatched or absent) else "pass",
            )
        else:
            self._compare_summary.setText("대조할 값이 없습니다.")
            set_state(self._compare_summary, "state", "")

        self._skipped_label.setText(self._skipped_text(compare_data))
        self._issue_label.setText(self._issue_text())

    # 고시에 대응하는 값이 없어 대조하지 않은 조견표 항목
    def _skipped_text(self, compare_data: dict) -> str:
        skipped = compare_data.get("대조 안 함") or []
        if not skipped:
            return "없음" if compare_data.get("행") else "—"
        return f"{len(skipped)}개 항목은 고시에 대응하는 값이 없어 대조하지 않았습니다.\n\n" + "\n".join(
            f"·  {key}" for key in skipped
        )

    def _issue_text(self) -> str:
        issues = self.issues()
        if not issues:
            return "검증 통과 — 확인이 필요한 항목이 없습니다."
        blocks = [f"[{item['항목']}]\n{str(item['메시지']).strip()}" for item in issues]
        return "\n\n".join(blocks) + "\n\n" + gosi_verifier.FIX_GUIDE

    def _row_keys(self, row: int) -> tuple[str, str] | None:
        key_item = self._price_table.item(row, 1)
        if not key_item:
            return None

        key = key_item.text().strip()
        if not key:
            return None

        service = ""
        cursor = row
        while not service and cursor >= 0:
            svc_item = self._price_table.item(cursor, 0)
            if svc_item:
                service = svc_item.text().strip()
            cursor -= 1

        return (service, key) if service else None

    def _on_item_changed(self, item) -> None:
        if item is None:
            return
        row, col = item.row(), item.column()
        if col not in EDITABLE_PRICE_COLS:
            return

        keys = self._row_keys(row)
        if keys is None:
            return
        service, key = keys
        col_name = PRICE_COLUMNS[col][0]

        new_val = _to_int(item.text())
        entry = ((self._result or {}).get("단가", {}).get(service) or {}).get(key) or {}
        origin_val = _to_int(entry.get(col_name))

        if new_val is None:
            new_val = origin_val if origin_val is not None else 0

        # 최소 0원 ~ 최대 천만원 범위 강제
        new_val = min(max(new_val, 0), 10_000_000)

        # 원본과 똑같이 입력했으면 수정 이력에서 지움
        if origin_val is not None and new_val == origin_val:
            self._price_overrides.pop((service, key, col_name), None)
            edited = False
        else:
            self._price_overrides[(service, key, col_name)] = new_val
            edited = True

        self._price_table.blockSignals(True)
        item.setText(f"{new_val:,}")
        item.setData(Qt.ItemDataRole.UserRole, new_val)
        if edited:
            item.setBackground(QBrush(QColor("#FFE79D")))
            item.setToolTip("직접 수정한 값입니다.")
        else:
            item.setData(Qt.ItemDataRole.BackgroundRole, None)
            item.setToolTip("")
        self._price_table.blockSignals(False)

        # 낡은 단가표 폐기 및 버튼 상태 갱신
        self._tables = None
        self._refresh_state()
        self.valuesChanged.emit()

    # --- 동작 및 상태 제어 --------------------------------------------------
    def _on_tab_changed(self) -> None:
        # notice_verify 전용 - 다른 흐름 키가 들어와도 첫 탭으로 설정
        spec = TABS.get(self._flow, TABS["notice_verify"])

        self._title.setText(spec["title"])
        self._card_title.setText(spec["card_title"])
        self._card_hint.setText(spec.get("card_hint", ""))

        if self._flow == "payment_price":
            self._stack.setCurrentIndex(1)
            self._diff_button.setVisible(False)
            self._doc.set_visible_chapters(("제3장", "제4장"))
        else:
            self._stack.setCurrentIndex(0)
            self._diff_button.setVisible(True)
            self._doc.set_visible_chapters(("제2장", "제3장", "부"))

    def _toggle_only_diff(self) -> None:
        self._only_diff = not self._only_diff
        self._diff_button.setText(_ONLY_DIFF_OFF if self._only_diff else _ONLY_DIFF_ON)
        set_state(self._diff_button, "state", "loaded" if self._only_diff else "")
        compare_data = (self._result or {}).get("대조") or {}
        self._compare_table.fill_data(compare_data, self._only_diff)

    def _toggle_document(self) -> None:
        # 접기 전 좌우 비율을 기억해 두었다가 다시 펼칠 때 그대로 되돌리기(편의기능)
        shown = self._doc.isVisible()
        if shown:
            self._doc_sizes = self._splitter.sizes()
        self._doc.setVisible(not shown)
        if not shown and self._doc_sizes:
            self._splitter.setSizes(self._doc_sizes)
        self._doc_button.setText(_DOC_SHOW_TEXT if shown else _DOC_HIDE_TEXT)

    def reset_next_button(self) -> None:
        if self._state == READY:
            self._next.setEnabled(True)
            self._next.setText(_NEXT_TEXT)

    def _on_next(self) -> None:
        if self._flow == "notice_verify":
            self.tablesReady.emit({})
            return
        if self._state in (FILLED, FAILED):
            self._start_table_write(self.return_values())
        elif self._state == READY and self._tables is not None:
            self._next.setEnabled(False)
            self._next.setText(_LOADING_TEXT)
            self._next.repaint()
            self.tablesReady.emit(self._tables)

    # 테이블 작성을 위해 슬롯에 있는 파일 읽어오기
    def _start_table_write(self, service_prices: dict) -> None:
        if self._table_writer is None:
            self._tables = {}
            self._set_state(READY)
            return

        # 파일 확인을 먼저 끝낸 뒤에 BUSY 로
        if not self._unit_price_path or not os.path.exists(self._unit_price_path):
            self._set_state(
                FAILED,
                "기본급여 단가표 파일을 찾지 못했습니다.\n"
                "업로드 화면에서 파일을 올렸는지 확인해 주세요.",
            )
            return
        try:
            basic_df = pd.read_excel(self._unit_price_path)
        except Exception as error:
            self._set_state(FAILED, f"기본급여 단가표를 읽지 못했습니다.\n{error}")
            return

        self._set_state(BUSY)
        self._generation += 1

        self._basic_df = basic_df
        task = _TableWriteTask(
            self._table_writer, service_prices, basic_df, self._generation
        )
        task.signals.finished.connect(self._on_table_complete)
        task.signals.failed.connect(self._on_table_failed)
        self._pool.start(task)

    def _on_table_complete(self, generation: int, tables: dict) -> None:
        if generation != self._generation:
            return
        self._tables = tables
        self._set_state(READY)

    def _on_table_failed(self, generation: int, reason: str) -> None:
        if generation != self._generation:
            return
        self._tables = None
        self._set_state(FAILED, reason)

    def _refresh_state(self) -> None:
        if self._state == BUSY:
            return
        if not self.values() or self.issues():
            self._set_state(WAITING)
        elif self._tables is not None:
            self._set_state(READY)
        else:
            self._set_state(FILLED)

    def _set_state(self, state: str, reason: str = "") -> None:
        self._state = state
        busy = state == BUSY

        self._next.setEnabled(state in (FILLED, READY, FAILED))

        if self._flow == "notice_verify":
            self._next.setText("검증 완료")
        else:
            if busy:
                self._next.setText(_BUSY_TEXT)
            elif state == READY:
                self._next.setText(_NEXT_TEXT)
            else:
                self._next.setText(_GENERATE_TEXT)

        compare = (self._result or {}).get("대조") or {}
        wrong = compare.get("불일치", 0) + compare.get("조견표에 없음", 0)

        if state == WAITING and not self._result:
            self._hint.setText("고시 파일을 불러오면 결과가 표시됩니다.")
        elif state == WAITING:
            self._hint.setText(
                f"단가에서 확인이 필요한 항목이 {len(self.issues())}건 있어 다음 단계로 갈 수 없습니다.\n"
                "아래 '검증' 내용을 확인해 주세요."
            )
        elif state == FILLED:
            head = (
                "확인이 완료되었다면 '검증 완료'를 눌러주세요"
                if self._flow == "notice_verify"
                else "단가를 확인했다면 '결제단가표 생성'을 눌러주세요."
            )
            self._hint.setText(
                head + (f"\n조견표와 다른 항목이 {wrong}건 있습니다." if wrong else "")
            )
        elif state == BUSY:
            self._hint.setText("결제단가표를 생성하고 있습니다. 잠시만 기다려 주세요.")
        elif state == READY:
            self._hint.setText(
                "결제단가표를 생성했습니다. 다음 화면에서 확인할 수 있습니다."
            )
        else:
            self._hint.setText(
                f"결제단가표를 만들지 못했습니다.\n{reason}\n값을 확인한 뒤 다시 시도해 주세요."
            )

        set_state(self._hint, "state", state)
        self._hint.setVisible(True)
