# 0단계 — 문서 업로드 화면
#
# 카드에 파일이 다 채워지면 백그라운드에서 문서를 읽어 상수를 뽑는다.
# 읽기가 성공했을 때만 다음 단계로 넘어가는 버튼이 켜진다.
# (다음 화면 시작할 때 여기서 읽어온 값이 필요하기 때문)

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from models.dto import ConstantValues, UploadedFile
from models.flows import FlowSpec, UNIT_PRICE
from services import recent_files
from ui.components.button import PrimaryButton
from ui.components.scroll_page import centered_scroll_page
from utils.qss import set_state
from ui.widgets.upload_card import UploadCard

# 파일 묶음을 받아 상수를 돌려준다. 예외를 던지면 화면에 사유가 뜬다.
ValueExtractor = Callable[[dict[str, UploadedFile]], ConstantValues]

WAITING, BUSY, READY, FAILED = "waiting", "busy", "ready", "failed"

_NEXT_TEXT = "값 읽어오기 완료 — 다음 단계로  →"
_BUSY_TEXT = "⟳  문서에서 값을 읽는 중..."


class _ExtractSignals(QObject):
    finished = pyqtSignal(int, object)  # generation, ConstantValues
    failed = pyqtSignal(int, str)  # generation, 사유


class _ExtractTask(QRunnable):
    # 추출기를 GUI 스레드 밖에서 돌린다.

    def __init__(
        self,
        extractor: ValueExtractor,
        files: dict[str, UploadedFile],
        generation: int,
    ) -> None:
        super().__init__()
        self.signals = _ExtractSignals()
        self._extractor = extractor
        self._files = files
        self._generation = generation

    def run(self) -> None:
        try:
            values = self._extractor(self._files)
        except Exception as error:  # 파서가 어떤 예외를 던질지 알 수 없다
            self.signals.failed.emit(
                self._generation, str(error) or type(error).__name__
            )
        else:
            self.signals.finished.emit(self._generation, values)


class UploadPage(QWidget):
    # valuesReady(ConstantValues) — 다음 단계로 넘어가도 좋을 때

    valuesReady = pyqtSignal(object)  # ConstantValues

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
        self._values: ConstantValues | None = None
        self._generation = 0
        self._state = WAITING

        self._build()

    # --- 구성 -------------------------------------------------------------
    def _build(self) -> None:
        page, column = centered_scroll_page(640)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._cards_holder = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_holder)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(14)

        self._next = PrimaryButton(_NEXT_TEXT)
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
        self._cards.clear()
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
        for slot in self._flow.uploads:
            card = UploadCard(slot.title, slot.description, slot.extensions, slot.icon)
            card.fileSelected.connect(
                lambda file, key=slot.key: self._on_file_selected(key, file)
            )
            self._cards[slot.key] = card
            self._cards_layout.addWidget(card)
        self._set_state(WAITING)

    def values(self) -> ConstantValues | None:
        return self._values

    # --- 동작 -------------------------------------------------------------
    def _files(self) -> dict[str, UploadedFile]:
        return {
            key: card.file() for key, card in self._cards.items() if card.file()
        }  # type: ignore[misc]

    def _on_file_selected(self, key: str, _file: UploadedFile) -> None:
        self._values = None
        self._generation += 1  # 파일이 바뀌었으므로 이전 추출 결과를 버림
        if (
            self._flow is not None
            and self._flow.key == UNIT_PRICE.key
            and key == "sheet"
        ):
            # flow 1(조견표 -> 단가표 생성)에서 조견표를 올리면
            # flow 2가 나중에 자동으로 불러올 수 있도록 경로 저장
            recent_files.set_recent_path(key, _file.path)
        files = self._files()
        if len(files) < len(self._cards):
            self._set_state(WAITING)
            return
        self._start_extract(files)

    def _start_extract(self, files: dict[str, UploadedFile]) -> None:
        if self._extractor is None:
            # 추출기를 안 붙인 경우: 파일 확인까지만 하고 넘긴다
            self._values = {}
            self._set_state(READY)
            return

        self._set_state(BUSY)
        task = _ExtractTask(self._extractor, files, self._generation)
        task.signals.finished.connect(self._on_extracted)
        task.signals.failed.connect(self._on_extract_failed)
        self._pool.start(task)

    def _on_extracted(self, generation: int, values: ConstantValues) -> None:
        if generation != self._generation:
            return  # 중간에 파일이 바뀐 경우: 결과가 낡은 값이므로 다시 읽어야 함
        self._values = values
        self._set_state(READY)

    def _on_extract_failed(self, generation: int, reason: str) -> None:
        if generation != self._generation:
            return
        self._values = None
        self._set_state(FAILED, reason)

    def _on_next(self) -> None:
        if self._state == READY and self._values is not None:
            self.valuesReady.emit(self._values)

    # --- 내부 -------------------------------------------------------------
    def _set_state(self, state: str, reason: str = "") -> None:
        self._state = state
        busy = state == BUSY
        for card in self._cards.values():
            card.set_locked(busy)

        self._next.setEnabled(state == READY)
        self._next.setText(_BUSY_TEXT if busy else _NEXT_TEXT)

        if state == WAITING:
            missing = len(self._cards) - len(self._files())
            self._hint.setText(f"파일을 업로드해야 다음 단계로 갈 수 있습니다.")
        elif state == BUSY:
            self._hint.setText("문서를 읽고 있습니다. 잠시만 기다려 주세요.")
        elif state == READY:
            count = len(self._values or {})
            self._hint.setText(
                f"값 {count}개를 읽었습니다. 다음 화면에서 확인·수정할 수 있습니다."
                if count
                else "문서를 확인했습니다."
            )
        else:
            self._hint.setText(
                f"문서를 읽지 못했습니다 — {reason}\n파일을 다시 골라 주세요."
            )

        set_state(self._hint, "state", state)
        self._hint.setVisible(True)
