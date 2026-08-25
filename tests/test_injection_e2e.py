# 오류 주입 조견표 22건 E2E 검증

from __future__ import annotations

import _support

from app.jogyeon_matcher import Status, match_workbooks
from app.jogyeon_matcher import table_analyzer
from app.jogyeon_matcher.label_rules import normalize


_REPORT = None


def _report():
    global _REPORT
    if _REPORT is None:
        _REPORT = match_workbooks(
            _support.require(_support.BASELINE),
            _support.require(_support.TARGET),
        )
    return _REPORT


def _item(sheet: str, label: str):
    key = normalize(label)
    for item in _report().items:
        location = item.input_label.location
        if (
            location
            and location.sheet == sheet
            and normalize(item.input_label.raw) == key
        ):
            return item
    return None


def _alerts(code: str, sheet: str | None = None):
    return [
        alert
        for alert in _report().structural_alerts
        if alert.code == code and (sheet is None or alert.sheet == sheet)
    ]


def _anomalies(code: str, sheet: str | None = None):
    return [
        anomaly
        for anomaly in _report().value_anomalies
        if anomaly.code == code and (sheet is None or anomaly.sheet == sheet)
    ]


def _assert_auto_pass(sheet: str, label: str, expected: str, inj: str):
    item = _item(sheet, label)
    assert item is not None, f"[{inj}] {label!r} 항목이 없음"
    assert item.status is Status.AUTO_PASS, (
        f"[{inj}] {label!r} 가 {item.status} — auto_pass 여야 함 "
        f"(top3={[c.base_label for c in item.candidates]})"
    )
    assert normalize(item.matched_label or "") == normalize(expected), (
        f"[{inj}] {label!r} 가 {item.matched_label!r} 에 붙음, 기대 {expected!r}"
    )


def _assert_in_top3(sheet: str, label: str, expected: str, inj: str):
    item = _item(sheet, label)
    assert item is not None, f"[{inj}] {label!r} 항목이 없음"

    names = [normalize(candidate.base_label) for candidate in item.candidates]

    assert item.status is Status.NEEDS_REVIEW, f"[{inj}] {label!r} 가 {item.status}"
    assert normalize(expected) in names, (
        f"[{inj}] {expected!r} 가 top3 밖 — "
        f"{[c.base_label for c in item.candidates]}"
    )


# 일반 표기 변형
def test_j01_notation_change_auto_passes():
    _assert_auto_pass("인정조사", "기본단가", "기본 단가(원)", "J01")


def test_j02_fullwidth_parentheses_auto_pass():
    _assert_auto_pass(
        "인정조사",
        "(본인부담금 상한액)",
        "（본인부담금 상한액）",
        "J02",
    )


def test_j03_year_prefix_reaches_top3():
    # 연도 표기는 숫자 충돌로 강등하지 않음
    _assert_in_top3("인정조사", "A값", "2027 A값", "J03")


def test_j04_synonym_reaches_top3():
    # 문자 겹침이 적은 동의어는 임베딩 점수로 후보에 포함
    _assert_in_top3("인정조사", "본인부담금", "자기부담금", "J04")


def test_j05_typo_reaches_top3():
    _assert_in_top3("인정조사", "차상위", "차상휘", "J05")


def test_j12_word_order_reaches_top3():
    _assert_in_top3(
        "인정조사",
        "추가급여 월한도액",
        "월한도액(추가급여)",
        "J12",
    )


def test_j17_percent_annotation_auto_passes():
    # 단위 괄호의 %는 제거하고 비율 조건의 %는 유지
    _assert_auto_pass(
        "산정특례",
        "기본 부담률",
        "기본부담률(%)",
        "J17",
    )


# 비가시 문자와 판별자 변형
def test_j06_zero_width_space_removed():
    _assert_auto_pass("인정조사", "월 한도액", "월 한도액", "J06")


def test_j07_non_breaking_space_removed():
    _assert_auto_pass("인정조사", "지원시간", "지원시간 ", "J07")


