from __future__ import annotations
 
import re
from dataclasses import dataclass

#단가표 파싱용도


#소득형 6단계
TIERS = ("가", "나", "다", "라", "마", "바")

#기본단가 등급명 해석
_NAME_RE = re.compile(r"^(?P<base>.+?)\((?P<letter>[가-힣])형\)(?P<ext>_주간확장)?$")
SPECIAL_NAMES = ("긴급활동지원", "부적합")

#추가급여 "출산가구_가형"
_ADD_NAME_RE = re.compile(r"^(?P<base>.+?)_(?P<letter>[가-힣])형$")

#인정조사(1등급 ~ 4등급)
_IJ_RE = re.compile(r"^\d등급$")
#종합조사(1구간 ~ 15구간)
_JH_RE = re.compile(r"^\d+구간$")
#산정특례(특례1 ~ 특례60)
_SJ_RE = re.compile(r"^특례\d+$")

@dataclass(frozen=True)
class ParsedRow:
    kind: str  # "ij" | "jh" | "sj" | "add" | "special" | "unknown"
    base: str = ""  # "1등급" / "3구간" / "특례12" / "출산가구" / (special·unknown 은 원문)
    letter: str = ""  # 가~바
    variant: str = "기본형"  # 기본형 / 확장형(_주간확장)

def parse_name(name: str)->ParsedRow:
    text = str(name or "").strip()
    if text in SPECIAL_NAMES:
        return ParsedRow("special", base=text)
    m=_NAME_RE.match(text)
    #기본단가
    if m:
        base,letter=m.group("base"), m.group("letter")
        variant = "확장형" if m.group("ext") else "기본형"

        if letter not in TIERS:
            return ParsedRow("unknown", base=text)
        if _IJ_RE.match(base):
            return ParsedRow("ij",base,letter,variant)
        if _JH_RE.match(base):
            return ParsedRow("jh", base, letter, variant)
        if _SJ_RE.match(base):
            return ParsedRow("sj", base, letter, variant)
        return ParsedRow("unknown", base=text)

    #추가급여
    m=_ADD_NAME_RE.match(text)
    if m and m.group("letter") in TIERS:
        return ParsedRow("add", m.group("base"), m.group("letter"))
    return ParsedRow("unknown", base=text)