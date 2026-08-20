# 연도별로 사용한 파일 경로 캐싱 함수

from __future__ import annotations
import json
from pathlib import Path

# 캐시 데이터를 저장할 파일
CACHE_FILE = Path(".recent_paths_cache.json")


# 저장소에서 key 에 해당하는 경로를 읽어 반환
def get_recent_path(year: int, key: str) -> Path | None:
    # 기록이 없거나 파일이 더 이상 존재하지 않으면 None
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        year_str = str(year)

        year_data = data.get(year_str)
        if not year_data:
            return None

        path_str = year_data.get(key)
        if not path_str:
            return None

        path = Path(path_str)
        if path.exists():
            return path
        return None

    except Exception as e:
        print(f"캐시 파일 읽기 실패: {e}")
        return None


# key: path 를 저장소에 기록 (마지막 값으로 덮어쓰기)
def set_recent_path(year: int, key: str, path: Path) -> None:
    data = {}

    # 기존 데이터가 있으면 먼저 읽어옴
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass  # 파일이 깨져있으면 무시하고 덮어씀

    year_str = str(year)

    # 값 업데이트 (Path 객체는 문자열로 변환해서 저장)
    data.setdefault(year_str, {})
    data[year_str][key] = str(path)

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"캐시 파일 저장 실패: {e}")


# 전년도 조견표 경로가 캐시에 있는지 찾아서 가장 최근 것을 반환
# TODO: 기존 Path 하나 -> 있는 파일들 모두 dict로 반환하기
def search_jogyeon_history(year: int, key: str = "jogyeon") -> Path | None:
    # 기록이 없거나 파일이 더 이상 존재하지 않으면 None
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for y in sorted(data.keys(), reverse=True):
            if not y.isdigit() or int(y) >= year:
                continue
            path_str = data[y].get(key)
            if path_str is not None:
                return Path(path_str)

        return None

    except Exception as e:
        print(f"캐시 파일 읽기 실패: {e}")
        return None
