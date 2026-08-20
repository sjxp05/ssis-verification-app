# 리소스 경로 해석
#
# 읽기 전용(번들 동봉)과 쓰기 가능(사용자 영역)을 나눠서 다룬다.
# PyInstaller 분기를 여기 한 곳에 가둬서 --onedir <-> --onefile 전환 시
# 이 파일만 손보면 되게 한다.

from __future__ import annotations

import sys
from pathlib import Path

from utils.appdata import user_data_dir

__all__ = ["bundle_dir", "model_dir", "user_data_dir"]


def bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "jogyeon_matcher"
    return Path(__file__).resolve().parent


def model_dir() -> Path:
    return bundle_dir() / "resources" / "model"
