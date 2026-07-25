"""셀 옆에 붙는 말풍선. 선택한 셀의 산식을 보여준다.

Qt.ToolTip 플래그를 쓰기 때문에 마우스를 가로채지 않는다.
표를 계속 클릭해도 말풍선만 따라 움직인다.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from resources.styles import theme

TAIL_W = 9  # 꼬리 너비
TAIL_H = 14  # 꼬리 높이
TAIL_TOP = 22  # 꼬리 중심이 위에서 얼마나 떨어지는지
RADIUS = 7
MARGIN = 10  # 그림자 여유
MAX_WIDTH = 320


class FormulaBubble(QWidget):
    """bubble.show_beside(cell_rect_in_global, "산식", "지원량 - 본인부담금")"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._tail_side = "left"  # 꼬리가 붙는 쪽

        self._title = QLabel()
        self._title.setObjectName("BubbleTitle")

        self._body = QLabel()
        self._body.setObjectName("BubbleBody")
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._foot = QLabel()
        self._foot.setObjectName("BubbleFoot")
        self._foot.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.addWidget(self._title)
        layout.addWidget(self._body)
        layout.addWidget(self._foot)
        self._layout = layout
        self._apply_margins()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 55))
        self.setGraphicsEffect(shadow)

    # --- API -------------------------------------------------------------
    def show_beside(
        self,
        anchor: QRect,
        title: str = "산식",
        formula: str = "",
        note: str = "",
    ) -> None:
        """anchor 는 전역 좌표 기준 셀 사각형."""
        if not formula:
            self.hide()
            return

        self._title.setText(title)
        self._body.setText(formula)
        self._foot.setText(note)
        self._foot.setVisible(bool(note))

        self._body.setMaximumWidth(MAX_WIDTH)
        self._tail_side = "left"
        self._apply_margins()
        self.adjustSize()

        screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()

        x = anchor.right() + 4
        y = anchor.center().y() - TAIL_TOP - MARGIN

        if x + self.width() > area.right():
            self._tail_side = "right"
            self._apply_margins()
            self.adjustSize()
            x = anchor.left() - self.width() + 4

        y = max(area.top() + 4, min(y, area.bottom() - self.height() - 4))
        self.move(int(x), int(y))
        self.show()
        self.raise_()

    # --- 그리기 ----------------------------------------------------------
    def _apply_margins(self) -> None:
        left = MARGIN + (TAIL_W if self._tail_side == "left" else 0)
        right = MARGIN + (TAIL_W if self._tail_side == "right" else 0)
        self._layout.setContentsMargins(left + 12, MARGIN + 10, right + 12, MARGIN + 10)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 시그니처)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        left = MARGIN + (TAIL_W if self._tail_side == "left" else 0)
        right = self.width() - MARGIN - (TAIL_W if self._tail_side == "right" else 0)
        body = QRectF(left, MARGIN, right - left, self.height() - MARGIN * 2)

        path = QPainterPath()
        path.addRoundedRect(body, RADIUS, RADIUS)

        tip_y = min(MARGIN + TAIL_TOP, body.center().y())
        if self._tail_side == "left":
            tail = QPolygonF(
                [
                    QPointF(body.left() - TAIL_W, tip_y),
                    QPointF(body.left() + 1, tip_y - TAIL_H / 2),
                    QPointF(body.left() + 1, tip_y + TAIL_H / 2),
                ]
            )
        else:
            tail = QPolygonF(
                [
                    QPointF(body.right() + TAIL_W, tip_y),
                    QPointF(body.right() - 1, tip_y - TAIL_H / 2),
                    QPointF(body.right() - 1, tip_y + TAIL_H / 2),
                ]
            )
        path.addPolygon(tail)
        path = path.simplified()

        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(QColor(theme.SURFACE))
        painter.drawPath(path)
