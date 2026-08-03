# 최근 사용한 파일 경로 저장소 (자리만 마련해 둔 상태. 아직 미구현)
#
# 2번째 flow의 조견표와 기본급여 단가표는 여기 저장된 경로를 먼저 확인
# -> 있으면 자동으로 불러오기
# -> 없거나 파일이 사라졌을 때만 UploadPage 에서 직접 업로드를 받도록 바꿀 예정.
# 연동 지점: models.flows.UploadSlot.remember_last, ui.pages.upload_page.UploadPage.reset()
#
# TODO: 실제 저장 위치(예: 사용자 설정 폴더의 json 파일)를 정하고 구현을 채운다.

from __future__ import annotations

from pathlib import Path


def get_recent_path(key: str) -> Path | None:
    # TODO: 저장소에서 key 에 해당하는 경로를 읽어 반환
    # 기록이 없거나 파일이 더 이상 존재하지 않으면 None
    return None


def set_recent_path(key: str, path: Path) -> None:
    # TODO: key: path 를 저장소에 기록한다 (마지막 값으로 덮어쓰기)
    pass
