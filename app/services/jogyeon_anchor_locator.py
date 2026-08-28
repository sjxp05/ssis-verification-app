from __future__ import annotations

import re

import pandas as pd

from config.anchors import AnchorFindMode
from jogyeon_matcher.label_rules import sanitize


# 공백, 비가시문자
_WS = re.compile(r"\s+")


class AnchorLocateError(Exception):
    """조견표에서 앵커 위치를 결정하지 못한 경우 발생하는 예외"""


class AnchorLocator:
    def __init__(self, norm: pd.DataFrame):
        self._norm = norm

    # ValueExtractor와 동일한 방식으로 검색 문구 정규화
    @staticmethod
    def squeeze(text) -> str:
        return _WS.sub("", sanitize(text))

    # 원본 DataFrame을 앵커 검색용 문자열 DataFrame으로 변환
    @classmethod
    def normalize_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        return df.astype(str).map(cls.squeeze)

    # 키워드가 나오는 모든 셀을 읽는 순서대로 반환
    def find_all(self, keyword: str) -> list[tuple[int, int]]:
        key = self.squeeze(keyword)
        hit = self._norm.apply(
            lambda series: series.str.contains(key, regex=False, na=False)
        )

        found = sorted(
            (int(row), int(column))
            for row, column in zip(
                *hit.to_numpy().nonzero(),
                strict=True,
            )
        )

        if not found:
            raise AnchorLocateError(f"'{keyword}'를 찾지 못했습니다.")

        return found

    # 여러 행에 존재하면 어느 표의 앵커인지 특정할 수 없으므로 예외 처리
    def find_one(self, keyword: str) -> tuple[int, int]:
        found = self.find_all(keyword)

        if len({row for row, _ in found}) > 1:
            raise AnchorLocateError(f"'{keyword}'가 여러 표에 있습니다")

        return found[0]

    # 여러 곳에 반복되는 것이 정상인 문구는 첫 번째 탐색 셀 사용
    def find_first(self, keyword: str) -> tuple[int, int]:
        return self.find_all(keyword)[0]

    # 앵커 명세의 one/first 방식에 따라 위치 결정
    def locate(
        self,
        keyword: str,
        mode: AnchorFindMode,
    ) -> tuple[int, int]:
        if mode == "one":
            return self.find_one(keyword)

        if mode == "first":
            return self.find_first(keyword)

        raise ValueError(f"지원하지 않는 앵커 탐색 방식입니다: {mode}")