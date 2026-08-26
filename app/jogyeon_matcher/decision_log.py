# 로그 기록 (누가 언제 이 라벨 매핑으로 정했는지)

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import paths
from models.dto import Decision

LOG_NAME = "decisions.jsonl"


def log_path() -> Path:
    return paths.user_data_dir() / LOG_NAME


# 기존 내용에 한 줄 추가 ("a" 모드로 열기)
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
            continue  # 손상된 줄 하나가 전체 조회를 막지 않도록 함
    return entries
