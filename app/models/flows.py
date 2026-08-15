from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
# 업로드 화면의 카드 한 장
class UploadSlot:
    key: str  # 추출기에 넘길 때 쓰는 이름
    title: str
    description: str
    extensions: tuple[str, ...]
    icon: str = "📄"
    # True면 services.recent_files 에 저장된 최근 경로가 있을 때 업로드를 건너뛸 후보
    # (경로 저장은 구현됨. 카드 자동 채움은 미구현 — upload_page.py 의 TODO 참고)
    remember_last: bool = False


@dataclass(frozen=True, slots=True)
class FlowSpec:
    # 업로드 → 값 확인 → 표 생성으로 이어지는 작업 흐름 하나

    key: str
    menu_title: str  # 메인 화면 버튼 제목
    menu_description: str  # 메인 화면 버튼 설명
    window_title: str  # 헤더에 뜨는 제목
    steps: tuple[str, ...]
    upload_title: str
    upload_description: str
    uploads: tuple[UploadSlot, ...]
    export_names: tuple[str, ...] = ()  # 탭 인덱스별 기본 저장 파일명
    enabled: bool = True

    stub: bool = False
    stub_notice: str = "이 작업은 아직 준비 중입니다."

    def export_name(self, tab_index: int) -> str:
        # 탭 인덱스에 해당하는 기본 저장 파일명. 범위를 벗어나면 첫 번째를 쓴다
        if 0 <= tab_index < len(self.export_names):
            return self.export_names[tab_index]
        return self.export_names[0]


UNIT_PRICE = FlowSpec(
    key="unit_price",
    menu_title="조견표 → 단가표 생성",
    menu_description=("조견표에서 상수를 읽어 기본급여·추가급여 단가표를 만듭니다."),
    window_title="조견표 → 단가표 생성",
    steps=("조견표 업로드", "단가 정보 확인", "단가표 생성 및 저장"),
    upload_title="조견표 업로드",
    upload_description=("조견표를 올리면 단가 계산에 필요한 값을 자동으로 읽어옵니다."),
    uploads=(
        UploadSlot(
            key="jogyeon",
            title="조견표",
            description="Excel 형식의 조견표 · 등급·구간 정보를 읽습니다",
            extensions=(".xlsx", ".xls"),
            icon="▦",
            remember_last=True,
        ),
    ),
    export_names=("기본급여_단가표.xlsx", "추가급여_단가표.xlsx"),
)

NOTICE_VERIFY = FlowSpec(
    key="notice_verify",
    menu_title="고시 검증 및 결제단가표 생성",
    menu_description="고시와 조견표, 단가표를 대조해 고시의 내용이 옳은지 검증합니다.",
    window_title="고시 검증 및 결제단가표 생성",
    steps=("문서 업로드", "값 확인", "결제단가표 생성 및 저장"),
    upload_title="문서 업로드",
    upload_description=(
        "고시 문서와 조견표, 기본급여 단가표를 올리면 검증에 필요한 값을 자동으로 읽어옵니다."
    ),
    uploads=(
        UploadSlot(
            key="guide",
            title="고시",
            description="hwpx 형식의 고시 문서를 업로드해 주세요.",
            extensions=(".hwpx",),
            icon="📄",
            remember_last=True,
        ),
        UploadSlot(
            key="jogyeon",
            title="조견표",
            description="Excel 형식의 조견표 · 등급·구간 정보를 읽습니다",
            extensions=(".xlsx", ".xls"),
            icon="▦",
            remember_last=True,
        ),
        UploadSlot(
            key="basic_unit_price",
            title="기본급여 단가표",
            description="Excel 형식의 기본급여 단가표를 업로드해 주세요.",
            extensions=(".xlsx", ".xls"),
            icon="📊",
            remember_last=True,
        ),
    ),
    export_names=("결제단가표.xlsx",),
    stub=True,
    stub_notice="검증 파이프라인은 준비 중입니다. 파일 확인까지만 가능합니다.",
)

FLOWS: tuple[FlowSpec, ...] = (UNIT_PRICE, NOTICE_VERIFY)
