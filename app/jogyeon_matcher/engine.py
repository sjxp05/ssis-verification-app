# 파이프라인 조립 — 엑셀 적재부터 MatchReport 생성까지
#
# 작년 조견표의 라벨 하나하나에 대해 올해 대응물을 찾는다. 감시 대상을 고정
# 목록으로 두지 않는 이유는, 값 추출이 의존하는 것이 앵커 문자열만이 아니라
# 그것을 둘러싼 헤더·행 이름 전체이기 때문이다.
#
# 판정 순서가 곧 신뢰 순서다.
#     원문 일치 -> 정규화 일치 -> 규칙 파서 동등 -> 하이브리드
# 앞의 셋만 auto_pass 근거가 된다. 유사도 점수는 0.99 가 나와도 근거가 못 된다.
#
# 매칭은 시트 스코프 안에서만 한다. 추출기가 시트별로 값을 읽으므로 다른 시트의
# 동명 라벨과 이어붙이면 그 자체가 오류다.

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from .config import anchors
from .contracts.schemas import (
    Candidate,
    LabelRef,
    MatchItem,
    MatchPath,
    MatchReport,
    Status,
    StructuralAlert,
    Summary,
)
from .ingest import loader, segmenter
from .matching import constraints, rule_parser
from .matching.hybrid import HybridConfig, HybridMatcher
from .matching.normalizer import find_normalization_collisions, normalize
from .validation import value_checks

# 라벨이 아니라 값 자체를 나타내는 문구
IGNORED = frozenset({"면제", "-", "해당없음", "비고"})

TOP_K = 3


def match_workbooks(
    baseline_path: str | Path,
    target_path: str | Path,
    config: HybridConfig | None = None,
) -> MatchReport:
    config = config or HybridConfig()
    baseline = loader.load(baseline_path, anchors.JOGYEON_SHEET_NAMES)
    target = loader.load(target_path, anchors.JOGYEON_SHEET_NAMES)

    report = MatchReport(
        run_id=datetime.now().strftime("%Y%m%dT%H%M%S"),
        baseline_file=baseline.name,
        target_file=target.name,
    )

    base_regions = {s: segmenter.find_tables(s, f) for s, f in baseline.sheets.items()}
    target_regions = {s: segmenter.find_tables(s, f) for s, f in target.sheets.items()}

    report.structural_alerts += segmenter.compare_sheets(base_regions, target_regions)
    for regions in target_regions.values():
        report.structural_alerts += segmenter.check_anchor_uniqueness(
            regions, anchors.SCALAR_ANCHORS
        )
    report.value_anomalies += value_checks.compare_regions(base_regions, target_regions)

    for sheet in baseline.sheets:
        if sheet in target.sheets:
            report.items += _match_sheet(
                sheet,
                _collect_labels(base_regions.get(sheet, [])),
                _collect_labels(target_regions.get(sheet, [])),
                config,
                report,
            )

    report.summary = _summarize(report.items)
    return report


def _summarize(items: list[MatchItem]) -> Summary:
    return Summary(
        total_labels=len(items),
        auto_passed=sum(1 for i in items if i.status is Status.AUTO_PASS),
        needs_review=sum(1 for i in items if i.status is Status.NEEDS_REVIEW),
        unmatched=sum(1 for i in items if i.status is Status.UNMATCHED),
        contested=sum(1 for i in items if "CONTESTED" in i.flags),
    )


# 표에서 라벨 후보를 모은다. 정규형이 같으면 먼저 나온 셀을 대표로 삼는다.
def _collect_labels(regions: list) -> dict[str, LabelRef]:
    labels: dict[str, LabelRef] = {}
    for region in regions:
        for text, location in region.text_cells():
            key = normalize(text)
            if key and text.strip() not in IGNORED:
                labels.setdefault(key, LabelRef(text, key, location))
    return labels


