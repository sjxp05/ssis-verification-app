"""
입력받는 형식
{'사업연도': 2026, '차수': 1, '기본단가': 17270, 'A값': 3089062, '인정조사 본인부담금 상한액': 154400,
'인정조사 본인부담률 (기본급여).가': 0, '인정조사 본인부담률 (기본급여).나': 20000, '인정조사 본인부담률 (기본급여).다': 0.06, '인정조사 본인부담률 (기본급여).라': 0.09, '인정조사 본인부담률 (기본급여).마': 0.12, '인정조사 본인부담률 (기본급여).바': 0.15,
'인정조사 본인부담률 (추가급여).가': 0, '인정조사 본인부담률 (추가급여).나': 0, '인정조사 본인부담률 (추가급여).다': 0.02, '인정조사 본인부담률 (추가급여).라': 0.03, '인정조사 본인부담률 (추가급여).마': 0.04, '인정조사 본인부담률 (추가급여).바': 0.05,
'인정조사 월한도액 (기본형).1등급': 2041000, '인정조사 월한도액 (기본형).2등급': 1627000, '인정조사 월한도액 (기본형).3등급': 1230000, '인정조사 월한도액 (기본형).4등급': 815000,
'인정조사 월한도액 (확장형).1등급': 1662000, '인정조사 월한도액 (확장형).2등급': 1248000, '인정조사 월한도액 (확장형).3등급': 851000, '인정조사 월한도액 (확장형).4등급': 436000,
'추가급여 월한도액.최중증1인가구': 4718000, '추가급여 월한도액.1등급1인가구': 1385000, '추가급여 월한도액.2등급이하1인가구': 349000,
'추가급여 월한도액.최중증취약가구': 4718000, '추가급여 월한도액.1등급취약가구': 1385000, '추가급여 월한도액.2등급이하취약가구': 349000,
'추가급여 월한도액.출산': 1385000, '추가급여 월한도액.자립준비': 349000, '추가급여 월한도액.학교생활': 175000, '추가급여 월한도액.직장생활': 694000,
'추가급여 월한도액.보호자일시부재': 349000, '추가급여 월한도액.나머지가구구성원의직장생활등': 1264000,
'종합조사/산정특례 본인부담금 상한액': 216200,
'종합조사/산정특례 본인부담률.가': 0, '종합조사/산정특례 본인부담률.나': 20000, '종합조사/산정특례 본인부담률.다': 0.04, '종합조사/산정특례 본인부담률.라': 0.06, '종합조사/산정특례 본인부담률.마': 0.08, '종합조사/산정특례 본인부담률.바': 0.1,
'종합조사 월한도액 (기본형).1구간': 8293000, '종합조사 월한도액 (기본형).2구간': 7774000, '종합조사 월한도액 (기본형).3구간': 7257000, '종합조사 월한도액 (기본형).4구간': 6739000,
'종합조사 월한도액 (기본형).5구간': 6221000, '종합조사 월한도액 (기본형).6구간': 5703000, '종합조사 월한도액 (기본형).7구간': 5181000, '종합조사 월한도액 (기본형).8구간': 4665000,
'종합조사 월한도액 (기본형).9구간': 4148000, '종합조사 월한도액 (기본형).10구간': 3629000, '종합조사 월한도액 (기본형).11구간': 3112000, '종합조사 월한도액 (기본형).12구간': 2593000,
'종합조사 월한도액 (기본형).13구간': 2076000, '종합조사 월한도액 (기본형).14구간': 1558000, '종합조사 월한도액 (기본형).15구간': 1040000,
'종합조사 월한도액 (확장형).1구간': 7914000, '종합조사 월한도액 (확장형).2구간': 7395000, '종합조사 월한도액 (확장형).3구간': 6878000, '종합조사 월한도액 (확장형).4구간': 6360000,
'종합조사 월한도액 (확장형).5구간': 5842000, '종합조사 월한도액 (확장형).6구간': 5324000, '종합조사 월한도액 (확장형).7구간': 4802000, '종합조사 월한도액 (확장형).8구간': 4286000,
'종합조사 월한도액 (확장형).9구간': 3769000, '종합조사 월한도액 (확장형).10구간': 3250000, '종합조사 월한도액 (확장형).11구간': 2733000, '종합조사 월한도액 (확장형).12구간': 2214000,
'종합조사 월한도액 (확장형).13구간': 1697000, '종합조사 월한도액 (확장형).14구간': 1179000, '종합조사 월한도액 (확장형).15구간': 661000}
"""

