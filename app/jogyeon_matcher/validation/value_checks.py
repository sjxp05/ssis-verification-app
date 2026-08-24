# 값 수준 검증: 작년 표에서 불변식을 유도, 라벨 검증에서 놓치는 부분 검사

from __future__ import annotations

import itertools

from models.dto import ValueAnomaly

# 이 배수를 넘으면 연도별 인상이 아닌 단위 변경으로 간주
UNIT_SHIFT_RATIO = 10


def compare_regions(baseline: dict, target: dict) -> list[ValueAnomaly]:
    anomalies: list[ValueAnomaly] = []
    for sheet, target_regions in target.items():
        base_regions = baseline.get(sheet)
        if not base_regions or len(base_regions) != len(target_regions):
            continue
        for base, tgt in zip(base_regions, target_regions):
            anomalies += _compare_columns(sheet, base, tgt)
    return anomalies


def _compare_columns(sheet: str, base, target) -> list[ValueAnomaly]:
    out = []
    for col in range(min(base.shape[1], target.shape[1])):
        base_values = _numeric_column(base, col)
        target_values = _numeric_column(target, col)
        if len(base_values) < 3 or len(target_values) < 3:
            continue
        header = _column_header(target, col) or f"{col + 1}번째 열"

        direction = _direction(base_values)
        if direction and _direction(target_values) != direction:
            word = "감소" if direction < 0 else "증가"
            out.append(
                ValueAnomaly(
                    "MONOTONICITY_BROKEN",
                    sheet,
                    f"'{header}' 열은 작년에 계속 {word}했는데 올해는 그렇지 않습니다. "
                    "행 순서나 값 배치가 바뀌었을 수 있습니다.",
                )
            )

        base_median = _median(base_values)
        ratio = _median(target_values) / base_median if base_median else 0
        if ratio and (ratio > UNIT_SHIFT_RATIO or ratio < 1 / UNIT_SHIFT_RATIO):
            out.append(
                ValueAnomaly(
                    "UNIT_SHIFT_SUSPECTED",
                    sheet,
                    f"'{header}' 열 값이 작년의 {ratio:.0f}배입니다. "
                    "단위가 바뀌었을 수 있습니다(예: 시간 → 분).",
                )
            )
    return out


def _numeric_column(region, col: int) -> list[float]:
    values = []
    for row in range(region.shape[0]):
        value = region.cell(row, col)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def _column_header(region, col: int) -> str:
    value = region.cell(0, col)
    return value.strip() if isinstance(value, str) else ""


# 전 구간 단조면 -1(감소)/+1(증가), 아니면 0
def _direction(values: list[float]) -> int:
    if all(a > b for a, b in itertools.pairwise(values)):
        return -1
    if all(a < b for a, b in itertools.pairwise(values)):
        return 1
    return 0


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
