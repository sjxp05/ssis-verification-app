# 드래그앤드롭 + 클릭 업로드 카드
#
# 상태(idle / hover / done / rejected)는 동적 property 로만 표현

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from models.dto import UploadedFile
from utils.qss import set_state

IDLE, HOVER, DONE, REJECTED = "idle", "hover", "done", "rejected"


# 드래그앤드롭 또는 클릭으로 파일 한 개를 받는 카드
class UploadCard(QFrame):
    fileSelected = Signal(object)  # UploadedFile

    def __init__(
        self,
        title: str,
        description: str,
        extensions: tuple[str, ...],
        icon: str = "📄",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("UploadCard")
        self._extensions = tuple(e.lower() for e in extensions)
        self._file: UploadedFile | None = None
        self._locked = False

        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(title, description, icon)
        self._apply_state(IDLE)

    # --- 구성 -------------------------------------------------------------
    def _build(self, title: str, description: str, icon: str) -> None:
        self._icon = QLabel(icon)
        self._icon.setObjectName("UploadIcon")
        self._icon.setFixedSize(36, 36)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("UploadTitle")
        desc_label = QLabel(description)
        desc_label.setObjectName("UploadDesc")
        desc_label.setWordWrap(True)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(title_label)
        text.addWidget(desc_label)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(text, 1)

        self._status = QLabel()
        self._status.setObjectName("UploadStatus")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)
        outer.addLayout(top)
        outer.addWidget(self._status)

    # --- API --------------------------------------------------------------
    def file(self) -> UploadedFile | None:
        return self._file

    # 파일 지정: 확장자 틀리면 False
    def set_path(self, path: str | Path) -> bool:
        if Path(path).suffix.lower() not in self._extensions:
            self._apply_state(REJECTED)
            return False
        self._file = UploadedFile.from_path(path)
        self._apply_state(DONE)
        self.fileSelected.emit(self._file)
        return True

    # 추출하는 중 파일 변경 불가
    def set_locked(self, locked: bool) -> None:
        self.setAcceptDrops(not locked)
        self.setCursor(
            Qt.CursorShape.ArrowCursor if locked else Qt.CursorShape.PointingHandCursor
        )
        self._locked = locked

    # --- 내부 -------------------------------------------------------------
    def _resting_state(self) -> str:
        return DONE if self._file else IDLE

    def _apply_state(self, state: str) -> None:
        if state == DONE and self._file:
            self._icon.setText("✔")
            self._status.setText(f"✔  {self._file.name}  ·  {self._file.size_text}")
        elif state == REJECTED:
            allowed = " / ".join(self._extensions)
            self._status.setText(f"⚠  {allowed} 형식만 올릴 수 있습니다")
        else:
            self._status.setText("⬆  클릭하거나 파일을 끌어다 놓으세요")
        for widget in (self, self._icon, self._status):
            set_state(widget, "state", state)

    # --- 이벤트 -----------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._locked and event.button() == Qt.MouseButton.LeftButton:
            pattern = " ".join(f"*{e}" for e in self._extensions)
            path, _ = QFileDialog.getOpenFileName(
                self, "파일 선택", "", f"파일 ({pattern})"
            )
            if path:
                self.set_path(path)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in self._extensions:
            self._apply_state(HOVER)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._apply_state(self._resting_state())
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if not urls or not self.set_path(urls[0].toLocalFile()):
            self._apply_state(self._resting_state())
        super().dropEvent(event)
