# 문서 업로드 화면

from __future__ import annotations
import os
from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from services.jogyeon_value_extractor import ValueExtractor
from services.gosi_verifier import read_gosi
from models.dto import ConstantValues, UploadedFile
from models.flows import NOTICE_VERIFY, FlowSpec, UNIT_PRICE, PAYMENT_PRICE
from services import recent_files
from ui.components.button import PrimaryButton, GhostButton
from ui.components.scroll_page import centered_scroll_page
from utils.qss import set_state
from ui.widgets.upload_card import UploadCard
from pathlib import Path
from ui.components.spinner import Spinner

from utils.date import yearConfig

WAITING, FILLED, BUSY, READY, FAILED = "waiting", "filled", "busy", "ready", "failed"

_LOAD_CACHE_BTN_TEXT = "📂 {system_year}년도 작업 기록 불러오기"

_CONFIRM_TEXT = "문서 읽기 시작"
_NEXT_TEXT = "다음 단계로  →"
_BUSY_TEXT = "⟳  문서에서 값을 읽는 중..."


class _ExtractSignals(QObject):
    finished = pyqtSignal(int, object)  # generation, ConstantValues
    failed = pyqtSignal(int, str)  # generation, 사유


# 추출기는 GUI 스레드 밖에서
class _ExtractTask(QRunnable):
    def __init__(
        self,
        extractor: ValueExtractor,
        files: dict[str, UploadedFile],
        flow: FlowSpec,
        generation: int,
    ) -> None:
        super().__init__()
        self.signals = _ExtractSignals()
        self._extractor = extractor
        self._files = files
        self._flow = flow
        self._generation = generation

    def run(self) -> None:
        try:
            # self._files["jogyeon"] -> 슬롯이 없으면 KeyError 대신 읽을 수 있는 메시지 표시
            if self._flow.key == PAYMENT_PRICE.key:
                values = {}
            else:
                jogyeon = self._files.get("jogyeon")
                if jogyeon is None:
                    raise ValueError("조견표 파일이 없습니다.")
                values = self._extractor.extract_jogyeon_values(jogyeon)

            if self._flow.key in (NOTICE_VERIFY.key,PAYMENT_PRICE.key):
                guide = self._files.get("guide")
                if guide is None:
                    raise ValueError("고시 파일이 없습니다.")
                reference_dict = {}
                raw_data = values if isinstance(values, list) else [values]
                for tab in raw_data:
                    for k, v in tab.items():
                        if isinstance(v, dict):
                            for sk, sv in v.items():
                                reference_dict[f"{k}.{sk}"] = sv
                        else:
                            reference_dict[k] = v
                result = read_gosi(guide.path, reference_dict, self._flow.key)

                if not result.get("단가"):
                    issues = result.get("검증") or []
                    error_texts = [f"· {issue['메시지']}" for issue in issues if '메시지' in issue]
                    error_msg = "\n".join(error_texts) if error_texts else "고시 파일에서 알맞은 표를 찾을 수 없습니다."
                    raise ValueError(error_msg)
                
        except Exception as error:
            self.signals.failed.emit(
                self._generation, str(error) or type(error).__name__
            )
        else:
            self.signals.finished.emit(self._generation, values)


