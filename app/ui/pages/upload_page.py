# 0단계 — 문서 업로드 화면
#
# 카드에 파일이 다 채워지면 '확인' 버튼이 켜지고, 버튼을 눌러야 그때 백그라운드에서 문서를 읽어 상수를 뽑는다.
# 추출이 성공하면 바로 다음 단계로 넘어간다. (다음 화면 시작할 때 여기서 읽어온 값이 필요하기 때문)

from __future__ import annotations
import os
from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from services.jogyeon_value_extractor import ValueExtractor
from models.dto import ConstantValues, UploadedFile
from models.flows import FlowSpec, UNIT_PRICE
from services import recent_files
from ui.components.button import PrimaryButton, GhostButton
from ui.components.scroll_page import centered_scroll_page
from utils.qss import set_state
from ui.widgets.upload_card import UploadCard

# 파일 묶음을 받아 상수를 돌려준다. 예외를 던지면 화면에 사유가 뜬다.
# ValueExtractor = Callable[[dict[str, UploadedFile]], ConstantValues]

WAITING, FILLED, BUSY, READY, FAILED = "waiting", "filled", "busy", "ready", "failed"


_CONFIRM_TEXT = "문서 읽기 시작"
_NEXT_TEXT = "다음 단계로  →"
_BUSY_TEXT = "⟳  문서에서 값을 읽는 중..."


# 임시 상수 추출 함수: 고시에서 값 추출 구현하기 전 까지 사용
def extract_values(files: dict[str, UploadedFile]) -> ConstantValues:
    import time

    time.sleep(0.3)
    values: ConstantValues = {"copay_cap": 216000, "base_unit_price": 30500}
    values.update(
        {
            f"copay_rate_{c}": r
            for c, r in (("da", 6), ("ra", 9), ("ma", 12), ("ba", 15))
        }
    )
    values.update({f"monthly_limit_{i}": 100000 * i for i in range(1, 9)})
    return values


class _ExtractSignals(QObject):
    finished = pyqtSignal(int, object)  # generation, ConstantValues
    failed = pyqtSignal(int, str)  # generation, 사유


# 추출기를 GUI 스레드 밖에서 돌린다.
class _ExtractTask(QRunnable):
    def __init__(
        self,
        extractor: ValueExtractor,
        files: dict[str, UploadedFile],
        flow_key: str,
        generation: int,
    ) -> None:
        super().__init__()
        self.signals = _ExtractSignals()
        self._extractor = extractor
        self._files = files
        self._flow_key = flow_key
        self._generation = generation

    def run(self) -> None:
        try:
            # self._files["sheet"] -> 슬롯이 없으면 KeyError 대신 읽을 수 있는 메시지 표시
            sheet = self._files.get("sheet")
            if sheet is None:
                raise ValueError("조견표(sheet) 파일이 없습니다.")
            values = self._extractor.extract_jogyeon_values(sheet)
        except Exception as error:
            self.signals.failed.emit(
                self._generation, str(error) or type(error).__name__
            )
        else:
            self.signals.finished.emit(self._generation, values)


