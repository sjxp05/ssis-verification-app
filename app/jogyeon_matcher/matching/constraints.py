# 판정 제약 — 점수 위에 겹치는 딱딱한 층
#
# 숫자 불일치와 반의어는 점수와 무관하게 매칭을 막는다. 점수 공간은 연속적인데
# 이 실패 모드들은 이산적이라 어떤 임계값으로도 갈라낼 수 없기 때문이다.
#     자기부담금 ↔ 본인부담금   한 글자 차이인데 매칭해야 함
#     10구간    ↔ 11구간      한 글자 차이인데 절대 금지
#
# 제약은 후보를 목록에서 지우지 않고 강등만 한다. 완전히 막으면 기준중위소득이
# 85%→90% 로 바뀌었을 때 정답이 후보에서 사라져, 가장 놓치면 안 되는 변경에서
# Recall 이 깨진다. 제약의 역할은 auto_pass 를 막는 것이지 후보를 없애는 게 아니다.

from __future__ import annotations

import re
from collections import Counter

import numpy as np

from ..config.antonyms import ANTONYM_GROUPS, NEGATION_MARKERS

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

CONFLICT_PENALTY = 0.15  # 값이 정면으로 다름
EXTRA_PENALTY = 0.6      # 한쪽에 숫자가 덧붙기만 함
LOW_MARGIN_THRESHOLD = 0.05


def numbers_of(label: str) -> Counter:
    return Counter(_NUMBER.findall(label))


# 숫자 관계. 모든 불일치가 같은 무게는 아니다.
#     10구간 ↔ 11구간     {10} vs {11}     값 충돌   -> conflict
#     A값   ↔ 2027 A값   {}   vs {2027}   부가 표기 -> extra
# 포함 관계까지 같은 계수로 누르면 정당한 개칭이 후보에서 밀려난다.
def numeric_relation(left: str, right: str) -> str:
    a, b = numbers_of(left), numbers_of(right)
    if a == b:
        return "same"
    if not (a - b) or not (b - a):
        return "extra"
    return "conflict"


def antonym_conflict(left: str, right: str) -> bool:
    for group in ANTONYM_GROUPS:
        left_hits = {w for w in group if w in left}
        right_hits = {w for w in group if w in right}
        if left_hits and right_hits and left_hits != right_hits:
            return True

    left_negated = any(m in left for m in NEGATION_MARKERS)
    right_negated = any(m in right for m in NEGATION_MARKERS)
    return left_negated != right_negated


def apply_vetoes(
    query: str, labels: list[str], scores: np.ndarray
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


# 1순위를 두 개 이상이 공유하는 대상들의 인덱스.
#
# 모든 대상의 1순위가 서로 다르면 그 배정은 각 행의 최댓값을 동시에 취한 것이라
# 총합의 상한을 달성한다. 즉 그리디가 곧 최적해이고 헝가리안과 반드시 일치한다.
# 대우를 취하면 둘이 갈리려면 1순위가 겹쳐야 하므로, 겹침만 보면 헝가리안이
# 잡아낼 항목을 하나도 빠뜨리지 않는다. scipy 를 들일 이유가 없다.
def find_contested(score_matrix: np.ndarray) -> set[int]:
    if score_matrix.size == 0:
        return set()

    owners: dict[int, list[int]] = {}
    for row, best in enumerate(np.argmax(score_matrix, axis=1)):
        owners.setdefault(int(best), []).append(row)
    return {row for rows in owners.values() if len(rows) > 1 for row in rows}


def margin_flag(scores: np.ndarray) -> list[str]:
    if len(scores) < 2:
        return []
    top2 = np.partition(-scores, 1)[:2]
    return ["LOW_MARGIN"] if (-top2[0] + top2[1]) < LOW_MARGIN_THRESHOLD else []
