from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from utils.qss import set_state


# 여백은 QSS padding 이 아니라 레이아웃으로 준다.
# wordWrap 라벨에 QSS padding 을 주면 Qt 가 높이 계산에서 그 여백을 빠뜨린다.
def banner(text: str, state: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("ReviewBanner")
    set_state(frame, "state", state)

    layout = QHBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    label = WrapLabel(text)
    label.setObjectName("ReviewBannerText")
    layout.addWidget(label)
    return frame


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("ReviewSectionTitle")
    return label


# 줄바꿈되는 라벨은 폭이 정해져야 높이가 나오는데, 스크롤 안 중첩 레이아웃에서는
# 그 순서가 보장되지 않아 글자가 잘린다. 폭이 바뀔 때마다 필요한 높이를 직접
# 최소 높이로 박아 레이아웃이 반드시 그만큼 잡게 한다.
class WrapLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def resizeEvent(self, event):  # noqa: N802 (Qt 시그니처)
        super().resizeEvent(event)
        self._sync_height()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt 시그니처)
        super().setText(text)
        self._sync_height()

    def _sync_height(self) -> None:
        if self.width() > 0:
            self.setMinimumHeight(self.heightForWidth(self.width()))