"""
인정조사에서 필요한 것:
'인정조사 본인부담금 상한액': 154400,
'인정조사 본인부담률 (기본급여).가': 0, '인정조사 본인부담률 (기본급여).나': 20000, '인정조사 본인부담률 (기본급여).다': 0.06, 
'인정조사 본인부담률 (기본급여).라': 0.09, '인정조사 본인부담률 (기본급여).마': 0.12, '인정조사 본인부담률 (기본급여).바': 0.15,
'인정조사 월한도액 (기본형).1등급': 2041000, '인정조사 월한도액 (기본형).2등급': 1627000, '인정조사 월한도액 (기본형).3등급': 1230000, '인정조사 월한도액 (기본형).4등급': 815000,
'인정조사 월한도액 (확장형).1등급': 1662000, '인정조사 월한도액 (확장형).2등급': 1248000, '인정조사 월한도액 (확장형).3등급': 851000, '인정조사 월한도액 (확장형).4등급': 436000,
"""

"""
종합조사에서 필요한 것:
'종합조사/산정특례 본인부담금 상한액': 216200,
'종합조사/산정특례 본인부담률.가': 0, '종합조사/산정특례 본인부담률.나': 20000, '종합조사/산정특례 본인부담률.다': 0.04, '종합조사/산정특례 본인부담률.라': 0.06, '종합조사/산정특례 본인부담률.마': 0.08, '종합조사/산정특례 본인부담률.바': 0.1,
'종합조사 월한도액 (기본형).1구간': 8293000, '종합조사 월한도액 (기본형).2구간': 7774000, '종합조사 월한도액 (기본형).3구간': 7257000, '종합조사 월한도액 (기본형).4구간': 6739000,
'종합조사 월한도액 (기본형).5구간': 6221000, '종합조사 월한도액 (기본형).6구간': 5703000, '종합조사 월한도액 (기본형).7구간': 5181000, '종합조사 월한도액 (기본형).8구간': 4665000,
'종합조사 월한도액 (기본형).9구간': 4148000, '종합조사 월한도액 (기본형).10구간': 3629000, '종합조사 월한도액 (기본형).11구간': 3112000, '종합조사 월한도액 (기본형).12구간': 2593000,
'종합조사 월한도액 (기본형).13구간': 2076000, '종합조사 월한도액 (기본형).14구간': 1558000, '종합조사 월한도액 (기본형).15구간': 1040000,
'종합조사 월한도액 (확장형).1구간': 7914000, '종합조사 월한도액 (확장형).2구간': 7395000, '종합조사 월한도액 (확장형).3구간': 6878000, '종합조사 월한도액 (확장형).4구간': 6360000,
'종합조사 월한도액 (확장형).5구간': 5842000, '종합조사 월한도액 (확장형).6구간': 5324000, '종합조사 월한도액 (확장형).7구간': 4802000, '종합조사 월한도액 (확장형).8구간': 4286000,
'종합조사 월한도액 (확장형).9구간': 3769000, '종합조사 월한도액 (확장형).10구간': 3250000, '종합조사 월한도액 (확장형).11구간': 2733000, '종합조사 월한도액 (확장형).12구간': 2214000,
'종합조사 월한도액 (확장형).13구간': 1697000, '종합조사 월한도액 (확장형).14구간': 1179000, '종합조사 월한도액 (확장형).15구간': 661000}
"""


from pandas import DataFrame

# 단가표 컬럼명 - 서식 변경시 여기만 변경
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

