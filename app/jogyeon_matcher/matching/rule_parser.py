# 규칙 파서 — 결정론 경로
#
# 파싱에 성공한 라벨은 유사도 문제가 아니라 동등성 문제가 된다. '90% 이하'가
# Band(90, 이하) 가 되는 순간 '90% 초과'와의 비교는 참/거짓이고 퍼지 매칭이
# 사라진다. auto_pass 를 걸어도 되는 유일한 퍼지 경로가 이것이다.
#
# 패턴이 안 맞으면 None 을 돌려 하이브리드 매처로 넘긴다. 느슨하게 매칭하는
# 파서는 없느니만 못하므로 형태가 정확할 때만 받는다.

from __future__ import annotations

import re
from dataclasses import dataclass

_BAND = re.compile(r"^(\d+(?:\.\d+)?)%(이하|이상|초과|미만)$")
_ORDINAL = re.compile(r"^(\d+)(등급|구간)$")
_FORM = re.compile(r"^(.*?)(기본형|확장형)$")


# 경계값과 개폐 여부까지 담아야 이하/초과가 구분된다
@dataclass(frozen=True)
class Band:
    value: float
    direction: str


@dataclass(frozen=True)
class Ordinal:
    number: int
    kind: str


@dataclass(frozen=True)
class Form:
    stem: str
    kind: str


# 원래 표기가 등급인지 구간인지. engine.py에서 표기 변경 여부를 알려주기 위해 사용
def ordinal_kind_diff(label: str) -> str | None:
    matched = _ORDINAL.match(label)
    return matched.group(2) if matched else None


def parse(label: str) -> Band | Ordinal | Form | None:
    matched = _BAND.match(label)
    if matched:
        return Band(float(matched.group(1)), matched.group(2))

    matched = _ORDINAL.match(label)
    if matched:
        # 실제 조견표 간 매칭 시에는 '등급'으로 표시
        return Ordinal(int(matched.group(1)), "등급")

    matched = _FORM.match(label)
    if matched:
        return Form(matched.group(1), matched.group(2))

    return None


# True  파싱 성공 + 동일 -> auto_pass 가능
# False 파싱 성공 + 상이 -> 점수와 무관하게 매칭 금지
# None  파싱 불가       -> 하이브리드로 폴백
def equals(left: str, right: str) -> bool | None:
    a, b = parse(left), parse(right)
    if a is None or b is None:
        return None
    if type(a) is not type(b):
        return False
    return a == b
