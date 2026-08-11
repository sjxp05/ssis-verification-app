# 최근 사용한 파일 경로 저장소
#
# 조견표 라벨 대조는 작년 파일이 있어야 하므로, 마지막에 읽은 조견표 경로를 남긴다.
# 파일이 사라졌으면 기록이 있어도 None 을 돌려준다.

from __future__ import annotations
import json
from pathlib import Path

# 캐시 데이터를 저장할 파일
CACHE_FILE = Path(".recent_paths_cache.json")

def get_recent_path(key: str) -> Path | None:
    # TODO: 저장소에서 key 에 해당하는 경로를 읽어 반환
    # 기록이 없거나 파일이 더 이상 존재하지 않으면 None
    if not CACHE_FILE.exists():
            return None
        
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        path_str = data.get(key)
        if not path_str:
            return None
            
        path = Path(path_str)
        if path.exists():
            return path
        return None
        
    except Exception as e:
        print(f"캐시 파일 읽기 실패: {e}")
        return None


def set_recent_path(key: str, path: Path) -> None:
    # TODO: key: path 를 저장소에 기록한다 (마지막 값으로 덮어쓰기)
    data = {}
    
    # 기존 데이터가 있으면 먼저 읽어옴
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass # 파일이 깨져있으면 무시하고 덮어씀
            
    # 값 업데이트 (Path 객체는 문자열로 변환해서 저장)
    data[key] = str(path)
    
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"캐시 파일 저장 실패: {e}")
