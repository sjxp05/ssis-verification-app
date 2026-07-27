# ui/components/scroll_page.py
"""가운데 정렬된 폭 제한 세로 컬럼 + 스크롤 영역."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget


def centered_scroll_page(max_width: int = 640) -> tuple[QScrollArea, QVBoxLayout]:
    """스크롤 영역과, 거기에 위젯을 쌓을 세로 레이아웃을 함께 돌려준다."""
    column = QWidget()
    column.setObjectName("ScrollColumn")
    column.setMaximumWidth(max_width)
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 24, 0, 24)
    layout.setSpacing(14)

    holder = QWidget()
    holder_layout = QVBoxLayout(holder)
    holder_layout.setContentsMargins(28, 0, 28, 0)
    holder_layout.addWidget(column, 0, Qt.AlignmentFlag.AlignHCenter)

    area = QScrollArea()
    area.setObjectName("ScrollPage")
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(holder)
    return area, layout