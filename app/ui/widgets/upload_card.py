import os
import sys
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout,
)

sys.path.append('ssis-verification-app/app/models/dto.py')
from dto import UploadedFile

class UploadCard(QFrame):
    """드래그앤드롭 + 클릭 업로드 카드."""
    fileSelected = pyqtSignal(object)   # UploadedFile

    def __init__(self, title: str, desc: str, exts: list[str], icon: str = "📄"):
        super().__init__()
        self.exts = exts
        self.file: Optional[UploadedFile] = None
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(12)
        self._icon = QLabel(icon)
        self._icon.setFixedSize(36, 36)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        txt = QVBoxLayout()
        txt.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"font-weight:600; font-size:13px; color:{T.FG}; background:transparent;")
        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet(f"font-size:11px; color:{T.MUTED_FG}; background:transparent;")
        txt.addWidget(t)
        txt.addWidget(d)
        top.addLayout(txt, 1)
        lay.addLayout(top)

        self._status = QLabel()
        lay.addWidget(self._status)
        self._render(state="idle")

    # 상태 렌더링
    def _render(self, state: str):
        """state: idle | hover | done"""
        icon_css = f"border-radius:4px; font-size:16px;"
        if state == "done" and self.file:
            self.setStyleSheet(f"UploadCard{{background:#f6fdf8; border:1px solid {T.GREEN_BORDER}; border-radius:4px;}}")
            self._icon.setText("✔")
            self._icon.setStyleSheet(f"background:#dcfce7; color:{T.GREEN}; {icon_css}")
            self._status.setText(f"✔  {self.file.name}  ·  {self.file.size_text}")
            self._status.setStyleSheet(
                f"font-size:11px; color:{T.GREEN}; padding:8px 10px; border-radius:4px;"
                f" background:{T.GREEN_BG}; font-family:'{T.FONT_MONO}';")
        else:
            border = f"2px dashed {T.PRIMARY}" if state == "hover" else f"2px dashed {T.BORDER}"
            bg = T.SECONDARY if state == "hover" else T.CARD
            self.setStyleSheet(f"UploadCard{{background:{bg}; border:{border}; border-radius:4px;}}")
            self._icon.setStyleSheet(f"background:{T.SECONDARY}; color:{T.PRIMARY}; {icon_css}")
            self._status.setText("⬆  클릭하거나 파일을 끌어다 놓으세요")
            self._status.setStyleSheet(f"font-size:11px; color:{T.MUTED_FG}; padding:8px 10px; background:transparent;")

    # 파일 세팅
    def set_path(self, path: str):
        size = os.path.getsize(path) if os.path.exists(path) else 0
        self.file = UploadedFile(path=path, name=os.path.basename(path), size=size)
        self._render("done")
        self.fileSelected.emit(self.file)

    # 이벤트
    def mousePressEvent(self, e):
        filt = f"파일 ({' '.join('*' + x for x in self.exts)})"
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", filt)
        if path:
            self.set_path(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self._render("hover")
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._render("done" if self.file else "idle")

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.set_path(urls[0].toLocalFile())
        else:
            self._render("done" if self.file else "idle")
