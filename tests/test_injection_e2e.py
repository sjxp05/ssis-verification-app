# 오류 주입 조견표 22건 E2E 검증
#
# 실제 파일 형태의 합성 조견표 한 쌍(기준 2026 / 오류 주입 2027)을 파이프라인
# 전체에 통과시키고, fixtures/injection_answer_key.xlsx 의 기대 동작과 대조한다.
#
# test_label_matching.py 가 매칭 함수 단위라면 이쪽은 엑셀 적재부터 리포트
# 생성까지 전 구간을 본다. 픽스처를 다시 만들려면 fixtures/generate_synthetic_jogyeon.py
# 를 실행하면 된다.
#
#   python tests/test_injection_e2e.py

from __future__ import annotations

import _support
from jogyeon_matcher import Status, match_workbooks
from jogyeon_matcher.ingest import loader, segmenter
from jogyeon_matcher.matching.normalizer import normalize

_REPORT = None


def _report():
    global _REPORT
    if _REPORT is None:
        _REPORT = match_workbooks(
            _support.require(_support.BASELINE), _support.require(_support.TARGET)
        )
    return _REPORT


def _item(sheet: str, label: str):
    key = normalize(label)
    for item in _report().items:
        location = item.input_label.location
        if location and location.sheet == sheet and normalize(item.input_label.raw) == key:
            return item
    return None


def _alerts(code: str, sheet: str | None = None):
    return [
        a for a in _report().structural_alerts
        if a.code == code and (sheet is None or a.sheet == sheet)
    ]


