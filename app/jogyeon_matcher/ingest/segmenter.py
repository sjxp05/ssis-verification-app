# 표 경계를 찾고 각 표의 구조 지문(헤더 순서열, 크기, 열 타입)을 만들어 작년과 비교

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from models.dto import StructuralAlert, TableRegion, Fingerprint
from ..label_rules import normalize

# 이보다 작은 덩어리는 표가 아니라 흩어진 주석으로 본다
MIN_CELLS = 2


def _is_number(text: str) -> bool:
    try:
        float(text.replace(",", "").replace("%", ""))
    except ValueError:
        return False
    return True


def _empty(value) -> bool:
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


# 시트 전체의 빈 셀 여부를 한 번에 계산한 bool 행렬
def _empty_mask(frame: pd.DataFrame) -> np.ndarray:
    if frame.empty:
        return np.zeros(frame.shape, dtype=bool)
    na = frame.isna().to_numpy()
    # frame.iat 를 셀마다 호출하지 않고 컬럼 단위 pandas 벡터 연산으로 만든다
    blank = frame.astype(str).apply(lambda c: c.str.strip().eq("")).to_numpy()
    return na | blank


# 빈 행 또는 열을 기준으로 표 구분
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
            filled = int((~mask[r0 : r1 + 1, c0 : c1 + 1]).sum())
            if filled >= MIN_CELLS:
                regions.append(TableRegion(sheet, r0, c0, r1, c1, frame))

    for i, region in enumerate(regions):
        region.index = i
    return regions


# 빈 줄로 구분되는 연속 구간의 (시작, 끝)
def _blocks(is_empty: list[bool]) -> list[tuple[int, int]]:
    spans, start = [], None
    for i, empty in enumerate(is_empty):
        if not empty and start is None:
            start = i
        elif empty and start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(is_empty) - 1))
    return spans


# 실제 값이 있는 최소 사각형으로 줄인다
def _trim(mask: np.ndarray, row0, col0, row1, col1):
    sub = mask[row0 : row1 + 1, col0 : col1 + 1]
    row_has_data = ~sub.all(axis=1)
    col_has_data = ~sub.all(axis=0)
    if not row_has_data.any() or not col_has_data.any():
        return None
    rows = row0 + np.where(row_has_data)[0]
    cols = col0 + np.where(col_has_data)[0]
    return int(rows[0]), int(cols[0]), int(rows[-1]), int(cols[-1])


def fingerprint(region: TableRegion) -> Fingerprint:
    headers = tuple(
        normalize(region.cell(0, c))
        for c in range(region.shape[1])
        if isinstance(region.cell(0, c), str) and region.cell(0, c).strip()
    )
    types = []
    for c in range(region.shape[1]):
        values = [
            v
            for v in (region.cell(r, c) for r in range(region.shape[0]))
            if not _empty(v)
        ]
        if not values:
            types.append("empty")
            continue
        numeric = sum(
            1 for v in values if isinstance(v, (int, float)) or _is_number(str(v))
        )
        ratio = numeric / len(values)
        types.append("num" if ratio > 0.8 else "text" if ratio < 0.2 else "mixed")
    return Fingerprint(region.table_id, region.shape, headers, tuple(types))


# 작년 ↔ 올해 표 구조 비교
def compare_sheets(
    baseline: dict, target: dict, required: tuple[str, ...] = ()
) -> list[StructuralAlert]:
    # 작년 시트이름과 완전히 동일하지 않아도 시트이름에 키워드가 포함되면 일단 매칭을 진행하도록 수정
    alerts: list[StructuralAlert] = []

    base_to_target = {}
    target_to_base = {}

    # 필수키워드가 포함된 작년-올해 시트끼리 매칭
    for req in required:
        b_sheet = next((s for s in baseline if req in s), None)
        t_sheet = next((s for s in target if req in s), None)

        if b_sheet and t_sheet:
            base_to_target[b_sheet] = t_sheet
            target_to_base[t_sheet] = b_sheet

        # 작년에는 키워드가 포함된 시트가 있었는데 올해는 없는 경우
        elif b_sheet and not t_sheet:
            alerts.append(
                StructuralAlert(
                    "SHEET_MISSING",
                    b_sheet,
                    f"값을 읽어야 하는 '{req}' 관련 시트가 올해 파일에 없습니다.",
                    fatal=True,
                )
            )

    # 필수 키워드가 없는 시트들은 이름이 완벽히 같으면 매핑
    for t_sheet in target:
        if t_sheet not in target_to_base:
            if t_sheet in baseline and t_sheet not in base_to_target:
                base_to_target[t_sheet] = t_sheet
                target_to_base[t_sheet] = t_sheet
            else:
                alerts.append(
                    StructuralAlert("SHEET_ADDED", t_sheet, "작년에 없던 시트입니다.")
                )

    for b_sheet, t_sheet in base_to_target.items():
        base_regions = baseline[b_sheet]
        target_regions = target[t_sheet]

        if len(base_regions) != len(target_regions):
            alerts.append(
                StructuralAlert(
                    "TABLE_COUNT_CHANGED",
                    t_sheet,
                    f"표가 {len(base_regions)}개에서 {len(target_regions)}개로 늘거나 줄어, "
                    "이 시트는 값 비교를 건너뜁니다.",
                )
            )
            continue

        for base, tgt in zip(base_regions, target_regions):
            for issue in fingerprint(tgt).diff(fingerprint(base)):
                code = (
                    "HEADER_ORDER_CHANGED" if "순서" in issue else "TABLE_SHAPE_CHANGED"
                )
                alerts.append(StructuralAlert(code, t_sheet, issue, tgt.table_id))

    for b_sheet in baseline:
        if b_sheet not in base_to_target:
            is_missing_req = any(req in b_sheet for req in required)
            if not is_missing_req:
                alerts.append(
                    StructuralAlert(
                        "SHEET_REMOVED",
                        b_sheet,
                        "작년 파일에만 있던 시트 (값 추출에 쓰지 않음)",
                    )
                )
    return alerts


# 앵커 키워드 중복 여부 판정 (기준은 추출기와 일치시킴)
def check_anchor_uniqueness(
    regions: list[TableRegion], anchors: tuple[str, ...]
) -> list[StructuralAlert]:
    alerts = []
    for region in regions:
        cells = [(normalize(t), loc) for t, loc in region.text_cells()]
        for anchor in anchors:
            key = normalize(anchor)
            rows = {loc.row for text, loc in cells if key in text}
            if len(rows) > 1:
                hits = sorted({text for text, _ in cells if key in text})
                alerts.append(
                    StructuralAlert(
                        "ANCHOR_NOT_UNIQUE",
                        region.sheet,
                        f"'{anchor}' 를 포함한 셀이 서로 다른 {len(rows)}개 행에 있습니다: "
                        f"{hits}. 어느 행에서 값을 읽을지 결정할 수 없어 값 추출이 실패합니다.",
                        region.table_id,
                        fatal=True,
                    )
                )
    return alerts
