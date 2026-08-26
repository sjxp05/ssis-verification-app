# ONNX 임베딩 인코더

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import paths

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

        # 모델을 실제 사용하는 시점까지 무거운 라이브러리 로딩을 지연
        import onnxruntime as ort
        from tokenizers import Tokenizer

        meta = json.loads((self._dir / "meta.json").read_text(encoding="utf-8"))
        self._prefix = meta.get("prefix", self._prefix)

        self._tokenizer = Tokenizer.from_file(str(self._dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=MAX_LEN)
        self._tokenizer.enable_padding()

        options = ort.SessionOptions()

        # 0이면 CPU 코어 수에 맞춰 스레드 수를 자동 설정
        options.intra_op_num_threads = 0

        self._session = ort.InferenceSession(
            str(self._dir / "model_int8.onnx"),
            options,
            providers=["CPUExecutionProvider"],
        )

    # ONNX 그래프에서 풀링과 L2 정규화까지 처리
    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        self._load()

        encoded = self._tokenizer.encode_batch(
            [self._prefix + text for text in texts]
        )

        return self._session.run(
            None,
            {
                "input_ids": np.array(
                    [item.ids for item in encoded],
                    dtype=np.int64,
                ),
                "attention_mask": np.array(
                    [item.attention_mask for item in encoded],
                    dtype=np.int64,
                ),
            },
        )[0]