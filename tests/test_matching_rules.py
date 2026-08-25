# 규칙 파서와 제약 층 단위 검증
#
# 임베딩 모델을 쓰지 않으므로 몇 초면 끝난다. 엔진을 고쳤을 때 가장 먼저 돌린다.
#
#   python tests/test_matching_rules.py

from __future__ import annotations

import numpy as np

import _support  # noqa: F401  (sys.path 설정)
from app.jogyeon_matcher import label_rules
from app.jogyeon_matcher.label_rules import (
    find_normalization_collisions,
    normalize,
    sanitize,
)

# 비가시 문자는 소스에 그대로 적지 않고 이스케이프로 쓴다.
# 눈에 안 보이는 문자를 코드에 넣으면 편집기·인코딩에 따라 조용히 깨진다.
ZWSP = "​"      # ZERO WIDTH SPACE
NBSP = " "      # NO-BREAK SPACE
BOM = "﻿"       # ZERO WIDTH NO-BREAK SPACE
LRM = "‎"       # LEFT-TO-RIGHT MARK
WORD_JOINER = "⁠"
SOFT_HYPHEN = "­"
FULLWIDTH_A = "Ａ"

# (작년 문구, 올해 문구, 기대, 왜 이런 기대인가)
#   True  구조가 동등 -> auto_pass 가능
#   False 구조가 상이 -> 점수와 무관하게 매칭 금지
#   None  파싱 불가   -> 하이브리드로 폴백
PARSER_CASES = [
    ("100% 이하", "100% 이하", True, "항등"),
    ("90% 이하", "90% 초과", False, "반의어 — 점수와 무관하게 거부"),
    ("90% 이하", "90% 미만", False, "경계 개폐 차이"),
    ("3등급", "3등급", True, "항등"),
    ("10구간", "11구간", False, "숫자 판별자"),
    ("3등급", "3구간", False, "종류 다름"),
    ("주간활동 기본형", "주간활동 확장형", False, "유형어"),
    ("기본단가", "본인부담금", None, "파싱 불가 -> 하이브리드 폴백"),
]

# (작년 문구, 올해 문구, 숫자 관계, 반의어 충돌, 왜)
VETO_CASES = [
    ("10구간", "11구간", "conflict", False, "값이 정면 충돌 — 강한 강등"),
    ("100%이하", "150%이하", "conflict", False, "형제 밴드"),
    ("2024 A값", "2025 A값", "same", False, "연도는 시점 표기 — 해마다 바뀌는 게 정상"),
    ("A값", "2027 A값", "same", False, "연도만 덧붙음 — 판별자가 아님"),
    ("2등급이하1인가구", "2등급이하취약가구", "extra", False, "한쪽이 다른 쪽을 포함"),
    ("1등급취약가구", "1등급취약계층", "same", False, "숫자 동일 — 동의어 후보로 살려둠"),
    ("90%이하", "90%초과", "same", True, "반의어"),
    ("자기부담금", "본인부담금", "same", False, "동의어 — 어느 제약도 걸리면 안 됨"),
    ("재판정가능", "재판정불가능", "same", True, "가능/불가능"),
    ("2024년 10구간", "2025년 11구간", "conflict", False, "연도를 빼도 구간이 충돌"),
]

# (원문, 정규형, 왜)
NORMALIZE_CASES = [
    ("기본 단가(원)", "기본단가", "단위 괄호 주석 제거"),
    ("[기본단가]", "기본단가", "장식 괄호는 기호만 벗김"),
    ("（본인부담금 상한액）", "(본인부담금상한액)", "전각 괄호는 NFKC 로 해소하되 괄호 자체는 보존"),
    ("1등급(가형)", "1등급(가형)", "판별 내용을 담은 괄호는 절대 제거하지 않음"),
    ("100 % 이하", "100%이하", "공백만 제거, % 와 방향어는 보존"),
    (f"월{ZWSP} 한도액", "월한도액", "ZWSP 제거"),
    (f"지원시간{NBSP}", "지원시간", "NBSP 제거"),
    (f"{FULLWIDTH_A}값", "A값", "전각 A 호모글리프 해소"),
    ("150% 초과", "150%초과", "방향어는 판별자라 보존"),
]


def test_normalizer():
    for raw, expected, why in NORMALIZE_CASES:
        got = normalize(raw)
        assert got == expected, f"{raw!r} -> {got!r}, 기대 {expected!r} ({why})"


def test_sanitize_removes_invisible_characters():
    # 문자를 열거하는 방식으로 거르면 반드시 누락이 생기므로,
    # sanitize 는 유니코드 카테고리(Cf·Cc)로 판단해야 한다.
    for char in (ZWSP, BOM, LRM, WORD_JOINER, SOFT_HYPHEN):
        got = sanitize(f"기본{char}단가")
        assert got == "기본단가", f"U+{ord(char):04X} 미제거 -> {got!r}"


def test_normalization_keeps_labels_distinct():
    # 과잉 정규화로 서로 다른 라벨이 같아지면 안 된다
    labels = ["기본 부담률", "추가 부담률", "100% 이하", "100% 초과", "1등급", "1등급1인가구"]
    collisions = find_normalization_collisions(labels)
    assert not collisions, f"정규화 충돌: {collisions}"


def test_rule_parser():
    for left, right, expected, why in PARSER_CASES:
        got = label_rules.rule_parser.equals(normalize(left), normalize(right))
        assert got is expected, f"{left!r} vs {right!r} -> {got}, 기대 {expected} ({why})"


def test_numeric_and_antonym_constraints():
    for left, right, expected_relation, expected_antonym, why in VETO_CASES:
        relation = label_rules.constraints.numeric_relation(normalize(left), normalize(right))
        antonym = label_rules.constraints.antonym_conflict(normalize(left), normalize(right))
        assert relation == expected_relation, (
            f"{left!r} vs {right!r} 숫자 관계 {relation!r}, 기대 {expected_relation!r} ({why})"
        )
        assert antonym is expected_antonym, (
            f"{left!r} vs {right!r} 반의어 {antonym}, 기대 {expected_antonym} ({why})"
        )


def test_veto_demotes_but_does_not_erase():
    # 차단이 아니라 강등이어야 한다. 완전히 0 으로 만들면 기준이 바뀐 해에
    # 정답이 후보 목록에서 아예 사라진다.
    labels = ["11구간", "10구간"]
    scores = np.array([0.9, 0.9])
    adjusted, flags = label_rules.constraints.apply_vetoes("10구간", labels, scores)
    assert adjusted[0] < adjusted[1], "충돌 후보가 강등되지 않음"
    assert adjusted[0] > 0, "강등이 아니라 소거됨 — 후보에서 사라지면 안 됨"
    assert "NUMERIC_VETO_APPLIED" in flags[0]


def test_contested_detection():
    # 0행과 1행이 모두 열 0 을 1순위로 지목 -> 둘 다 경합
    matrix = np.array([[0.9, 0.5, 0.1], [0.8, 0.2, 0.1], [0.1, 0.2, 0.7]])
    contested = label_rules.constraints.find_contested(matrix)
    assert contested == {0, 1}, f"경합 대상 {sorted(contested)}, 기대 [0, 1]"


if __name__ == "__main__":
    raise SystemExit(_support.run_module(dict(globals())))
