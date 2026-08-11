from collections import Counter
from pandas import DataFrame

# 기본급여 단가표 컬럼명 - 서식 변경시 여기만 변경
COL_SEQ = "안"
COL_BUSINESS_TYPE_ID = "사업유형ID"
COL_BUSINESS_YEAR = "사업년도"
COL_CHASU = "차수"
COL_GRADE_CODE = "등급구분"
COL_GRADE_NAME = "등급명"
COL_VOUCHER_TYPE = "바우처구분"
COL_SUPPORT_AMOUNT = "지원량"
COL_GOV_SUPPORT = "정부지원금"
COL_COPAYMENT = "본인부담금"
COL_BLANK = ""
COL_REJUDGE_YN = "재판정여부"
COL_REJUDGE_PERIOD = "재판정기간"
COL_INCOME_CRITERIA_ID = "소득기준ID"
COL_INCOME_CRITERIA_YEAR = "소득기준년도"
COL_INCOME_TYPE = "소득구분"
COL_SORT_NUM = "정렬순서"
COL_ITEM_CODE = "물품코드"

# 추가급여 단가표 칼럼명
ADD_COL_SEQ = "순번"
ADD_COL_GRADE_CODE = "등급구분"
ADD_COL_GRADE_NAME = "등급명"
ADD_COL_SUPPORT_AMOUNT = "지원량"
ADD_COL_GOV_SUPPORT = "정부지원금"
ADD_COL_COPAYMENT = "본인부담금"
ADD_COL_INCOME_TYPE = "소득구분"
ADD_COL_CATEGORY = "추가급여구분"

# 결제단가표 컬럼명
PAYMENT_COL_ORDER = "순번"
PAYMENT_COL_BUSINESS_YEAR = "사업년도"
PAYMENT_COL_CHASU = "차수"
PAYMENT_COL_BUSINESS_DIV = "사업구분"
PAYMENT_COL_BUSINESS_DIV_NAME = "사업구분명"
PAYMENT_COL_BUSINESS_TYPE_ID = "사업유형ID"
PAYMENT_COL_BUSINESS_TYPE_NAME = "사업유형명"
PAYMENT_COL_SERVICE_TYPE_ID = "서비스유형ID"
PAYMENT_COL_SERVICE_TYPE_NAME = "서비스유형명"
PAYMENT_COL_SERVICE_KIND = "서비스종류"
PAYMENT_COL_SERVICE_KIND_NAME = "서비스종유명"
PAYMENT_COL_GRADE_CODE = "등급구분"
PAYMENT_COL_GRADE_NAME = "등급명"
PAYMENT_COL_SERVICE_TIME = "서비스시간"
PAYMENT_COL_SERVICE_TIME_NAME = "서비스시간명"
PAYMENT_COL_UNIT_PRICE = "단위기준단가"
PAYMENT_COL_UNIT_PRICE_NIGHT = "단위기준심야단가"
PAYMENT_COL_SUPPORT_AMOUNT = "지원량"
PAYMENT_COL_GOV_SUPPORT_AMOUNT = "정부지원금액"
PAYMENT_COL_COPAYMENT_AMOUNT = "본인부담금액"
PAYMENT_COL_GOV_SUPPORT_RATE = "정부지원금율"
PAYMENT_COL_COPAYMENT_RATE = "본인부담금율"
PAYMENT_COL_USE_YN = "사용여부"
PAYMENT_COL_SERVICE_START_DATE = "서비스시작일자"
PAYMENT_COL_SERVICE_END_DATE = "서비스종료일자"
PAYMENT_COL_PRICE_MGMT_LEVEL = "단가관리레벨"
PAYMENT_COL_REMARKS = "비고"

# 기본급여 단가표 헤더
BASIC_HEADERS = [
    COL_SEQ,
    COL_BUSINESS_TYPE_ID,
    COL_BUSINESS_YEAR,
    COL_CHASU,
    COL_GRADE_CODE,
    COL_GRADE_NAME,
    COL_VOUCHER_TYPE,
    COL_SUPPORT_AMOUNT,
    COL_GOV_SUPPORT,
    COL_COPAYMENT,
    COL_BLANK,
    COL_REJUDGE_YN,
    COL_REJUDGE_PERIOD,
    COL_INCOME_CRITERIA_ID,
    COL_INCOME_CRITERIA_YEAR,
    COL_INCOME_TYPE,
    COL_SORT_NUM,
    COL_ITEM_CODE,
]

# 추가급여 단가표 헤더
ADD_HEADERS = [
    ADD_COL_SEQ,
    ADD_COL_GRADE_CODE,
    ADD_COL_GRADE_NAME,
    ADD_COL_SUPPORT_AMOUNT,
    ADD_COL_GOV_SUPPORT,
    ADD_COL_COPAYMENT,
    ADD_COL_INCOME_TYPE,
    ADD_COL_CATEGORY,
]

