# 표 분리와 구조 지문
#
# 표 경계를 찾아 메모리 안의 TableRegion 으로만 다룬다. 파일로 쪼개 저장하면
# 재직렬화가 날짜·부동소수점·서식을 변형시켜 새 오류원을 만든다.
#
# 표마다 지문(헤더 순서열, 크기, 열 타입)을 만들어 작년과 비교한다. 열이 통째로
# 뒤바뀌면 라벨은 완벽히 일치하므로, 이것이 그 변화를 잡는 유일한 경로다.

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..contracts.schemas import CellLocation, StructuralAlert
from ..matching.normalizer import normalize

# 이보다 작은 덩어리는 표가 아니라 흩어진 주석으로 본다
MIN_CELLS = 2


@dataclass
class TableRegion:
    sheet: str
    row0: int
    col0: int
    row1: int
    col1: int
    frame: pd.DataFrame
    index: int = 0

    @property
    def table_id(self) -> str:
        return f"{self.sheet}#{self.index + 1}"

    @property
    def shape(self) -> tuple[int, int]:
        return (self.row1 - self.row0 + 1, self.col1 - self.col0 + 1)

    def cell(self, row: int, col: int):
        return self.frame.iat[self.row0 + row, self.col0 + col]

    # 숫자만 든 셀은 라벨이 아니므로 제외한다
    def text_cells(self) -> list[tuple[str, CellLocation]]:
        found = []
        for r in range(self.row0, self.row1 + 1):
            for c in range(self.col0, self.col1 + 1):
                value = self.frame.iat[r, c]
                if not isinstance(value, str):
                    continue
                text = value.strip()
                if text and not _is_number(text):
                    found.append((text, CellLocation(self.sheet, r, c, self.table_id)))
        return found


# 표의 내용이 아니라 배치를 요약한 값
@dataclass
class Fingerprint:
    table_id: str
    shape: tuple[int, int]
    header_sequence: tuple[str, ...]
    column_types: tuple[str, ...]

    def diff(self, other: Fingerprint) -> list[str]:
        issues = []
        if self.shape != other.shape:
            issues.append(f"크기 {other.shape} -> {self.shape}")
        if self.header_sequence != other.header_sequence:
            if sorted(self.header_sequence) == sorted(other.header_sequence):
                issues.append(
                    f"헤더 순서 변경: {list(other.header_sequence)} -> {list(self.header_sequence)}"
                )
            else:
                issues.append("헤더 구성 변경")
        if self.column_types != other.column_types:
            issues.append(f"열 타입 패턴 {other.column_types} -> {self.column_types}")
        return issues


def _is_number(text: str) -> bool:
    try:
        float(text.replace(",", "").replace("%", ""))
    except ValueError:
        return False
    return True


def _empty(value) -> bool:
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


# 빈 행·열로 갈라지는 덩어리를 표로 본다. 서식(테두리·병합)에 기대면 서식이
# 조금만 바뀌어도 탐지가 무너지므로, 가장 견고한 신호인 빈 줄을 쓴다.
def find_tables(sheet: str, frame: pd.DataFrame) -> list[TableRegion]:
    regions: list[TableRegion] = []
    row_empty = [
        all(_empty(frame.iat[r, c]) for c in range(frame.shape[1]))
        for r in range(frame.shape[0])
    ]
    for row0, row1 in _blocks(row_empty):
        col_empty = [
            all(_empty(frame.iat[r, c]) for r in range(row0, row1 + 1))
            for c in range(frame.shape[1])
        ]
        for col0, col1 in _blocks(col_empty):
            box = _trim(frame, row0, col0, row1, col1)
            if box is None:
                continue
            r0, c0, r1, c1 = box
            filled = sum(
                not _empty(frame.iat[r, c])
                for r in range(r0, r1 + 1)
                for c in range(c0, c1 + 1)
            )
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


# 실제 값이 있는 최소 사각형으로 줄인다. 행을 먼저 나누고 열을 나누므로,
# 나란히 붙은 표에서 한쪽이 짧으면 빈 영역까지 끌어안는다.
def _trim(frame, row0, col0, row1, col1):
    rows = [r for r in range(row0, row1 + 1)
            if any(not _empty(frame.iat[r, c]) for c in range(col0, col1 + 1))]
    cols = [c for c in range(col0, col1 + 1)
            if any(not _empty(frame.iat[r, c]) for r in range(row0, row1 + 1))]
    if not rows or not cols:
        return None
    return rows[0], cols[0], rows[-1], cols[-1]


def fingerprint(region: TableRegion) -> Fingerprint:
    headers = tuple(
        normalize(region.cell(0, c))
        for c in range(region.shape[1])
        if isinstance(region.cell(0, c), str) and region.cell(0, c).strip()
    )
    types = []
    for c in range(region.shape[1]):
        values = [v for v in (region.cell(r, c) for r in range(region.shape[0]))
                  if not _empty(v)]
        if not values:
            types.append("empty")
            continue
        numeric = sum(1 for v in values if isinstance(v, (int, float)) or _is_number(str(v)))
        ratio = numeric / len(values)
        types.append("num" if ratio > 0.8 else "text" if ratio < 0.2 else "mixed")
    return Fingerprint(region.table_id, region.shape, headers, tuple(types))


def compare_sheets(baseline: dict, target: dict) -> list[StructuralAlert]:
    alerts: list[StructuralAlert] = []
    for sheet, target_regions in target.items():
        base_regions = baseline.get(sheet)
        if base_regions is None:
            alerts.append(StructuralAlert("SHEET_ADDED", sheet, "작년에 없던 시트입니다."))
            continue

        if len(base_regions) != len(target_regions):
            alerts.append(StructuralAlert(
                "TABLE_COUNT_CHANGED", sheet,
                f"표 개수가 {len(base_regions)}개에서 {len(target_regions)}개로 바뀌었습니다. "
                "표 대응이 어긋날 수 있으므로 값 검증 결과를 반드시 확인하세요.",
                fatal=True,
            ))
            continue

        for base, tgt in zip(base_regions, target_regions):
            for issue in fingerprint(tgt).diff(fingerprint(base)):
                code = "HEADER_ORDER_CHANGED" if "순서" in issue else "TABLE_SHAPE_CHANGED"
                alerts.append(StructuralAlert(code, sheet, issue, tgt.table_id))

    for sheet in baseline:
        if sheet not in target:
            alerts.append(StructuralAlert(
                "SHEET_MISSING", sheet, "작년에 있던 시트가 없습니다.", fatal=True
            ))
    return alerts


# 앵커가 표 스코프 안에서 유일한지. 추출기가 부분문자열로 찾으므로 검사도 같은
# 기준이어야 한다. 완전일치로만 세면 '(본인부담금 상한액)'과 '추가급여 상한액'이
# 공존해도 통과하고, 추출기는 둘 중 아무거나 집는다.
def check_anchor_uniqueness(
    regions: list[TableRegion], anchors: tuple[str, ...]
) -> list[StructuralAlert]:
    alerts = []
    for region in regions:
        texts = [normalize(t) for t, _ in region.text_cells()]
        for anchor in anchors:
            hits = [t for t in texts if normalize(anchor) in t]
            if len(hits) > 1:
                alerts.append(StructuralAlert(
                    "ANCHOR_NOT_UNIQUE", region.sheet,
                    f"'{anchor}' 를 포함한 셀이 표 안에 {len(hits)}개 있습니다: {hits}. "
                    "어느 셀에서 값을 읽을지 결정할 수 없습니다.",
                    region.table_id, fatal=True,
                ))
    return alerts
