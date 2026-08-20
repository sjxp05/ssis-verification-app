# 엔진과 UI 사이의 데이터 계약
#
# 점수 분해와 플래그를 항상 실어 보낸다. 담당자가 top-3 에서 고르려면 "왜 이게
# 1순위인지"가 화면에 있어야 하므로 장식이 아니라 요구사항이다.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Status(StrEnum):
    AUTO_PASS = "auto_pass"        # 검토 큐에 들어가지 않음
    NEEDS_REVIEW = "needs_review"  # top-3 제시, 사람이 선택
    UNMATCHED = "unmatched"        # 전 후보가 컷오프 미만, 직접 입력 유도


# 어느 경로로 판정했는가. 신뢰 수준이 다르므로 항상 명시한다.
class MatchPath(StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    RULE_PARSER = "rule_parser"  # auto_pass 가능한 유일한 퍼지 경로
    HYBRID = "hybrid"            # 유사도 기반. 단독으로 auto_pass 근거가 못 된다


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
