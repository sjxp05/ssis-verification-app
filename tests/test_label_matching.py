# 라벨 매칭 205건 검증 (fixtures/synthetic_label_tests.xlsx)
#
# 매칭 함수 단위의 회귀 테스트다. 표기 변형·동의어·오타·반의어·숫자 판별자 등
# 13개 세부유형이 들어 있고, production 기본값(HybridConfig)을 그대로 쓴다.
#
# 임베딩 모델을 로드하므로 20~30초 걸린다.
#
#   python tests/test_label_matching.py

from __future__ import annotations

import numpy as np
import pandas as pd

import _support
from jogyeon_matcher.matching.hybrid import HybridConfig, HybridMatcher
from jogyeon_matcher.matching.normalizer import normalize

# 부품 성능이 실제로 갈리는 구간. 나머지는 항등(74건)·정규화(28건)라
# 전체 평균을 지표로 쓰면 차이가 희석된다.
FUZZY_TYPES = ("A2.동의어", "A3.축약확장", "A4.어순·조사", "A5.오타·자소")
NO_GOLD = "(없음)"


def _load_cases() -> pd.DataFrame:
    path = _support.require(_support.LABEL_CASES)
    df = pd.read_excel(path, sheet_name="테스트케이스", engine="openpyxl")
    df = df.rename(columns={
        "기준라벨(정답)": "gold",
        "입력라벨(변형)": "query",
        "지정 교란 후보": "distractors",
        "기대결과": "expect",
        "세부유형": "subtype",
    })
    df["distractors"] = df["distractors"].map(_split)
    return df


def _split(cell) -> list[str]:
    if pd.isna(cell):
        return []
    raw = str(cell)
    for sep in ("|", ";", ",", "/"):
        raw = raw.replace(sep, "\n")
    return [s.strip() for s in raw.split("\n") if s.strip()]


def _corpus(df: pd.DataFrame) -> list[str]:
    labels = {g for g in df["gold"] if not pd.isna(g) and g != NO_GOLD}
    for row in df["distractors"]:
        labels.update(row)
    return sorted(labels)


def _judge(row, ranked: list[tuple[str, float]], cutoff: float) -> str:
    """통과하면 빈 문자열, 실패하면 사유를 돌려준다."""
    expect, gold = row["expect"], row["gold"]
    top3 = [label for label, _ in ranked[:3]]
    scores = dict(ranked)

    if expect in ("auto_pass", "auto_pass_after_norm", "auto_pass_BLINDSPOT"):
        if normalize(row["query"]) != normalize(gold):
            return f"정규화 불일치 {normalize(row['query'])!r} != {normalize(gold)!r}"

    elif expect == "pairwise_distinct":
        for other in row["distractors"]:
            if normalize(gold) == normalize(other):
                return f"정규화 충돌 {gold!r} == {other!r}"

    elif expect == "no_match":
        top = ranked[0][1] if ranked else 0.0
        if top >= cutoff:
            return f"컷오프 초과 {ranked[0][0]!r} {top:.3f}"

    elif expect == "review_top3":
        if gold not in top3:
            return f"top3 밖 {top3}"

    elif expect == "top1_strict":
        if not ranked or ranked[0][0] != gold:
            return f"1순위 아님 {top3}"
        for other in row["distractors"]:
            if scores.get(other, 0.0) >= scores.get(gold, 0.0):
                return f"교란 후보에 밀림 {other!r}"

    elif expect == "never_silent_fail":
        if normalize(row["query"]) != normalize(gold) and gold not in top3:
            return f"조용한 실패 {top3}"

    return ""


def _evaluate() -> pd.DataFrame:
    df = _load_cases()
    corpus = _corpus(df)
    corpus_norm = [normalize(c) for c in corpus]
    queries = [normalize(q) for q in df["query"]]

    config = HybridConfig()
    matcher = HybridMatcher(corpus_norm, config)

    # 채널을 한 번에 계산한다. 쿼리마다 재인코딩하면 훨씬 느려진다.
    sparse = np.array([matcher._bm25.scores(q) for q in queries])
    cosine = matcher._encoder.encode(queries) @ matcher._encoder.encode(corpus_norm).T
    floor = config.cosine_floor
    dense = np.clip((cosine - floor) / (1 - floor), 0.0, 1.0)
    final = config.alpha * sparse + (1 - config.alpha) * dense

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        ranked = sorted(zip(corpus, final[i]), key=lambda pair: -pair[1])
        reason = _judge(row, ranked, config.cutoff)
        rows.append({
            "test_id": row["test_id"], "subtype": row["subtype"],
            "query": row["query"], "gold": row["gold"],
            "top3": " | ".join(label for label, _ in ranked[:3]),
            "passed": not reason, "reason": reason,
        })
    return pd.DataFrame(rows)


_RESULT: pd.DataFrame | None = None


def _result() -> pd.DataFrame:
    global _RESULT
    if _RESULT is None:
        _RESULT = _evaluate()
    return _RESULT


def test_all_cases_pass():
    res = _result()
    failed = res[~res["passed"]]
    detail = "\n".join(
        f"  {r.test_id} [{r.subtype}] {r.query!r} -> {r.gold!r}: {r.reason}"
        for r in failed.itertuples()
    )
    assert failed.empty, f"{len(failed)}/{len(res)} 실패\n{detail}"


def test_fuzzy_population_recall():
    # 유효 모집단(퍼지 매칭이 실제로 일하는 구간)은 전량 통과해야 한다
    res = _result()
    fuzzy = res[res["subtype"].isin(FUZZY_TYPES)]
    assert len(fuzzy) > 0, "유효 모집단 케이스를 찾지 못함 — 픽스처 확인 필요"
    failed = fuzzy[~fuzzy["passed"]]
    assert failed.empty, f"유효 모집단 {len(failed)}/{len(fuzzy)} 실패"


if __name__ == "__main__":
    result = _result()
    fuzzy = result[result["subtype"].isin(FUZZY_TYPES)]
    print(f"유효 모집단 {fuzzy['passed'].sum()}/{len(fuzzy)} · "
          f"전체 {result['passed'].sum()}/{len(result)}\n")
    raise SystemExit(_support.run_module(dict(globals())))