# 결제단가표 헤더
PAYMENT_HEADERS = [
    PAYMENT_COL_ORDER,
    PAYMENT_COL_BUSINESS_YEAR,
    PAYMENT_COL_CHASU,
    PAYMENT_COL_BUSINESS_DIV,
    PAYMENT_COL_BUSINESS_DIV_NAME,
    PAYMENT_COL_BUSINESS_TYPE_ID,
    PAYMENT_COL_BUSINESS_TYPE_NAME,
    PAYMENT_COL_SERVICE_TYPE_ID,
    PAYMENT_COL_SERVICE_TYPE_NAME,
    PAYMENT_COL_SERVICE_KIND,
    PAYMENT_COL_SERVICE_KIND_NAME,
    PAYMENT_COL_GRADE_CODE,
    PAYMENT_COL_GRADE_NAME,
    PAYMENT_COL_SERVICE_TIME,
    PAYMENT_COL_SERVICE_TIME_NAME,
    PAYMENT_COL_UNIT_PRICE,
    PAYMENT_COL_UNIT_PRICE_NIGHT,
    PAYMENT_COL_SUPPORT_AMOUNT,
    PAYMENT_COL_GOV_SUPPORT_AMOUNT,
    PAYMENT_COL_COPAYMENT_AMOUNT,
    PAYMENT_COL_GOV_SUPPORT_RATE,
    PAYMENT_COL_COPAYMENT_RATE,
    PAYMENT_COL_USE_YN,
    PAYMENT_COL_SERVICE_START_DATE,
    PAYMENT_COL_SERVICE_END_DATE,
    PAYMENT_COL_PRICE_MGMT_LEVEL,
    PAYMENT_COL_REMARKS,
]

SORT_NUM_START = {"기본": 1, "확장": 241, "특례": 361}
SJ_SORT_NUM_START = {"기본형": 361, "확장형": 1081}

BUSINESS_ID = "HWG001"
VOUCHER_TYPE = "포인트"
REJUDGE_IMPOSSIBLE = "불가능"
UNSELECTED_INCOME = ":::선택:::"

IJ_GRADES = tuple(f"{i}등급" for i in range(1, 5))
JH_ZONES = tuple(f"{i}구간" for i in range(1, 16))
INCOME_LETTERS = ("가", "나", "다", "라", "마", "바")

IJ_ROW_COUNT = len(IJ_GRADES) * len(INCOME_LETTERS)

# 인정조사(등급) 소득구분 라벨
IJ_INCOME_LABELS = {
    "가": "기초수급자",
    "나": "차상위",
    "다": "전국가구평균소득50%이하",
    "라": "전국가구평균소득50%초과~100%이하",
    "마": "전국가구평균소득100%초과~150%이하",
    "바": "전국가구평균소득150%초과~200%이하",
}
# 종합조사(구간) 소득구분 라벨
JH_INCOME_LABELS = {
    "가": "기초수급자",
    "나": "차상위",
    "다": "기준중위소득70%이하",
    "라": "기준중위소득70%초과~120%이하",
    "마": "기준중위소득120%초과~180%이하",
    "바": "기준중위소득180%초과",
}

# 추가급여 단가표 라벨별 (시작코드번호, 등급명, 추가급여구분 '여부' 표기 여부) 정의
ADD_CODE_INFO = {
    "출산": (25, "출산가구", 1),
    "학교생활": (31, "학교생활", 1),
    "직장생활": (37, "직장생활", 1),
    "자립준비": (43, "자립준비", 1),
    "보호자일시부재": (61, "보호자일시부재", 0),
    "나머지가구구성원의직장생활등": (67, "가족의직장생활", 0),
    "최중증1인가구": (73, "최중증1인가구", 1),
    "1등급1인가구": (79, "1등급1인가구", 0),
    "2등급이하1인가구": (85, "2등급이하1인가구", 0),
    "최중증취약가구": (91, "최중증취약가구", 0),
    "1등급취약가구": (97, "1등급취약가구", 0),
    "2등급이하취약가구": (103, "2등급이하취약가구", 0),
}

SJ_ORDER = [
    (
        "1등급",
        [
            "최중증취약가구",
            "최중증1인가구",
            "1등급취약가구",
            "1등급1인가구",
            "나머지가구구성원의직장생활등",
            None,
        ],
    ),
    ("2등급", ["2등급이하취약가구", "2등급이하1인가구", None]),
    ("3등급", ["2등급이하취약가구", "2등급이하1인가구", None]),
    ("4등급", ["2등급이하취약가구", "2등급이하1인가구", None]),
]

SJ_COMBOS = [(True, True), (True, False), (False, True), (False, False)]

SJ_CASE_CNT = 60
SJ_GROUP_SIZE = 15
SJ_DAYTIME_HOURS = 22

SJ_KEYS = [
    "기본단가",
    "종합조사/산정특례 본인부담금 상한액",
    "종합조사/산정특례 본인부담률",
    "인정조사 월한도액 (기본형)",
    "추가급여 월한도액",
]

# 사업 고정값: 결제단가표 전체 행에 동일하게 들어감
BUSINESS = {
    PAYMENT_COL_BUSINESS_DIV: "HW01",
    PAYMENT_COL_BUSINESS_DIV_NAME: "장애인활동지원",
    PAYMENT_COL_BUSINESS_TYPE_ID: "HWG001",
    PAYMENT_COL_BUSINESS_TYPE_NAME: "장애인활동지원",
}

