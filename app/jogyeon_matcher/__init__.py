# 조견표 라벨 매칭 엔진
#
# 작년 조견표를 기준으로 올해 조견표의 라벨 대응을 찾는다. 문구가 바뀌면 값
# 추출이 조용히 어긋나므로, 그 변화를 사람이 확인할 수 있게 만든다.
#
#     from jogyeon_matcher import match_workbooks
#     report = match_workbooks("조견표_2026.xlsx", "조견표_2027.xlsx")

from .contracts.schemas import (
    Candidate,
    Decision,
    MatchItem,
    MatchPath,
    MatchReport,
    Status,
)
from .engine import match_workbooks
from .matching.hybrid import HybridConfig

__all__ = [
    "match_workbooks",
    "MatchReport",
    "MatchItem",
    "Candidate",
    "Decision",
    "Status",
    "MatchPath",
    "HybridConfig",
]
