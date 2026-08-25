# 조견표 적재, 표 구조 분석, 값 이상 검증

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from models.dto import (
    Fingerprint,
    SanitizedCell,
    StructuralAlert,
    TableRegion,
    ValueAnomaly,
    Workbook,
)

from utils import xlsx_scan
from .label_rules import normalize, sanitize


MIN_CELLS = 2
UNIT_SHIFT_RATIO = 10


class IngestError(Exception):
    """적재 단계에서 진행 불가한 상황"""


# 엑셀 적재와 문자열 정제
def load(path: str | Path, required_sheets: tuple[str, ...] = ()) -> Workbook:
    path = Path(path)

    if not path.exists():
        raise IngestError(f"파일이 없습니다: {path}")

    try:
        # 서식만 남은 후행 행은 읽지 않도록 실제 데이터 마지막 행을 먼저 탐지
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
        workbook.sheets[sheet_name] = _sanitize(
            trimmed,
            sheet_name,
            workbook.audit,
        )

    # [인정조사, 산정특례, 종합조사] 시트이름 완전일치 탐색에서 필수 시트명 키워드를 포함하면 동일 시트로 판정
    missing = []

    for required in required_sheets:
        if not any(required in actual for actual in workbook.sheets):
            missing.append(required)

    if missing:
        raise IngestError(
            f"필수 시트가 없습니다: {missing}\n"
            f"조치: 조견표 서식이 바뀌었는지 확인하세요. "
            f"(있는 시트: {list(workbook.sheets)})"
        )

    return workbook


# openpyxl 이 보고하는 시트 크기에서 실제 값이 있는 마지막 셀까지만 남기고 빈 영역은 잘라내기
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


# 문자열 컬럼 단위로 정제하고 변경된 셀은 audit에 기록
def _sanitize(
    frame: pd.DataFrame,
    sheet: str,
    audit: list[SanitizedCell],
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
                SanitizedCell(
                    sheet,
                    int(row),
                    int(col),
                    original[row],
                    fixed[row],
                )
            )

        cleaned.loc[is_str, col] = fixed

    return cleaned


# 표 경계와 구조 지문
def _is_number(text: str) -> bool:
    try:
        float(text.replace(",", "").replace("%", ""))
    except ValueError:
        return False

    return True


def _empty(value) -> bool:
    return pd.isna(value) or (
        isinstance(value, str)
        and not value.strip()
    )


def _empty_mask(frame: pd.DataFrame) -> np.ndarray:
    if frame.empty:
        return np.zeros(frame.shape, dtype=bool)

    na = frame.isna().to_numpy()
    blank = (
        frame.astype(str)
        .apply(lambda column: column.str.strip().eq(""))
        .to_numpy()
    )

    return na | blank


# 빈 행과 열을 기준으로 TableRegion 분리
def find_tables(sheet: str, frame: pd.DataFrame) -> list[TableRegion]:
    regions: list[TableRegion] = []
    mask = _empty_mask(frame)
    row_empty = mask.all(axis=1)

    for row0, row1 in _blocks(row_empty.tolist()):
        col_empty = mask[row0 : row1 + 1].all(axis=0)

        for col0, col1 in _blocks(col_empty.tolist()):
            box = _trim(mask, row0, col0, row1, col1)

            if box is None:
                continue

            r0, c0, r1, c1 = box
            filled = int(
                (~mask[r0 : r1 + 1, c0 : c1 + 1]).sum()
            )

            if filled >= MIN_CELLS:
                regions.append(
                    TableRegion(
                        sheet,
                        r0,
                        c0,
                        r1,
                        c1,
                        frame,
                    )
                )

    for index, region in enumerate(regions):
        region.index = index

    return regions


def _blocks(is_empty: list[bool]) -> list[tuple[int, int]]:
    spans = []
    start = None

    for index, empty in enumerate(is_empty):
        if not empty and start is None:
            start = index

        elif empty and start is not None:
            spans.append((start, index - 1))
            start = None

    if start is not None:
        spans.append((start, len(is_empty) - 1))

    return spans


