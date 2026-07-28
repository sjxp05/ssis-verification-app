# 상단 네이비 헤더 바

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class HeaderBar(QFrame):
    # < 메인으로 | 화면명 ............ 날짜

    backRequested = pyqtSignal()

    def __init__(self, title: str, meta: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setFixedHeight(52)

        self._back = QPushButton("‹  메인으로")
        self._back.setObjectName("HeaderBack")
        self._back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back.clicked.connect(self.backRequested.emit)

        divider = QFrame()
        divider.setObjectName("HeaderDivider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedWidth(1)

        self._title = QLabel(title)
        self._title.setObjectName("HeaderTitle")

        self._meta = QLabel(meta)
        self._meta.setObjectName("HeaderMeta")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 20, 0)
        layout.setSpacing(12)
        layout.addWidget(self._back)
        layout.addWidget(divider)
        layout.addWidget(self._title)
        layout.addStretch(1)
        layout.addWidget(self._meta)

    # --- API -------------------------------------------------------------
    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_meta(self, text: str) -> None:
        self._meta.setText(text)

    def set_back_visible(self, visible: bool) -> None:
        self._back.setVisible(visible)
