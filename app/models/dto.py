from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
import pandas as pd
import numpy as np

ConstantValues = dict[str, float | int | None]


# 파일 업로드 시 {경로, 파일명, 크기} 형식으로 저장
@dataclass
class UploadedFile:
    path: Path
    name: str
    size: int

    @classmethod
    def from_path(cls, path: str | Path) -> UploadedFile:
        p = Path(path)
        size = p.stat().st_size if p.exists() else 0
        return cls(path=p, name=p.name, size=size)

    @property
    def size_text(self) -> str:
        s = self.size
        if s < 1024:
            return f"{s} B"
        if s < 1024**2:
            return f"{s / 1024:.1f} KB"
        return f"{s / 1024 ** 2:.1f} MB"


@dataclass(frozen=True)
class RequiredLabel:
    label: str
    sheet: str
    produces: str  # 이 문구로 찾을 값
    tables: tuple[str, ...]  # 해당 값이 있어야 만들 수 있는 표
    exact: bool = False  # True이면 셀 내용이 정확히 일치해야 함
    optional: bool = False


class Status(StrEnum):
    AUTO_PASS = "auto_pass"  # 검토 큐에 들어가지 않음
    NEEDS_REVIEW = "needs_review"  # top-3 제시, 사람이 선택
    UNMATCHED = "unmatched"  # 전 후보가 컷오프 미만, 직접 입력 유도


# 어느 경로로 판정했는가. 신뢰 수준이 다르므로 항상 명시한다.
class MatchPath(StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    RULE_PARSER = "rule_parser"  # auto_pass 가능한 유일한 퍼지 경로
    HYBRID = "hybrid"  # 유사도 기반. 단독으로 auto_pass 근거가 못 된다


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


@dataclass(frozen=True)
class CellLocation:
    sheet: str
    row: int
    column: int
    table_id: str = ""

    # 0-기반 인덱스를 사람이 읽는 엑셀 좌표로
    @property
    def a1(self) -> str:
        col, name = self.column + 1, ""
        while col:
            col, rem = divmod(col - 1, 26)
            name = chr(65 + rem) + name
        return f"{name}{self.row + 1}"


@dataclass
class LabelRef:
    raw: str
    normalized: str
    location: CellLocation | None = None


@dataclass
class Candidate:
    rank: int
    base_label: str
    final: float
    bm25: float
    embedding: float
    base_location: CellLocation | None = None
    margin_to_next: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass
class MatchItem:
    item_id: str
    input_label: LabelRef
    status: Status
    match_path: MatchPath
    candidates: list[Candidate] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    matched_label: str | None = None


@dataclass
class MissingValue:
    """올해 파일에서 못 읽는 값. 이게 있으면 그 단가표를 만들 수 없다."""

    label: str  # 작년에 쓰던 문구
    sheet: str
    produces: str  # 이 문구로 읽던 값
    tables: tuple[str, ...]  # 못 만들게 되는 표
    reason: str  # 못 찾음 / 여러 행에 흩어짐
    candidates: list[Candidate] = field(default_factory=list)
    baseline_location: CellLocation | None = None


# 표 개수·앵커 유일성·헤더 순서 이상
@dataclass
class StructuralAlert:
    code: str
    sheet: str
    detail: str
    table_id: str = ""
    fatal: bool = False


# 라벨 검증이 볼 수 없는 사각지대에서 나온 이상
@dataclass
class ValueAnomaly:
    code: str
    sheet: str
    detail: str


@dataclass
class Summary:
    total_labels: int = 0
    auto_passed: int = 0
    needs_review: int = 0
    unmatched: int = 0
    contested: int = 0


# 실행 1회 = 리포트 1개
@dataclass
class MatchReport:
    run_id: str
    baseline_file: str
    target_file: str
    summary: Summary = field(default_factory=Summary)
    structural_alerts: list[StructuralAlert] = field(default_factory=list)
    value_anomalies: list[ValueAnomaly] = field(default_factory=list)
    missing_values: list[MissingValue] = field(default_factory=list)
    items: list[MatchItem] = field(default_factory=list)

    @property
    def review_items(self) -> list[MatchItem]:
        return [i for i in self.items if i.status is not Status.AUTO_PASS]

    @property
    def changed_items(self) -> list[MatchItem]:
        """작년에 있던 문구가 올해 달라진 것."""
        return [i for i in self.review_items if "NEW_IN_TARGET" not in i.flags]

    @property
    def blocked_tables(self) -> list[str]:
        """지금 상태로는 만들 수 없는 표."""
        tables: list[str] = []
        for missing in self.missing_values:
            tables += [t for t in missing.tables if t not in tables]
        return tables

    @property
    def new_labels(self) -> list[MatchItem]:
        """올해 새로 생긴 문구. 값 추출에 쓰이지 않으면 그냥 두면 된다."""
        return [i for i in self.items if "NEW_IN_TARGET" in i.flags]

    @property
    def blocked(self) -> bool:
        return any(a.fatal for a in self.structural_alerts)


# 담당자의 선택 1건. 학습용이 아니라 감사 추적용 기록이다.
@dataclass
class Decision:
    run_id: str
    item_id: str
    action: str  # select_candidate | manual_input
    input_label: str
    selected_label: str | None = None
    selected_rank: int | None = None
    manual_input: str | None = None
    reviewed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


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

    def _is_number(self, text: str) -> bool:
        try:
            float(text.replace(",", "").replace("%", ""))
        except ValueError:
            return False
        return True
    
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
                if text and not self._is_number(text):
                    found.append(
                        (
                            text,
                            CellLocation(self.sheet, self.row0 + i, c, self.table_id),
                        )
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
            return f"{note}, " + (
                ", ".join(changed[:2]) if changed else "내용 종류도 달라짐"
            )
        if not changed:
            return "열 내용 종류가 달라짐"

        head = ", ".join(changed[:3])
        if len(changed) > 3:
            head += f" 외 {len(changed) - 3}개 열"
        return f"열 내용 종류 바뀜: {head}"