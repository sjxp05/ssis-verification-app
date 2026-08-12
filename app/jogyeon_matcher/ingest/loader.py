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
        trimmed = _trim_to_used_range(frame)
        workbook.sheets[sheet_name] = _sanitize(trimmed, sheet_name, workbook.audit)

    missing = [s for s in required_sheets if s not in workbook.sheets]
    if missing:
        raise IngestError(
            f"필수 시트가 없습니다: {missing}\n"
            f"조치: 조견표 서식이 바뀌었는지 확인하세요. (있는 시트: {list(workbook.sheets)})"
        )
    return workbook


# openpyxl이 보고하는 시트 크기에는 값 없이 서식만 남은 행/열까지 포함될 수
# 있다. 실제 값이 있는 마지막 행/열까지만 남기고 뒤쪽 빈 영역은 잘라낸다.
def _trim_to_used_range(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    has_value = frame.notna()
    rows_with_data = has_value.any(axis=1)
    cols_with_data = has_value.any(axis=0)
    if not rows_with_data.any() or not cols_with_data.any():
        return frame.iloc[0:0, 0:0]
    last_row = rows_with_data[rows_with_data].index[-1]
    last_col = cols_with_data[cols_with_data].index[-1]
    return frame.loc[: last_row, : last_col]


# 셀 단위 파이썬 루프 대신 문자열 컬럼 단위로 정제한다. object dtype이 아닌
# 컬럼(순수 숫자 컬럼 등)은 애초에 문자열 셀을 담을 수 없으므로 건너뛴다.
def _sanitize(frame: pd.DataFrame, sheet: str, audit: list[SanitizedCell]) -> pd.DataFrame:
    cleaned = frame.copy()
    for col in cleaned.columns:
        series = cleaned[col]
        if series.dtype != object:
            continue
        is_str = series.map(type) == str
        if not is_str.any():
            continue
        original = series[is_str]
        fixed = original.map(sanitize)
        changed = fixed != original
        if not changed.any():
            continue
        for row in changed[changed].index:
            audit.append(SanitizedCell(sheet, int(row), int(col), original[row], fixed[row]))
        cleaned.loc[is_str, col] = fixed
    return cleaned
