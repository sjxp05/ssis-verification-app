# 희소 검색 — 문자 2-gram BM25
#
# 외부 의존성 없음. 형태소 분석기는 측정 결과 개선 여지가 0이라 넣지 않았다.

from __future__ import annotations

import math
from collections import Counter

K1 = 1.5
B = 0.75


# 숫자는 삭제하지 않고 토큰에 포함시킨다
def tokenize(text: str) -> list[str]:
    if len(text) < 2:
        return [text] if text else []
    return [text[i : i + 2] for i in range(len(text) - 1)]


class BM25:
    def __init__(self, corpus: list[str]):
        self.docs = [tokenize(d) for d in corpus]
        self.lens = [len(d) for d in self.docs]
        self.avg_len = (sum(self.lens) / len(self.docs)) if self.docs else 1.0
        self.tfs = [Counter(d) for d in self.docs]

        n_docs = len(self.docs)
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(set(doc))
        self.idf = {
            t: max(math.log((n_docs - n + 0.5) / (n + 0.5) + 1.0), 0.01)
            for t, n in df.items()
        }
        # 코퍼스에 없는 토큰의 idf(df=0일 때의 최댓값).
        # 자기 점수 분모에서 미지 토큰을 0으로 두면 분모에 매칭된 부분만 남아
        # 쿼리가 미지 문자열일수록 오히려 만점이 나온다.
        self.oov_idf = math.log((n_docs + 0.5) / 0.5 + 1.0)

    def _raw(self, query_tokens: list[str], tf: Counter, doc_len: int) -> float:
        score = 0.0
        for token in query_tokens:
            freq = tf.get(token, 0)
            if not freq:
                continue
            denom = freq + K1 * (1 - B + B * doc_len / self.avg_len)
            score += self.idf.get(token, self.oov_idf) * freq * (K1 + 1) / denom
        return score

    # 0~1 절대 점수. 후보 풀의 최고점이 아니라 쿼리 자기 자신과의 점수로 나눈다.
    # "이 후보가 쿼리의 근거 총량 중 얼마를 설명하는가"가 되어 후보 풀과 무관해진다.
    # 쿼리별 max 정규화를 쓰면 1순위가 항상 1.0이라 컷오프가 작동하지 못한다.
    # 모든 후보를 같은 상수로 나누므로 순위는 그대로 보존된다.
    def scores(self, query: str) -> list[float]:
        tokens = tokenize(query)
        if not tokens or not self.docs:
            return [0.0] * len(self.docs)

        self_score = self._raw(tokens, Counter(tokens), len(tokens))
        if self_score <= 0:
            return [0.0] * len(self.docs)

        return [
            min(self._raw(tokens, tf, dl) / self_score, 1.0)
            for tf, dl in zip(self.tfs, self.lens)
        ]
