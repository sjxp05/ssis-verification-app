from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QLabel, QPushButton)

class Theme:
    PRIMARY     = "#1b3d7a"
    PRIMARY_HOV = "#274e94"
    SECONDARY   = "#eef1f7"
    BACKGROUND  = "#f8f8f7"
    CARD        = "#ffffff"
    BORDER      = "#e2e2e0"
    MUTED       = "#f0f0ee"
    MUTED_FG    = "#6b6b78"
    FG          = "#1a1a1f"

    RED_BG, RED_BORDER, RED, RED_DARK       = "#fef2f2", "#fecaca", "#dc2626", "#991b1b"
    GREEN_BG, GREEN_BORDER, GREEN, GREEN_DARK = "#f0fdf4", "#86efac", "#16a34a", "#166534"

    FONT_SANS = "Noto Sans KR"
    FONT_MONO = "Consolas"


T = Theme  # 짧은 별칭


def primary_button(text: str, height: int = 40, font_size: int = 13) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(height)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{T.PRIMARY}; color:white; border:none; border-radius:4px;"
        f" font-size:{font_size}px; font-weight:600; padding:0 16px;}}"
        f"QPushButton:hover{{background:{T.PRIMARY_HOV};}}"
        f"QPushButton:disabled{{background:{T.MUTED}; color:{T.MUTED_FG};}}")
    return b


def outline_button(text: str, height: int = 32) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(height)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{T.CARD}; color:{T.PRIMARY}; border:1px solid {T.PRIMARY};"
        f" border-radius:4px; font-size:11px; font-weight:500; padding:0 12px;}}"
        f"QPushButton:hover{{background:{T.SECONDARY};}}"
        f"QPushButton:disabled{{color:{T.MUTED_FG}; border-color:{T.BORDER};}}")
    return b


def section_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"font-size:10px; font-weight:600; color:{T.MUTED_FG}; letter-spacing:1px;")
    return l


TABLE_QSS = (
    f"QTableWidget{{background:white; alternate-background-color:{T.BACKGROUND};"
    f" gridline-color:{T.BORDER}; font-size:11px; font-family:'{T.FONT_MONO}';"
    f" border:1px solid {T.BORDER};}}"
    f"QHeaderView::section{{background:{T.PRIMARY}; color:white;"
    f" border:1px solid rgba(255,255,255,0.2); padding:6px 10px; font-size:11px;}}")