# 결제단가표에 포함하지 않는 등급 (부적합)
EXCLUDED_GRADES = {"9999"}

# 각 서비스 유형별 시간 분리 방법
TIME_DIVISIONS = {
    "활동보조": [30, 60],
    "방문목욕": [40, 60],
    "방문간호": [0, 30, 60],
    "방문간호지시서": [60],
}

# 활동보조/방문간호 서비스종류 구분
SERVICE_KINDS = {
    "활동보조": ["사회활동지원", "신체활동지원", "가사활동지원", "기타서비스"],
    "방문간호": ["기본간호", "치료간호", "교육상담"],
}

# 방문간호 시간 매핑
NURSING_TIME_CODES = {"30분미만": 0, "30분이상60분미만": 30, "60분이상": 60}

# 서비스유형 코드
SERVICE_TYPE_CODES = {
    "활동보조": "ST0001",
    "방문간호": "ST0002",
    "방문목욕": "ST0003",
    "방문간호지시서": "ST0004",
}

# 서비스종류 코드
SERVICE_KIND_CODES = {
    "사회활동지원": "SK0001",
    "신체활동지원": "SK0002",
    "가사활동지원": "SK0003",
    "기타서비스": "SK0004",
    "기본간호": "SK0005",
    "치료간호": "SK0006",
    "교육상담": "SK0007",
    "차량내입욕": "SK0008",
    "가정내입욕": "SK0009",
    "의료기관 방문": "SK0010",
    "의료기관 의사내방": "SK0011",
    "보건기관 방문": "SK0012",
    "보건기관 의사내방": "SK0013",
}

# 활동보조 4x2=8, 방문간호 3x3=9, 방문목욕 2x2=4, 지시서 4x1=4
EXPECTED_SERVICE_ROW_COUNTS = {
    "ST0001": 8,
    "ST0002": 9,
    "ST0003": 4,
    "ST0004": 4,
}

TIME_NAMES = {
    0: "0분부터 30분미만",
    30: "30분부터 60분미만",
    40: "40분부터 59분까지",
    60: "60분이상",
}


# 고시에서 추출한 서비스별 단가 검증 함수
# (고시검증/값 확인 화면에서 이미 검증해서 올라와야 하는데 만약을 대비해 여기 넣어둠)
def validate_service_prices(prices: dict) -> None:
    # 0 이하인 단가가 있으면 안 된다
    for service, items in prices.items():
        for key, amount in items.items():
            if amount <= 0:
                raise ValueError(
                    f"서비스 단가 {service}/{key}가 0 이하입니다: {amount}"
                )

    # 방문간호는 시간이 길수록 비싸야 한다
    g = prices["방문간호"]
    if not (g["30분미만"] < g["30분이상60분미만"] < g["60분이상"]):
        raise ValueError(
            "방문간호 단가가 시간 구간 순으로 증가하지 않습니다: "
            f"30분미만={g['30분미만']}, 30분이상60분미만={g['30분이상60분미만']}, "
            f"60분이상={g['60분이상']}"
        )

    # 공휴일 및 심야 단가는 일반 단가보다 높아야 한다
    h = prices["활동보조"]
    if not (h["일반"] < h["심야"] and h["일반"] < h["공휴일"]):
        raise ValueError(
            "활동보조 심야/공휴일 단가가 일반보다 높지 않습니다: "
            f"일반={h['일반']}, 심야={h['심야']}, 공휴일={h['공휴일']}"
        )


# 기본급여 단가표의 각 등급 검증
# (고시검증/값 확인 화면에서 이미 검증해서 올라와야 하는데 만약을 대비해 여기 넣어둠)
def validate_basic_df(df: DataFrame) -> None:
    # 등급구분은 유일해야 한다 (중복되면 어떤 금액이 맞는지 알 수 없음)
    dup = df[df[COL_GRADE_CODE].duplicated(keep=False)]
    if not dup.empty:
        raise ValueError(f"등급구분이 중복된 행이 있습니다:\n{dup.to_string()}")

    # 항등식: 지원량 = 정부지원금 + 본인부담금 (기본 단가표 자체의 무결성)
    bad = df[df[COL_SUPPORT_AMOUNT] != df[COL_GOV_SUPPORT] + df[COL_COPAYMENT]]
    if not bad.empty:
        raise ValueError(
            "지원량 = 정부지원금 + 본인부담금 항등식이 깨진 행이 있습니다:\n"
            f"{bad.head(10).to_string()}"
        )

    # 율 계산에 지원량이 0이면 안 된다 (부적합 제외 후에는 없어야 정상)
    zero = df[df[COL_SUPPORT_AMOUNT] <= 0]
    if not zero.empty:
        raise ValueError(f"지원량이 0 이하인 등급이 있습니다:\n{zero.to_string()}")


