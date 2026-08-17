import inspect
import json
import math

RULES_PATH = "rules_2025.json"

# 가능한 연산 종류
ADD = "+"
SUBTRACT = "-"
MULTIPLY = "*"
DIVIDE = "/"
MIN = "MIN"
MAX = "MAX"
ROUNDUP = "ROUNDUP"
ROUNDDOWN = "ROUNDDOWN"
IF = "IF"

OPS = [ADD, SUBTRACT, MULTIPLY, DIVIDE, MIN, MAX, ROUNDUP, ROUNDDOWN, IF]

# 연산자별 피연산자 개수 (IF만 4개, 나머지는 2개)
OPNDS_LENGTH = {op: (4 if op == IF else 2) for op in OPS}

# 변수 타입 매핑
TYPE_MAP = {
    "int": (int,),
    "float": (int, float),  # int도 float 자리에 허용
    "str": (str,),
    "bool": (bool,),
}

RULE_COPAYMENT = "copayment"
RULE_COPAYMENT_EXTENDED = "copayment_extended"
RULE_ADD_COPAYMENT = "add_copayment"
RULE_SJ_MONTHLY_LIMIT = "sj_monthly_limit"
RULE_EXTENDED_MONTHLY_LIMIT = "extended_monthly_limit"
RULE_GOVERNMENT_SUPPORT = "government_support"
RULE_ACTIVITY_SUPPORT_30MIN = "activity_support_30min"
RULE_ACTIVITY_SUPPORT_30MIN_NIGHT = "activity_support_30min_night"
RULE_BATH_40MIN = "bath_40min"


class RuleConfig:
    def __init__(self):
        self.set_functions()

    def _resolve_operand(self, arg, inputs: list, values: dict):
        if isinstance(arg, str):
            for input in inputs:
                # input 리스트에 해당 변수명이 있는지 찾기
                if input.get("name") == arg:
                    # input에 있는 이름이면
                    value = values.get(input.get("var"))
                    if value is not None:
                        return value

        elif isinstance(arg, dict):
            return self._evaluate(arg, inputs, values)

        # value에 매칭되는 값이 없는 문자열 또는 상수 리터럴인 경우 그대로 반환
        return arg

    def _evaluate(self, formula: dict, inputs: list, values: dict) -> int | float:
        op = formula.get("op")
        if op not in OPS:
            raise ValueError("수행할 수 없는 연산입니다.")

        args = formula.get("args")
        if args is None:
            raise ValueError("피연산자가 없습니다.")
        if len(args) != OPNDS_LENGTH[op]:
            raise ValueError("피연산자의 개수가 올바르지 않습니다.")

        opnds = [self._resolve_operand(arg, inputs, values) for arg in args]

        if op == ADD:
            return opnds[0] + opnds[1]
        elif op == SUBTRACT:
            return opnds[0] - opnds[1]
        elif op == MULTIPLY:
            return opnds[0] * opnds[1]
        elif op == DIVIDE:
            return opnds[0] / opnds[1]
        elif op == MIN:
            return min(opnds[0], opnds[1])
        elif op == MAX:
            return max(opnds[0], opnds[1])
        elif op == ROUNDUP:
            scale = 10 ** -opnds[1]
            return math.ceil(opnds[0] / scale) * scale
        elif op == ROUNDDOWN:
            scale = 10 ** -opnds[1]
            return math.floor(opnds[0] / scale) * scale
        elif op == IF:
            return opnds[2] if opnds[0] == opnds[1] else opnds[3]

    def _build_formula_function(self, rule_id: str):
        rule = self._rules[rule_id]

        inputs = rule["inputs"]
        formula = rule["formula"]
        arg_names = [i["var"] for i in inputs]  # 함수 인자명
        display = {i["var"]: i["name"] for i in inputs}  # 에러 메시지용
        types = {i["var"]: i.get("type") for i in inputs}
        defaults = {
            i["var"]: i["default"] for i in inputs if "default" in i
        }  # 변수에 디폴트값이 있으면 설정

        # default 값 자체의 타입 검사
        for n, d in defaults.items():
            expected = TYPE_MAP.get(types[n])
            if expected and not isinstance(d, expected):
                raise ValueError(
                    f"[{rule_id}] {n}({display[n]})의 기본값 {d!r}이(가) {types[n]} 타입이 아닙니다."
                )

        def fn(*args, **kwargs):
            # 위치/키워드 인자 결합
            if len(args) > len(arg_names):
                raise TypeError(
                    f"calculate_{rule_id}()는 인자를 최대 {len(arg_names)}개 받습니다"
                )

            values = dict(zip(arg_names, args))
            for k, v in kwargs.items():
                if k not in arg_names:
                    raise TypeError(f"알 수 없는 인자입니다: {k}")
                if k in values:
                    raise TypeError(f"인자가 중복 전달되었습니다: {k}")
                values[k] = v

            # 값이 누락된 인자는 default 값 채우기
            for n in arg_names:
                if n not in values:
                    d = defaults.get(n)
                    if d is not None:
                        values[n] = d

            # 누락 검사
            missing = [n for n in arg_names if n not in values]
            if missing:
                labels = [f"{n}({display[n]})" for n in missing]
                raise TypeError(f"누락된 인자: {', '.join(labels)}")

            # 타입 검사 (bool은 int의 서브클래스라 명시적으로 배제)
            for n, v in values.items():
                expected = TYPE_MAP.get(types[n])
                if expected and not isinstance(v, expected):
                    raise TypeError(
                        f"{n}({display[n]})은(는) {types[n]} 타입이어야 합니다: {v!r}"
                    )

            # 계산 실행
            return self._evaluate(formula, inputs, values)

        fn.__name__ = f"calculate_{rule_id}"
        fn.__qualname__ = fn.__name__
        fn.__doc__ = f"{rule.get('name', rule_id)} 계산"
        fn.__signature__ = inspect.Signature(
            [
                inspect.Parameter(
                    n,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=defaults.get(n, inspect.Parameter.empty),
                )
                for n in arg_names
            ]
        )
        return fn

    def set_functions(self):
        try:
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                self._rules = json.load(f)

            self.calculate_copayment = self._build_formula_function(RULE_COPAYMENT)
            self.calculate_copayment_extended = self._build_formula_function(
                RULE_COPAYMENT_EXTENDED
            )
            self.calculate_add_copayment = self._build_formula_function(
                RULE_ADD_COPAYMENT
            )
            self.calculate_sj_monthly_limit = self._build_formula_function(
                RULE_SJ_MONTHLY_LIMIT
            )
            self.calculate_extended_monthly_limit = self._build_formula_function(
                RULE_EXTENDED_MONTHLY_LIMIT
            )
            self.calculate_government_support = self._build_formula_function(
                RULE_GOVERNMENT_SUPPORT
            )
            self.calculate_activity_support_30min = self._build_formula_function(
                RULE_ACTIVITY_SUPPORT_30MIN
            )
            self.calculate_activity_support_30min_night = self._build_formula_function(
                RULE_ACTIVITY_SUPPORT_30MIN_NIGHT
            )
            self.calculate_bath_40min = self._build_formula_function(RULE_BATH_40MIN)

        except Exception as e:
            print(f"계산 규칙 파일 읽기 실패: {e}")


ruleConfig = RuleConfig()
