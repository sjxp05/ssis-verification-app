# 디자인 토큰 정의 및 QSS 로더
#
# app.qss 안의 ${TOKEN} 자리에 아래 값들이 치환된다.
# QPainter로 직접 그리는 위젯(말풍선 등)도 같은 토큰을 import 해서 쓴다.

from pathlib import Path
from string import Template

# --- Color ---------------------------------------------------------------
NAVY = "#1B3A63"  # 헤더 / 테이블 헤더 / 주요 버튼
NAVY_DARK = "#14304F"  # hover, pressed
NAVY_LIGHT = "#2C5488"
SCROLLBAR_THUMB = "#6787B4"  # 스크롤바 핸들 (NAVY보다 명도 높고 채도 낮음)
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
SUB_TEXT = "#636363"
TEXT_MUTED = "#7B8794"
TEXT_ON_NAVY = "#FFFFFF"
TEXT_ON_NAVY_MUTED = "#C7D3E2"
TEXT_GRAY = "#F2F2F2"

DANGER = "#DC2626"  # 잘못된 값 / 확장자 불일치
DANGER_DARK = "#991B1B"
DANGER_BG = "#FEF2F2"
DANGER_BORDER = "#FECACA"

SUCCESS = "#16A34A"  # 업로드 완료
SUCCESS_DARK = "#166534"
SUCCESS_BG = "#F0FDF4"
SUCCESS_BORDER = "#86EFAC"
SUCCESS_SOFT = "#DCFCE7"

ERROR_BG = "#FF7A7A"    # 오류 셀 (분명한 빨강 계열)
WARNING_BG = "#F4D87B"  # 확인 필요 셀 (분명한 노랑 계열)

WARNING_BANNER = "#FFF8E6"
WARNING_BORDER = "#F0D9A0"
INFO_BANNER = "#F2F7FD"
WARNING_TEXT = "#7A5A10"

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
    # app.qss를 읽어 토큰을 치환한 문자열을 돌려준다.
    try:
        raw = _QSS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RuntimeError(f"스타일시트를 찾을 수 없습니다: {_QSS_PATH}") from error
    try:
        return Template(raw).substitute(_TOKENS)
    except KeyError as error:
        raise KeyError(f"app.qss가 정의되지 않은 토큰{error}를 참조함") from None
