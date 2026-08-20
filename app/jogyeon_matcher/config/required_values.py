# 단가표를 만드는 데 반드시 필요한 문구
#
# 판정 기준 2가지
#   ANCHOR  부분문자열로 탐색, 한 행에만 있어야 함 (_find_one) => exact=False
#           연도가 붙어도 추출 가능 (예시: '2024 A값' 안의 'A값')
#   ITEM    셀 내용 정확히 일치 (등급·구간·추가급여 항목의 행/열 이름) => exact=True
#
# 다음 파일에 변경사항이 있으면 REQUIRED 목록에도 반영 필요
#   services/jogyeon_value_extractor.py  (어떤 문구로 값울 찾을지 기준이 바뀔 경우)
#   services/table_writer.py             (단가표 생성에 필요한 값의 종류가 바뀔 경우)

from __future__ import annotations

from dataclasses import dataclass

from .anchors import (
    ADD_ITEMS,
    A_VALUE,
    BASE_PRICE,
    BASIC_RATE,
    CAP_LABEL,
    GRADE_HEADER,
    IJ_GRADES,
    INCOME_HEADER,
    JH_BASIC,
    JH_EXTENDED,
    JH_ZONES,
)

BASIC = "기본급여 단가표"
ADD = "추가급여 단가표"


@dataclass(frozen=True)
class RequiredLabel:
    label: str
    sheet: str
    produces: str  # 이 문구로 찾을 값
    tables: tuple[str, ...]  # 해당 값이 있어야 만들 수 있는 표
    exact: bool = False  # True이면 셀 내용이 정확히 일치해야 함


REQUIRED: tuple[RequiredLabel, ...] = (
    # ANCHOR (부분 문자열로 찾음)
    RequiredLabel(BASE_PRICE, "인정조사", "기본단가", (BASIC,)),
    RequiredLabel(A_VALUE, "인정조사", "인정조사 본인부담금 상한액", (BASIC,)),
    RequiredLabel(BASIC_RATE, "인정조사", "인정조사 본인부담률", (BASIC, ADD)),
    RequiredLabel(GRADE_HEADER, "인정조사", "인정조사 월한도액", (BASIC,)),
    RequiredLabel(
        CAP_LABEL, "산정특례", "종합조사·산정특례 본인부담금 상한액", (BASIC,)
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
