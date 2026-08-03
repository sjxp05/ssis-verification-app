from __future__ import annotations
from datetime import datetime
import pandas as pd
import itertools
import re

from models.dto import UploadedFile

JOGYEON_SHEET_NAMES = ["인정조사", "산정특례", "종합조사"]

# 조견표에서 찾는 문구 상수로 정리 - 서식 변경시 여기만 변경
BASE_PRICE = "기본단가"
A_VALUE = "A값"
BASIC_RATE = "기본 부담률"
CAP_LABEL = "상한액"
GRADE_HEADER = "활동지원등급"
INCOME_HEADER = "기준중위소득"
JH_BASIC = "주간활동 기본형"
JH_EXTENDED = "주간활동 확장형"

IJ_GRADES = tuple(f"{i}등급" for i in range(1, 5))
JH_ZONES = tuple(f"{i}등급" for i in range(1, 16))
JH_LABELS = tuple(f"{i}구간" for i in range(1, 16))
RATE_GRADES = ("다", "라", "마", "바")
# 조견표 위쪽 테이블에는 없는 가형/나형의 고정 금액
# 기초수급자(가)는 항상 면제, 차상위(나)는 정액 부담, 추가급여는 기초·차상위 모두 면제
FIXED_BASIC_RATE = {"가": 0, "나": 20000}
FIXED_ADD_RATE = {"가": 0, "나": 0}

ADD_ITEMS = (
    "최중증1인가구",
    "1등급1인가구",
    "2등급이하1인가구",
    "최중증취약가구",
    "1등급취약가구",
    "2등급이하취약가구",
    "출산",
    "자립준비",
    "학교생활",
    "직장생활",
    "보호자일시부재",
    "나머지가구구성원의직장생활등",
)

# 공백·줄바꿈·비단절공백
_WS = re.compile(r"[\s ]+")


class ExtractError(Exception):
    """에러용 클래스"""


