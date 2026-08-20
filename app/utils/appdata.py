# 앱이 쓰기 가능한 사용자 데이터 폴더
#
# exe 는 Program Files 아래 설치되고 그곳은 쓰기가 금지된다.
# 설정·로그처럼 저장이 필요한 것은 모두 여기로 보낸다.

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ssis-verification"


def user_data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
