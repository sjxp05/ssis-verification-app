# 기능별 백에서 UI 로 넘겨주어야 할 데이터 형식과 필요 함수 정의 파일
from dataclasses import dataclass, field

# 조견표 / 고시 업로드 시 파일 이름과 경로, 크기 필요
@dataclass
class UploadFile:
    path: str
    name: str
    size: int

    @property
    def size_text(self) -> str:
        s = self.size
        if s < 1024:
            return f"{s} B"
        if s < 1024 ** 2:
            return f"{s / 1024:.1f} KB"
        return f"{s / 1024 ** 2:.1f} MB"

# 예: 조견표의 단가 정보 확인 기능 - 기본단가, A값, 상한액 등 필요
@dataclass
class CheckPrice: # 이름은 적절히 변경 .. 
    basic_price: int
    A_value: int
    upper_limit: int
    #TODO: 더 필요한 필드 정의
    
