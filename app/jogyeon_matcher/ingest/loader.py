# 엑셀 적재 + 정제
#
# 읽는 즉시 모든 문자열 셀에서 비가시 문자를 걷어낸다. 눈에 보이지 않으면서
# 문자열 비교를 조용히 깨뜨리므로, 가장 앞에서 처리해야 뒤쪽 층이 전부 혜택을 받는다.
# 원본과 정제본이 다른 셀은 나중에 추적할 수 있게 감사 로그로 남긴다.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..matching.normalizer import sanitize


class IngestError(Exception):
    """적재 단계에서 진행 불가한 상황"""


@dataclass
class SanitizedCell:
    sheet: str
    row: int
    column: int
    original: str
    cleaned: str

    @property
    def removed_hex(self) -> str:
        removed = [c for c in self.original if c not in self.cleaned]
        return " ".join(f"U+{ord(c):04X}" for c in dict.fromkeys(removed))


@dataclass
class Workbook:
    path: Path
    sheets: dict[str, pd.DataFrame] = field(default_factory=dict)
    audit: list[SanitizedCell] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name


# 필수 시트가 없으면 즉시 중단한다. 조용히 진행하면 뒤에서 훨씬 알아보기
# 어려운 형태로 실패한다.
def load(path: str | Path, required_sheets: tuple[str, ...] = ()) -> Workbook:
    path = Path(path)
    if not path.exists():
        raise IngestError(f"파일이 없습니다: {path}")

    try:
        raw = pd.read_excel(path, sheet_name=None, engine="openpyxl", header=None)
    except Exception as error:
        raise IngestError(f"엑셀을 읽지 못했습니다: {error}") from None

    workbook = Workbook(path=path)
    for sheet_name, frame in raw.items():
        workbook.sheets[sheet_name] = _sanitize(frame, sheet_name, workbook.audit)

    missing = [s for s in required_sheets if s not in workbook.sheets]
    if missing:
        raise IngestError(
            f"필수 시트가 없습니다: {missing}\n"
            f"조치: 조견표 서식이 바뀌었는지 확인하세요. (있는 시트: {list(workbook.sheets)})"
        )
    return workbook


def _sanitize(frame: pd.DataFrame, sheet: str, audit: list[SanitizedCell]) -> pd.DataFrame:
    cleaned = frame.copy()
    for row in range(frame.shape[0]):
        for col in range(frame.shape[1]):
            value = frame.iat[row, col]
            if not isinstance(value, str):
                continue
            fixed = sanitize(value)
            if fixed != value:
                audit.append(SanitizedCell(sheet, row, col, value, fixed))
                cleaned.iat[row, col] = fixed
    return cleaned
