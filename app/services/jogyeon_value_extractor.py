from __future__ import annotations
import pandas as pd
import itertools
import re
from pathlib import Path
from models.dto import UploadedFile
from utils.date import yearConfig

# 조견표에서 찾는 문구는 라벨 매처와 함께 쓰므로 config/anchors.py 에 모아 두었다.
from jogyeon_matcher.config.anchors import (  # noqa: F401  (외부에서 이 모듈 경유로 참조)
    A_VALUE,
    ADD_ITEMS,
    BASE_PRICE,
    BASIC_RATE,
    CAP_LABEL,
    FIXED_ADD_RATE,
    FIXED_BASIC_RATE,
    GRADE_HEADER,
    IJ_GRADES,
    INCOME_HEADER,
    JH_BASIC,
    JH_EXTENDED,
    JH_LABELS,
    JH_ZONES,
    JOGYEON_SHEET_NAMES,
    RATE_GRADES,
)
from jogyeon_matcher.ingest import xlsx_scan
from jogyeon_matcher.matching.normalizer import sanitize

# 공백류. 비가시 문자(ZWSP·BOM 등)는 문자로 열거하지 않고 sanitize 가 유니코드
# 카테고리로 걷어낸다. 열거 방식은 항상 누락이 생긴다.
_WS = re.compile(r"\s+")


class ExtractError(Exception):
    """에러용 클래스"""


