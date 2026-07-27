"""동적 property 로 위젯 상태를 바꿀 때 쓰는 도우미.

QSS 의 [state="done"] 같은 선택자는 property 를 바꾼 뒤 스타일을 다시
계산해 줘야 반영된다.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget


def repolish(widget: QWidget) -> None:
    """동적 property 변경 후 QSS를 다시 적용시킨다."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def set_state(widget: QWidget, name: str, value: object) -> None:
    """동적 property 를 세팅하고 스타일을 즉시 반영한다."""
    if widget.property(name) == value:
        return  # 값이 같으면 repolish 비용을 아낀다
    widget.setProperty(name, value)
    repolish(widget)
