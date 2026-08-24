# 조견표에서 찾는 문구 상수로 정리 - 서식 변경시 여기만 변경
#
# 값 추출기(services/jogyeon_value_extractor.py)와 라벨 매처가 함께 사용

from __future__ import annotations

from models.dto import RequiredLabel

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

# 동시에 성립할 수 없는 표현들. 정규화된 라벨에서 부분문자열로 찾는다
ANTONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("이하", "초과"),
    ("이상", "미만"),
    ("기본형", "확장형"),
    ("가능", "불가능"),
    ("포함", "제외"),
    ("이전", "이후"),
    ("최소", "최대"),
    ("가산", "감산"),
)
# 한쪽에만 있으면 의미가 뒤집히는 부정 표현
NEGATION_MARKERS: tuple[str, ...] = ("아님", "않음", "없음", "미해당", "비해당")

# 단가표를 만드는 데 반드시 필요한 문구
BASIC = "기본급여 단가표"
ADD = "추가급여 단가표"
REQUIRED: tuple[RequiredLabel, ...] = (
    # ANCHOR (부분 문자열로 찾음)
    RequiredLabel(BASE_PRICE, "인정조사", "기본단가", (BASIC,)),
    RequiredLabel(
        A_VALUE,
        "인정조사",
        "인정조사 본인부담금 상한액",
        (BASIC,),
    ),
    RequiredLabel(BASIC_RATE, "인정조사", "인정조사 본인부담률", (BASIC, ADD)),
    RequiredLabel(GRADE_HEADER, "인정조사", "인정조사 월한도액", (BASIC,)),
    RequiredLabel(
        CAP_LABEL,
        "산정특례",
        "종합조사·산정특례 본인부담금 상한액",
        (BASIC,),
        optional=True,
    ),
    RequiredLabel(INCOME_HEADER, "산정특례", "종합조사·산정특례 본인부담률", (BASIC,)),
    RequiredLabel(JH_BASIC, "종합조사", "종합조사 월한도액 (기본형)", (BASIC,)),
    RequiredLabel(JH_EXTENDED, "종합조사", "종합조사 월한도액 (확장형)", (BASIC,)),
    # ITEM (행/열 이름. 정확히 일치 필요)
    *(
        RequiredLabel(
            g, "인정조사", "인정조사 월한도액의 등급 행", (BASIC,), exact=True
        )
        for g in IJ_GRADES
    ),
    *(
        RequiredLabel(
            z, "종합조사", "종합조사 월한도액의 구간 열", (BASIC,), exact=True
        )
        for z in JH_ZONES
    ),
    *(
        RequiredLabel(
            i, "산정특례", "추가급여 월한도액의 항목 열", (BASIC, ADD), exact=True
        )
        for i in ADD_ITEMS
    ),
)