class UploadPage(QWidget):
    valuesReady = pyqtSignal(object) # 다음 단계로 넘어가도 된다는 신호
    filesDiverged = pyqtSignal(bool) # 지금 올라온 파일이 마지막으로 추출에 쓰인 파일과 다른지 여부 / True: 단계 이동 잠금, False: 단계 이동 가능

    def __init__(
        self,
        extractor: ValueExtractor | None = None,
        label_reviewer: (
            Callable[[UploadedFile, Callable[[bool], None]], None] | None
        ) = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._extractor = extractor
        # 값을 읽기 전에 작년 조견표와 라벨 대조
        self._label_reviewer = label_reviewer
        self._pool = QThreadPool.globalInstance()

        #멈춤상황에서 spinner추가하기
        self._spinner=Spinner(size=22)

        self._flow: FlowSpec | None = None
        self._cards: dict[str, UploadCard] = {}
        self._values: ConstantValues | None = None
        self._generation = 0
        self._state = WAITING
        # 마지막으로 추출에 성공했을 때 올라와 있던 파일들과 그 결과값
        self._confirmed_files: dict[str, UploadedFile] = {}
        self._confirmed_values: ConstantValues | None = None

        self._build()

    # --- 구성 -------------------------------------------------------------
    def _build(self) -> None:
        page, column = centered_scroll_page(640)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        # 캐싱된 데이터 불러오기 버튼 추가
        self._load_cache_btn = GhostButton(
            _LOAD_CACHE_BTN_TEXT.format(system_year=yearConfig.SYSTEM_YEAR)
        )
        self._load_cache_btn.clicked.connect(self._load_cached_files)

        self._cards_holder = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_holder)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(14)

        self._next = PrimaryButton(_CONFIRM_TEXT)
        self._next.setEnabled(False)
        self._next.clicked.connect(self._on_next)

        self._hint = QLabel()
        self._hint.setObjectName("UploadHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)

        column.addWidget(self._title)
        column.addWidget(self._subtitle)
        column.addSpacing(6)
        column.addWidget(self._cards_holder)
        column.addSpacing(6)
        column.addWidget(self._load_cache_btn)  # 타이틀 아래에 캐시 로드 버튼 추가
        column.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        column.addWidget(self._next)
        column.addWidget(self._hint)
        column.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

    # --- API --------------------------------------------------------------
    def set_extractor(self, extractor: ValueExtractor | None) -> None:
        self._extractor = extractor

    # flow 세팅
    def set_flow(self, flow: FlowSpec) -> None:
        if self._flow is not None and self._flow.key == flow.key:
            return 
        self._flow = flow
        self._title.setText(flow.upload_title)
        self._subtitle.setText(flow.upload_description)
        self.reset()

    # 진행상황 리셋 (flow 바뀌거나 다른 파일 업로드시 동작)
    def reset(self) -> None:
        self._generation += 1
        self._values = None
        self._confirmed_files = {}
        self._confirmed_values = None
        self._cards.clear()
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        if self._flow is None:
            return

        has_cache = False
        for slot in self._flow.uploads:
            card = UploadCard(slot.title, slot.description, slot.extensions, slot.icon)
            card.fileSelected.connect(self._on_file_selected)
            self._cards[slot.key] = card
            self._cards_layout.addWidget(card)

            if recent_files.get_recent_path(yearConfig.SYSTEM_YEAR, slot.key):
                has_cache = True
        self._load_cache_btn.setText(
            _LOAD_CACHE_BTN_TEXT.format(system_year=yearConfig.SYSTEM_YEAR)
        )
        self._load_cache_btn.setVisible(has_cache)

        self._set_state(WAITING)

    def values(self) -> ConstantValues | None:
        return self._values

    # --- 동작 -------------------------------------------------------------
    def files(self) -> dict[str, UploadedFile]:
        return self._files()

    def _files(self) -> dict[str, UploadedFile]:
        return {
            key: card.file() for key, card in self._cards.items() if card.file()
        } 

    #마지막 추출에 사용한 원본경로와 셀 좌표
    def export_info(self) -> tuple[Path | None, dict]:
        if self._extractor is None:
            return None, {}
        return self._extractor.source_path(), self._extractor.cell_map()

    # 기존 작업이 있다면 무효로(사용자가 파일을 올렸을 때 동작)
    def _on_file_selected(self) -> None:
        self._generation += 1
        self._refresh_files_state()

    # 지금 파일은 그대로 들고 ui 상태만 다시 계산
    def _refresh_files_state(self) -> None:
        files = self._files()
        # _confirmed_files : 추출 성공해서 들고 있는 파일
        matches_confirmed = (
            bool(self._confirmed_files) and files == self._confirmed_files
        )

        # 원래 추출에 썼던 파일 그대로 돌아온 경우
        if matches_confirmed:
            self._values = self._confirmed_values
            self._set_state(READY)

        # 추출에 성공한 적이 없는 경우
        else:
            self._values = None
            self._set_state(FILLED if len(files) == len(self._cards) else WAITING)
        diverged = bool(self._confirmed_files) and not matches_confirmed
        self.filesDiverged.emit(diverged)

    def _start_extract(self, files: dict[str, UploadedFile]) -> None:
        # 추출기가 없는 경우: 파일 확인까지만 하고 READY 로
        if self._extractor is None:
            self._values = {}
            self._confirmed_files = dict(files)
            self._confirmed_values = self._values
            self._set_state(READY)
            return

        self._set_state(BUSY)
        task = _ExtractTask(self._extractor, files, self._flow, self._generation)
        task.signals.finished.connect(self._on_extracted)
        task.signals.failed.connect(self._on_extract_failed)
        self._pool.start(task)

    # 추출 함수
    def _on_extracted(self, generation: int, values: ConstantValues) -> None:
        # 중간에 파일이 바뀐 경우
        if generation != self._generation:
            return

        # 추출에 성공한 파일은 캐시로 저장
        if self._flow is not None:
            # 어느 플로우에서든 조견표/고시/단가표를 올리면 다른 플로우도 자동으로 불러올 수 있음
            for key, file in self._files().items():
                recent_files.set_recent_path(yearConfig.SYSTEM_YEAR, key, file.path)

        self._values = values
        self._confirmed_files = dict(self._files())
        self._confirmed_values = values
        self._set_state(READY)

    def _on_extract_failed(self, generation: int, reason: str) -> None:
        if generation != self._generation:
            return
        self._values = None
        self._set_state(FAILED, reason)

    def _on_next(self) -> None:
        if self._state in (FILLED, FAILED):
            # '확인' 버튼: 파일이 다 준비됐거나 추출이 실패해 재시도하는 경우
            files = self._files()
            self._set_state(BUSY)
            self._review_labels(files, lambda ok: self._after_review(ok, files))
        elif self._state == READY and self._values is not None:
            self.valuesReady.emit(self._values)

    def _after_review(self, ok: bool, files: dict[str, UploadedFile]) -> None:
        # 검토 취소시 값 읽지 않고 원래 상태로
        if not ok:
            self._refresh_files_state()
            return
        self._start_extract(files)

    def _review_labels(self, files: dict[str, UploadedFile], on_done: Callable[[bool], None]) -> None:
        sheet = files.get("jogyeon")
        if self._label_reviewer is None or sheet is None:
            on_done(True)
            return
        if self._flow is None or self._flow.key != UNIT_PRICE.key:
            on_done(True)
            return
        self._label_reviewer(sheet, on_done)

    def _load_cached_files(self) -> None:
        loaded = False
        for key, card in self._cards.items():
            cached_path = recent_files.get_recent_path(yearConfig.SYSTEM_YEAR, key)
            if not cached_path or not os.path.exists(str(cached_path)):
                continue
            if hasattr(card, "set_path"):
                card.set_path(str(cached_path))
            loaded = True

        if not loaded:
            return
        self._load_cache_btn.setVisible(False)
        self._refresh_files_state()

    # --- 내부 -------------------------------------------------------------
    def _set_state(self, state: str, reason: str = "") -> None:
        self._state = state
        busy = state == BUSY
        for card in self._cards.values():
            card.set_locked(busy)

        self._next.setEnabled(state in (FILLED, READY, FAILED))
        self._next.setText(
            _BUSY_TEXT if busy else _NEXT_TEXT if state == READY else _CONFIRM_TEXT
        )

        if state == WAITING:
            self._hint.setText("파일을 업로드해야 다음 단계로 갈 수 있습니다.")
        elif state == FILLED:
            self._hint.setText(
                "파일을 모두 올렸습니다. '문서 읽기 시작'을 누르면 값을 읽어옵니다."
            )
        elif state == BUSY:
            self._hint.setText("문서를 읽고 있습니다. 잠시만 기다려 주세요.")
        elif state == READY:
            self._hint.setText(
                "문서에서 값을 추출했습니다. 다음 화면에서 확인·수정할 수 있습니다."
            )
        else:
            self._hint.setText(
                f"문서를 읽지 못했습니다.\n{reason}\n올바른 형식의 파일인지 확인해 주세요."
            )

        if state==BUSY:
            self._spinner.start()
        else:
            self._spinner.stop()

        set_state(self._hint, "state", state)
        self._hint.setVisible(True)