def _match_sheet(
    sheet: str,
    base_labels: dict[str, LabelRef],
    target_labels: dict[str, LabelRef],
    config: HybridConfig,
    report: MatchReport,
) -> list[MatchItem]:
    for norm_form, originals in find_normalization_collisions(
        [ref.raw for ref in base_labels.values()]
    ).items():
        report.structural_alerts.append(StructuralAlert(
            "NORMALIZATION_COLLISION", sheet,
            f"서로 다른 라벨이 정규화 후 같아집니다: {originals} -> {norm_form!r}",
        ))

    matcher = HybridMatcher(list(target_labels), config) if target_labels else None
    items: list[MatchItem] = []
    claimed: set[str] = set()
    reviewed: list[tuple[MatchItem, np.ndarray]] = []

    for index, ref in enumerate(base_labels.values()):
        item, matched, scores = _match_one(
            f"{sheet}-{index:03d}", ref, target_labels, matcher, config
        )
        if matched:
            claimed.add(matched)
        if scores is not None:
            reviewed.append((item, scores))
        items.append(item)

    # 역방향: 작년에 없던 올해 라벨. 신설 항목이거나 개칭의 반대쪽이다.
    for key, ref in target_labels.items():
        if key not in claimed and key not in base_labels:
            items.append(MatchItem(
                f"{sheet}-new-{len(items):03d}", ref,
                Status.UNMATCHED, MatchPath.HYBRID, flags=["NEW_IN_TARGET"],
            ))

    if reviewed:
        for position in constraints.find_contested(np.vstack([s for _, s in reviewed])):
            reviewed[position][0].flags.append("CONTESTED")
    return items


def _match_one(
    item_id: str,
    ref: LabelRef,
    target_labels: dict[str, LabelRef],
    matcher: HybridMatcher | None,
    config: HybridConfig,
) -> tuple[MatchItem, str | None, np.ndarray | None]:
    matched = _match_deterministic(ref, target_labels)
    if matched:
        path, key = matched
        found = target_labels[key]
        item = MatchItem(
            item_id, ref, Status.AUTO_PASS, path,
            candidates=[Candidate(1, found.raw, 1.0, 1.0, 1.0, found.location)],
            matched_label=found.raw,
        )
        return item, key, None

    if matcher is None:
        return MatchItem(item_id, ref, Status.UNMATCHED, MatchPath.HYBRID), None, None

    scores, candidates = _rank_candidates(ref.normalized, target_labels, matcher)
    passes = bool(candidates) and candidates[0].final >= config.cutoff
    item = MatchItem(
        item_id, ref,
        Status.NEEDS_REVIEW if passes else Status.UNMATCHED,
        MatchPath.HYBRID, candidates, constraints.margin_flag(scores),
    )
    return item, normalize(candidates[0].base_label) if passes else None, scores


# 유사도가 아니라 동등성으로 판정되는 경로. 여기서 걸리면 auto_pass 다.
def _match_deterministic(
    ref: LabelRef, target_labels: dict[str, LabelRef]
) -> tuple[MatchPath, str] | None:
    for key, found in target_labels.items():
        if found.raw == ref.raw:
            return MatchPath.EXACT, key
    if ref.normalized in target_labels:
        return MatchPath.NORMALIZED, ref.normalized
    for key in target_labels:
        if rule_parser.equals(ref.normalized, key) is True:
            return MatchPath.RULE_PARSER, key
    return None


def _rank_candidates(
    query: str, target_labels: dict[str, LabelRef], matcher: HybridMatcher
) -> tuple[np.ndarray, list[Candidate]]:
    keys = matcher.labels
    final, sparse, dense = matcher.score_components(query)
    adjusted, veto_flags = constraints.apply_vetoes(query, keys, final)

    candidates = []
    for rank, i in enumerate(np.argsort(-adjusted)[:TOP_K], start=1):
        found = target_labels[keys[i]]
        candidates.append(Candidate(
            rank, found.raw, float(adjusted[i]), float(sparse[i]), float(dense[i]),
            found.location, flags=list(veto_flags[i]),
        ))
    if len(candidates) >= 2:
        candidates[0].margin_to_next = candidates[0].final - candidates[1].final
    return adjusted, candidates
