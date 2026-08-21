# review_flow._MatchTask에서 호출되어 두 조견표를 비교한 MatchReport를 반환

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from .config import anchors, required_values
from .contracts.schemas import (
    Candidate,
    LabelRef,
    MatchItem,
    MatchPath,
    MatchReport,
    MissingValue,
    Status,
    StructuralAlert,
    Summary,
)
from .ingest import loader, segmenter
from .matching import constraints, rule_parser
from .matching.dense import DenseEncoder
from .matching.hybrid import HybridConfig, HybridMatcher
from .matching.normalizer import find_normalization_collisions, normalize
from .validation import value_checks

# 라벨이 아닌 값 자체를 나타내는 문구. 해당 문구가 있는 셀은 다른 셀과 유사도 비교하지 않음
IGNORED = frozenset({"면제", "-", "해당없음", "비고"})

TOP_K = 3


def match_workbooks(
    baseline_path: str | Path,
    target_path: str | Path,
    config: HybridConfig | None = None,
) -> MatchReport:
    config = (
        config or HybridConfig()
    )  # 실험을 통해 찾아낸 최적의 모델 하이퍼파라미터 hybrid.py에서 불러오기
    baseline = loader.load(baseline_path, anchors.JOGYEON_SHEET_NAMES)
    target = loader.load(target_path, anchors.JOGYEON_SHEET_NAMES)

    report = MatchReport(
        run_id=datetime.now().strftime("%Y%m%dT%H%M%S"),
        baseline_file=baseline.name,
        target_file=target.name,
    )

    base_regions = {s: segmenter.find_tables(s, f) for s, f in baseline.sheets.items()}
    target_regions = {s: segmenter.find_tables(s, f) for s, f in target.sheets.items()}

    report.structural_alerts += segmenter.compare_sheets(
        base_regions, target_regions, anchors.JOGYEON_SHEET_NAMES
    )
    for regions in target_regions.values():
        report.structural_alerts += segmenter.check_anchor_uniqueness(
            regions, anchors.SCALAR_ANCHORS
        )
    report.value_anomalies += value_checks.compare_regions(base_regions, target_regions)

    base_labels = {s: _collect_labels(base_regions.get(s, [])) for s in baseline.sheets}
    target_labels = {
        s: _collect_labels(target_regions.get(s, [])) for s in target.sheets
    }
    matchers: dict[str, HybridMatcher | None] = {}

    # 유사도 대조가 필요한 경우에만 지연 로딩되는 인코더, 모든 시트에서 공유
    encoder = DenseEncoder()

    # ValueExtractor와 동일하게 라벨 매칭을 같은 시트 안에서만 수행
    # 시트 이름이 완전히 같지 않아도(연도 표기 등) _find_missing과 같은 방식으로 찾는다
    for sheet in baseline.sheets:
        target_sheet = _resolve_sheet(sheet, target.sheets, anchors.JOGYEON_SHEET_NAMES)
        if target_sheet is None:
            continue
        matcher = (
            HybridMatcher(list(target_labels[target_sheet]), config, encoder=encoder)
            if target_labels[target_sheet]
            else None
        )
        matchers[target_sheet] = matcher
        report.items += _match_sheet(
            sheet, base_labels[sheet], target_labels[target_sheet], matcher, report
        )

    report.missing_values = _find_missing(target_labels, matchers, base_labels)
    report.summary = _summarize(report.items)
    return report


# 시트 이름이 완전히 같지 않을 때(연도 표기 등) 키워드를 포함하는 시트를 찾는다.
# 완전일치가 있으면 그걸 우선한다.
def _resolve_sheet(name: str, candidates, keywords: tuple[str, ...]) -> str | None:
    if name in candidates:
        return name
    keyword = next((k for k in keywords if k in name), None)
    if keyword is None:
        return None
    return next((s for s in candidates if keyword in s), None)


