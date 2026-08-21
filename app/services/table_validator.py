from __future__ import annotations

import math
import os
from pathlib import Path

from dataclasses import dataclass, field

import pandas as pd

from services.price_table_parser import TIERS, ParsedRow, parse_name
from services.table_writer import ADD_CODE_INFO, TableWriter
from utils.rules import ruleConfig

# 조견표 추출 상수
K_UNIT_PRICE = "기본단가"
K_A_VALUE = "A값"
K_IJ_CAP = "인정조사 본인부담금 상한액"
K_SJ_CAP = "종합조사/산정특례 본인부담금 상한액"
K_IJ_BASIC_RATES = "인정조사 본인부담률 (기본급여)"
K_IJ_ADD_RATES = "인정조사 본인부담률 (추가급여)"
K_SJ_RATES = "종합조사/산정특례 본인부담률"
K_IJ_LIMITS = {
    "기본형": "인정조사 월한도액 (기본형)",
    "확장형": "인정조사 월한도액 (확장형)",
}
K_JH_LIMITS = {
    "기본형": "종합조사 월한도액 (기본형)",
    "확장형": "종합조사 월한도액 (확장형)",
}
K_ADD_LIMITS = "추가급여 월한도액"
K_PREV_UNIT_PRICE = "작년 기본단가"

# 기본,추가급여 단가표 공통으로 사용
C_SUPPORT = "지원량"
C_GOV = "정부지원금"
C_COPAY = "본인부담금"
C_CODE = "등급구분"
C_NAME = "등급명"

# 결제 단가표
P_SUPPORT = "지원량"
P_GOV = "정부지원금액"
P_COPAY = "본인부담금액"
P_GOV_RATE = "정부지원금율"
P_COPAY_RATE = "본인부담금율"
P_SERVICE = "서비스종유명"
P_TIME = "서비스시간명"
P_CODE = "등급구분"
P_UNIT = "단위기준단가"
P_UNIT_NIGHT = "단위기준심야단가"

# 추가급여 등급명
_ADD_BASE_TO_KEY = {info[1]: key for key, info in ADD_CODE_INFO.items()}


def floor_100(value):
    # 100원 단위 버림
    return int(math.floor(value / 100 + 1e-9) * 100)


def growth_rate(prev, curr):
    # 증가율(%). 작년이 0이면 계산 못하기에 None
    if not prev or curr is None:
        return None
    return round((curr - prev) / prev * 100, 2)


# 증가율 경고 임계값 정하기
GROWTH_TOLERANCE = 0.5  # (%p)폭 이상 벗어나면 경고

# 임계값을 알 수 없는 경우 사용하는 값
GROWTH_WARN_MAX = 4.0  # 이보다 크면 과도한 증가
GROWTH_WARN_MIN = 0.0  # 이보다 작으면 경고


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return (
            None
            if pd.isna(value)
            else (int(value) if float(value).is_integer() else float(value))
        )
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, AttributeError):
        return None


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.4g}"
    return f"{int(value):,}"


@dataclass
class CellIssue:
    row: int
    column: str | None
    reason: str
    expected: object = None
    actual: object = None
    fixes: tuple[str, ...] = ()
    extra: str = ""  # 부가 설명용

    def is_table_level(self) -> bool:
        return self.row < 0

    def title(self) -> str:
        if self.is_table_level():
            return f"[표 전체] {self.reason}"
        where = f"{self.row + 1}행"
        if self.column:
            where += f" · {self.column}"
        return f"{where} — {self.reason}"

    # 상세 본문(제목 제외) — 패널이 "[오류 n/m] 제목" 을 붙인 뒤 이어서 보여준다
    def body(self) -> str:
        lines = []
        if self.expected is not None or self.actual is not None:
            lines.append(
                f"  기대값 {_fmt(self.expected)}  /  실제값 {_fmt(self.actual)}"
            )
        if self.extra:
            # extra(계산 과정 등)의 모든 줄을 2칸 들여쓰기로 통일
            lines.extend(
                "  " + line.lstrip() if line.strip() else ""
                for line in self.extra.split("\n")
            )
        if self.fixes:
            lines.append("  수정 제안")
            lines.extend(f"  · {fix}" for fix in self.fixes)
        return "\n".join(lines)

    def detail(self) -> str:
        return f"{self.reason}\n{self.body()}"


@dataclass
class ValidationReport:
    issues: list[CellIssue] = field(default_factory=list)
    # 셀 클릭을 통해 그 셀의 이슈를 알 수 있음
    cells: dict[tuple[int, str], list[CellIssue]] = field(default_factory=dict)
    # 행 단위로 부담률과 증가율알기
    metrics: dict[int, str] = field(default_factory=dict)
    # 확인이 필요한 셀 경고 아이콘 넣는용도
    warn_cells: dict[tuple[int, str], str] = field(default_factory=dict)
    # 검증을 못 돌린 경우
    notice: str = ""

    # 이슈가 비어있으면 통과
    def passed(self) -> bool:
        return not self.issues and not self.notice

    # 이슈가 있을 경우 오류 있음 개수 반환, 이슈가 없는 경우 오류 없음
    def summary(self) -> str:
        if self.notice:
            return self.notice
        return "PASS — 오류 없음" if not self.issues else f"FAIL — {len(self.issues)}건"

    # 한 셀에 이슈가 여러개일 경우 리스트로 넣어준다
    def add(self, issue: CellIssue) -> None:
        self.issues.append(issue)
        if not issue.is_table_level() and issue.column:
            self.cells.setdefault((issue.row, issue.column), []).append(issue)

    # 셀 클릭시 사이드 패널 상세 띄우는 용도
    def issues_at(self, row: int, column: str) -> list[CellIssue]:
        return self.cells.get((row, column), [])


