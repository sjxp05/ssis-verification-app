# 조견표에서 찾는 문구 상수로 정리 - 서식 변경시 여기만 변경
#
# 값 추출기(services/jogyeon_value_extractor.py)와 라벨 매처가 함께 사용

from __future__ import annotations

JOGYEON_SHEET_NAMES = ("인정조사", "산정특례", "종합조사")

BASE_PRICE = "기본단가"
A_VALUE = "A값"
BASIC_RATE = "기본 부담률"
CAP_LABEL = "상한액"
GRADE_HEADER = "활동지원등급"
INCOME_HEADER = "기준중위소득"
JH_BASIC = "주간활동 기본형"
JH_EXTENDED = "주간활동 확장형"

# 한 표 안에서 유일해야 하는 앵커 (여러 개면 어느 셀을 읽을지 정할 수 없다)
SCALAR_ANCHORS = (
    BASE_PRICE,
    A_VALUE,
    BASIC_RATE,
    CAP_LABEL,
    GRADE_HEADER,
    INCOME_HEADER,
    JH_BASIC,
    JH_EXTENDED,
)

IJ_GRADES = tuple(f"{i}등급" for i in range(1, 5))
JH_ZONES = tuple(f"{i}등급" for i in range(1, 16))
JH_LABELS = tuple(f"{i}구간" for i in range(1, 16))
RATE_GRADES = ("다", "라", "마", "바")

# 조견표에 없는 가형/나형의 고정 금액
# - 기초수급자(가)는 항상 면제
# - 차상위(나)는 정액 부담 (기본형: 20,000원 / 확장형: 면제)
# - 추가급여는 기초, 차상위 모두 면제
FIXED_BASIC_RATE = {"가": 0, "나": 20000}
FIXED_ADD_RATE = {"가": 0, "나": 0}

ADD_ITEMS = (
    "최중증1인가구",
    "1등급1인가구",
    "2등급이하1인가구",
    "최중증취약가구",
    "1등급취약가구",
    "2등급이하취약가구",
    "출산",
    "자립준비",
    "학교생활",
    "직장생활",
    "보호자일시부재",
    "나머지가구구성원의직장생활등",
)
