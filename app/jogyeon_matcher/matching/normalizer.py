# 라벨 정제·정규화
#
# 표현 분산만 제거하고 판별 내용은 절대 보존한다.
#   제거 - 공백류, 단위 괄호 주석, 장식 괄호
#   보존 - 숫자, %, ~, 방향어(이하/이상/초과/미만), 유형어(기본형/확장형)

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# 단위 주석으로 보고 통째로 지울 괄호.
# (가형)·(나형)처럼 판별 내용을 담은 괄호는 지우면 안 되므로 화이트리스트로 둔다.
_UNIT_PAREN = re.compile(
    r"[(\[]\s*(?:단위\s*[:：][^)\]]*|원|천원|백만원|pt|포인트|%|점|명|개|월|년)\s*[)\]]"
)

# 내용은 살리고 기호만 벗기는 장식 괄호
_DECORATIVE = str.maketrans("", "", "[]「」『』【】〔〕<>")

_WS = re.compile(r"\s+")


# NFKC 정규화 후 서식(Cf)·제어(Cc) 문자 제거.
# ZWSP·BOM·LRM 등을 문자로 열거하지 않고 카테고리로 거른다. 열거는 항상 누락된다.
def sanitize(text) -> str:
    s = unicodedata.normalize("NFKC", str(text))
    return "".join(ch for ch in s if unicodedata.category(ch) not in ("Cf", "Cc"))


def normalize(text) -> str:
    # 같은 라벨이 수집·대조·앵커 검사에서 반복 정규화되므로 문자열 입력은 캐싱한다.
    # 순수 함수라 결과는 동일하고, 항목 수는 파일의 고유 라벨 수로 유한하다.
    if isinstance(text, str):
        return _normalize_cached(text)
    return _normalize_impl(text)


@lru_cache(maxsize=None)
def _normalize_cached(text: str) -> str:
    return _normalize_impl(text)


def _normalize_impl(text) -> str:
    s = sanitize(text)
    s = _UNIT_PAREN.sub("", s)
    s = s.translate(_DECORATIVE)
    return _WS.sub("", s).strip()


# 기동 시 불변식: 기준 라벨들이 정규화 후에도 쌍별로 구분되는가.
# 비어 있지 않으면 정규화가 판별 내용을 삼킨 것이다.
def find_normalization_collisions(labels) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for label in labels:
        buckets.setdefault(normalize(label), []).append(label)
    return {k: v for k, v in buckets.items() if len(set(v)) > 1}
