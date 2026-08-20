# 희소(BM25) + 밀집(임베딩) 결합
#
#     final = α · bm25 + (1-α) · rescale(cosine)
#
# 코사인은 척도가 보정돼 있지 않다. 실측 분포가 min=0.760 mean=0.830 이라
# 무관한 문자열끼리도 0.83 이 나온다. 순위를 매기는 데는 쓸 수 있어도
# "얼마나 확신하는가"의 절대 척도로는 쓸 수 없어서, 바닥을 걷어내 두 채널을
# 같은 0~1 척도로 맞춘다. 맞추지 않으면 밀집 채널이 절대 스케일을 지배해
# 컷오프가 무너진다.
#
# COSINE_FLOOR 는 모델 고유값이라 모델을 바꾸면 반드시 다시 측정해야 한다.

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dense import DenseEncoder
from .sparse import BM25

COSINE_FLOOR = 0.76  # intfloat/multilingual-e5-small 실측


@dataclass
class HybridConfig:
    # 재척도화 전에는 α=0.8 한 점만 통과했으나, 맞춘 뒤에는 0.4~0.9 전 구간이
    # 통과한다. 고원 중앙을 골라 모델·데이터가 달라져도 여유를 둔다.
    alpha: float = 0.6

    cosine_floor: float = COSINE_FLOOR

    # 음성(무관) 최대 0.235 와 양성(정답 존재) 최소 0.323 사이 간극의 중앙.
    # 이 미만이면 unmatched 로 보내 직접 입력을 유도한다.
    cutoff: float = 0.28


class HybridMatcher:
    # 임베딩은 지연 로딩된다. 규칙 우선 판정으로 다 끝나는 해에는 모델이
    # 메모리에 올라오지도 않는다.
    def __init__(self, labels: list[str], config: HybridConfig | None = None,
                 encoder: DenseEncoder | None = None):
        self.labels = list(labels)
        self.config = config or HybridConfig()
        self._bm25 = BM25(self.labels)
        self._encoder = encoder or DenseEncoder()
        self._label_vectors: np.ndarray | None = None
        self._query_vectors: dict[str, np.ndarray] = {}

    # 하이브리드로 떨어질 쿼리들을 모아 한 번의 배치로 인코딩해 둔다.
    # 쿼리마다 단건 인코딩을 반복하면 ONNX 호출 오버헤드가 쿼리 수만큼 쌓인다.
    def precompute_queries(self, queries: list[str]) -> None:
        fresh = [q for q in dict.fromkeys(queries) if q not in self._query_vectors]
        if fresh:
            self._query_vectors.update(zip(fresh, self._encoder.encode(fresh)))

    def score_components(self, query: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        # (최종, BM25, 임베딩). 분해가 필요하면 이 함수를 한 번만 부르고 셋을
        # 함께 써야 한다. 따로 얻으려 여러 번 부르면 쿼리를 그때마다 재인코딩한다.
        sparse = np.array(self._bm25.scores(query), dtype=np.float64)
        dense = self._dense_scores(query)
        alpha = self.config.alpha
        return alpha * sparse + (1 - alpha) * dense, sparse, dense

    def scores(self, query: str) -> np.ndarray:
        return self.score_components(query)[0]

    def _dense_scores(self, query: str) -> np.ndarray:
        if self._label_vectors is None:
            self._label_vectors = self._encoder.encode(self.labels)
        vector = self._query_vectors.get(query)
        if vector is None:
            vector = self._encoder.encode([query])[0]
            self._query_vectors[query] = vector
        # 두 벡터 모두 L2 정규화되어 있으므로 내적이 곧 코사인
        cosine = vector @ self._label_vectors.T
        floor = self.config.cosine_floor
        return np.clip((cosine - floor) / (1.0 - floor), 0.0, 1.0)