def _trim(
    mask: np.ndarray,
    row0,
    col0,
    row1,
    col1,
):
    sub = mask[row0 : row1 + 1, col0 : col1 + 1]
    row_has_data = ~sub.all(axis=1)
    col_has_data = ~sub.all(axis=0)

    if not row_has_data.any() or not col_has_data.any():
        return None

    rows = row0 + np.where(row_has_data)[0]
    cols = col0 + np.where(col_has_data)[0]

    return (
        int(rows[0]),
        int(cols[0]),
        int(rows[-1]),
        int(cols[-1]),
    )


def fingerprint(region: TableRegion) -> Fingerprint:
    headers = tuple(
        normalize(region.cell(0, col))
        for col in range(region.shape[1])
        if isinstance(region.cell(0, col), str)
        and region.cell(0, col).strip()
    )

    types = []

    for col in range(region.shape[1]):
        values = [
            value
            for value in (
                region.cell(row, col)
                for row in range(region.shape[0])
            )
            if not _empty(value)
        ]

        if not values:
            types.append("empty")
            continue

        numeric = sum(
            1
            for value in values
            if isinstance(value, (int, float))
            or _is_number(str(value))
        )

        ratio = numeric / len(values)

        types.append(
            "num"
            if ratio > 0.8
            else "text"
            if ratio < 0.2
            else "mixed"
        )

    return Fingerprint(
        region.table_id,
        region.shape,
        headers,
        tuple(types),
    )


# 작년과 올해의 시트와 TableRegion 구조 비교
def compare_sheets(
    baseline: dict,
    target: dict,
    required: tuple[str, ...] = (),
) -> list[StructuralAlert]:
    alerts: list[StructuralAlert] = []

    base_to_target = {}
    target_to_base = {}

    # 필수 시트는 시트명 키워드로 작년과 올해를 연결
    for required_name in required:
        base_sheet = next(
            (
                sheet
                for sheet in baseline
                if required_name in sheet
            ),
            None,
        )
        target_sheet = next(
            (
                sheet
                for sheet in target
                if required_name in sheet
            ),
            None,
        )

        if base_sheet and target_sheet:
            base_to_target[base_sheet] = target_sheet
            target_to_base[target_sheet] = base_sheet

        elif base_sheet and not target_sheet:
            alerts.append(
                StructuralAlert(
                    "SHEET_MISSING",
                    base_sheet,
                    f"값을 읽어야 하는 '{required_name}' 관련 시트가 "
                    "올해 파일에 없습니다.",
                    fatal=True,
                )
            )

    # 필수 시트 외에는 동일한 시트명만 연결
    for target_sheet in target:
        if target_sheet in target_to_base:
            continue

        if (
            target_sheet in baseline
            and target_sheet not in base_to_target
        ):
            base_to_target[target_sheet] = target_sheet
            target_to_base[target_sheet] = target_sheet

        else:
            alerts.append(
                StructuralAlert(
                    "SHEET_ADDED",
                    target_sheet,
                    "작년에 없던 시트입니다.",
                )
            )

    for base_sheet, target_sheet in base_to_target.items():
        base_regions = baseline[base_sheet]
        target_regions = target[target_sheet]

        if len(base_regions) != len(target_regions):
            alerts.append(
                StructuralAlert(
                    "TABLE_COUNT_CHANGED",
                    target_sheet,
                    f"표가 {len(base_regions)}개에서 "
                    f"{len(target_regions)}개로 늘거나 줄어, "
                    "이 시트는 값 비교를 건너뜁니다.",
                )
            )
            continue

        for base, target_region in zip(
            base_regions,
            target_regions,
        ):
            for issue in fingerprint(target_region).diff(
                fingerprint(base)
            ):
                code = (
                    "HEADER_ORDER_CHANGED"
                    if "순서" in issue
                    else "TABLE_SHAPE_CHANGED"
                )

                alerts.append(
                    StructuralAlert(
                        code,
                        target_sheet,
                        issue,
                        target_region.table_id,
                    )
                )

    for base_sheet in baseline:
        if base_sheet in base_to_target:
            continue

        is_missing_required = any(
            required_name in base_sheet
            for required_name in required
        )

        if not is_missing_required:
            alerts.append(
                StructuralAlert(
                    "SHEET_REMOVED",
                    base_sheet,
                    "작년 파일에만 있던 시트 (값 추출에 쓰지 않음)",
                )
            )

    return alerts