def test_j16_fullwidth_homoglyph_removed():
    _assert_auto_pass("산정특례", "A값", "Ａ값", "J16")


def test_j08_income_band_spacing_auto_passes():
    _assert_auto_pass("인정조사", "100% 이하", "100 % 이하", "J08")


def test_j09_antonym_band_not_confused():
    # 같은 표의 '150% 이하'가 아닌 동일 방향 조건과 매칭되어야 함
    _assert_auto_pass("인정조사", "150% 초과", "150%초과", "J09")


def test_j13_substring_does_not_contaminate():
    # '1등급1인가구'보다 완전일치 '1등급'을 우선
    _assert_auto_pass("인정조사", "1등급", "1등급", "J13")


def test_j15_duplicate_anchor_is_fatal():
    # 동일 앵커가 여러 행에 있으면 값 위치를 확정할 수 없음
    alerts = _alerts("ANCHOR_NOT_UNIQUE", "산정특례")
    assert alerts, "앵커 중복이 탐지되지 않음"
    assert alerts[0].fatal, "앵커 중복은 진행 불가 상태여야 함"


def test_j18_column_swap_detected_by_fingerprint():
    # 동일 라벨의 열 순서 변경은 HEADER_ORDER_CHANGED로 탐지
    assert _alerts(
        "HEADER_ORDER_CHANGED",
        "종합조사",
    ), "열 순서 교체 미탐지"


def test_j14_unit_shift_detected_by_values():
    # 지원시간의 시간 단위가 분 단위로 변경된 경우 탐지
    assert _anomalies(
        "UNIT_SHIFT_SUSPECTED",
        "인정조사",
    ), "단위 이동 미탐지"


def test_j19_monotonicity_break_detected():
    assert _anomalies(
        "MONOTONICITY_BROKEN",
        "고시 본문",
    ), "단조성 파괴 미탐지"


# 정상 동작 오탐 방지
def test_j10_new_label_flagged():
    for item in _report().items:
        if normalize(item.input_label.raw) == normalize("긴급돌봄"):
            assert "NEW_IN_TARGET" in item.flags, (
                f"신규 라벨 플래그 없음 {item.flags}"
            )
            return

    raise AssertionError("신규 라벨 '긴급돌봄' 항목이 없음")


def test_j11_deleted_label_not_auto_passed():
    item = _item("인정조사", "출산")
    assert item is not None, "'출산' 항목이 없음"
    assert item.status is not Status.AUTO_PASS, "삭제된 라벨이 자동 통과됨"


def test_j20_no_normalization_collision():
    # 서로 다른 부담률 라벨이 정규화 후 동일해지지 않는지 확인
    collisions = _alerts("NORMALIZATION_COLLISION")
    assert not collisions, f"정규화 충돌 {[a.detail for a in collisions]}"


def test_j21_unchanged_label_auto_passes():
    # 값만 갱신된 동일 라벨은 AUTO_PASS 유지
    _assert_auto_pass("산정특례", "기본단가", "기본단가", "J21")


def test_j22_adjacent_tables_separated():
    # 빈 열로 구분된 인접 표를 각각의 TableRegion으로 분리
    workbook = table_analyzer.load(_support.BASELINE)
    regions = table_analyzer.find_tables(
        "고시 본문",
        workbook.sheets["고시 본문"],
    )
    assert len(regions) == 2, f"표가 {len(regions)}개로 분리됨, 기대 2개"


if __name__ == "__main__":
    summary = _report().summary

    print(f"{_report().baseline_file} -> {_report().target_file}")
    print(
        f"전체 {summary.total_labels} · "
        f"auto_pass {summary.auto_passed} · "
        f"검토 {summary.needs_review} · "
        f"미매칭 {summary.unmatched}"
    )
    print(
        f"구조 경보 {len(_report().structural_alerts)}건 · "
        f"값 이상 {len(_report().value_anomalies)}건\n"
    )

    raise SystemExit(_support.run_module(dict(globals())))