# 검증
class TableValidator:
    def __init__(self) -> None:
        self._writer = TableWriter()

    def validate(
        self,
        flow: str,
        tab_index: int,
        df: pd.DataFrame,
        values: dict | None,
        prev_df: pd.DataFrame | None = None,
        basic_df: pd.DataFrame | None = None,
    ) -> ValidationReport:
        if df is None or df.empty:
            report = ValidationReport()
            report.notice = "표가 비어 있어 검증할 내용이 없습니다."
            return report

        # table_viewer_page의 흐름의 문제
        if flow == "unit_price":
            v = self._unflatten(values)
            if not v:
                report = ValidationReport()
                report.notice = "조견표에서 추출한 값이 없어 검증을 건너뛰었습니다."
                return report
            if tab_index == 0:  # 기본급여단가표
                report = self._validate_basic(df, v)
            else:  # 추가급여단가표
                report = self._validate_add(df, v)
        else:  # notice_verify로 결제단가표
            report = self._validate_payment(df, basic_df, service_prices=values)

        # 작년
        if prev_df is not None:
            caps = self._collect_caps(values)
            raw = values or {}
            baseline = growth_rate(raw.get(K_PREV_UNIT_PRICE), raw.get(K_UNIT_PRICE))
            if flow == "unit_price":
                self._append_growth_metrics(report, df, prev_df, caps, baseline)
            else:
                self._append_growth_metrics_pay(report, df, prev_df, caps, baseline)
        return report

    # 본인부담금 상한액인 것
    @staticmethod
    def _collect_caps(values: dict | None) -> set[int]:
        caps: set[int] = set()
        for key, value in (values or {}).items():
            if "상한액" not in str(key):
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                caps.add(int(value))
        return caps

    # 값 꺼내기
    def _unflatten(self, values: dict | None) -> dict:
        params: dict = {}
        for key, value in (values or {}).items():
            self._writer._save_param(params, key, value)
        return params

    @staticmethod
    def _need(report: ValidationReport, values: dict, key: str):
        # 필요한 값이 없는 경우 전체 이슈이고 none
        value = values.get(key)
        if value is None or (isinstance(value, dict) and not value):
            report.add(
                CellIssue(
                    row=-1,
                    column=None,
                    reason=f"검증에 필요한 값이 없습니다: '{key}'",
                    extra="이전 단계(값 확인 화면)에서 이 값이 추출·입력됐는지 확인해 주세요.",
                )
            )
            return None
        return value

    # 기본급여 단가표
    def _validate_basic(self, df: pd.DataFrame, values: dict) -> ValidationReport:
        report = ValidationReport()

        ij_cap = self._need(report, values, K_IJ_CAP)
        sj_cap = self._need(report, values, K_SJ_CAP)
        ij_rates = self._need(report, values, K_IJ_BASIC_RATES) or {}
        sj_rates = self._need(report, values, K_SJ_RATES) or {}
        ij_limits = {v: values.get(k) or {} for v, k in K_IJ_LIMITS.items()}
        jh_limits = {v: values.get(k) or {} for v, k in K_JH_LIMITS.items()}

        # 특례 월한도액 생성
        sj_limits: dict[str, int] = {}
        # deduction = {"기본형": 0, "확장형": 0}
        base_limits = values.get(K_IJ_LIMITS["기본형"]) or {}
        add_limits = values.get(K_ADD_LIMITS) or {}
        unit_price = values.get(K_UNIT_PRICE)
        if base_limits and add_limits:
            try:
                sj_limits = self._writer._build_sj_limits(base_limits, add_limits)
            except Exception:
                sj_limits = {}
        # if unit_price:
        #     deduction["확장형"] = self._writer._sj_ext_deduction(int(unit_price))

        emergency_limit = (jh_limits["기본형"] or {}).get("13구간")

        for i in range(len(df.index)):
            row = df.iloc[i]
            name = str(row.get(C_NAME, "") or "")
            support = _num(row.get(C_SUPPORT))
            gov = _num(row.get(C_GOV))
            copay = _num(row.get(C_COPAY))
            if not name.strip():
                continue
            parsed = parse_name(name)

            # 고정 행 2개
            if parsed.kind == "special":
                if parsed.base == "긴급활동지원" and emergency_limit is not None:
                    if support != emergency_limit:
                        report.add(
                            CellIssue(
                                i,
                                C_SUPPORT,
                                "긴급활동지원 지원량이 종합조사 기본형 13구간 한도액과 다름",
                                expected=emergency_limit,
                                actual=support,
                                fixes=(
                                    f"{C_SUPPORT} {_fmt(support)} → {_fmt(emergency_limit)}",
                                ),
                            )
                        )
                    if copay not in (0, None):
                        report.add(
                            CellIssue(
                                i,
                                C_COPAY,
                                "긴급활동지원 본인부담금은 0이어야 함",
                                expected=0,
                                actual=copay,
                                fixes=(f"{C_COPAY} {_fmt(copay)} → 0",),
                            )
                        )
                if parsed.base == "부적합":
                    for col, value in (
                        (C_SUPPORT, support),
                        (C_GOV, gov),
                        (C_COPAY, copay),
                    ):
                        if value not in (0, None):
                            report.add(
                                CellIssue(
                                    i,
                                    col,
                                    "부적합 행의 금액은 모두 0이어야 함",
                                    expected=0,
                                    actual=value,
                                    fixes=(f"{col} {_fmt(value)} → 0",),
                                )
                            )
                self._check_sum(report, i, support, gov, copay)
                continue

            if parsed.kind == "unknown":
                report.add(
                    CellIssue(
                        i,
                        C_NAME,
                        "등급명 형식을 해석할 수 없음",
                        actual=None,
                        extra=f"등급명: {name!r}\n예: '1등급(다형)', '3구간(가형)_주간확장', '특례12(바형)'",
                    )
                )
                continue

            # 부담률, 상한액, 월한도액
            if parsed.kind == "ij":
                rates, cap = ij_rates, ij_cap
                expected_limit = (ij_limits[parsed.variant] or {}).get(parsed.base)
                limit_src = K_IJ_LIMITS[parsed.variant]
            elif parsed.kind == "jh":
                rates, cap = sj_rates, sj_cap
                expected_limit = (jh_limits[parsed.variant] or {}).get(parsed.base)
                limit_src = K_JH_LIMITS[parsed.variant]
            else:  # sj
                rates, cap = sj_rates, sj_cap
                expected_limit = sj_limits.get(parsed.base)
                if expected_limit is not None and parsed.variant == "확장형":
                    expected_limit = ruleConfig.calculate_extended_monthly_limit(
                        expected_limit, unit_price
                    )
                limit_src = "인정조사 월한도액(기본형)+추가급여 월한도액 조합"

            # 1) 지원량=월한도액
            if (
                expected_limit is not None
                and support is not None
                and support != expected_limit
            ):
                report.add(
                    CellIssue(
                        i,
                        C_SUPPORT,
                        "지원량이 조견표 월한도액과 다름",
                        expected=expected_limit,
                        actual=support,
                        fixes=(
                            f"{C_SUPPORT} {_fmt(support)} → {_fmt(expected_limit)}",
                        ),
                        extra=f"기준: {limit_src} [{parsed.base}]",
                    )
                )

            # 2) 본인부담금 재계산
            rate = rates.get(parsed.letter)
            expected_copay = None
            if rate is not None and support is not None and cap is not None:
                expected_copay = self._writer._resolve_copayment(
                    support, cap, parsed.letter, rate, parsed.variant
                )
                if copay is not None and copay != expected_copay:
                    report.add(
                        CellIssue(
                            i,
                            C_COPAY,
                            "본인부담금 재계산 값과 다름",
                            expected=expected_copay,
                            actual=copay,
                            fixes=(
                                f"{C_COPAY} {_fmt(copay)} → {_fmt(expected_copay)}",
                                f"동시에 {C_GOV} → {_fmt((support or 0) - expected_copay)}",
                            ),
                            extra=self._copay_formula_text(parsed, support, rate, cap),
                        )
                    )

            support_ok = expected_limit is not None and support == expected_limit
            copay_ok = expected_copay is not None and copay == expected_copay
            # 3) 지원량 = 정부지원금 + 본인부담금
            self._check_sum(
                report, i, support, gov, copay, support_ok=support_ok, copay_ok=copay_ok
            )

            # 4) 100원 단위 절사
            if copay is not None and copay != floor_100(copay):
                report.add(
                    CellIssue(
                        i,
                        C_COPAY,
                        "본인부담금이 100원 단위가 아님",
                        expected=floor_100(copay),
                        actual=copay,
                        fixes=(f"{C_COPAY} {_fmt(copay)} → {_fmt(floor_100(copay))}",),
                    )
                )

            # 5) 상한액 초과
            if cap is not None and copay is not None and copay > cap:
                report.add(
                    CellIssue(
                        i,
                        C_COPAY,
                        f"본인부담금이 상한액 {_fmt(cap)}원을 넘음",
                        expected=cap,
                        actual=copay,
                        fixes=(
                            f"{C_COPAY} {_fmt(copay)} → {_fmt(cap)}"
                            f" (동시에 {C_GOV} {_fmt(gov)} → {_fmt((support or 0) - cap)})",
                        ),
                    )
                )

            # 부담률
            self._check_rate_deviation(report, i, parsed, support, copay, rate, cap)
            report.metrics[i] = self._rate_metric_text(
                parsed, support, copay, rate, cap
            )

        # 표 전체 검증: 행 수와 소득형 결손, 등급 구분 중복여부
        expected_rows = (4 + 15 + 60) * len(
            TIERS
        ) * 2 + 2  # 인정4·구간15·특례60 x 6 x (기본/확장) + 고정 2
        # 사용자가 추가한 빈 행(등급명 없음)은 정원 외로 포함X
        expected_rows += sum(1 for n in df.get(C_NAME, []) if not str(n or "").strip())
        self._check_row_count(report, df, expected_rows)
        self._check_tier_groups(report, df, name_col=C_NAME)
        self._check_duplicate_codes(report, df)
        self._check_duplicate_names(report, df)
        return report

    # 추가급여
    def _validate_add(self, df: pd.DataFrame, values: dict) -> ValidationReport:
        report = ValidationReport()
        rates = self._need(report, values, K_IJ_ADD_RATES) or {}
        limits = self._need(report, values, K_ADD_LIMITS) or {}

        for i in range(len(df.index)):
            row = df.iloc[i]
            name = str(row.get(C_NAME, "") or "")
            support = _num(row.get(C_SUPPORT))
            gov = _num(row.get(C_GOV))
            copay = _num(row.get(C_COPAY))
            if not name.strip():
                continue
            parsed = parse_name(name)

            if parsed.kind != "add":
                report.add(
                    CellIssue(
                        i,
                        C_NAME,
                        "등급명 형식을 해석할 수 없음",
                        extra=f"등급명: {name!r}\n예: '출산가구_가형'",
                    )
                )
                continue

            # 1) 지원량 = 추가급여 월한도액
            limit_key = _ADD_BASE_TO_KEY.get(parsed.base)
            expected_limit = limits.get(limit_key) if limit_key else None
            if (
                expected_limit is not None
                and support is not None
                and support != expected_limit
            ):
                report.add(
                    CellIssue(
                        i,
                        C_SUPPORT,
                        "지원량이 추가급여 월한도액과 다름",
                        expected=expected_limit,
                        actual=support,
                        fixes=(
                            f"{C_SUPPORT} {_fmt(support)} → {_fmt(expected_limit)}",
                        ),
                        extra=f"기준: {K_ADD_LIMITS} [{limit_key}]",
                    )
                )

            # 2) 본인부담금 재계산 추가급여는 상한액없음
            rate = rates.get(parsed.letter)
            expected_copay = None
            if rate is not None and support is not None:
                expected_copay = ruleConfig.calculate_add_copayment(
                    support,
                    parsed.letter,
                    rate,
                )
                if copay is not None and copay != expected_copay:
                    if not rate:
                        formula = "가·나형은 추가급여 본인부담금이 면제되어 0원입니다."
                    else:
                        raw = support * rate
                        formula = (
                            "계산 과정 (추가급여는 상한액이 없습니다)\n"
                            f" ① 지원량 × 부담률 {rate * 100:g}% = {_fmt(support)} × {rate:g}"
                            f" = {raw:,.0f}원\n"
                            f" ② 100원 미만 버림 → {_fmt(floor_100(raw))}원\n"
                            f"∴ 본인부담금 = {_fmt(floor_100(raw))}원"
                        )
                    report.add(
                        CellIssue(
                            i,
                            C_COPAY,
                            "본인부담금 재계산 값과 다름",
                            expected=expected_copay,
                            actual=copay,
                            fixes=(
                                f"{C_COPAY} {_fmt(copay)} → {_fmt(expected_copay)}",
                                f"동시에 {C_GOV} → {_fmt((support or 0) - int(expected_copay))}",
                            ),
                            extra=formula,
                        )
                    )

            support_ok = expected_limit is not None and support == expected_limit
            copay_ok = expected_copay is not None and copay == expected_copay
            # 3) 지원량 = 정부지원금 + 본인부담금
            self._check_sum(
                report, i, support, gov, copay, support_ok=support_ok, copay_ok=copay_ok
            )

            # 4) 100원 단위 절사
            if copay is not None and copay != floor_100(copay):
                report.add(
                    CellIssue(
                        i,
                        C_COPAY,
                        "본인부담금이 100원 단위가 아님",
                        expected=floor_100(copay),
                        actual=copay,
                        fixes=(f"{C_COPAY} {_fmt(copay)} → {_fmt(floor_100(copay))}",),
                    )
                )

            # 부담률
            self._check_rate_deviation(
                report, i, parsed, support, copay, rate, cap=None
            )
            report.metrics[i] = self._rate_metric_text(
                parsed, support, copay, rate, cap=None
            )

        # 표 전체 검증: 행 수와 소득형(가~바), 등급 구분 중복여부
        expected_rows = len(ADD_CODE_INFO) * len(TIERS)  # 12 x 6 = 72
        # 사용자가 추가한 빈 행은 정원 외
        expected_rows += sum(1 for n in df.get(C_NAME, []) if not str(n or "").strip())
        self._check_row_count(report, df, expected_rows)
        self._check_tier_groups(report, df, name_col=C_NAME)
        self._check_duplicate_codes(report, df)
        self._check_duplicate_names(report, df)
        return report

    # 결제단가표
    # 기본급여 단가표와 대조한다 없을 경우 지원량, 금액과 율 상호 연관으로 특정
    def _validate_payment(
        self,
        df: pd.DataFrame,
        basic_df: pd.DataFrame | None = None,
        service_prices: dict | None = None,
    ) -> ValidationReport:
        report = ValidationReport()
        needed = {P_SUPPORT, P_GOV, P_COPAY}
        if not needed.issubset(set(map(str, df.columns))):
            report.notice = "결제단가표 검증은 준비 중입니다. (지원량/정부지원금액/본인부담금액 컬럼이 생기면 자동으로 검증합니다)"
            return report

        # 기본급여 표에서 등급구분 (지원량, 정부지원금, 본인부담금) 기준표
        grade_ref: dict[str, tuple[int, int, int]] = {}
        if basic_df is not None and {C_CODE, C_SUPPORT, C_GOV, C_COPAY}.issubset(
            set(map(str, basic_df.columns))
        ):
            for _, b in basic_df.iterrows():
                code = str(b.get(C_CODE, "") or "").strip()
                s, g, c = (
                    _num(b.get(C_SUPPORT)),
                    _num(b.get(C_GOV)),
                    _num(b.get(C_COPAY)),
                )
                if code and None not in (s, g, c):
                    grade_ref[code] = (s, g, c)

        # 서비스종류명, 서비스 시간명 별 기대 단가
        svc_ref: dict[tuple[str, str], tuple[int, int]] = {}
        if service_prices:
            try:
                for svc in self._writer._build_service_rows(service_prices):
                    svc_ref[(svc[P_SERVICE], svc[P_TIME])] = (
                        svc[P_UNIT],
                        svc[P_UNIT_NIGHT],
                    )
            except (ValueError, KeyError):
                pass
        has_units = {P_UNIT, P_UNIT_NIGHT}.issubset(set(map(str, df.columns)))

        has_rates = {P_GOV_RATE, P_COPAY_RATE}.issubset(set(map(str, df.columns)))
        for i in range(len(df.index)):
            row = df.iloc[i]
            support = _num(row.get(P_SUPPORT))
            gov = _num(row.get(P_GOV))
            copay = _num(row.get(P_COPAY))
            if None in (support, gov, copay):
                continue

            gov_rate = copay_rate = None
            if has_rates:
                try:
                    gov_rate = float(row.get(P_GOV_RATE))
                except (TypeError, ValueError):
                    gov_rate = None
                try:
                    copay_rate = float(row.get(P_COPAY_RATE))
                except (TypeError, ValueError):
                    copay_rate = None

            code = str(row.get(C_CODE, "") or "").strip()
            ref = grade_ref.get(code)

            if ref is not None:
                # 기본급여 표 기준 대조
                ref_s, ref_g, ref_c = ref

                # 1) 지원량부터 틀리면 나머지 대조는 기준이 없으므로 중단
                if support != ref_s:
                    report.add(
                        CellIssue(
                            i,
                            P_SUPPORT,
                            f"지원량이 기본급여 단가표({code})와 다름",
                            expected=ref_s,
                            actual=support,
                            fixes=(f"{P_SUPPORT} {_fmt(support)} → {_fmt(ref_s)}",),
                            extra="결제단가의 지원량은 같은 등급구분의 기본급여 지원량과 같아야 합니다.\n"
                            "지원량을 먼저 바로잡은 뒤 재검증하면 금액·율도 검사됩니다.",
                        )
                    )
                else:
                    # 2) 지원량이 맞음 -> 정부지원금액·본인부담금액 대조
                    if gov != ref_g:
                        report.add(
                            CellIssue(
                                i,
                                P_GOV,
                                f"정부지원금액이 기본급여 단가표({code})와 다름",
                                expected=ref_g,
                                actual=gov,
                                fixes=(f"{P_GOV} {_fmt(gov)} → {_fmt(ref_g)}",),
                            )
                        )
                    if copay != ref_c:
                        report.add(
                            CellIssue(
                                i,
                                P_COPAY,
                                f"본인부담금액이 기본급여 단가표({code})와 다름",
                                expected=ref_c,
                                actual=copay,
                                fixes=(f"{P_COPAY} {_fmt(copay)} → {_fmt(ref_c)}",),
                            )
                        )
                    # 3) 퍼센트(율) 기본급여 금액으로 계산한 값과 대조
                    if has_rates:
                        for col, rate, expected_rate in (
                            (
                                P_GOV_RATE,
                                gov_rate,
                                0 if ref_s == 0 else round(ref_g / ref_s, 10),
                            ),
                            (
                                P_COPAY_RATE,
                                copay_rate,
                                0 if ref_s == 0 else round(ref_c / ref_s, 10),
                            ),
                        ):
                            if rate is not None and abs(rate - expected_rate) > 1e-9:
                                report.add(
                                    CellIssue(
                                        i,
                                        col,
                                        f"{col}이 기본급여 기준 계산값과 다름",
                                        expected=expected_rate,
                                        actual=rate,
                                        fixes=(f"{col} {rate} → {expected_rate}",),
                                        extra=f"{col} = 기본급여 금액 ÷ 지원량 ({code} 기준)",
                                    )
                                )
            else:
                # 기준표 없음(폴백): 금액·율 상호 연관으로 범인 특정
                self._check_payment_consistency(
                    report, i, support, gov, copay, gov_rate, copay_rate
                )

            # 100원 단위 절사
            if copay and copay != floor_100(copay):
                report.add(
                    CellIssue(
                        i,
                        P_COPAY,
                        "본인부담금액이 100원 단위가 아님",
                        expected=floor_100(copay),
                        actual=copay,
                        fixes=(f"{P_COPAY} {_fmt(copay)} → {_fmt(floor_100(copay))}",),
                    )
                )

        # (등급구분 x 서비스종류 x 서비스시간) 중복
        if {P_CODE, P_SERVICE, P_TIME}.issubset(set(map(str, df.columns))):
            seen: dict[tuple, int] = {}
            for i in range(len(df.index)):
                row = df.iloc[i]
                key = (row.get(P_CODE), row.get(P_SERVICE), row.get(P_TIME))
                if key in seen:
                    report.add(
                        CellIssue(
                            i,
                            P_CODE,
                            f"중복 행: {seen[key] + 1}행과 키가 같음",
                            fixes=(f"{i + 1}행 또는 {seen[key] + 1}행 중 하나 삭제",),
                        )
                    )
                else:
                    seen[key] = i

                # 고시 단가 대조 확인
                if svc_ref and has_units:
                    service = str(row.get(P_SERVICE, "") or "").strip()
                    time_name = str(row.get(P_TIME, "") or "").strip()
                    ref = svc_ref.get((service, time_name))
                    if ref is not None:
                        exp_day, exp_night = ref
                        day = _num(row.get(P_UNIT))
                        night = _num(row.get(P_UNIT_NIGHT))
                        if day is not None and day != exp_day:
                            report.add(
                                CellIssue(
                                    i,
                                    P_UNIT,
                                    "단위기준단가가 고시 기준 계산값과 다름",
                                    expected=exp_day,
                                    actual=day,
                                    fixes=(f"{P_UNIT} {_fmt(day)} -> {_fmt(exp_day)}",),
                                    extra=f"기준: 고시단가 X 시간 변환 규칙 ({service}/{time_name})",
                                )
                            )
                        if night is not None and night != exp_night:
                            report.add(
                                CellIssue(
                                    i,
                                    P_UNIT_NIGHT,
                                    "단위기준심야단가가 고시 기준 계산값과 다름",
                                    expected=exp_night,
                                    actual=night,
                                    fixes=(
                                        f"{P_UNIT_NIGHT} {_fmt(night)} -> {_fmt(exp_night)}",
                                    ),
                                )
                            )
        return report

    # 결제단가 폴백 검사: 금액·율 다섯 값의 상호 연관으로 추측
    # 관계식 1. 정부지원금액+본인부담금액=지원량 2. 정부지원금율=정부지원금액/지원량 3. 본인부담금율=본인부담금액/지원량  (4. 율 합=1 은 ①②③이 맞으면 자동 성립)
    @staticmethod
    def _check_payment_consistency(
        report, i, support, gov, copay, gov_rate, copay_rate
    ):
        TOL = 1e-6
        if not support:
            return
        sum_ok = gov + copay == support
        gr_ok = None if gov_rate is None else abs(gov_rate - gov / support) <= TOL
        cr_ok = None if copay_rate is None else abs(copay_rate - copay / support) <= TOL

        exp_gr = round(gov / support, 10)
        exp_cr = round(copay / support, 10)

        if gr_ok is None or cr_ok is None:
            # 율이 없으면 합계만 검사
            if not sum_ok:
                report.add(
                    CellIssue(
                        i,
                        P_SUPPORT,
                        "지원량 ≠ 정부지원금액 + 본인부담금액",
                        expected=support,
                        actual=gov + copay,
                        fixes=(
                            f"{P_GOV} {_fmt(gov)} → {_fmt(support - copay)}",
                            f"{P_COPAY} {_fmt(copay)} → {_fmt(support - gov)}",
                            f"{P_SUPPORT} {_fmt(support)} → {_fmt(gov + copay)}",
                        ),
                    )
                )
            # 율이 1개만 없으면 율 있는 쪽 검사
            if gr_ok is False:
                report.add(
                    CellIssue(
                        i,
                        P_GOV_RATE,
                        "정부지원금율이 금액과 다름",
                        expected=exp_gr,
                        actual=gov_rate,
                        fixes=(f"{P_GOV_RATE} {gov_rate} → {exp_gr}",),
                    )
                )
            if cr_ok is False:
                report.add(
                    CellIssue(
                        i,
                        P_COPAY_RATE,
                        "본인부담금율이 금액과 다름",
                        expected=exp_cr,
                        actual=copay_rate,
                        fixes=(f"{P_COPAY_RATE} {copay_rate} → {exp_cr}",),
                    )
                )
            return

        if sum_ok and gr_ok and cr_ok:
            return  # 전부 일관

        # 금액이 맞고 율이 틀린경우
        if sum_ok and gr_ok and not cr_ok:
            report.add(
                CellIssue(
                    i,
                    P_COPAY_RATE,
                    "본인부담금율이 틀림 (금액·정부지원금율은 서로 일치)",
                    expected=exp_cr,
                    actual=copay_rate,
                    fixes=(f"{P_COPAY_RATE} {copay_rate} → {exp_cr}",),
                    extra=f"본인부담금율 = 본인부담금액 ÷ 지원량 = 1 − 정부지원금율 = {exp_cr}",
                )
            )
            return
        if sum_ok and cr_ok and not gr_ok:
            report.add(
                CellIssue(
                    i,
                    P_GOV_RATE,
                    "정부지원금율이 틀림 (금액·본인부담금율은 서로 일치)",
                    expected=exp_gr,
                    actual=gov_rate,
                    fixes=(f"{P_GOV_RATE} {gov_rate} → {exp_gr}",),
                    extra=f"정부지원금율 = 정부지원금액 ÷ 지원량 = 1 − 본인부담금율 = {exp_gr}",
                )
            )
            return
        if sum_ok:  # 두 율이 모두 어긋남 각각 금액 기준으로 지목
            report.add(
                CellIssue(
                    i,
                    P_GOV_RATE,
                    "정부지원금율이 금액과 다름",
                    expected=exp_gr,
                    actual=gov_rate,
                    fixes=(f"{P_GOV_RATE} {gov_rate} → {exp_gr}",),
                )
            )
            report.add(
                CellIssue(
                    i,
                    P_COPAY_RATE,
                    "본인부담금율이 금액과 다름",
                    expected=exp_cr,
                    actual=copay_rate,
                    fixes=(f"{P_COPAY_RATE} {copay_rate} → {exp_cr}",),
                )
            )
            return

        if gr_ok and abs(copay_rate - (support - gov) / support) <= TOL:
            report.add(
                CellIssue(
                    i,
                    P_COPAY,
                    "본인부담금액이 틀림 (지원량·정부지원금액·율과 대조)",
                    expected=support - gov,
                    actual=copay,
                    fixes=(f"{P_COPAY} {_fmt(copay)} → {_fmt(support - gov)}",),
                    extra="본인부담금액 = 지원량 − 정부지원금액 (본인부담금율과도 일치)",
                )
            )
            return
        if cr_ok and abs(gov_rate - (support - copay) / support) <= TOL:
            report.add(
                CellIssue(
                    i,
                    P_GOV,
                    "정부지원금액이 틀림 (지원량·본인부담금액·율과 대조)",
                    expected=support - copay,
                    actual=gov,
                    fixes=(f"{P_GOV} {_fmt(gov)} → {_fmt(support - copay)}",),
                    extra="정부지원금액 = 지원량 − 본인부담금액 (정부지원금율과도 일치)",
                )
            )
            return
        alt = gov + copay
        if (
            alt
            and abs(gov_rate - gov / alt) <= TOL
            and abs(copay_rate - copay / alt) <= TOL
        ):
            report.add(
                CellIssue(
                    i,
                    P_SUPPORT,
                    "지원량이 틀림 (금액 합·두 율과 대조)",
                    expected=alt,
                    actual=support,
                    fixes=(f"{P_SUPPORT} {_fmt(support)} → {_fmt(alt)}",),
                    extra="두 율이 (정부지원금액+본인부담금액) 기준과 일치하므로 지원량이 잘못된 값입니다.",
                )
            )
            return

        # 모든 내역이 틀린 경우
        report.add(
            CellIssue(
                i,
                P_SUPPORT,
                "지원량 ≠ 정부지원금액 + 본인부담금액",
                expected=support,
                actual=gov + copay,
                fixes=(
                    f"{P_GOV} {_fmt(gov)} → {_fmt(support - copay)}",
                    f"{P_COPAY} {_fmt(copay)} → {_fmt(support - gov)}",
                    f"{P_SUPPORT} {_fmt(support)} → {_fmt(gov + copay)}",
                ),
                extra="여러 값이 함께 어긋나 자동 판정이 어렵습니다. 아래 율 오류와 함께 확인해 주세요.",
            )
        )
        if not gr_ok:
            report.add(
                CellIssue(
                    i,
                    P_GOV_RATE,
                    "정부지원금율이 금액과 다름",
                    expected=exp_gr,
                    actual=gov_rate,
                    fixes=(f"{P_GOV_RATE} {gov_rate} → {exp_gr}",),
                )
            )
        if not cr_ok:
            report.add(
                CellIssue(
                    i,
                    P_COPAY_RATE,
                    "본인부담금율이 금액과 다름",
                    expected=exp_cr,
                    actual=copay_rate,
                    fixes=(f"{P_COPAY_RATE} {copay_rate} → {exp_cr}",),
                )
            )

    @staticmethod
    def _check_sum(report, i, support, gov, copay, support_ok=None, copay_ok=None):
        # support_ok / copay_ok: 조견표·재계산과 대조한 결과 (None=모름)
        if None in (support, gov, copay):
            return
        if gov + copay == support:
            return

        # 확정된 사실로 범인을 좁힌다
        if support_ok and copay_ok:
            # 지원량·본인부담금이 조견표와 일치 → 정부지원금이 범인
            report.add(
                CellIssue(
                    i,
                    C_GOV,
                    "정부지원금이 맞지 않음 (지원량·본인부담금은 조견표와 일치)",
                    expected=support - copay,
                    actual=gov,
                    fixes=(f"{C_GOV} {_fmt(gov)} → {_fmt(support - copay)}",),
                    extra="정부지원금 = 지원량 − 본인부담금",
                )
            )
        elif support_ok:
            # 지원량은 조견표와 일치 → 지원량 탓이 아님
            report.add(
                CellIssue(
                    i,
                    C_GOV,
                    "정부지원금 + 본인부담금이 지원량과 맞지 않음"
                    " (지원량은 조견표와 일치하므로 오른쪽 두 값의 문제)",
                    expected=support,
                    actual=gov + copay,
                    fixes=(
                        f"{C_GOV} {_fmt(gov)} → {_fmt(support - copay)}",
                        f"{C_COPAY} {_fmt(copay)} → {_fmt(support - gov)}",
                    ),
                )
            )
        else:
            # 판단 근거 없음 → 기존처럼 세 가지 다 제시
            report.add(
                CellIssue(
                    i,
                    C_SUPPORT,
                    "지원량 ≠ 정부지원금 + 본인부담금",
                    expected=support,
                    actual=gov + copay,
                    fixes=(
                        f"{C_GOV} {_fmt(gov)} → {_fmt(support - copay)}",
                        f"{C_COPAY} {_fmt(copay)} → {_fmt(support - gov)}",
                        f"{C_SUPPORT} {_fmt(support)} → {_fmt(gov + copay)}",
                    ),
                )
            )

    @staticmethod
    def _check_row_count(
        report: ValidationReport, df: pd.DataFrame, expected: int
    ) -> None:
        # 행 개수 검사
        if len(df.index) != expected:
            report.add(
                CellIssue(
                    -1,
                    None,
                    f"행 개수가 예상과 다름 (예상 {expected:,} / 실제 {len(df.index):,})",
                    expected=expected,
                    actual=len(df.index),
                )
            )

    @staticmethod
    def _check_tier_groups(
        report: ValidationReport, df: pd.DataFrame, name_col: str
    ) -> None:
        # 소득형 빠짐 확인
        groups: dict[tuple[str, str], set[str]] = {}
        for name in df.get(name_col, pd.Series(dtype=object)):
            parsed = parse_name(str(name or ""))
            if parsed.kind in ("ij", "jh", "sj", "add"):
                groups.setdefault((parsed.base, parsed.variant), set()).add(
                    parsed.letter
                )

        for (base, variant), letters in groups.items():
            if len(letters) != len(TIERS):
                missing = [f"{t}형" for t in TIERS if t not in letters]
                label = base + ("" if variant == "기본형" else "_주간확장")
                report.add(
                    CellIssue(
                        -1,
                        None,
                        f"'{label}' 그룹에 소득형이 빠짐: {', '.join(missing)}",
                    )
                )

    @staticmethod
    def _check_duplicate_codes(report: ValidationReport, df: pd.DataFrame) -> None:
        # 등급코드 중복행 채크
        if C_CODE not in df.columns:
            return
        seen: dict[str, int] = {}
        for i, code in enumerate(df[C_CODE]):
            code = str(code or "").strip()
            if not code:
                continue
            if code in seen:
                report.add(
                    CellIssue(
                        i,
                        C_CODE,
                        f"등급구분 '{code}' 중복 ({seen[code] + 1}행과 같음)",
                        fixes=(f"{i + 1}행 또는 {seen[code] + 1}행의 등급구분을 수정",),
                    )
                )
            else:
                seen[code] = i

    @staticmethod
    def _check_duplicate_names(report: ValidationReport, df: pd.DataFrame) -> None:
        # 등급명 중복행 채크
        # (등급명이 지원량·본인부담금을 결정하므로, 중복이면 같은 등급이 두 번 정의된 것)
        if C_NAME not in df.columns:
            return
        seen: dict[str, int] = {}
        for i, name in enumerate(df[C_NAME]):
            name = str(name or "").strip()
            if not name:
                continue
            if name in seen:
                report.add(
                    CellIssue(
                        i,
                        C_NAME,
                        f"등급명 '{name}' 중복 ({seen[name] + 1}행과 같음)",
                        fixes=(
                            f"{i + 1}행 또는 {seen[name] + 1}행 중 하나를 확인/삭제",
                        ),
                    )
                )
            else:
                seen[name] = i

    @staticmethod
    def _rate_text(rate) -> str:
        if rate is None:
            return "?"
        # 다~바는 소수(0.06) 요율, 나형은 정액(20000원)이 그대로 온다
        if isinstance(rate, float) and rate < 1:
            return f"{rate * 100:g}%"
        return f"정액 {int(rate):,}원"

    # 부담률 경고용
    def _check_rate_deviation(
        self,
        report: ValidationReport,
        i: int,
        parsed: ParsedRow,
        support,
        copay,
        rate,
        cap,
    ) -> None:
        if parsed.letter in ("가", "나"):
            return
        if support == 0:
            return  # 월한도액이 0원인 경우
        if not (isinstance(rate, float) and rate < 1) or not support or copay is None:
            return
        if cap is not None and floor_100(support * rate) >= cap:
            return  # 상한 적용
        if (i, C_COPAY) in report.cells:
            return  # 이 셀에 이미 오류가 있음
        stated = rate * 100
        actual = copay / support * 100
        tolerance = 100 / support * 100  # 100원 절사로 생길 수 있는 최대 차이(%p)
        if abs(actual - stated) <= tolerance + 1e-9:
            return
        report.warn_cells[(i, C_COPAY)] = (
            f"본인부담률이 조견표와 다름 (조견표 {stated:g}% · 실제 {actual:.2f}%)"
        )

    # 부담률
    def _rate_metric_text(self, parsed: ParsedRow, support, copay, rate, cap) -> str:
        lines = [
            f"{parsed.base}({parsed.letter}형)"
            + ("" if parsed.variant == "기본형" else " · 주간확장")
        ]
        if parsed.letter == "가":
            lines.append("부담률: 면제 (기초수급자)")
        elif parsed.letter == "나":
            lines.append(
                "부담률: "
                + (
                    "면제 (확장형 차상위)"
                    if parsed.variant == "확장형"
                    else f"{self._rate_text(rate)} (차상위)"
                )
            )
        elif support == 0:
            lines.append("부담률: 없음 (월한도액 0원)")
        elif rate is not None and support:
            actual = (copay or 0) / support * 100
            stated = rate * 100 if isinstance(rate, float) and rate < 1 else None
            capped = bool(
                cap
                and isinstance(rate, float)
                and rate < 1
                and floor_100(support * rate) >= cap
            )

            line = f"부담률: 조견표 {self._rate_text(rate)} · 실제 {actual:.2f}%"
            if stated is not None:
                line += f" · 차이 {actual - stated:+.2f}%"
            if capped:
                line += "  ← 상한 적용"
            lines.append(line)
            lines.append("※ 100원 절사로 실제가 조금 낮게 나오는 것은 정상")
        return "\n".join(lines)

    @staticmethod
    def _copay_formula_text(parsed: ParsedRow, support, rate, cap) -> str:
        # 본인부담금이 어떻게 계산되는지 단계별로 풀어서 설명한다.
        if parsed.letter == "가":
            return "가형(기초수급자)은 본인부담금이 면제되어 0원입니다."
        if parsed.letter == "나":
            if parsed.variant == "확장형":
                return "나형(차상위)은 확장형(주간확장)에서 본인부담금이 면제되어 0원입니다."
            return (
                "나형(차상위)은 비율이 아니라 정액으로 부담합니다.\n"
                f" · 정액 {int(rate):,}원과 상한액 {_fmt(cap)}원 중 작은 금액\n"
                f"∴ 본인부담금 = {_fmt(min(int(rate), cap) if cap is not None else int(rate))}원"
            )
        # 다~바형: 요율 → 절사 → 상한 비교 순서로 실제 숫자를 보여준다
        raw = support * rate
        floored = floor_100(raw)
        lines = [
            "계산 과정",
            f" ① 지원량 × 부담률 {rate * 100:g}% = {_fmt(support)} × {rate:g}"
            f" = {raw:,.0f}원",
            f" ② 100원 미만 버림 → {_fmt(floored)}원",
        ]
        if cap is None:
            lines.append(f"∴ 본인부담금 = {_fmt(floored)}원")
        elif floored >= cap:
            lines.append(
                f" ③ 상한액 {_fmt(cap)}원과 비교 → 상한액이 더 작으므로 상한액 적용"
            )
            lines.append(f"∴ 본인부담금 = {_fmt(cap)}원 (상한 적용)")
        else:
            lines.append(
                f" ③ 상한액 {_fmt(cap)}원과 비교 → 계산값이 더 작으므로 그대로 적용"
            )
            lines.append(f"∴ 본인부담금 = {_fmt(floored)}원")
        return "\n".join(lines)

    def _warn_growth(
        self,
        report: ValidationReport,
        i: int,
        col: str,
        g: float | None,
        capped: bool = False,
        baseline=None,
    ) -> None:
        # 증가율이 정상범위 넘어가면 노란색 경고
        if g is None:
            return
        if baseline is not None:
            if capped:
                return
            diff = g - baseline
            if abs(diff) <= GROWTH_TOLERANCE:
                return
            direction = "높음" if diff > 0 else "낮음"
            msg = (
                f"작년 대비 증가율 {g:+.2f}%  기본단가 인상률 {baseline:+.2f}%보다"
                f" {abs(diff):.2f}%p {direction}"
            )
        else:
            if g > GROWTH_WARN_MAX:
                msg = (
                    f"작년 대비 증가율 {g:+.2f}%  과도한 증가"
                    f" (기준 +{GROWTH_WARN_MAX:g}% 초과)"
                )
            elif g < GROWTH_WARN_MIN:
                msg = f"작년 대비 증가율 {g:+.2f}%  작년보다 감소"
            else:
                return
        if capped:
            msg += "(상한액 적용 부분)"
        if (i, col) in report.cells:
            return
        old = report.warn_cells.get((i, col))
        report.warn_cells[(i, col)] = f"{old}\n{msg}" if old else msg

    def _append_growth_metrics(
        self,
        report: ValidationReport,
        df: pd.DataFrame,
        prev_df: pd.DataFrame,
        caps: set[int] | None = None,
        baseline=None,
    ) -> None:
        # 과거 단가표와 비교해 증가율
        if C_CODE not in df.columns or C_CODE not in prev_df.columns:
            return
        caps = caps or set()
        prev_by_code = {
            str(row.get(C_CODE, "") or "").strip(): row for _, row in prev_df.iterrows()
        }
        head = "증가율(비교단가)"
        if baseline is not None:
            head += f" [기본단가 인상률 {baseline:+.2f}% 기준]"
        cap_pairs: dict[int, int] = {}
        for i in range(len(df.index)):
            row = df.iloc[i]
            old = prev_by_code.get(str(row.get(C_CODE, "") or "").strip())
            if old is None:
                extra = "증가율: 작년 단가표에 없던 항목"
            else:
                parts = []
                for col in (C_SUPPORT, C_GOV, C_COPAY):
                    curr = _num(row.get(col))
                    prev = _num(old.get(col))
                    g = growth_rate(prev, curr)
                    capped = col == C_COPAY and curr is not None and int(curr) in caps
                    if capped and prev:
                        cap_pairs.setdefault(int(curr), int(prev))
                    text = f"{col} {'-' if g is None else f'{g:+.2f}%'}"
                    parts.append(text + (" (상한 적용)" if capped else ""))
                    self._warn_growth(
                        report, i, col, g, capped=capped, baseline=baseline
                    )
                extra = head + ": " + " · ".join(parts)
            report.metrics[i] = (report.metrics.get(i, "") + "\n" + extra).strip()

    def _append_growth_metrics_pay(
        self,
        report: ValidationReport,
        df: pd.DataFrame,
        prev_df: pd.DataFrame,
        caps: set[int] | None = None,
        baseline=None,
    ) -> None:
        # 과거 결제 단가표와 비교해 증가율
        caps = caps or set()
        if P_CODE not in df.columns or P_CODE not in prev_df.columns:
            return
        prev_by_code = {
            str(row.get(P_CODE, "") or "").strip(): row for _, row in prev_df.iterrows()
        }
        head = "증가율(비교단가)"
        if baseline is not None:
            head += f" [기본단가 인상률 {baseline:+.2f}% 기준]"
        cap_pairs: dict[int, int] = {}
        for i in range(len(df.index)):
            row = df.iloc[i]
            old = prev_by_code.get(str(row.get(P_CODE, "") or "").strip())
            if old is None:
                extra = "증가율: 작년 단가표에 없던 항목"
            else:
                parts = []
                for col in (P_SUPPORT, P_GOV, P_COPAY):
                    curr = _num(row.get(col))
                    prev = _num(old.get(col))
                    g = growth_rate(prev, curr)
                    capped = col == P_COPAY and curr is not None and int(curr) in caps
                    if capped and prev:
                        cap_pairs.setdefault(int(curr), int(prev))
                    text = f"{col} {'-' if g is None else f'{g:+.2f}%'}"
                    parts.append(text + (" (상한 적용)" if capped else ""))
                    self._warn_growth(
                        report, i, col, g, capped=capped, baseline=baseline
                    )
                extra = head + ": " + " · ".join(parts)
            report.metrics[i] = (report.metrics.get(i, "") + "\n" + extra).strip()