def _anomalies(code: str, sheet: str | None = None):
    return [
        a for a in _report().value_anomalies
        if a.code == code and (sheet is None or a.sheet == sheet)
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
    names = [normalize(c.base_label) for c in item.candidates]
    assert item.status is Status.NEEDS_REVIEW, f"[{inj}] {label!r} 가 {item.status}"
    assert normalize(expected) in names, (
        f"[{inj}] {expected!r} 가 top3 밖 — {[c.base_label for c in item.candidates]}"
    )


# ── A. 일반 변형 — 정규화가 흡수하거나 하이브리드가 후보로 올려야 한다 ──

def test_j01_notation_change_auto_passes():
    _assert_auto_pass("인정조사", "기본단가", "기본 단가(원)", "J01")


def test_j02_fullwidth_parentheses_auto_pass():
    _assert_auto_pass("인정조사", "(본인부담금 상한액)", "（본인부담금 상한액）", "J02")


def test_j03_year_prefix_reaches_top3():
    # 숫자 거부권이 '덧붙은 연도'까지 눌러버리면 정답이 후보에서 사라진다
    _assert_in_top3("인정조사", "A값", "2027 A값", "J03")


def test_j04_synonym_reaches_top3():
    # 문자 겹침이 거의 없어 임베딩이 견인해야 하는 사례
    _assert_in_top3("인정조사", "본인부담금", "자기부담금", "J04")


def test_j05_typo_reaches_top3():
    _assert_in_top3("인정조사", "차상위", "차상휘", "J05")


def test_j12_word_order_reaches_top3():
    _assert_in_top3("인정조사", "추가급여 월한도액", "월한도액(추가급여)", "J12")


def test_j17_percent_annotation_auto_passes():
    # '(%)' 는 단위 주석이라 제거하지만, '100% 이하' 의 % 는 판별자라 보존해야 한다
    _assert_auto_pass("산정특례", "기본 부담률", "기본부담률(%)", "J17")


# ── C. 우회·적대 — 비가시 문자, 판별자, 사각지대 ──

def test_j06_zero_width_space_removed():
    _assert_auto_pass("인정조사", "월 한도액", "월​ 한도액", "J06")


def test_j07_non_breaking_space_removed():
    _assert_auto_pass("인정조사", "지원시간", "지원시간 ", "J07")


def test_j16_fullwidth_homoglyph_removed():
    _assert_auto_pass("산정특례", "A값", "Ａ값", "J16")


def test_j08_income_band_spacing_auto_passes():
    _assert_auto_pass("인정조사", "100% 이하", "100 % 이하", "J08")


def test_j09_antonym_band_not_confused():
    # '150% 이하' 가 같은 표에 공존한다. 그쪽에 붙으면 실패다.
    _assert_auto_pass("인정조사", "150% 초과", "150%초과", "J09")


def test_j13_substring_does_not_contaminate():
    # '1등급1인가구' 가 같은 시트에 있다. 완전일치가 이겨야 한다.
    _assert_auto_pass("인정조사", "1등급", "1등급", "J13")


def test_j15_duplicate_anchor_is_fatal():
    # '상한액' 을 포함한 셀이 2개 — 추출기가 어느 쪽을 읽을지 정할 수 없다
    alerts = _alerts("ANCHOR_NOT_UNIQUE", "산정특례")
    assert alerts, "앵커 중복이 탐지되지 않음"
    assert alerts[0].fatal, "앵커 중복은 진행 불가 상태여야 함"


def test_j18_column_swap_detected_by_fingerprint():
    # 라벨 텍스트는 100% 일치한다. 구조 지문만이 볼 수 있는 사각지대.
    assert _alerts("HEADER_ORDER_CHANGED", "종합조사"), "열 순서 교체 미탐지"


def test_j14_unit_shift_detected_by_values():
    # 지원시간이 시간 -> 분(60배)으로 바뀌었다. 라벨은 그대로라 값만이 잡을 수 있다.
    assert _anomalies("UNIT_SHIFT_SUSPECTED", "인정조사"), "단위 이동 미탐지"


def test_j19_monotonicity_break_detected():
    assert _anomalies("MONOTONICITY_BROKEN", "고시 본문"), "단조성 파괴 미탐지"


# ── B. 컨트롤 — 정상 동작이 오탐하지 않는지 ──

def test_j10_new_label_flagged():
    for item in _report().items:
        if normalize(item.input_label.raw) == normalize("긴급돌봄"):
            assert "NEW_IN_TARGET" in item.flags, f"신규 라벨 플래그 없음 {item.flags}"
            return
    raise AssertionError("신규 라벨 '긴급돌봄' 항목이 없음")


def test_j11_deleted_label_not_auto_passed():
    item = _item("인정조사", "출산")
    assert item is not None, "'출산' 항목이 없음"
    assert item.status is not Status.AUTO_PASS, "삭제된 라벨이 자동 통과됨"


def test_j20_no_normalization_collision():
    # '기본 부담률' 과 '추가 부담률' 이 과잉 정규화로 같아지면 안 된다
    collisions = _alerts("NORMALIZATION_COLLISION")
    assert not collisions, f"정규화 충돌 {[a.detail for a in collisions]}"


def test_j21_unchanged_label_auto_passes():
    # 값(17270 -> 17790)만 바뀐 정상 갱신. 라벨 검증이 반응하면 안 된다.
    _assert_auto_pass("산정특례", "기본단가", "기본단가", "J21")


def test_j22_adjacent_tables_separated():
    # 고시 본문에 나란한 표 2개. 하나로 오인하면 이후 전 단계가 오염된다.
    workbook = loader.load(_support.BASELINE)
    regions = segmenter.find_tables("고시 본문", workbook.sheets["고시 본문"])
    assert len(regions) == 2, f"표가 {len(regions)}개로 분리됨, 기대 2개"


if __name__ == "__main__":
    summary = _report().summary
    print(f"{_report().baseline_file} -> {_report().target_file}")
    print(f"전체 {summary.total_labels} · auto_pass {summary.auto_passed} · "
          f"검토 {summary.needs_review} · 미매칭 {summary.unmatched}")
    print(f"구조 경보 {len(_report().structural_alerts)}건 · "
          f"값 이상 {len(_report().value_anomalies)}건\n")
    raise SystemExit(_support.run_module(dict(globals())))
