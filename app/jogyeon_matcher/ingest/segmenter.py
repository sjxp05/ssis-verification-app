# 표 분리와 구조 지문
#
# 표 경계를 찾아 메모리 안의 TableRegion 으로만 다룬다. 파일로 쪼개 저장하면
# 재직렬화가 날짜·부동소수점·서식을 변형시켜 새 오류원을 만든다.
#
# 표마다 지문(헤더 순서열, 크기, 열 타입)을 만들어 작년과 비교한다. 열이 통째로
# 뒤바뀌면 라벨은 완벽히 일치하므로, 이것이 그 변화를 잡는 유일한 경로다.

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
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
    # 캐시 — frame.iat 는 셀당 파이썬 오버헤드가 커서 큰 표의 전 셀 순회가 수 초씩
    # 걸린다. 열 단위 numpy 배열로 한 번만 꺼내 둔다. dtype 을 유지해 iat 와 같은
    # 스칼라 타입이 나오게 한다. frame 은 적재 후 불변이므로 캐시가 낡을 일이 없다.
    _columns: list[np.ndarray] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _text_cells: list | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @property
    def table_id(self) -> str:
        return f"{self.sheet}#{self.index + 1}"

    @property
    def shape(self) -> tuple[int, int]:
        return (self.row1 - self.row0 + 1, self.col1 - self.col0 + 1)

    def _column_arrays(self) -> list[np.ndarray]:
        if self._columns is None:
            self._columns = [
                self.frame.iloc[self.row0 : self.row1 + 1, c].to_numpy()
                for c in range(self.col0, self.col1 + 1)
            ]
        return self._columns

    def cell(self, row: int, col: int):
        return self._column_arrays()[col][row]

    # 숫자만 든 셀은 라벨이 아니므로 제외한다.
    # '먼저 나온 셀이 대표' 규칙이 있으므로 순회는 원래대로 행 우선을 유지한다.
    def text_cells(self) -> list[tuple[str, CellLocation]]:
        if self._text_cells is not None:
            return self._text_cells
        text_columns = [
            (self.col0 + offset, column)
            for offset, column in enumerate(self._column_arrays())
            if column.dtype == object  # 순수 숫자 열에는 문자열 셀이 없다
        ]
        found = []
        for i in range(self.shape[0]):
            for c, column in text_columns:
                value = column[i]
                if not isinstance(value, str):
                    continue
                text = value.strip()
                if text and not _is_number(text):
                    found.append(
                        (text, CellLocation(self.sheet, self.row0 + i, c, self.table_id))
                    )
        self._text_cells = found
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
            was, now = other.shape, self.shape
            issues.append(f"표 크기 {was[0]}행 {was[1]}열 → {now[0]}행 {now[1]}열")
        if self.header_sequence != other.header_sequence:
            if sorted(self.header_sequence) == sorted(other.header_sequence):
                issues.append(
                    f"머리글 순서 바뀜: {' · '.join(other.header_sequence)}"
                    f" → {' · '.join(self.header_sequence)}"
                )
            else:
                issues.append("머리글 구성이 달라짐")
        if self.column_types != other.column_types:
            issues.append(self._column_type_summary(other))
        return issues

    def _column_type_summary(self, other: Fingerprint) -> str:
        # 열이 수십 개라 패턴을 통째로 찍으면 읽을 수 없다. 바뀐 열만 짚는다.
        korean = {"num": "숫자", "text": "문자", "mixed": "혼합", "empty": "빈칸"}
        changed = [
            f"{i + 1}번째 {korean.get(was, was)}→{korean.get(now, now)}"
            for i, (was, now) in enumerate(zip(other.column_types, self.column_types))
            if was != now
        ]
        if len(self.column_types) != len(other.column_types):
            note = f"열이 {len(other.column_types)}개에서 {len(self.column_types)}개로"
            return f"{note}, " + (", ".join(changed[:2]) if changed else "내용 종류도 달라짐")
        if not changed:
            return "열 내용 종류가 달라짐"

        head = ", ".join(changed[:3])
        if len(changed) > 3:
            head += f" 외 {len(changed) - 3}개 열"
        return f"열 내용 종류 바뀜: {head}"


def _is_number(text: str) -> bool:
    try:
        float(text.replace(",", "").replace("%", ""))
    except ValueError:
        return False
    return True


def _empty(value) -> bool:
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


