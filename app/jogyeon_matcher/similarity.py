# BM25와 임베딩 점수를 결합해 HYBRID 후보 점수 계산

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from .embedding_encoder import DenseEncoder

K1 = 1.5
B = 0.75

COSINE_FLOOR = 0.76


def tokenize(text: str) -> list[str]:
    if len(text) < 2:
        return [text] if text else []

    return [text[i : i + 2] for i in range(len(text) - 1)]


class BM25:
    def __init__(self, corpus: list[str]):
        self.docs = [tokenize(doc) for doc in corpus]
        self.lens = [len(doc) for doc in self.docs]
        self.avg_len = (
            sum(self.lens) / len(self.docs)
            if self.docs
            else 1.0
        )
        self.tfs = [Counter(doc) for doc in self.docs]

        n_docs = len(self.docs)
        df: Counter[str] = Counter()

        for doc in self.docs:
            df.update(set(doc))

        self.idf = {
            token: max(
                math.log((n_docs - count + 0.5) / (count + 0.5) + 1.0),
                0.01,
            )
            for token, count in df.items()
        }

        # 코퍼스에 없는 토큰은 df=0일 때의 최대 IDF 사용
        self.oov_idf = math.log((n_docs + 0.5) / 0.5 + 1.0)

    def _raw(
        self,
        query_tokens: list[str],
        tf: Counter,
        doc_len: int,
    ) -> float:
        score = 0.0

        for token in query_tokens:
            freq = tf.get(token, 0)

            if not freq:
                continue

            denom = freq + K1 * (
                1 - B + B * doc_len / self.avg_len
            )

            score += (
                self.idf.get(token, self.oov_idf)
                * freq
                * (K1 + 1)
                / denom
            )

        return score

    # 쿼리 자기 점수로 나눠 후보 풀과 무관한 0~1 점수로 정규화
    def scores(self, query: str) -> list[float]:
        tokens = tokenize(query)

        if not tokens or not self.docs:
            return [0.0] * len(self.docs)

        self_score = self._raw(
            tokens,
            Counter(tokens),
            len(tokens),
        )

        if self_score <= 0:
            return [0.0] * len(self.docs)

        return [
            min(self._raw(tokens, tf, doc_len) / self_score, 1.0)
            for tf, doc_len in zip(self.tfs, self.lens)
        ]


@dataclass
class HybridConfig:
    alpha: float = 0.6
    cosine_floor: float = COSINE_FLOOR
    cutoff: float = 0.28


class HybridMatcher:
    def __init__(
        self,
        labels: list[str],
        config: HybridConfig | None = None,
        encoder: DenseEncoder | None = None,
    ):
        self.labels = list(labels)
        self.config = config or HybridConfig()
        self._bm25 = BM25(self.labels)
        self._encoder = encoder or DenseEncoder()
        self._label_vectors: np.ndarray | None = None
        self._query_vectors: dict[str, np.ndarray] = {}

    # HYBRID 판정 대상 쿼리를 한 번에 인코딩해 ONNX 호출 횟수 최소화
    def precompute_queries(self, queries: list[str]) -> None:
        fresh = [
            query
            for query in dict.fromkeys(queries)
            if query not in self._query_vectors
        ]

        if fresh:
            self._query_vectors.update(
                zip(fresh, self._encoder.encode(fresh))
            )

    def score_components(
        self,
        query: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sparse = np.array(
            self._bm25.scores(query),
            dtype=np.float64,
        )
        dense = self._dense_scores(query)

        alpha = self.config.alpha
        final = alpha * sparse + (1 - alpha) * dense

        return final, sparse, dense

    def scores(self, query: str) -> np.ndarray:
        return self.score_components(query)[0]

    def _dense_scores(self, query: str) -> np.ndarray:
        if self._label_vectors is None:
            self._label_vectors = self._encoder.encode(self.labels)

        vector = self._query_vectors.get(query)

        if vector is None:
            vector = self._encoder.encode([query])[0]
            self._query_vectors[query] = vector

        # DenseEncoder 결과는 L2 정규화되어 있어 내적이 코사인 유사도
        cosine = vector @ self._label_vectors.T

        floor = self.config.cosine_floor

        return np.clip(
            (cosine - floor) / (1.0 - floor),
            0.0,
            1.0,
        )