def read_prev_table(path: str) -> pd.DataFrame:
    # '작년 단가표 불러오기' 버튼용 등급구분/지원량/정부지원금/본인부담금만 있으면 된다.
    cached = _read_table_cache(path)
    if cached is not None:
        return cached
    df = pd.read_excel(path, engine="openpyxl")
    _write_table_cache(path, df)
    return df


# --- 단가표 로딩 캐시 -------------------------------------------------------
# 캐시는 순수한 가속 장치다: 어떤 실패든 조용히 무시하고 원래 경로로 읽는다.

_CACHE_KEEP = 8  # 이 개수를 넘으면 오래된 캐시부터 지운다


def _table_cache_file(path: str) -> Path:
    import hashlib
    from utils.appdata import user_data_dir

    stat = os.stat(path)
    key = f"{Path(path).resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    folder = user_data_dir() / "table_cache"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}.pkl"


def _read_table_cache(path: str) -> pd.DataFrame | None:
    try:
        file = _table_cache_file(path)
        if file.exists():
            return pd.read_pickle(file)
    except Exception:
        pass
    return None


def _write_table_cache(path: str, df: pd.DataFrame) -> None:
    try:
        file = _table_cache_file(path)
        df.to_pickle(file)
        stale = sorted(
            file.parent.glob("*.pkl"), key=lambda p: p.stat().st_mtime, reverse=True
        )[_CACHE_KEEP:]
        for old in stale:
            old.unlink(missing_ok=True)
    except Exception:
        pass
