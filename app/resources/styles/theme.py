"""디자인 토큰 정의 및 QSS 로더.

app.qss 안의 ${TOKEN} 자리에 아래 값들이 치환된다.
QPainter로 직접 그리는 위젯(말풍선 등)도 같은 토큰을 import 해서 쓴다.
"""

from pathlib import Path
from string import Template

# --- Color ---------------------------------------------------------------
NAVY = "#1B3A63"  # 헤더 / 테이블 헤더 / 주요 버튼
NAVY_DARK = "#14304F"  # hover, pressed
NAVY_LIGHT = "#2C5488"
ACCENT = "#2B6CB0"  # 코드 컬럼 등 강조 텍스트
ACCENT_SOFT = "#CFE3F5"  # pill 버튼 배경

BG = "#F4F5F7"  # 앱 배경
SURFACE = "#FFFFFF"  # 카드 / 테이블 배경
STEP_BG = "#EDEFF2"  # 스텝바 배경
CARD_HEADER_BG = "#E9EBEE"  # 카드 상단 회색 띠
FIELD_BG = "#FFFFFF"

BORDER = "#D8DCE1"
BORDER_SOFT = "#E8EAED"
GRID = "#E4E7EB"

TEXT = "#1F2933"
TEXT_MUTED = "#7B8794"
TEXT_ON_NAVY = "#FFFFFF"
TEXT_ON_NAVY_MUTED = "#C7D3E2"

# --- Metric --------------------------------------------------------------
RADIUS = "6px"
RADIUS_SM = "4px"
FONT_FAMILY = "'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"
FONT_MONO = "'D2Coding', 'Consolas', 'Menlo', monospace"

_TOKENS = {
    name: value
    for name, value in globals().items()
    if name.isupper() and isinstance(value, str)
}

_QSS_PATH = Path(__file__).with_name("app.qss")


def load_stylesheet() -> str:
    """app.qss를 읽어 토큰을 치환한 문자열을 돌려준다."""
    raw = _QSS_PATH.read_text(encoding="utf-8")
    return Template(raw).safe_substitute(_TOKENS)
