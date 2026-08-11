# 단가표를 만드는 데 반드시 필요한 문구
#
# "확인 안 하면 단가표를 못 만든다"와 "바뀌어도 상관없다"를 가르는 기준이다.
# 전자만 담당자를 붙잡고, 후자는 가볍게 넘긴다.
#
# 아래 대응은 두 파일을 따라가서 정리했다. 둘 중 하나가 바뀌면 여기도 고쳐야 한다.
#   services/jogyeon_value_extractor.py  어떤 문구로 어떤 값을 읽는가
#   services/table_writer.py             어떤 값으로 어떤 표를 만드는가
#
# 찾는 방식이 두 가지라 구분해서 다룬다.
#   ANCHOR  부분문자열로 찾고 한 행에만 있어야 한다 (_find_one)
#           '2024 A값' 안의 'A값' 도 찾아내므로, 연도가 붙어도 추출은 된다.
#   ITEM    셀 내용이 정확히 같아야 찾는다 (등급·구간·추가급여 항목의 행/열 이름)

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
    produces: str  # 이 문구로 읽어내는 값
    tables: tuple[str, ...]  # 그 값이 없으면 못 만드는 표
    exact: bool = False  # True 면 셀 내용이 정확히 같아야 한다


REQUIRED: tuple[RequiredLabel, ...] = (
    RequiredLabel(BASE_PRICE, "인정조사", "기본단가", (BASIC,)),
    RequiredLabel(A_VALUE, "인정조사", "인정조사 본인부담금 상한액", (BASIC,)),
    RequiredLabel(BASIC_RATE, "인정조사", "인정조사 본인부담률", (BASIC, ADD)),
    RequiredLabel(GRADE_HEADER, "인정조사", "인정조사 월한도액", (BASIC,)),
    RequiredLabel(CAP_LABEL, "산정특례", "종합조사·산정특례 본인부담금 상한액", (BASIC,)),
    RequiredLabel(INCOME_HEADER, "산정특례", "종합조사·산정특례 본인부담률", (BASIC,)),
    RequiredLabel(JH_BASIC, "종합조사", "종합조사 월한도액 (기본형)", (BASIC,)),
    RequiredLabel(JH_EXTENDED, "종합조사", "종합조사 월한도액 (확장형)", (BASIC,)),
    # 행·열을 짚는 이름들. 하나라도 없으면 그 표 전체를 못 읽는다.
    *(RequiredLabel(g, "인정조사", "인정조사 월한도액의 등급 행", (BASIC,), exact=True)
      for g in IJ_GRADES),
    *(RequiredLabel(z, "종합조사", "종합조사 월한도액의 구간 열", (BASIC,), exact=True)
      for z in JH_ZONES),
    *(RequiredLabel(i, "산정특례", "추가급여 월한도액의 항목 열", (BASIC, ADD), exact=True)
      for i in ADD_ITEMS),
)