# 추출에 사용하는 앵커가 여러 행에 존재하면 진행 차단
def check_anchor_uniqueness(
    regions: list[TableRegion],
    anchors: tuple[str, ...],
) -> list[StructuralAlert]:
    alerts = []

    for region in regions:
        cells = [
            (normalize(text), location)
            for text, location in region.text_cells()
        ]

        for anchor in anchors:
            key = normalize(anchor)

            rows = {
                location.row
                for text, location in cells
                if key in text
            }

            if len(rows) > 1:
                hits = sorted(
                    {
                        text
                        for text, _ in cells
                        if key in text
                    }
                )

                alerts.append(
                    StructuralAlert(
                        "ANCHOR_NOT_UNIQUE",
                        region.sheet,
                        f"'{anchor}' 를 포함한 셀이 서로 다른 "
                        f"{len(rows)}개 행에 있습니다: {hits}. "
                        "어느 행에서 값을 읽을지 결정할 수 없어 "
                        "값 추출이 실패합니다.",
                        region.table_id,
                        fatal=True,
                    )
                )

    return alerts


# TableRegion의 값 변화 검사
def compare_regions(
    baseline: dict,
    target: dict,
) -> list[ValueAnomaly]:
    anomalies: list[ValueAnomaly] = []

    for sheet, target_regions in target.items():
        base_regions = baseline.get(sheet)

        if (
            not base_regions
            or len(base_regions) != len(target_regions)
        ):
            continue

        for base, target_region in zip(
            base_regions,
            target_regions,
        ):
            anomalies += _compare_columns(
                sheet,
                base,
                target_region,
            )

    return anomalies


def _compare_columns(
    sheet: str,
    base,
    target,
) -> list[ValueAnomaly]:
    anomalies = []

    for col in range(
        min(base.shape[1], target.shape[1])
    ):
        base_values = _numeric_column(base, col)
        target_values = _numeric_column(target, col)

        if (
            len(base_values) < 3
            or len(target_values) < 3
        ):
            continue

        header = (
            _column_header(target, col)
            or f"{col + 1}번째 열"
        )

        direction = _direction(base_values)

        if (
            direction
            and _direction(target_values) != direction
        ):
            word = "감소" if direction < 0 else "증가"

            anomalies.append(
                ValueAnomaly(
                    "MONOTONICITY_BROKEN",
                    sheet,
                    f"'{header}' 열은 작년에 계속 {word}했는데 "
                    "올해는 그렇지 않습니다. "
                    "행 순서나 값 배치가 바뀌었을 수 있습니다.",
                )
            )

        base_median = _median(base_values)

        ratio = (
            _median(target_values) / base_median
            if base_median
            else 0
        )

        if ratio and (
            ratio > UNIT_SHIFT_RATIO
            or ratio < 1 / UNIT_SHIFT_RATIO
        ):
            anomalies.append(
                ValueAnomaly(
                    "UNIT_SHIFT_SUSPECTED",
                    sheet,
                    f"'{header}' 열 값이 작년의 "
                    f"{ratio:.0f}배입니다. "
                    "단위가 바뀌었을 수 있습니다"
                    "(예: 시간 → 분).",
                )
            )

    return anomalies


def _numeric_column(
    region,
    col: int,
) -> list[float]:
    values = []

    for row in range(region.shape[0]):
        value = region.cell(row, col)

        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            values.append(float(value))

    return values


def _column_header(
    region,
    col: int,
) -> str:
    value = region.cell(0, col)

    return (
        value.strip()
        if isinstance(value, str)
        else ""
    )


# 전 구간 단조 감소는 -1, 증가는 1, 그 외에는 0
def _direction(values: list[float]) -> int:
    if all(
        left > right
        for left, right in itertools.pairwise(values)
    ):
        return -1

    if all(
        left < right
        for left, right in itertools.pairwise(values)
    ):
        return 1

    return 0


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2

    return (
        ordered[mid]
        if len(ordered) % 2
        else (ordered[mid - 1] + ordered[mid]) / 2
    )