# 올해 파일에서 값을 읽을 수 있는지 미리 확인
# 추출기(ValueExtractor)와 같은 방식으로 부분문자열로 탐색. 단 등급, 구간 등 행·열 이름은 정확히 일치해야 함
def _find_missing(
    target_labels: dict[str, dict[str, LabelRef]],
    matchers: dict[str, HybridMatcher | None],
    base_labels: dict[str, dict[str, LabelRef]],
) -> list[MissingValue]:
    missing: list[MissingValue] = []
    for required in required_values.REQUIRED:
        actual_sheet = _resolve_sheet(
            required.sheet, target_labels, anchors.JOGYEON_SHEET_NAMES
        )
        labels = target_labels.get(actual_sheet, {}) if actual_sheet else {}
        key = normalize(required.label)

        if required.exact:
            found = key in labels
            if not found:
                # 등급/구간처럼 표기만 다른 동등 라벨도 인정
                parsed = rule_parser.parse(key)
                found = parsed is not None and any(
                    rule_parser.parse(other) == parsed for other in labels
                )
            reason = "" if found else "올해 파일에서 찾지 못했습니다"
        else:
            hits = [ref for norm, ref in labels.items() if key in norm]
            rows = {ref.location.row for ref in hits if ref.location}
            if not hits:
                reason = "올해 파일에서 찾지 못했습니다"
            elif len(rows) > 1:
                # 부분/전체 일치하는 후보가 여러 행에 중복으로 있으면 실패 (_find_one)
                reason = f"서로 다른 {len(rows)}개 행에 나뉘어 있어 어디서 읽을지 정할 수 없습니다"
            else:
                reason = ""

        # 에러 사유가 발생해도 optional 항목인 경우 에러 무시
        if (
            getattr(required, "optional", False)
            and reason == "올해 파일에서 찾지 못했습니다"
        ):
            reason = ""

        if not reason:
            continue

        actual_base_sheet = _resolve_sheet(
            required.sheet, base_labels, anchors.JOGYEON_SHEET_NAMES
        )
        baseline_ref = (
            base_labels.get(actual_base_sheet, {}).get(key) if actual_base_sheet else None
        )
        missing.append(
            MissingValue(
                label=required.label,
                sheet=required.sheet,
                produces=required.produces,
                tables=required.tables,
                reason=reason,
                candidates=_suggest(key, matchers.get(actual_sheet), labels),
                baseline_location=baseline_ref.location if baseline_ref else None,
            )
        )
    return missing


# 필수 문구 누락 시 올해 라벨에서 대체 후보 3개 제시
def _suggest(
    key: str, matcher: HybridMatcher | None, labels: dict[str, LabelRef]
) -> list[Candidate]:
    if matcher is None or not labels:
        return []
    keys = matcher.labels
    final, sparse, dense = matcher.score_components(key)
    adjusted, veto_flags = constraints.apply_vetoes(key, keys, final)
    return [
        Candidate(
            rank=rank,
            base_label=labels[keys[i]].raw,
            final=float(adjusted[i]),
            bm25=float(sparse[i]),
            embedding=float(dense[i]),
            base_location=labels[keys[i]].location,
            flags=list(veto_flags[i]),
        )
        for rank, i in enumerate(np.argsort(-adjusted)[:TOP_K], start=1)
    ]


def _summarize(items: list[MatchItem]) -> Summary:
    return Summary(
        total_labels=len(items),
        auto_passed=sum(1 for i in items if i.status is Status.AUTO_PASS),
        needs_review=sum(1 for i in items if i.status is Status.NEEDS_REVIEW),
        unmatched=sum(1 for i in items if i.status is Status.UNMATCHED),
        contested=sum(1 for i in items if "CONTESTED" in i.flags),
    )


