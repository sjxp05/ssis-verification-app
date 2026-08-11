# 최근 사용한 파일 경로 저장소
#
# 조견표 라벨 대조는 작년 파일이 있어야 하므로, 마지막에 읽은 조견표 경로를 남긴다.
# 파일이 사라졌으면 기록이 있어도 None 을 돌려준다.

from __future__ import annotations

import json
from pathlib import Path

from utils.appdata import user_data_dir

STORE_NAME = "recent_files.json"


def _store() -> Path:
    return user_data_dir() / STORE_NAME


def _load() -> dict[str, str]:
    path = _store()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def get_recent_path(key: str) -> Path | None:
    raw = _load().get(key)
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None


def set_recent_path(key: str, path: Path) -> None:
    data = _load()
    data[key] = str(Path(path).resolve())
    try:
        _store().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # 경로 기억은 편의 기능이므로 실패해도 작업을 막지 않는다
