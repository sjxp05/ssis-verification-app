# 밀집 검색 — ONNX int8 임베딩 인코더
#
# 런타임 의존성은 onnxruntime + tokenizers 둘뿐이다. torch/transformers 는
# 빌드 타임(tools/export_model.py)에만 쓰이고 번들에 들어가지 않는다.
#
# 지연 로딩이 핵심이다. 서식이 바뀌지 않은 해에는 규칙 판정으로 다 끝나서
# 하이브리드 경로에 도달하지 않으므로, 모델이 아예 로드되지 않는다.

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .. import paths

MAX_LEN = 64
EMBEDDING_DIM = 384


class DenseEncoder:
    def __init__(self, model_dir: Path | None = None):
        self._dir = model_dir or paths.model_dir()
        self._tokenizer = None
        self._session = None
        self._prefix = "query: "

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    def _load(self) -> None:
        if self._session is not None:
            return

        # 무거운 임포트도 이 시점까지 미룬다
        import onnxruntime as ort
        from tokenizers import Tokenizer

        meta = json.loads((self._dir / "meta.json").read_text(encoding="utf-8"))
        # e5 계열은 프리픽스가 필수다. 변환 시점 값을 그대로 따라간다.
        self._prefix = meta.get("prefix", self._prefix)

        self._tokenizer = Tokenizer.from_file(str(self._dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=MAX_LEN)
        self._tokenizer.enable_padding()

        options = ort.SessionOptions()
        # 담당자 PC 사양을 낙관하지 않는다. 연 1회 150라벨이면 1스레드로 충분하다.
        options.intra_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(self._dir / "model_int8.onnx"), options,
            providers=["CPUExecutionProvider"],
        )

    # L2 정규화된 임베딩 행렬. 풀링·정규화는 ONNX 그래프에 내장돼 있다.
    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        self._load()

        encoded = self._tokenizer.encode_batch([self._prefix + t for t in texts])
        return self._session.run(None, {
            "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64),
        })[0]
