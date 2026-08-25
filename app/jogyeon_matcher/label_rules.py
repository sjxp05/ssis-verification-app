# 라벨 정규화, 규칙 파싱, 후보 점수 보정

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from config.anchors import ANTONYM_GROUPS, NEGATION_MARKERS
from models.dto import LabelRef, MatchPath


# 문자열 정제, 정규화
# 단위 주석으로 보고 통째로 지울 괄호
_UNIT_PAREN = re.compile(
    r"[(\[]\s*(?:단위\s*[:：][^)\]]*|원|천원|백만원|pt|포인트|%|점|명|개|월|년)\s*[)\]]"
)

# 내용은 살리고 기호만 벗기는 장식 괄호
_DECORATIVE = str.maketrans("", "", "[]「」『』【】〔〕<>")

_WS = re.compile(r"\s+")


def sanitize(text) -> str:
    s = unicodedata.normalize("NFKC", str(text))
    return "".join(ch for ch in s if unicodedata.category(ch) not in ("Cf", "Cc"))


def normalize(text) -> str:
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


def find_normalization_collisions(labels) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for label in labels:
        buckets.setdefault(normalize(label), []).append(label)
    return {k: v for k, v in buckets.items() if len(set(v)) > 1}


# 구조 라벨 파싱
_BAND = re.compile(r"^(\d+(?:\.\d+)?)%(이하|이상|초과|미만)$")
_ORDINAL = re.compile(r"^(\d+)(등급|구간)$")
_FORM = re.compile(r"^(.*?)(기본형|확장형)$")


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


def ordinal_kind_diff(label: str) -> str | None:
    matched = _ORDINAL.match(label)
    return matched.group(2) if matched else None


def parse(label: str) -> Band | Ordinal | Form | None:
    matched = _BAND.match(label)
    if matched:
        return Band(float(matched.group(1)), matched.group(2))

    matched = _ORDINAL.match(label)
    if matched:
        return Ordinal(int(matched.group(1)), "등급")

    matched = _FORM.match(label)
    if matched:
        return Form(matched.group(1), matched.group(2))

    return None


def equals(left: str, right: str) -> bool | None:
    a, b = parse(left), parse(right)
    if a is None or b is None:
        return None
    if type(a) is not type(b):
        return False
    return a == b


# EXACT, NORMALIZED, RULE_PARSER로 모델 전 절대식 라벨 매칭
class DeterministicIndex:
    def __init__(self, target_labels: dict[str, LabelRef]):
        self.raw: dict[str, str] = {}
        self.parsed: dict[object, str] = {}

        for key, found in target_labels.items():
            # 동일 후보가 여러 개면 먼저 나온 라벨을 사용
            self.raw.setdefault(found.raw, key)

            token = parse(key)
            if token is not None:
                self.parsed.setdefault(token, key)


def match_deterministic(
    ref: LabelRef,
    target_labels: dict[str, LabelRef],
    index: DeterministicIndex,
) -> tuple[MatchPath, str] | None:
    key = index.raw.get(ref.raw)
    if key is not None:
        return MatchPath.EXACT, key

    if ref.normalized in target_labels:
        return MatchPath.NORMALIZED, ref.normalized

    token = parse(ref.normalized)
    if token is not None:
        key = index.parsed.get(token)
        if key is not None:
            return MatchPath.RULE_PARSER, key

    return None


# 숫자, 반의어 제약
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_YEAR = re.compile(r"^(?:19|20)\d{2}$")

CONFLICT_PENALTY = 0.15
EXTRA_PENALTY = 0.6
LOW_MARGIN_THRESHOLD = 0.05


def _is_year(token: str) -> bool:
    return bool(_YEAR.match(token))


def numbers_of(label: str) -> Counter:
    return Counter(_NUMBER.findall(label))


def numeric_relation(left: str, right: str) -> str:
    a, b = numbers_of(left), numbers_of(right)

    if a == b:
        return "same"

    # 연도 차이는 조견표의 정상적인 연도 갱신으로 처리
    a_rest = Counter({k: v for k, v in a.items() if not _is_year(k)})
    b_rest = Counter({k: v for k, v in b.items() if not _is_year(k)})

    if a_rest == b_rest:
        return "same"

    if not (a_rest - b_rest) or not (b_rest - a_rest):
        return "extra"

    return "conflict"


def antonym_conflict(left: str, right: str) -> bool:
    for group in ANTONYM_GROUPS:
        left_hits = {word for word in group if word in left}
        right_hits = {word for word in group if word in right}

        if left_hits and right_hits and left_hits != right_hits:
            return True

    left_negated = any(marker in left for marker in NEGATION_MARKERS)
    right_negated = any(marker in right for marker in NEGATION_MARKERS)

    return left_negated != right_negated


def apply_vetoes(
    query: str,
    labels: list[str],
    scores: np.ndarray,
) -> tuple[np.ndarray, list[list[str]]]:
    adjusted = scores.astype(np.float64).copy()
    flags: list[list[str]] = [[] for _ in labels]

    for i, label in enumerate(labels):
        relation = numeric_relation(query, label)

        if relation == "conflict":
            adjusted[i] *= CONFLICT_PENALTY
            flags[i].append("NUMERIC_VETO_APPLIED")

        elif relation == "extra":
            adjusted[i] *= EXTRA_PENALTY
            flags[i].append("NUMERIC_EXTRA")

        if antonym_conflict(query, label):
            adjusted[i] *= CONFLICT_PENALTY
            flags[i].append("ANTONYM_BLOCKED")

    return adjusted, flags


# 후보 경합, 마진 판정


def find_contested(score_matrix: np.ndarray) -> set[int]:
    if score_matrix.size == 0:
        return set()

    owners: dict[int, list[int]] = {}

    for row, best in enumerate(np.argmax(score_matrix, axis=1)):
        owners.setdefault(int(best), []).append(row)

    return {
        row
        for rows in owners.values()
        if len(rows) > 1
        for row in rows
    }


def margin_flag(scores: np.ndarray) -> list[str]:
    if len(scores) < 2:
        return []

    top2 = np.partition(-scores, 1)[:2]

    return (
        ["LOW_MARGIN"]
        if (-top2[0] + top2[1]) < LOW_MARGIN_THRESHOLD
        else []
    )