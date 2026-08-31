# 회색 제목 띠 + 흰 본문으로 이루어진 카드 컨테이너

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)


class Card(QFrame):
    # Card("문서 안의 값이 정확한지 확인해 주세요") 처럼 쓰고 body_layout 에 내용을 채운다.

    def __init__(
        self,
        title: str = "",
        hint: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header: QFrame | None = None
        if title:
            self._header = QFrame()
            self._header.setObjectName("CardHeader")
            header_layout = QHBoxLayout(self._header)
            header_layout.setContentsMargins(16, 10, 16, 10)
            header_layout.setSpacing(8)

            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            header_layout.addWidget(title_label)
            header_layout.addStretch(1)

            if hint:
                hint_label = QLabel(hint)
                hint_label.setObjectName("CardHint")
                header_layout.addWidget(hint_label)

            outer.addWidget(self._header)

        self._body = QWidget()
        self.body_layout = QVBoxLayout(self._body)
        self.body_layout.setContentsMargins(20, 18, 20, 20)
        self.body_layout.setSpacing(14)
        outer.addWidget(self._body)

    def add_widget(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def add_layout(self, layout: QLayout) -> None:
        self.body_layout.addLayout(layout)
