# 담당자 결정 기록
#
# 학습용이 아니라 감사 추적용이다. 조견표 작업은 연 1회, 검토 항목은 많아야
# 몇 건이라 통계적 학습에 필요한 양이 모이지 않는다. 게다가 기준표가 매년
# 갱신되므로 한 번 바뀐 라벨은 이듬해 기준에 흡수되어 기록의 유효 수명이 없다.
#
# 그럼에도 남기는 이유는 공공 업무라서다. "이 값이 왜 이렇게 정해졌는가",
# "누가 언제 이 매핑을 승인했는가"에 답할 수 있어야 한다.

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .. import paths
from ..contracts.schemas import Decision

LOG_NAME = "decisions.jsonl"


def log_path() -> Path:
    return paths.user_data_dir() / LOG_NAME


# 한 줄 덧붙인다. 기존 내용을 다시 쓰지 않으므로 손상 위험이 낮다.
def record(decision: Decision) -> None:
    if not decision.reviewed_at:
        decision.reviewed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with log_path().open("a", encoding="utf-8") as file:
        file.write(json.dumps(decision.to_dict(), ensure_ascii=False) + "\n")


def read_all() -> list[dict]:
    path = log_path()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 손상된 줄 하나가 전체 조회를 막지 않게 한다
    return entries
