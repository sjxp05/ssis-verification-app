# 버튼 3종. 스타일은 objectName 으로 app.qss 와 연결된다.
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QWidget


class _BaseButton(QPushButton):
    OBJECT_NAME = ""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName(self.OBJECT_NAME)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class PrimaryButton(_BaseButton):
    # 화면 하단 풀폭 네이비 버튼

    OBJECT_NAME = "PrimaryButton"

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setMinimumHeight(48)


# class PillButton(_BaseButton):
#     # 연한 파란색 둥근 버튼 - 미사용

#     OBJECT_NAME = "PillButton"

#     def __init__(self, text: str, parent: QWidget | None = None):
#         super().__init__(text, parent)
#         self.setMinimumHeight(32)


class GhostButton(_BaseButton):
    # 보조 동작용 외곽선 버튼.

    OBJECT_NAME = "GhostButton"

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setMinimumHeight(32)