class TableWriter:
    # --- 계산 공식 -----------------------------------------------------------------------

    # 절사 (rounddown(절사할 숫자, -자릿수) 엑셀 함수와 유사하게 작동)
    def _rounddown(self, x: float, digit: int) -> int:
        scale = 10 ** (-digit)
        return int(x) // scale * scale

    # ex: 본인부담금 계산 함수
    def _calculate_copayment(self, monthly_limit: int, copay_rate: float, cap: float):
        return min(self._rounddown(monthly_limit * copay_rate, -2), cap)

    # 정부지원금 계산 함수
    def _calculate_gov_support(self, monthly_limit: int, copayment: int):
        return monthly_limit - copayment

    # 가·나형은 정액(param 값 자체가 부담금), 다~바형은 요율 기반으로 계산
    def _resolve_copayment(
        self,
        letter: str,
        monthly_limit: int,
        rate_or_amount: float,
        cap: float,
        variant: str,
    ):
        if letter == "가":
            return 0
        if letter == "나":
            # 확장형(주간활동 확장형)은 차상위(나)도 본인부담금 면제
            return min(rate_or_amount, cap) if variant == "기본형" else 0
        return self._calculate_copayment(monthly_limit, rate_or_amount, cap)

    # 산정 주간확장 차감: 22시간 X 기본단가, 천원 미만 절사 적용
    def _sj_ext_deduction(self, unit_price: int) -> int:
        return self._rounddown(SJ_DAYTIME_HOURS * unit_price, -3)

    # 산정 특례 월한도액 계산함
    def _build_sj_limits(self, base_limits: dict, add_limits: dict) -> dict:
        limits = {}
        n = 1
        for grade, mains in SJ_ORDER:
            for main in mains:
                for school, work in SJ_COMBOS:
                    limit = base_limits[grade]
                    if main:
                        limit += add_limits[main]
                    if school:
                        limit += add_limits["학교생활"]
                    if work:
                        limit += add_limits["직장생활"]
                    limits[f"특례{n}"] = limit
                    n += 1

        assert n - 1 == SJ_CASE_CNT
        return limits

    # --- 기본급여/추가급여 단가표 (unit_price flow) -----------------------------------------------

    # 필요한 상수값만 선택해 가져오기
    def _save_param(
        self,
        params: dict[str, str | int | float],
        key: str,
        value: str | int | float,
    ):
        if key.find(".") != -1:
            prefix, suffix = key.split(".")
            params.setdefault(prefix, {}).update({suffix: value})
        else:
            params.update({key: value})

    def _select_params(self, values: dict[str, str | int | float], type: str) -> dict:
        params = {}

        # 사업연도 및 차수 넣기
        params.update({COL_BUSINESS_YEAR: values[COL_BUSINESS_YEAR]})
        params.update({COL_CHASU: values[COL_CHASU]})

        # 여기서 values 중에 필요한 파라미터만 골라주기
        for k, v in values.items():
            # 산정특례: 가져올 키 중에 인정, 종합, 추가 키가 섞여 있음. 별도의 리스트로 관리
            if type == "산정":
                for sj_key in SJ_KEYS:
                    if k.find(sj_key) != -1:
                        self._save_param(params, k, v)

            # 인정, 종합, 추가: 해당 단어를 포함하는 키를 모두 고르면 됨
            else:
                if k.find(type) != -1:
                    self._save_param(params, k, v)

        return params

    def _write_ij_prices(self, values: dict, variant: str) -> list[dict]:
        prefix = "D" if variant == "기본형" else "C"
        suffix = "" if variant == "기본형" else "_주간확장"
        limits = values[f"인정조사 월한도액 ({variant})"]
        rates = values["인정조사 본인부담률 (기본급여)"]
        cap = values["인정조사 본인부담금 상한액"]

        sort_num = SORT_NUM_START["기본" if variant == "기본형" else "확장"]
        code_num = 1
        rows = []
        for grade in IJ_GRADES:
            limit = limits[grade]
            for letter in INCOME_LETTERS:
                copayment = self._resolve_copayment(
                    letter, limit, rates[letter], cap, variant
                )
                rows.append(
                    {
                        COL_BUSINESS_TYPE_ID: BUSINESS_ID,
                        COL_BUSINESS_YEAR: values[COL_BUSINESS_YEAR],
                        COL_CHASU: values[COL_CHASU],
                        COL_GRADE_CODE: f"{prefix}{code_num:03d}",
                        COL_GRADE_NAME: f"{grade}({letter}형){suffix}",
                        COL_VOUCHER_TYPE: VOUCHER_TYPE,
                        COL_SUPPORT_AMOUNT: limit,
                        COL_GOV_SUPPORT: self._calculate_gov_support(limit, copayment),
                        COL_COPAYMENT: copayment,
                        COL_REJUDGE_YN: REJUDGE_IMPOSSIBLE,
                        COL_INCOME_TYPE: IJ_INCOME_LABELS[letter],
                        COL_SORT_NUM: sort_num,
                    }
                )
                code_num += 1
                sort_num += 1

        return rows

    def _write_sj_prices(self, values: dict, variant: str) -> list[dict]:
        # 월한도액 계산
        sj_limits = self._build_sj_limits(
            values["인정조사 월한도액 (기본형)"],
            values["추가급여 월한도액"],
        )

        prefix = "D" if variant == "기본형" else "C"
        suffix = "" if variant == "기본형" else "_주간확장"
        rates = values["종합조사/산정특례 본인부담률"]
        cap = values["종합조사/산정특례 본인부담금 상한액"]
        unit_price = values["기본단가"]
        deduction = 0 if variant == "기본형" else self._sj_ext_deduction(unit_price)

        sort_num = SJ_SORT_NUM_START[variant]
        rows = []
        for s in range(SJ_CASE_CNT):
            limit = sj_limits[f"특례{s+1}"] - deduction
            group_char = "ABCD"[s // SJ_GROUP_SIZE]
            for k, letter in enumerate(INCOME_LETTERS):
                code_num = (s % SJ_GROUP_SIZE) * len(INCOME_LETTERS) + k + 1
                copayment = self._resolve_copayment(
                    letter, limit, rates[letter], cap, variant
                )
                rows.append(
                    {
                        COL_BUSINESS_TYPE_ID: BUSINESS_ID,
                        COL_BUSINESS_YEAR: values[COL_BUSINESS_YEAR],
                        COL_CHASU: values[COL_CHASU],
                        COL_GRADE_CODE: f"{prefix}{group_char}{code_num:02d}",
                        COL_GRADE_NAME: f"특례{s + 1}({letter}형){suffix}",
                        COL_VOUCHER_TYPE: VOUCHER_TYPE,
                        COL_SUPPORT_AMOUNT: limit,
                        COL_GOV_SUPPORT: self._calculate_gov_support(limit, copayment),
                        COL_COPAYMENT: copayment,
                        COL_REJUDGE_YN: REJUDGE_IMPOSSIBLE,
                        COL_INCOME_TYPE: JH_INCOME_LABELS[letter],
                        COL_SORT_NUM: sort_num,
                    }
                )
                sort_num += 1
        return rows

    def _write_jh_prices(self, values: dict, variant: str) -> list[dict]:
        prefix = "D" if variant == "기본형" else "C"
        suffix = "" if variant == "기본형" else "_주간확장"
        limits = values[f"종합조사 월한도액 ({variant})"]
        rates = values["종합조사/산정특례 본인부담률"]
        cap = values["종합조사/산정특례 본인부담금 상한액"]

        # 인정조사(등급) 행 뒤에 이어지는 정렬순서/등급구분 번호에서 시작
        sort_num = (
            SORT_NUM_START["기본" if variant == "기본형" else "확장"] + IJ_ROW_COUNT
        )
        code_num = 501
        rows = []
        for zone in JH_ZONES:
            limit = limits[zone]
            for letter in INCOME_LETTERS:
                copayment = self._resolve_copayment(
                    letter, limit, rates[letter], cap, variant
                )
                rows.append(
                    {
                        COL_BUSINESS_TYPE_ID: BUSINESS_ID,
                        COL_BUSINESS_YEAR: values[COL_BUSINESS_YEAR],
                        COL_CHASU: values[COL_CHASU],
                        COL_GRADE_CODE: f"{prefix}{code_num:03d}",
                        COL_GRADE_NAME: f"{zone}({letter}형){suffix}",
                        COL_VOUCHER_TYPE: VOUCHER_TYPE,
                        COL_SUPPORT_AMOUNT: limit,
                        COL_GOV_SUPPORT: self._calculate_gov_support(limit, copayment),
                        COL_COPAYMENT: copayment,
                        COL_REJUDGE_YN: REJUDGE_IMPOSSIBLE,
                        COL_INCOME_TYPE: JH_INCOME_LABELS[letter],
                        COL_SORT_NUM: sort_num,
                    }
                )
                code_num += 1
                sort_num += 1

        return rows

    # 긴급활동지원/부적합 - 등급·구간과 무관한 고정 행 (안·정렬순서 고정값)
    def _write_urgent_unsuitable_prices(self, jh_values: dict) -> list[dict]:
        emergency_limit = jh_values["종합조사 월한도액 (기본형)"]["13구간"]
        rows = [
            {
                COL_SEQ: 949,
                COL_BUSINESS_TYPE_ID: BUSINESS_ID,
                COL_BUSINESS_YEAR: jh_values[COL_BUSINESS_YEAR],
                COL_CHASU: jh_values[COL_CHASU],
                COL_GRADE_CODE: "D599",
                COL_GRADE_NAME: "긴급활동지원",
                COL_VOUCHER_TYPE: VOUCHER_TYPE,
                COL_SUPPORT_AMOUNT: emergency_limit,
                COL_GOV_SUPPORT: emergency_limit,
                COL_COPAYMENT: 0,
                COL_REJUDGE_YN: REJUDGE_IMPOSSIBLE,
                COL_INCOME_TYPE: UNSELECTED_INCOME,
                COL_SORT_NUM: 1441,
            },
            {
                COL_SEQ: 950,
                COL_BUSINESS_TYPE_ID: BUSINESS_ID,
                COL_BUSINESS_YEAR: jh_values[COL_BUSINESS_YEAR],
                COL_CHASU: jh_values[COL_CHASU],
                COL_GRADE_CODE: "9999",
                COL_GRADE_NAME: "부적합",
                COL_VOUCHER_TYPE: VOUCHER_TYPE,
                COL_SUPPORT_AMOUNT: 0,
                COL_GOV_SUPPORT: 0,
                COL_COPAYMENT: 0,
                COL_REJUDGE_YN: REJUDGE_IMPOSSIBLE,
                COL_INCOME_TYPE: UNSELECTED_INCOME,
                COL_SORT_NUM: 1443,
            },
        ]
        return rows

    # 추가급여 단가표 작성 함수
    def _write_add_prices(self, values: dict) -> list[dict]:
        prefix = "A"
        limits = values["추가급여 월한도액"]
        rates = values["인정조사 본인부담률 (추가급여)"]

        rows = []
        seq = 1
        for key, (base_code, category_name, flag) in ADD_CODE_INFO.items():
            limit = limits[key]
            for k, letter in enumerate(INCOME_LETTERS):
                current_code = base_code + k
                copayment = self._calculate_copayment(
                    limit, rates[letter], float("inf")
                )
                rows.append(
                    {
                        ADD_COL_SEQ: seq,
                        ADD_COL_GRADE_CODE: f"{prefix}{current_code:03d}",
                        ADD_COL_GRADE_NAME: f"{category_name}_{letter}형",
                        ADD_COL_SUPPORT_AMOUNT: limit,
                        ADD_COL_GOV_SUPPORT: self._calculate_gov_support(
                            limit, copayment
                        ),
                        ADD_COL_COPAYMENT: copayment,
                        ADD_COL_INCOME_TYPE: IJ_INCOME_LABELS[letter],
                        ADD_COL_CATEGORY: (
                            f"{category_name}여부" if flag == 1 else f"{category_name}"
                        ),
                    }
                )
                seq += 1

        return rows

    # --- 결제단가표 (verify_notice flow) ----------------------------------------------------------

    # 기본급여 단가표의 등급 목록을 읽어옴
    def _prepare_basic_grades(self, basic_df: DataFrame) -> list[dict]:
        need = [
            COL_GRADE_CODE,
            COL_GRADE_NAME,
            COL_SUPPORT_AMOUNT,
            COL_GOV_SUPPORT,
            COL_COPAYMENT,
        ]
        missing = [c for c in need if c not in basic_df.columns]
        if missing:
            raise ValueError(f"기본급여 단가표에 필요한 열이 없습니다: {missing}")
        df = basic_df[need].copy()

        # 부적합 등 결제 불가 등급 제외
        df = df[~df[COL_GRADE_CODE].astype(str).isin(EXCLUDED_GRADES)]

        return df.sort_values(COL_GRADE_CODE).to_dict("records")

    # 서비스단가를 결제단가표로 생성하기 쉽게 3단계 dict로 재구성
    def _format_service_prices(self, prices: dict) -> dict:
        formatted_prices = {}

        for key, value in prices.items():
            if key.find(".") != -1:
                prefix, suffix = key.split(".")

                if prefix == "활동보조":
                    formatted_prices.setdefault(
                        prefix,
                        {
                            time: {
                                service_kind: {}
                                for service_kind in SERVICE_KINDS[prefix]
                            }
                            for time in TIME_DIVISIONS[prefix]
                        },
                    )
                    for time in TIME_DIVISIONS[prefix]:
                        for service_kind in SERVICE_KINDS[prefix]:
                            price = value
                            if time == 30:
                                price = self._rounddown((price * 0.5), -1)
                            formatted_prices[prefix][time][service_kind].update(
                                {"day": price} if suffix == "일반" else {"night": price}
                            )

                elif prefix == "방문간호":
                    formatted_prices.setdefault(prefix, {})

                    formatted_prices[prefix].update(
                        {
                            NURSING_TIME_CODES[suffix]: {
                                service_kind: {"day": value, "night": value}
                                for service_kind in SERVICE_KINDS[prefix]
                            }
                        }
                    )

                elif prefix == "방문목욕":
                    formatted_prices.setdefault(
                        prefix, {time: {} for time in TIME_DIVISIONS[prefix]}
                    )

                    for time in TIME_DIVISIONS[prefix]:
                        price = value
                        if time == 40:
                            price = self._rounddown(value * 0.8, -1)

                        formatted_prices[prefix][time].update(
                            {suffix: {"day": price, "night": price}}
                        )

                else:
                    formatted_prices.setdefault(
                        prefix, {time: {} for time in TIME_DIVISIONS[prefix]}
                    )

                    suffix = suffix.replace("_", " ")

                    for time in TIME_DIVISIONS[prefix]:
                        formatted_prices[prefix][time].update(
                            {suffix: {"day": price, "night": price}}
                        )

        return formatted_prices

    # 각 등급별로 유형별 조합 수와 단가 상식(0원 이하, 심야<주간 금지)을 검증
    def _validate_service_rows(self, rows: list[dict]) -> None:

        counts = Counter(r[PAYMENT_COL_SERVICE_TYPE_ID] for r in rows)
        if dict(counts) != EXPECTED_SERVICE_ROW_COUNTS:
            raise ValueError(
                f"서비스유형별 조합 수가 기댓값과 다릅니다: {dict(counts)} != {EXPECTED_SERVICE_ROW_COUNTS}"
            )

        for r in rows:
            # 0 이하인 단가가 있으면 안 된다
            if r[PAYMENT_COL_UNIT_PRICE] <= 0:
                raise ValueError(f"서비스 단가가 0 이하입니다: {r}")
            # 공휴일 및 심야 단가는 일반 단가보다 높아야 한다
            elif r[PAYMENT_COL_UNIT_PRICE_NIGHT] < r[PAYMENT_COL_UNIT_PRICE]:
                raise ValueError(f"단위기준심야단가가 단위기준단가보다 낮습니다: {r}")

    # (서비스 유형 x 종류 x 시간대) 조합 25개 행 만들기
    def _build_service_rows(self, prices: dict) -> list[dict]:
        formatted_prices = self._format_service_prices(prices)

        rows = []

        for service_type, values_per_type in formatted_prices.items():
            for time, values_per_time in values_per_type.items():
                for service_kind, values_per_kind in values_per_time.items():
                    rows.append(
                        {
                            PAYMENT_COL_SERVICE_TYPE_ID: SERVICE_TYPE_CODES[
                                service_type
                            ],
                            PAYMENT_COL_SERVICE_TYPE_NAME: service_type,
                            PAYMENT_COL_SERVICE_KIND: SERVICE_KIND_CODES[service_kind],
                            PAYMENT_COL_SERVICE_KIND_NAME: service_kind,
                            PAYMENT_COL_SERVICE_TIME: time,
                            PAYMENT_COL_SERVICE_TIME_NAME: TIME_NAMES[time],
                            PAYMENT_COL_UNIT_PRICE: values_per_kind["day"],
                            PAYMENT_COL_UNIT_PRICE_NIGHT: values_per_kind["night"],
                        }
                    )

        self._validate_service_rows(rows)  # 조합 수 25개인지, 단가 율 검증
        return rows

    # 등급 x 서비스 조합 -> 결제단가 DataFrame 생성
    def _build_payment_rows(
        self,
        grades: list[dict],
        service_rows: list[dict],
        business_year: int,
        chasu: int,
    ) -> DataFrame:
        # 행 순서: 서비스유형 블록 -> 등급구분 알파벳순 (실제 파일과 동일한 배치)
        by_type: dict[str, list[dict]] = {}
        for svc in service_rows:
            by_type.setdefault(svc[PAYMENT_COL_SERVICE_TYPE_ID], []).append(svc)

        rows = []
        for type_id in sorted(by_type):
            for grade in grades:
                support = grade[COL_SUPPORT_AMOUNT]
                for svc in by_type[type_id]:
                    rows.append(
                        {
                            PAYMENT_COL_BUSINESS_YEAR: business_year,
                            PAYMENT_COL_CHASU: chasu,
                            **BUSINESS,
                            PAYMENT_COL_SERVICE_TYPE_ID: svc[
                                PAYMENT_COL_SERVICE_TYPE_ID
                            ],
                            PAYMENT_COL_SERVICE_TYPE_NAME: svc[
                                PAYMENT_COL_SERVICE_TYPE_NAME
                            ],
                            PAYMENT_COL_SERVICE_KIND: svc[PAYMENT_COL_SERVICE_KIND],
                            PAYMENT_COL_SERVICE_KIND_NAME: svc[
                                PAYMENT_COL_SERVICE_KIND_NAME
                            ],
                            PAYMENT_COL_GRADE_CODE: grade[COL_GRADE_CODE],
                            PAYMENT_COL_GRADE_NAME: grade[COL_GRADE_NAME],
                            PAYMENT_COL_SERVICE_TIME: svc[PAYMENT_COL_SERVICE_TIME],
                            PAYMENT_COL_SERVICE_TIME_NAME: svc[
                                PAYMENT_COL_SERVICE_TIME_NAME
                            ],
                            PAYMENT_COL_UNIT_PRICE: svc[PAYMENT_COL_UNIT_PRICE],
                            PAYMENT_COL_UNIT_PRICE_NIGHT: svc[
                                PAYMENT_COL_UNIT_PRICE_NIGHT
                            ],
                            PAYMENT_COL_SUPPORT_AMOUNT: support,
                            PAYMENT_COL_GOV_SUPPORT_AMOUNT: grade[COL_GOV_SUPPORT],
                            PAYMENT_COL_COPAYMENT_AMOUNT: grade[COL_COPAYMENT],
                            PAYMENT_COL_GOV_SUPPORT_RATE: round(
                                grade[COL_GOV_SUPPORT] / support, 10
                            ),
                            PAYMENT_COL_COPAYMENT_RATE: round(
                                grade[COL_COPAYMENT] / support, 10
                            ),
                            PAYMENT_COL_USE_YN: "Y",
                            PAYMENT_COL_SERVICE_START_DATE: int(f"{business_year}0101"),
                            PAYMENT_COL_SERVICE_END_DATE: int(f"{business_year}1231"),
                            PAYMENT_COL_PRICE_MGMT_LEVEL: 0,
                            PAYMENT_COL_REMARKS: " ",
                        }
                    )

        df = DataFrame(rows)
        df.insert(0, PAYMENT_COL_ORDER, range(1, len(df) + 1))
        df = df[PAYMENT_HEADERS]

        # 자가 검증: 행수 = 등급수 x 조합수
        expected = len(grades) * len(service_rows)
        if len(df) != expected:
            raise ValueError(
                f"행수가 기댓값과 다릅니다: {len(df)} != 등급 {len(grades)} x 조합 {len(service_rows)}"
            )
        return df

    # --- 실제 페이지로 데이터프레임을 반환하는 함수 --------------------------------------------------

    # 기본급여 및 추가급여 단가표 생성
    def write_basic_add_tables(
        self, values: dict[str, str | int | float]
    ) -> dict[int, tuple[DataFrame, None]]:
        ij_values = self._select_params(values, "인정")
        jh_values = self._select_params(values, "종합")
        sj_values = self._select_params(values, "산정")
        add_values = self._select_params(values, "추가")

        rows = []
        add_rows = []
        for variant in ("기본형", "확장형"):
            rows += self._write_ij_prices(ij_values, variant)
            rows += self._write_jh_prices(jh_values, variant)

        for variant in ("기본형", "확장형"):
            rows += self._write_sj_prices(sj_values, variant)

        add_rows += self._write_add_prices(add_values)

        for i, row in enumerate(rows, start=1):
            row[COL_SEQ] = i

        rows += self._write_urgent_unsuitable_prices(jh_values)

        return {
            0: (DataFrame(rows, columns=BASIC_HEADERS), None),
            1: (DataFrame(add_rows, columns=ADD_HEADERS), None),
        }

    # 결제단가표 생성
    # 고시와 기본단가표는 이미 읽고 검증까지 마친 상태로 각각 service_prices, basic_df로 들어온다고 가정
    def write_payment_table(
        self,
        service_prices: dict[str, str | int | float],
        basic_df: DataFrame | str | None = None,
    ) -> dict[int, tuple[DataFrame, None]]:

        if basic_df is None:
            raise ValueError("[ERROR] 기본급여 단가표 읽기 실패")
        grades = self._prepare_basic_grades(basic_df)

        ## service_prices 형식
        """
        {'활동보조.일반': 17270, '활동보조.심야': 25900, '활동보조.공휴일': 25900, 
        '방문목욕.차량내입욕': 88990, '방문목욕.가정내입욕': 80230, 
        '방문간호.30분미만': 42880, '방문간호.30분이상60분미만': 53770, '방문간호.60분이상': 64690, 
        '방문간호지시서.의료기관_방문': 23180, '방문간호지시서.의료기관_의사내방': 71280, 
        '방문간호지시서.보건기관_방문': 6260, '방문간호지시서.보건기관_의사내방': 13500}
        """

        service_rows = self._build_service_rows(service_prices)

        business_year = service_prices.get(PAYMENT_COL_BUSINESS_YEAR, 2026)
        chasu = service_prices.get(PAYMENT_COL_CHASU, 1)

        df = self._build_payment_rows(grades, service_rows, business_year, chasu)

        return {0: (df, None)}


"""
현재 출력 형태
{
    "활동보조": {
        "사회활동지원": {
            30: {"day": 8630, "night": 12950},
            60: {"day": 17270, "night": 25900},
        },
        "가사활동지원": {
            30: {"day": 8630, "night": 12950},
            60: {"day": 17270, "night": 25900},
        },
        "신체활동지원": {
            30: {"day": 8630, "night": 12950},
            60: {"day": 17270, "night": 25900},
        },
        "기타서비스": {
            30: {"day": 8630, "night": 12950},
            60: {"day": 17270, "night": 25900},
        },
    },
    "방문목욕": {
        "차량내입욕": {
            40: {"day": 88990, "night": 88990},
            60: {"day": 88990, "night": 88990},
        },
        "가정내입욕": {
            40: {"day": 80230, "night": 80230},
            60: {"day": 80230, "night": 80230},
        },
    },
    '방문간호': {
        '기본간호': {
            0: {'day': 42880, 'night': 42880}, 
            30: {'day': 53770, 'night': 53770}, 
            60: {'day': 64690, 'night': 64690}}, 
        '치료간호': {
            0: {'day': 42880, 'night': 42880}, 
            30: {'day': 53770, 'night': 53770}, 
            60: {'day': 64690, 'night': 64690}}, 
        '교육상담': {
            0: {'day': 42880, 'night': 42880}, 
            30: {'day': 53770, 'night': 53770}, 
            60: {'day': 64690, 'night': 64690}
        }
    },
    "방문간호지시서": {
        "의료기관 방문": {60: {"day": 80230, "night": 80230}},
        "의료기관 의사내방": {60: {"day": 80230, "night": 80230}},
        "보건기관 방문": {60: {"day": 80230, "night": 80230}},
        "보건기관 의사내방": {60: {"day": 80230, "night": 80230}},
    },
}
"""