# 표에서 라벨 후보 추출. 정규형이 같으면 먼저 나온 셀 우선, 이후 find_normalization_collisions()로 따로 탐지
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
    matcher: HybridMatcher | None,
    report: MatchReport,
) -> list[MatchItem]:
    for norm_form, originals in find_normalization_collisions(
        [ref.raw for ref in base_labels.values()]
    ).items():
        report.structural_alerts.append(
            StructuralAlert(
                "NORMALIZATION_COLLISION",
                sheet,
                f"서로 다른 라벨이 정규화 후 같아집니다: {originals} -> {norm_form!r}",
            )
        )

    items: list[MatchItem] = []
    claimed: set[str] = set()
    reviewed: list[tuple[MatchItem, np.ndarray]] = []

    # 라벨마다 매번 전체 순회하면 O(라벨²)로 성능이 저하되므로 시트당 인덱스는 한 번만 생성
    det = _DeterministicIndex(target_labels)

    # 결정론 매칭에 실패한 라벨만 배치로 한번에 ONNX 호출하여 비용 최소화
    if matcher is not None:
        pending = [
            ref.normalized
            for ref in base_labels.values()
            if _match_deterministic(ref, target_labels, det) is None
        ]
        matcher.precompute_queries(pending)

    for index, ref in enumerate(base_labels.values()):
        item, matched, scores = _match_one(
            f"{sheet}-{index:03d}", ref, target_labels, matcher, det
        )
        if matched:
            claimed.add(matched)
        if item.match_path is MatchPath.RULE_PARSER:
            base_kind = rule_parser.ordinal_kind_diff(ref.raw)
            target_kind = rule_parser.ordinal_kind_diff(item.matched_label or "")
            if base_kind and target_kind and base_kind != target_kind:
                report.structural_alerts.append(
                    StructuralAlert(
                        "ORDINAL_KIND_CHANGED",
                        sheet,
                        f"작년 '{ref.raw}' -> 올해 '{item.matched_label}' "
                        f"({base_kind}에서 {target_kind}로 표기가 바뀌었습니다)",
                    )
                )
        if scores is not None:
            reviewed.append((item, scores))
        items.append(item)

    # 비교 대상 조견표에 없는 신설/개칭 항목 발견 시 등록
    for key, ref in target_labels.items():
        if key not in claimed and key not in base_labels:
            items.append(
                MatchItem(
                    f"{sheet}-new-{len(items):03d}",
                    ref,
                    Status.UNMATCHED,
                    MatchPath.HYBRID,
                    flags=["NEW_IN_TARGET"],
                )
            )

    if reviewed:
        for position in constraints.find_contested(np.vstack([s for _, s in reviewed])):
            reviewed[position][0].flags.append("CONTESTED")
    return items


def _match_one(
    item_id: str,
    ref: LabelRef,
    target_labels: dict[str, LabelRef],
    matcher: HybridMatcher | None,
    det: _DeterministicIndex,
) -> tuple[MatchItem, str | None, np.ndarray | None]:
    matched = _match_deterministic(ref, target_labels, det)
    if matched:
        path, key = matched
        found = target_labels[key]
        item = MatchItem(
            item_id,
            ref,
            Status.AUTO_PASS,  # 일치판정:EXACT, NORMALIZED, RULE_PARSER
            path,
            candidates=[Candidate(1, found.raw, 1.0, 1.0, 1.0, found.location)],
            matched_label=found.raw,
        )
        return item, key, None

    if matcher is None:
        return MatchItem(item_id, ref, Status.UNMATCHED, MatchPath.HYBRID), None, None

    scores, candidates = _rank_candidates(ref.normalized, target_labels, matcher)
    passes = bool(candidates) and candidates[0].final >= matcher.config.cutoff
    item = MatchItem(
        item_id,
        ref,
        Status.NEEDS_REVIEW if passes else Status.UNMATCHED,
        MatchPath.HYBRID,
        candidates,
        constraints.margin_flag(scores),
    )
    return item, normalize(candidates[0].base_label) if passes else None, scores


# 결정론 판정용 인덱스
class _DeterministicIndex:
    def __init__(self, target_labels: dict[str, LabelRef]):
        self.raw: dict[str, str] = {}
        self.parsed: dict[object, str] = {}
        for key, found in target_labels.items():
            # setdefault()로 먼저 나온 라벨 우선 적용
            self.raw.setdefault(found.raw, key)
            token = rule_parser.parse(key)
            if token is not None:
                self.parsed.setdefault(token, key)


# 규칙 기반 결정론적 경로 (auto pass)
def _match_deterministic(
    ref: LabelRef, target_labels: dict[str, LabelRef], det: _DeterministicIndex
) -> tuple[MatchPath, str] | None:
    key = det.raw.get(ref.raw)
    if key is not None:
        return MatchPath.EXACT, key
    if ref.normalized in target_labels:
        return MatchPath.NORMALIZED, ref.normalized

    # 구조 일치 비교(예: 100%이하 == 100 % 이하)
    token = rule_parser.parse(ref.normalized)
    if token is not None:
        key = det.parsed.get(token)
        if key is not None:
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
        candidates.append(
            Candidate(
                rank,
                found.raw,
                float(adjusted[i]),
                float(sparse[i]),
                float(dense[i]),
                found.location,
                flags=list(veto_flags[i]),
            )
        )
    if len(candidates) >= 2:
        candidates[0].margin_to_next = candidates[0].final - candidates[1].final
    return adjusted, candidates
