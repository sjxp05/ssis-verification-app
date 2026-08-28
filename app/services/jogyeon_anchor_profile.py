from __future__ import annotations

import json
from pathlib import Path

from jogyeon_matcher.paths import user_data_dir


SCHEMA_VERSION = 1
_PROFILE_DIR_NAME = "jogyeon_anchor_profiles"


def profile_path(year: int) -> Path:
    return user_data_dir() / _PROFILE_DIR_NAME / f"anchors_{year}.json"


def create_profile(year: int) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "year": year,
        "sheets": {},
        "values": {},
    }


# 해당 연도의 앵커 위치 JSON을 불러온다
def load_profile(year: int) -> dict | None:
    path = profile_path(year)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        profile = json.load(file)

    if profile.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"지원하지 않는 앵커 프로필 버전입니다: "
            f"{profile.get('schema_version')}"
        )

    if profile.get("year") != year:
        raise ValueError(
            f"앵커 프로필 연도가 일치하지 않습니다: "
            f"{profile.get('year')} != {year}"
        )

    return profile


# 해당 연도의 앵커 위치 JSON을 사용자 데이터 영역에 저장
def save_profile(year: int, profile: dict) -> Path:
    path = profile_path(year)
    path.parent.mkdir(parents=True, exist_ok=True)

    profile["schema_version"] = SCHEMA_VERSION
    profile["year"] = year
    profile.setdefault("sheets", {})
    profile.setdefault("values", {})

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            profile,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return path


# 시트와 앵커 ID에 해당하는 저장 위치를 조회
def get_anchor(
    profile: dict,
    sheet: str,
    anchor_id: str,
) -> dict | None:
    return (
        profile.get("sheets", {})
        .get(sheet, {})
        .get(anchor_id)
    )


# 확정된 앵커 문구와 위치를 시트별 JSON에 기록
def set_anchor(
    profile: dict,
    sheet: str,
    anchor_id: str,
    keyword: str,
    row: int,
    column: int,
) -> None:
    if row < 0 or column < 0:
        raise ValueError("앵커의 row와 column은 0 이상이어야 합니다.")

    sheets = profile.setdefault("sheets", {})
    sheet_anchors = sheets.setdefault(sheet, {})

    sheet_anchors[anchor_id] = {
        "keyword": keyword,
        "row": row,
        "column": column,
    }