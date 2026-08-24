from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
import pandas as pd

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
