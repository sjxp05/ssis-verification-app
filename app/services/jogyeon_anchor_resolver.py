from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.anchors import EXTRACTION_ANCHORS, ExtractionAnchorSpec
from models.dto import (
    Decision,
    LabelRef,
    MatchItem,
    MatchPath,
    MatchReport,
    ResolvedAnchor,
    Status,
)
from services.jogyeon_anchor_locator import AnchorLocateError, AnchorLocator
from services.jogyeon_anchor_profile import get_anchor
from utils import xlsx_scan


class AnchorResolveError(Exception):
    """매칭 결과에서 추출 앵커의 최종 위치를 확정하지 못한 경우 발생하는 예외"""


class AnchorResolver:
    def __init__(
        self,
        report: MatchReport,
        decisions: list[Decision],
        baseline_path: Path,
        target_path: Path,
        baseline_profile: dict | None = None,
    ):
        self._report = report
        self._decisions = {
            decision.item_id: decision
            for decision in decisions
        }
        self._baseline_path = baseline_path
        self._target_path = target_path
        self._baseline_profile = baseline_profile

        self._baseline_locators: dict[str, AnchorLocator] = {}
        self._target_locators: dict[str, AnchorLocator] = {}

    def resolve(self) -> list[ResolvedAnchor]:
        resolved: list[ResolvedAnchor] = []

        for spec in EXTRACTION_ANCHORS:
            anchor = self._resolve_anchor(spec)

            if anchor is not None:
                resolved.append(anchor)

        return resolved

    # 기존 연도 위치를 기준으로 해당 앵커의 MatchItem을 찾고 올해 위치를 확정
    def _resolve_anchor(
        self,
        spec: ExtractionAnchorSpec,
    ) -> ResolvedAnchor | None:
        baseline_location = self._baseline_location(spec)

        if baseline_location is None:
            return None

        item = self._find_match_item(
            spec.sheet,
            baseline_location[0],
            baseline_location[1],
        )

        if item is None:
            if spec.optional:
                return None

            raise AnchorResolveError(
                f"'{spec.sheet}' 시트의 '{spec.anchor_id}' 앵커에 해당하는 "
                "매칭 결과를 찾지 못했습니다."
            )

        if item.status is Status.AUTO_PASS:
            return self._resolve_candidate(
                spec,
                item,
                rank=1,
                source="auto",
            )

        decision = self._decisions.get(item.item_id)

        if decision is None:
            raise AnchorResolveError(
                f"'{spec.anchor_id}' 앵커의 검토 결과가 없습니다."
            )

        if decision.action == "select_candidate":
            if decision.selected_rank is None:
                raise AnchorResolveError(
                    f"'{spec.anchor_id}' 앵커의 선택 후보 순위가 없습니다."
                )

            return self._resolve_candidate(
                spec,
                item,
                rank=decision.selected_rank,
                source="candidate",
            )

        if decision.action == "manual_input":
            keyword = (decision.manual_input or "").strip()

            if not keyword:
                raise AnchorResolveError(
                    f"'{spec.anchor_id}' 앵커의 직접 입력 문구가 비어 있습니다."
                )

            row, column = self._locate_target(
                spec,
                keyword,
            )

            return ResolvedAnchor(
                anchor_id=spec.anchor_id,
                sheet=spec.sheet,
                keyword=keyword,
                row=row,
                column=column,
                source="manual",
            )

        raise AnchorResolveError(
            f"지원하지 않는 검토 방식입니다: {decision.action}"
        )

    # 이전 연도 JSON이 있으면 저장 위치를 사용하고 없으면 기존 검색 방식으로 찾음
    def _baseline_location(
        self,
        spec: ExtractionAnchorSpec,
    ) -> tuple[int, int] | None:
        if self._baseline_profile is not None:
            saved = get_anchor(
                self._baseline_profile,
                spec.sheet,
                spec.anchor_id,
            )

            if saved is not None:
                return int(saved["row"]), int(saved["column"])

        try:
            locator = self._get_locator(
                self._baseline_path,
                spec.sheet,
                self._baseline_locators,
            )
            return locator.locate(
                spec.keyword,
                spec.find_mode,
            )
        except AnchorLocateError as error:
            if spec.optional:
                return None

            raise AnchorResolveError(
                f"이전 조견표에서 '{spec.sheet}' 시트의 "
                f"'{spec.anchor_id}' 앵커를 찾지 못했습니다: {error}"
            ) from None

    # 이전 조견표의 정확한 셀 위치로 일반 매칭 또는 누락 항목의 MatchItem을 찾음
    # 이전 조견표의 정확한 셀 위치로 누락 항목을 우선 확인한 뒤 일반 MatchItem을 찾음
    def _find_match_item(
        self,
        sheet: str,
        row: int,
        column: int,
    ) -> MatchItem | None:
        for missing in self._report.missing_values:
            location = missing.baseline_location

            if location is None:
                continue

            if sheet not in location.sheet:
                continue

            if location.row == row and location.column == column:
                return MatchItem(
                    item_id=f"missing-{missing.sheet}-{missing.label}",
                    input_label=LabelRef(
                        missing.label,
                        missing.label,
                        missing.baseline_location,
                    ),
                    status=Status.UNMATCHED,
                    match_path=MatchPath.HYBRID,
                    candidates=missing.candidates,
                )

        for item in self._report.items:
            location = item.input_label.location

            if location is None:
                continue

            if sheet not in location.sheet:
                continue

            if location.row == row and location.column == column:
                return item

        return None
    
    # 선택한 후보의 실제 올해 위치를 ResolvedAnchor로 변환
    def _resolve_candidate(
        self,
        spec: ExtractionAnchorSpec,
        item: MatchItem,
        rank: int,
        source: str,
    ) -> ResolvedAnchor:
        candidate = next(
            (
                candidate
                for candidate in item.candidates
                if candidate.rank == rank
            ),
            None,
        )

        if candidate is None:
            raise AnchorResolveError(
                f"'{spec.anchor_id}' 앵커의 {rank}순위 후보를 찾지 못했습니다."
            )

        location = candidate.base_location

        if location is not None:
            if spec.sheet not in location.sheet:
                raise AnchorResolveError(
                    f"'{spec.anchor_id}' 후보가 다른 시트에서 발견되었습니다: "
                    f"{location.sheet}"
                )

            return ResolvedAnchor(
                anchor_id=spec.anchor_id,
                sheet=spec.sheet,
                keyword=candidate.base_label,
                row=location.row,
                column=location.column,
                source=source,
            )

        row, column = self._locate_target(
            spec,
            candidate.base_label,
        )

        return ResolvedAnchor(
            anchor_id=spec.anchor_id,
            sheet=spec.sheet,
            keyword=candidate.base_label,
            row=row,
            column=column,
            source=source,
        )

    # 직접 입력 문구 또는 위치 없는 후보를 현재 조견표에서 기존 탐색 방식으로 찾음
    def _locate_target(
        self,
        spec: ExtractionAnchorSpec,
        keyword: str,
    ) -> tuple[int, int]:
        try:
            locator = self._get_locator(
                self._target_path,
                spec.sheet,
                self._target_locators,
            )
            return locator.locate(
                keyword,
                spec.find_mode,
            )
        except AnchorLocateError as error:
            raise AnchorResolveError(
                f"'{spec.sheet}' 시트에서 '{keyword}'의 위치를 "
                f"확정하지 못했습니다: {error}"
            ) from None

    # 같은 시트는 한 번만 읽고 Locator를 재사용
    def _get_locator(
        self,
        file_path: Path,
        sheet: str,
        cache: dict[str, AnchorLocator],
    ) -> AnchorLocator:
        if sheet in cache:
            return cache[sheet]

        try:
            sheet_names = pd.ExcelFile(file_path).sheet_names
        except Exception as error:
            raise AnchorResolveError(
                f"조견표를 읽지 못했습니다: {error}"
            ) from None

        matched_sheet = next(
            (name for name in sheet_names if sheet in name),
            None,
        )

        if matched_sheet is None:
            raise AnchorResolveError(
                f"'{sheet}'(이)가 포함된 시트를 찾을 수 없습니다."
            )

        cap = xlsx_scan.true_row_counts(file_path).get(matched_sheet)
        df = pd.read_excel(
            file_path,
            matched_sheet,
            engine="openpyxl",
            header=None,
            **({"nrows": cap} if cap else {}),
        )

        locator = AnchorLocator(
            AnchorLocator.normalize_dataframe(df)
        )
        cache[sheet] = locator

        return locator


def resolve_anchors(
    report: MatchReport,
    decisions: list[Decision],
    baseline_path: Path,
    target_path: Path,
    baseline_profile: dict | None = None,
) -> list[ResolvedAnchor]:
    return AnchorResolver(
        report=report,
        decisions=decisions,
        baseline_path=baseline_path,
        target_path=target_path,
        baseline_profile=baseline_profile,
    ).resolve()