class UploadPage(QWidget):
    # valuesReady(ConstantValues): 다음 단계로 넘어가도 된다는 신호
    valuesReady = pyqtSignal(object)
    # filesDiverged(bool): 지금 올라온 파일이 마지막으로 추출에 쓰인 파일과 다른지 여부.
    # True면 2,3단계 값이 낡았을 수 있다는 뜻(단계 이동 잠금), False면 원래 파일로 되돌아왔다는 뜻(잠금 해제)
    filesDiverged = pyqtSignal(bool)

    def __init__(
        self,
        extractor: ValueExtractor | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PageBody")
        self._extractor = extractor
        self._pool = QThreadPool.globalInstance()

        self._flow: FlowSpec | None = None
        self._cards: dict[str, UploadCard] = {}
        self._pinned: set[str] = set()
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

        # 메뉴 1 데이터 불러오기 버튼 추가
        self._load_cache_btn = GhostButton("📂 이전 작업 불러오기 (메뉴 1)")
        self._load_cache_btn.clicked.connect(self._load_cached_files)
        self._load_cache_btn.setVisible(False)  # 숨겨두기

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
        column.addWidget(self._load_cache_btn) # 타이틀 아래에 캐시 로드 버튼 추가
        column.addWidget(self._next)
        column.addWidget(self._hint)
        column.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

    # --- API --------------------------------------------------------------
    def set_extractor(self, extractor: ValueExtractor | None) -> None:
        self._extractor = extractor

    def set_flow(self, flow: FlowSpec) -> None:
        # 흐름이 바뀌면 문구와 업로드 카드를 통째로 갈아 끼운다.
        if self._flow is not None and self._flow.key == flow.key:
            return  # 같은 흐름으로 되돌아온 경우: 올린 파일을 유지
        self._flow = flow
        self._title.setText(flow.upload_title)
        self._subtitle.setText(flow.upload_description)
        self.reset()

    def reset(self) -> None:
        # 카드를 새로 만들고 상태를 처음으로 되돌린다.
        self._generation += 1  # 돌고 있던 추출 결과를 무효로 만든다
        self._values = None
        self._confirmed_files = {}
        self._confirmed_values = None
        self._cards.clear()
        self._pinned.clear() 
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        if self._flow is None:
            return
        # TODO(remember_last):
        # slot.remember_last==True 인 슬롯은 카드를 만든 뒤
        # services.recent_files.get_recent_path(slot.key) 로 저장된 경로가 있는지 확인
        #   -> 있으면 card.set_path(path) 를 바로 호출해 자동으로 채운다.
        #   -> 없거나 파일이 사라졌을 때만 지금처럼 빈 카드로 두고 직접 업로드를 받는다.
        # 주의: 이 루프 중간에 자동 채움이 fileSelected -> _on_file_selected 를 곧바로 태우면
        # 아직 안 만들어진 카드까지 "다 찼다"고 오판할 수 있음
        # 카드를 전부 만든 다음 한 번에 자동 채움을 돌리는 편이 안전하다.
        has_cache = False
        for slot in self._flow.uploads:
            card = UploadCard(slot.title, slot.description, slot.extensions, slot.icon)
            card.fileSelected.connect(
                lambda file, key=slot.key: self._on_file_selected(key, file)
            )
            self._cards[slot.key] = card
            self._cards_layout.addWidget(card)

            if recent_files.get_recent_path(slot.key):
                has_cache = True
        show_btn = has_cache and (self._flow.key == "notice_verify")
        self._load_cache_btn.setVisible(show_btn)
        self._set_state(WAITING)

    def values(self) -> ConstantValues | None:
        return self._values

    # --- 동작 -------------------------------------------------------------
    def files(self) -> dict[str, UploadedFile]:
        return self._files()

    def _files(self) -> dict[str, UploadedFile]:
        return {
            key: card.file() for key, card in self._cards.items() if card.file()
        }  # type: ignore[misc]

    def _on_file_selected(self, key: str, _file: UploadedFile) -> None:
        self._generation += 1  # 진행 중이던 추출이 있었다면 무효로 만든다
        if (
            self._flow is not None
            and self._flow.key == UNIT_PRICE.key
            and key == "sheet"
        ):
            # flow 1(조견표 -> 단가표 생성)에서 조견표를 올리면
            # flow 2가 나중에 자동으로 불러올 수 있도록 경로 저장
            recent_files.set_recent_path(key, _file.path)
        self._refresh_files_state()

    # _on_file_selected 안에 있던 상태 재계산을 꺼내서 재사용 가능하게 분리
    def _refresh_files_state(self) -> None:
        files = self._files()
        # 추출에 성공한 적이 없으면(_confirmed_files 비어있음) 아직 비교할 대상 자체가 없다.
        matches_confirmed = bool(self._confirmed_files) and files == self._confirmed_files
        if matches_confirmed:
            # 원래 추출에 썼던 파일 그대로 돌아온 경우: 다시 읽을 필요 없이 그 값을 그대로 쓴다.
            self._values = self._confirmed_values
            self._set_state(READY)
        else:
            self._values = None
            self._set_state(FILLED if len(files) == len(self._cards) else WAITING)
        diverged = bool(self._confirmed_files) and not matches_confirmed
        self.filesDiverged.emit(diverged)

    def _start_extract(self, files: dict[str, UploadedFile]) -> None:
        if self._extractor is None:
            # 추출기를 안 붙인 경우: 파일 확인까지만 하고 READY 로 넘어간다
            self._values = {}
            self._confirmed_files = dict(files)
            self._confirmed_values = self._values
            self._set_state(READY)
            return

        self._set_state(BUSY)
        task = _ExtractTask(self._extractor, files, self._flow.key, self._generation)
        task.signals.finished.connect(self._on_extracted)
        task.signals.failed.connect(self._on_extract_failed)
        self._pool.start(task)

    def _on_extracted(self, generation: int, values: ConstantValues) -> None:
        if generation != self._generation:
            return  # 중간에 파일이 바뀐 경우: 결과가 낡은 값이므로 다시 읽어야 함
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
            self._start_extract(self._files())
        elif self._state == READY and self._values is not None:
            self.valuesReady.emit(self._values)

    def _load_cached_files(self) -> None:
        loaded = False
        for key, card in self._cards.items():
            cached_path = recent_files.get_recent_path(key)
            if not cached_path or not os.path.exists(str(cached_path)):
                continue
            if hasattr(card, "set_path"):
                card.set_path(str(cached_path))
            self._pinned.add(key)
            loaded = True

        if not loaded:
            return
        # 다 불러왔으면 버튼 숨기기
        self._load_cache_btn.setVisible(False)
        # set_path 가 fileSelected 를 쏘지 않는 구현일 수 있어 상태를 직접 다시 계산한다.
        self._refresh_files_state()

    # --- 내부 -------------------------------------------------------------
    def _set_state(self, state: str, reason: str = "") -> None:
        self._state = state
        busy = state == BUSY
        for key, card in self._cards.items():
            card.set_locked(busy or key in self._pinned)

        self._next.setEnabled(state in (FILLED, READY, FAILED))
        self._next.setText(
            _BUSY_TEXT if busy else _NEXT_TEXT if state == READY else _CONFIRM_TEXT
        )

        if state == WAITING:
            # missing = len(self._cards) - len(self._files())
            self._hint.setText("파일을 업로드해야 다음 단계로 갈 수 있습니다.")
        elif state == FILLED:
            self._hint.setText(
                "파일을 모두 올렸습니다. '확인'을 누르면 값을 읽어옵니다."
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

        set_state(self._hint, "state", state)
        self._hint.setVisible(True)