class ValueExtractor:
    # _WS 처리
    def _squeeze(self, text):
        return _WS.sub("", str(text))

    # 파일 읽고 원본(df)과 공백 제거한 검색용 사본(norm)을 함께 반환
    def _load(self, file_path, sheet_name):
        df = pd.read_excel(file_path, sheet_name, engine="openpyxl", header=None)
        norm = df.astype(str).apply(lambda s: s.str.replace(_WS, "", regex=True))
        return df, norm

    # 키워드가 나오는 모든 칸을 읽는 순서(위→아래, 왼→오른쪽)로 반환
    def _find_all(self, norm, keyword):
        key = self._squeeze(keyword)
        # 모든 칸을 True, False 로 표시
        hit = norm.apply(lambda s: s.str.contains(key, regex=False, na=False))
        found = sorted(
            (int(r), int(c)) for r, c in zip(*hit.to_numpy().nonzero(), strict=True)
        )
        if not found:
            raise ExtractError(f"'{keyword}'를 찾지 못했습니다.")
        return found

    # 한 곳에만 있어야 하는 문구, 여러 번 나오면 예외
    def _find_one(self, norm, keyword):
        found = self._find_all(norm, keyword)
        if len({r for r, _ in found}) > 1:
            raise ExtractError(f"'{keyword}'가 여러 표에 있습니다")
        return found[0]

    # 여러 곳에 반복되는 게 정상인 문구. 첫 번째만 쓴다
    def _find_first(self, norm, keyword):
        return self._find_all(norm, keyword)[0]

    # 엑셀에서 온 value 받아서 계산가능한 숫자로 반환
    def _num(self, value):
        item = getattr(value, "item", None)
        value = item() if callable(item) else value

        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if numeric and not pd.isna(value):
            return int(value) if float(value).is_integer() else float(value)

        text = self._squeeze(value).replace(",", "").replace("%", "")
        if text.lower() in ("", "nan", "none"):
            raise ExtractError("값이 비어 있습니다")
        try:
            number = float(text)
        except ValueError:
            raise ExtractError(f"수치로 읽을 수 없는 값: {value!r}") from None
        return int(number) if number.is_integer() else number

    # 인정조사 시트 읽고 A값, 본인부담금 상한액, 본인부담률 등 값 반환
    def read_ij_value(self, file_path, sheet_name):
        # 파일 열기
        df, norm = self._load(file_path, sheet_name)

        # A값, 본인부담금 상한액
        r, c = self._find_one(norm, A_VALUE)
        a_value = self._num(df.iat[r, c + 1])
        copay_cap = self._num(df.iat[r, c + 2])

        # 기본단가
        r, c = self._find_one(norm, BASE_PRICE)
        base_price = self._num(df.iat[r, c + 1])

        # 본인 부담률 - 가·나는 고정값, 다~바는 조견표에서 읽는다
        r, c = self._find_one(norm, BASIC_RATE)
        basic_rates = {
            **FIXED_BASIC_RATE,
            **{
                g: self._num(df.iat[r, c + i])
                for i, g in enumerate(RATE_GRADES, start=1)
            },
        }
        add_rates = {
            **FIXED_ADD_RATE,
            **{
                g: self._num(df.iat[r + 1, c + i])
                for i, g in enumerate(RATE_GRADES, start=1)
            },
        }

        # 월 한도액
        r, c = self._find_one(norm, GRADE_HEADER)
        base_r, base_c = r + 2, c
        row_map: dict[str, int] = {}
        for i in range(5):
            if base_r + i >= len(norm.index):
                break
            name = norm.iat[base_r + i, base_c]
            if name in IJ_GRADES and name not in row_map:
                row_map[name] = i

        missing = [g for g in IJ_GRADES if g not in row_map]
        if missing:
            raise ExtractError(f"등급을 찾지 못했습니다: {missing}")

        basic_limits: dict[str, int | float] = {}
        extended_limits: dict[str, int | float] = {}
        for grade in IJ_GRADES:
            i = row_map[grade]
            basic_limits[grade] = self._num(df.iat[base_r + i, base_c + 3])
            extended_limits[grade] = self._num(df.iat[base_r + i, base_c + 4])

        return {
            "기본단가": base_price,
            "A값": a_value,
            "인정조사 본인부담금 상한액": copay_cap,
            "인정조사 본인부담률 (기본급여)": basic_rates,
            "인정조사 본인부담률 (추가급여)": add_rates,
            "인정조사 월한도액 (기본형)": basic_limits,
            "인정조사 월한도액 (확장형)": extended_limits,
        }

    # 산정 특례
    def read_sj_value(self, file_path, sheet_name):
        df, norm = self._load(file_path, sheet_name)

        # 본인부담금 상한액 - "상한액" 문구 바로 왼쪽 칸에 값이 있다
        r, c = self._find_one(norm, CAP_LABEL)
        copay_cap = self._num(df.iat[r, c - 1])

        # 본인부담률 - 가·나는 고정값, 다~바는 조견표에서 읽는다
        r, c = self._find_one(norm, INCOME_HEADER)
        rates = {
            **FIXED_BASIC_RATE,
            **{g: self._num(df.iat[r + 1, c + i]) for i, g in enumerate(RATE_GRADES)},
        }

        # 추가급여 월 한도액
        base_r, base_c = self._find_first(norm, ADD_ITEMS[0])
        col_map: dict[str, int] = {}
        for i in range(len(norm.columns) - base_c):
            name = norm.iat[base_r, base_c + i]
            if name in ADD_ITEMS and name not in col_map:
                col_map[name] = i

        missing = [k for k in ADD_ITEMS if k not in col_map]
        if missing:
            raise ExtractError(f"추가급여 항목을 찾지 못했습니다: {missing}")

        limits = {
            k: self._num(df.iat[base_r + 1, base_c + col_map[k]]) for k in ADD_ITEMS
        }
        return {
            "종합조사/산정특례 본인부담금 상한액": copay_cap,
            "종합조사/산정특례 본인부담률": rates,
            "추가급여 월한도액": limits,
        }

    def _read_jh_row(self, df, norm, keyword):
        r, _ = self._find_first(norm, keyword)
        base_r = r + 1

        col_map: dict[str, int] = {}
        for offset in (-2, -1, 0):
            row = base_r + offset
            if not 0 <= row < len(norm.index):
                continue
            for col in range(len(norm.columns)):
                name = norm.iat[row, col]
                if name in JH_ZONES and name not in col_map:
                    col_map[name] = col

        missing = [z for z in JH_ZONES if z not in col_map]
        if missing:
            raise ExtractError(f"'{keyword}' 표에서 구간을 찾지 못했습니다: {missing}")
        return {
            label: self._num(df.iat[base_r, col_map[zone]])
            for label, zone in zip(JH_LABELS, JH_ZONES, strict=True)
        }

    def read_jh_value(self, file_path, sheet_name):
        df, norm = self._load(file_path, sheet_name)
        return {
            "종합조사 월한도액 (기본형)": self._read_jh_row(df, norm, JH_BASIC),
            "종합조사 월한도액 (확장형)": self._read_jh_row(df, norm, JH_EXTENDED),
        }

    _EXPECTED_LEN = {
        "인정조사 본인부담률 (기본급여)": 6,
        "인정조사 본인부담률 (추가급여)": 6,
        "종합조사/산정특례 본인부담률": 6,
        "인정조사 월한도액 (기본형)": 4,
        "인정조사 월한도액 (확장형)": 4,
        "종합조사 월한도액 (기본형)": 15,
        "종합조사 월한도액 (확장형)": 15,
    }

    _AMOUNT_KEYS = (
        "기본단가",
        "A값",
        "인정조사 본인부담금 상한액",
        "종합조사/산정특례 본인부담금 상한액",
    )
    _LIMIT_KEYS = tuple(k for k in _EXPECTED_LEN if "월한도액" in k)

    def _validate(self, data):
        for key, size in self._EXPECTED_LEN.items():
            actual = len(data[key])
            if actual != size:
                raise ExtractError(
                    f"'{key}' 항목이 {size}개여야 하는데 {actual}개입니다."
                )
        if len(data["추가급여 월한도액"]) != len(ADD_ITEMS):
            raise ExtractError(f"'추가급여 월한도액'이 {len(ADD_ITEMS)}개가 아닙니다.")

        # 금액은 모두 양수여야 한다 (가·나는 면제/정액 고정값이라 제외)
        amounts = {k: data[k] for k in self._AMOUNT_KEYS}
        for key in self._LIMIT_KEYS:
            amounts.update({f"{key}[{label}]": v for label, v in data[key].items()})
        amounts.update(
            {f"추가급여 월한도액[{k}]": v for k, v in data["추가급여 월한도액"].items()}
        )
        bad = {k: v for k, v in amounts.items() if v <= 0}
        if bad:
            raise ExtractError(f"금액이 0 이하인 항목이 있습니다: {bad}")

        # 종합조사 월 한도액이 구간이 올라갈수록 감소하는지 검증
        for key in ("종합조사 월한도액 (기본형)", "종합조사 월한도액 (확장형)"):
            series = list(data[key].values())
            if any(a <= b for a, b in itertools.pairwise(series)):
                raise ExtractError(
                    f"'{key}'가 구간 순으로 감소하지 않습니다: {series}"
                    "\n조치: 조견표의 구간 배치가 바뀌었는지 확인하세요."
                )

    # 12월에 다음 연도 단가표를 생성하는 경우에만 연도 + 1
    def _business_year(self) -> int:
        today = datetime.today()
        return today.year + (1 if today.month == 12 else 0)

    # 인정조사 탭(1페이지)에 표시할 키
    _TAB1_KEYS = (
        "기본단가",
        "A값",
        "인정조사 본인부담금 상한액",
        "인정조사 본인부담률 (기본급여)",
        "인정조사 본인부담률 (추가급여)",
        "인정조사 월한도액 (기본형)",
        "인정조사 월한도액 (확장형)",
        "추가급여 월한도액",
    )
    # 종합조사/산정특례 탭(2페이지)에 표시할 키
    _TAB2_KEYS = (
        "종합조사/산정특례 본인부담금 상한액",
        "종합조사/산정특례 본인부담률",
        "종합조사 월한도액 (기본형)",
        "종합조사 월한도액 (확장형)",
    )

    def extract_jogyeon_values(self, file: UploadedFile):
        readers = (self.read_ij_value, self.read_sj_value, self.read_jh_value)
        data = {}
        for reader, sheet in zip(readers, JOGYEON_SHEET_NAMES, strict=True):
            try:
                data.update(reader(file.path, sheet))
            except ExtractError as error:
                raise ExtractError(f"'{sheet}' 시트 — {error}") from None
        self._validate(data)

        # 화면에 탭(페이지) 2개로 나눠 보여주기 위해 dict 2개짜리 list로 반환
        tab1 = {"사업연도": self._business_year(), "차수": 1}
        tab1.update({key: data[key] for key in self._TAB1_KEYS})
        tab2 = {key: data[key] for key in self._TAB2_KEYS}
        return [tab1, tab2]