# 시트 전체의 빈 셀 여부를 한 번에 계산한 bool 행렬. frame.iat 를 셀마다 부르는
# 대신 컬럼 단위 pandas 벡터 연산으로 만든다. 숫자 등 비문자 값은 문자열로
# 바뀌어도 빈 문자열이 될 수 없으므로 안전하다.
def _empty_mask(frame: pd.DataFrame) -> np.ndarray:
    if frame.empty:
        return np.zeros(frame.shape, dtype=bool)
    na = frame.isna().to_numpy()
    blank = frame.astype(str).apply(lambda c: c.str.strip().eq("")).to_numpy()
    return na | blank


# 빈 행·열로 갈라지는 덩어리를 표로 본다. 서식(테두리·병합)에 기대면 서식이
# 조금만 바뀌어도 탐지가 무너지므로, 가장 견고한 신호인 빈 줄을 쓴다.
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


# 실제 값이 있는 최소 사각형으로 줄인다. 행을 먼저 나누고 열을 나누므로,
# 나란히 붙은 표에서 한쪽이 짧으면 빈 영역까지 끌어안는다.
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
        values = [v for v in (region.cell(r, c) for r in range(region.shape[0]))
                  if not _empty(v)]
        if not values:
            types.append("empty")
            continue
        numeric = sum(1 for v in values if isinstance(v, (int, float)) or _is_number(str(v)))
        ratio = numeric / len(values)
        types.append("num" if ratio > 0.8 else "text" if ratio < 0.2 else "mixed")
    return Fingerprint(region.table_id, region.shape, headers, tuple(types))


def compare_sheets(
    baseline: dict, target: dict, required: tuple[str, ...] = ()
) -> list[StructuralAlert]:
    """작년 ↔ 올해 표 구조 비교.

    치명으로 올리는 것은 값 추출이 실제로 불가능해지는 경우뿐이다. 담당자가
    작업용으로 남긴 시트가 사라지거나 표가 더 쪼개지는 일은 정상 범위이고,
    그런 것까지 막으면 정상적인 조견표로도 진행이 안 된다.
    """
    alerts: list[StructuralAlert] = []
    for sheet, target_regions in target.items():
        base_regions = baseline.get(sheet)
        if base_regions is None:
            alerts.append(StructuralAlert("SHEET_ADDED", sheet, "작년에 없던 시트입니다."))
            continue

        if len(base_regions) != len(target_regions):
            alerts.append(StructuralAlert(
                "TABLE_COUNT_CHANGED", sheet,
                f"표가 {len(base_regions)}개에서 {len(target_regions)}개로 늘거나 줄어, "
                "이 시트는 값 비교를 건너뜁니다.",
            ))
            continue

        for base, tgt in zip(base_regions, target_regions):
            for issue in fingerprint(tgt).diff(fingerprint(base)):
                code = "HEADER_ORDER_CHANGED" if "순서" in issue else "TABLE_SHAPE_CHANGED"
                alerts.append(StructuralAlert(code, sheet, issue, tgt.table_id))

    for sheet in baseline:
        if sheet in target:
            continue
        if sheet in required:
            alerts.append(StructuralAlert(
                "SHEET_MISSING", sheet,
                "값을 읽어야 하는 시트인데 올해 파일에 없습니다.", fatal=True,
            ))
        else:
            alerts.append(StructuralAlert(
                "SHEET_REMOVED", sheet, "작년 파일에만 있던 시트 (값 추출에 쓰지 않음)",
            ))
    return alerts


# 앵커로 값을 특정할 수 있는지. 판정 기준을 추출기와 맞춘다.
#
#   _find_one 은 앵커를 부분문자열로 찾은 뒤 '서로 다른 행'에 걸쳐 있을 때만
#   실패한다. 같은 행에 여러 개면 첫 번째를 쓰고 정상 동작한다.
#
# 실제 조견표의 '기준중위소득70%이하 / 120%이하 / 180%이하 / 180%초과' 처럼
# 한 행에 나란한 밴드 헤더가 정상이므로, 셀 개수로 세면 멀쩡한 파일이 막힌다.
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
                alerts.append(StructuralAlert(
                    "ANCHOR_NOT_UNIQUE", region.sheet,
                    f"'{anchor}' 를 포함한 셀이 서로 다른 {len(rows)}개 행에 있습니다: "
                    f"{hits}. 어느 행에서 값을 읽을지 결정할 수 없어 값 추출이 실패합니다.",
                    region.table_id, fatal=True,
                ))
    return alerts
