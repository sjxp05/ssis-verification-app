# 엑셀 적재 + 정제
#
# 읽는 즉시 모든 문자열 셀에서 비가시 문자를 걷어낸다. 눈에 보이지 않으면서
# 문자열 비교를 조용히 깨뜨리므로, 가장 앞에서 처리해야 뒤쪽 층이 전부 혜택을 받는다.
# 원본과 정제본이 다른 셀은 나중에 추적할 수 있게 감사 로그로 남긴다.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from models.dto import SanitizedCell, Workbook

from . import xlsx_scan
from ..matching.normalizer import sanitize


class IngestError(Exception):
    """적재 단계에서 진행 불가한 상황"""


# 필수 시트가 없으면 즉시 중단한다. 조용히 진행하면 뒤에서 훨씬 알아보기
# 어려운 형태로 실패한다.
def load(path: str | Path, required_sheets: tuple[str, ...] = ()) -> Workbook:
    path = Path(path)
    if not path.exists():
        raise IngestError(f"파일이 없습니다: {path}")

    try:
        # 값이 있는 마지막 행을 미리 알아내 nrows 로 읽기를 끊는다. 서식만 남은
        # 행이 시트 끝까지 부풀어 있는 파일(실측 시트당 ~10초)을 방어한다.
        # 탐지에 실패한 시트는 nrows 없이 기존대로 전체를 읽는다.
        caps = xlsx_scan.true_row_counts(path)
        raw = {}
        with pd.ExcelFile(path, engine="openpyxl") as book:
            for sheet_name in book.sheet_names:
                cap = caps.get(sheet_name)
                raw[sheet_name] = book.parse(
                    sheet_name,
                    header=None,
                    **({"nrows": cap} if cap else {}),
                )
    except Exception as error:
        raise IngestError(f"엑셀을 읽지 못했습니다: {error}") from None

    workbook = Workbook(path=path)
    for sheet_name, frame in raw.items():
        trimmed = _trim_to_used_range(frame)
        workbook.sheets[sheet_name] = _sanitize(trimmed, sheet_name, workbook.audit)

    # [인정조사, 산정특례, 종합조사] 시트이름 완전일치 탐색에서 키워드 포함 탐색으로 변경
    # missing = [s for s in required_sheets if s not in workbook.sheets]
    missing = []
    for req in required_sheets:
        if not any(req in actual for actual in workbook.sheets):
            missing.append(req)

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
    return frame.loc[:last_row, :last_col]


# 셀 단위 파이썬 루프 대신 문자열 컬럼 단위로 정제한다. object dtype이 아닌
# 컬럼(순수 숫자 컬럼 등)은 애초에 문자열 셀을 담을 수 없으므로 건너뛴다.
def _sanitize(
    frame: pd.DataFrame, sheet: str, audit: list[SanitizedCell]
) -> pd.DataFrame:
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
            audit.append(
                SanitizedCell(sheet, int(row), int(col), original[row], fixed[row])
            )
        cleaned.loc[is_str, col] = fixed
    return cleaned