HEADERS = [
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

SORT_NUM_START = {"기본": 1, "확장": 241, "특례": 361}

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


def _save_param(
    params: dict[str, str | int | float],
    key: str,
    value: str | int | float,
):
    if key.find(".") != -1:
        prefix, suffix = key.split(".")
        params.setdefault(prefix, {}).update({suffix: value})
    else:
        params.update({key: value})


def _select_params(values: dict[str, str | int | float], type: str) -> dict:
    params = {}

    # 사업연도 및 차수 넣기
    params.update({COL_BUSINESS_YEAR: values[COL_BUSINESS_YEAR]})
    params.update({COL_CHASU: values[COL_CHASU]})

    # 여기서 values 중에 필요한 파라미터만 골라주기
    if type == "인정":
        for k, v in values.items():
            if k.find("인정") != -1:
                _save_param(params, k, v)

    elif type == "종합":
        for k, v in values.items():
            if k.find("종합") != -1:
                _save_param(params, k, v)

    return params


# ex: 본인부담금 계산 함수
def _calculate_copayment(monthly_limit: int, copay_rate: float, cap: float):
    return min((monthly_limit * copay_rate) // 100 * 100, cap)


# 정부지원금 계산 함수
def _calculate_gov_support(monthly_limit: int, copayment: int):
    return monthly_limit - copayment


# 가·나형은 정액(param 값 자체가 부담금), 다~바형은 요율 기반으로 계산
def _resolve_copayment(
    letter: str, monthly_limit: int, rate_or_amount: float, cap: float, variant: str
):
    if letter == "가":
        return 0
    if letter == "나":
        # 확장형(주간활동 확장형)은 차상위(나)도 본인부담금 면제
        return min(rate_or_amount, cap) if variant == "기본형" else 0
    return _calculate_copayment(monthly_limit, rate_or_amount, cap)


def _write_ij_prices(values: dict, variant: str) -> list[dict]:
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
            copayment = _resolve_copayment(letter, limit, rates[letter], cap, variant)
            rows.append(
                {
                    COL_BUSINESS_TYPE_ID: BUSINESS_ID,
                    COL_BUSINESS_YEAR: values[COL_BUSINESS_YEAR],
                    COL_CHASU: values[COL_CHASU],
                    COL_GRADE_CODE: f"{prefix}{code_num:03d}",
                    COL_GRADE_NAME: f"{grade}({letter}형){suffix}",
                    COL_VOUCHER_TYPE: VOUCHER_TYPE,
                    COL_SUPPORT_AMOUNT: limit,
                    COL_GOV_SUPPORT: _calculate_gov_support(limit, copayment),
                    COL_COPAYMENT: copayment,
                    COL_REJUDGE_YN: REJUDGE_IMPOSSIBLE,
                    COL_INCOME_TYPE: IJ_INCOME_LABELS[letter],
                    COL_SORT_NUM: sort_num,
                }
            )
            code_num += 1
            sort_num += 1

    return rows


def _write_jh_prices(values: dict, variant: str) -> list[dict]:
    prefix = "D" if variant == "기본형" else "C"
    suffix = "" if variant == "기본형" else "_주간확장"
    limits = values[f"종합조사 월한도액 ({variant})"]
    rates = values["종합조사/산정특례 본인부담률"]
    cap = values["종합조사/산정특례 본인부담금 상한액"]

    # 인정조사(등급) 행 뒤에 이어지는 정렬순서/등급구분 번호에서 시작
    sort_num = SORT_NUM_START["기본" if variant == "기본형" else "확장"] + IJ_ROW_COUNT
    code_num = 501
    rows = []
    for zone in JH_ZONES:
        limit = limits[zone]
        for letter in INCOME_LETTERS:
            copayment = _resolve_copayment(letter, limit, rates[letter], cap, variant)
            rows.append(
                {
                    COL_BUSINESS_TYPE_ID: BUSINESS_ID,
                    COL_BUSINESS_YEAR: values[COL_BUSINESS_YEAR],
                    COL_CHASU: values[COL_CHASU],
                    COL_GRADE_CODE: f"{prefix}{code_num:03d}",
                    COL_GRADE_NAME: f"{zone}({letter}형){suffix}",
                    COL_VOUCHER_TYPE: VOUCHER_TYPE,
                    COL_SUPPORT_AMOUNT: limit,
                    COL_GOV_SUPPORT: _calculate_gov_support(limit, copayment),
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
def _write_urgent_unsuitable_prices(jh_values: dict) -> list[dict]:
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


def main(values: dict) -> DataFrame:
    ij_values = _select_params(values, "인정")
    jh_values = _select_params(values, "종합")

    rows = []
    for variant in ("기본형", "확장형"):
        rows += _write_ij_prices(ij_values, variant)
        rows += _write_jh_prices(jh_values, variant)

    for i, row in enumerate(rows, start=1):
        row[COL_SEQ] = i

    rows += _write_urgent_unsuitable_prices(jh_values)

    return DataFrame(rows, columns=HEADERS)


if __name__ == "__main__":
    sample_values = {
        "사업년도": 2026,
        "차수": 1,
        "기본단가": 17270,
        "A값": 3089062,
        "인정조사 본인부담금 상한액": 154400,
        "인정조사 본인부담률 (기본급여).가": 0,
        "인정조사 본인부담률 (기본급여).나": 20000,
        "인정조사 본인부담률 (기본급여).다": 0.06,
        "인정조사 본인부담률 (기본급여).라": 0.09,
        "인정조사 본인부담률 (기본급여).마": 0.12,
        "인정조사 본인부담률 (기본급여).바": 0.15,
        "인정조사 본인부담률 (추가급여).가": 0,
        "인정조사 본인부담률 (추가급여).나": 0,
        "인정조사 본인부담률 (추가급여).다": 0.02,
        "인정조사 본인부담률 (추가급여).라": 0.03,
        "인정조사 본인부담률 (추가급여).마": 0.04,
        "인정조사 본인부담률 (추가급여).바": 0.05,
        "인정조사 월한도액 (기본형).1등급": 2041000,
        "인정조사 월한도액 (기본형).2등급": 1627000,
        "인정조사 월한도액 (기본형).3등급": 1230000,
        "인정조사 월한도액 (기본형).4등급": 815000,
        "인정조사 월한도액 (확장형).1등급": 1662000,
        "인정조사 월한도액 (확장형).2등급": 1248000,
        "인정조사 월한도액 (확장형).3등급": 851000,
        "인정조사 월한도액 (확장형).4등급": 436000,
        "추가급여 월한도액.최중증1인가구": 4718000,
        "추가급여 월한도액.1등급1인가구": 1385000,
        "추가급여 월한도액.2등급이하1인가구": 349000,
        "추가급여 월한도액.최중증취약가구": 4718000,
        "추가급여 월한도액.1등급취약가구": 1385000,
        "추가급여 월한도액.2등급이하취약가구": 349000,
        "추가급여 월한도액.출산": 1385000,
        "추가급여 월한도액.자립준비": 349000,
        "추가급여 월한도액.학교생활": 175000,
        "추가급여 월한도액.직장생활": 694000,
        "추가급여 월한도액.보호자일시부재": 349000,
        "추가급여 월한도액.나머지가구구성원의직장생활등": 1264000,
        "종합조사/산정특례 본인부담금 상한액": 216200,
        "종합조사/산정특례 본인부담률.가": 0,
        "종합조사/산정특례 본인부담률.나": 20000,
        "종합조사/산정특례 본인부담률.다": 0.04,
        "종합조사/산정특례 본인부담률.라": 0.06,
        "종합조사/산정특례 본인부담률.마": 0.08,
        "종합조사/산정특례 본인부담률.바": 0.1,
        "종합조사 월한도액 (기본형).1구간": 8293000,
        "종합조사 월한도액 (기본형).2구간": 7774000,
        "종합조사 월한도액 (기본형).3구간": 7257000,
        "종합조사 월한도액 (기본형).4구간": 6739000,
        "종합조사 월한도액 (기본형).5구간": 6221000,
        "종합조사 월한도액 (기본형).6구간": 5703000,
        "종합조사 월한도액 (기본형).7구간": 5181000,
        "종합조사 월한도액 (기본형).8구간": 4665000,
        "종합조사 월한도액 (기본형).9구간": 4148000,
        "종합조사 월한도액 (기본형).10구간": 3629000,
        "종합조사 월한도액 (기본형).11구간": 3112000,
        "종합조사 월한도액 (기본형).12구간": 2593000,
        "종합조사 월한도액 (기본형).13구간": 2076000,
        "종합조사 월한도액 (기본형).14구간": 1558000,
        "종합조사 월한도액 (기본형).15구간": 1040000,
        "종합조사 월한도액 (확장형).1구간": 7914000,
        "종합조사 월한도액 (확장형).2구간": 7395000,
        "종합조사 월한도액 (확장형).3구간": 6878000,
        "종합조사 월한도액 (확장형).4구간": 6360000,
        "종합조사 월한도액 (확장형).5구간": 5842000,
        "종합조사 월한도액 (확장형).6구간": 5324000,
        "종합조사 월한도액 (확장형).7구간": 4802000,
        "종합조사 월한도액 (확장형).8구간": 4286000,
        "종합조사 월한도액 (확장형).9구간": 3769000,
        "종합조사 월한도액 (확장형).10구간": 3250000,
        "종합조사 월한도액 (확장형).11구간": 2733000,
        "종합조사 월한도액 (확장형).12구간": 2214000,
        "종합조사 월한도액 (확장형).13구간": 1697000,
        "종합조사 월한도액 (확장형).14구간": 1179000,
        "종합조사 월한도액 (확장형).15구간": 661000,
    }

    TEST_FILE_PATH = "C:\\Users\\LG\\Downloads\\생성된_기본단가.xlsx"

    df = main(sample_values)
    df.to_excel(TEST_FILE_PATH, header=True, index=False)