class ValueExtractor:
    def __init__(self):
        self._cell_map:dict[str,tuple[str,int,int]]={}
        self._source_path: Path | None=None

    #값을 읽은 셀 좌표 기록함(수정본 저장 시 사용하기 위해 필요함)
    def _mark(self,key:str,sheet:str,r:int,c:int)->None:
        self._cell_map[key]=(sheet,r,c)

    def cell_map(self)->dict[str,tuple[str,int,int]]:
        return dict(self._cell_map)

    def source_path(self)-> Path |None:
        return self._source_path

    # 비교용으로 공백과 비가시 문자를 걷어낸다
    def _squeeze(self, text):
        return _WS.sub("", sanitize(text))

    # 파일 읽고 원본(df)과 공백 제거한 검색용 사본(norm)을 함께 반환
    def _load(self, file_path, sheet_name):
        # 서식만 남은 빈 행이 시트 끝까지 부풀어 있는 파일 방어 — 값이 있는
        # 마지막 행까지만 읽는다. 탐지 실패 시 기존대로 전체를 읽는다.
        cap = xlsx_scan.true_row_counts(file_path).get(sheet_name)
        df = pd.read_excel(
            file_path,
            sheet_name,
            engine="openpyxl",
            header=None,
            **({"nrows": cap} if cap else {}),
        )
        norm = df.astype(str).map(self._squeeze)
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
        self._mark("A값",sheet_name,r,c+1)
        copay_cap = self._num(df.iat[r, c + 2])
        self._mark("인정조사 본인부담금 상한액",sheet_name,r,c+2)

        # 기본단가
        r, c = self._find_one(norm, BASE_PRICE)
        base_price = self._num(df.iat[r, c + 1])
        self._mark("기본단가",sheet_name,r,c+1)

        # 본인 부담률 - 가·나는 고정값, 다~바는 조견표에서 읽는다
        # r, c = self._find_one(norm, BASIC_RATE)
        # basic_rates = {
        #     **FIXED_BASIC_RATE
        #     **{
        #         g: self._num(df.iat[r, c + i])
        #         for i, g in enumerate(RATE_GRADES, start=1)
        #     },
        # }
        # add_rates = {
        #     **FIXED_ADD_RATE,
        #     **{
        #         g: self._num(df.iat[r + 1, c + i])
        #         for i, g in enumerate(RATE_GRADES, start=1)
        #     },
        # }
        r, c = self._find_one(norm, BASIC_RATE)
        basic_rates = {**FIXED_BASIC_RATE}
        add_rates = {**FIXED_ADD_RATE}
        for i, g in enumerate(RATE_GRADES, start=1):
            basic_rates[g]=self._num(df.iat[r,c+i])
            self._mark(f"인정조사 본인부담률 (기본급여).{g}",sheet_name,r,c+i)
            add_rates[g]=self._num(df.iat[r+1,c+i])
            self._mark(f"인정조사 본인부담률 (추가급여).{g}",sheet_name,r+1,c+i)

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
            self._mark(f"인정조사 월한도액 (기본형).{grade}",sheet_name,base_r+i,base_c+3)
            extended_limits[grade] = self._num(df.iat[base_r + i, base_c + 4])
            self._mark(f"인정조사 월한도액 (확장형).{grade}",sheet_name,base_r+i,base_c+4)

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
        self._mark("종합조사/산정특례 본인부담금 상한액",sheet_name,r,c-1)

        # 본인부담률 - 가·나는 고정값, 다~바는 조견표에서 읽는다
        r, c = self._find_one(norm, INCOME_HEADER)
        # rates = {
        #     **FIXED_BASIC_RATE,
        #     **{g: self._num(df.iat[r + 1, c + i]) for i, g in enumerate(RATE_GRADES)},
        # }
        rates={**FIXED_BASIC_RATE}
        for i,g in enumerate(RATE_GRADES):
            rates[g]=self._num(df.iat[r+1,c+i])
            self._mark(f"종합조사/산정특례 본인부담률.{g}",sheet_name,r+1,c+i)

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

        # limits = {
        #     k: self._num(df.iat[base_r + 1, base_c + col_map[k]]) for k in ADD_ITEMS
        # }
        limits={}
        for k in ADD_ITEMS:
            limits[k]=self._num(df.iat[base_r+1, base_c + col_map[k]])
            self._mark(f"추가급여 월한도액.{k}",sheet_name, base_r+1, base_c + col_map[k])

        return {
            "종합조사/산정특례 본인부담금 상한액": copay_cap,
            "종합조사/산정특례 본인부담률": rates,
            "추가급여 월한도액": limits,
        }

    def _read_jh_row(self, df, norm, keyword,mark_prefix,sheet_name):
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
        # return {
        #     label: self._num(df.iat[base_r, col_map[zone]])
        #     for label, zone in zip(JH_LABELS, JH_ZONES, strict=True)
        # }
        result={}
        for label,zone in zip(JH_LABELS,JH_ZONES,strict=True):
            result[label]=self._num(df.iat[base_r, col_map[zone]])
            self._mark(f"{mark_prefix}.{label}",sheet_name,base_r,col_map[zone])
        return result

    def read_jh_value(self, file_path, sheet_name):
        df, norm = self._load(file_path, sheet_name)
        return {
            "종합조사 월한도액 (기본형)": self._read_jh_row(df, norm, JH_BASIC,"종합조사 월한도액 (기본형)",sheet_name),
            "종합조사 월한도액 (확장형)": self._read_jh_row(df, norm, JH_EXTENDED,"종합조사 월한도액 (확장형)",sheet_name),
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
        self._cell_map.clear()
        self._source_path=file.path
        readers = (self.read_ij_value, self.read_sj_value, self.read_jh_value)
        data = {}
        for reader, sheet in zip(readers, JOGYEON_SHEET_NAMES, strict=True):
            try:
                data.update(reader(file.path, sheet))
            except ExtractError as error:
                raise ExtractError(f"'{sheet}' 시트 — {error}") from None
        self._validate(data)

        # 화면에 탭(페이지) 2개로 나눠 보여주기 위해 dict 2개짜리 list로 반환
        tab1 = {"사업년도": yearConfig.SYSTEM_YEAR, "차수": 1}
        tab1.update({key: data[key] for key in self._TAB1_KEYS})
        tab2 = {key: data[key] for key in self._TAB2_KEYS}
        return [tab1, tab2]
