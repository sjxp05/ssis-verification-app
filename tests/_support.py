# 테스트 공통 — 경로 설정과 간이 실행기
#
# pytest 없이도 돌아가야 한다. 각 테스트 파일을 python 으로 직접 실행하면
# 이 모듈의 run_module() 이 test_ 로 시작하는 함수를 모두 실행하고
# 실패가 하나라도 있으면 종료 코드 1 을 낸다.
#
# 나중에 pytest 를 도입하면 같은 파일이 그대로 수집된다.

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# app/ 을 sys.path 루트로 쓰는 기존 컨벤션을 따른다
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

LABEL_CASES = FIXTURES / "synthetic_label_tests.xlsx"
BASELINE = FIXTURES / "jogyeon_test_baseline_2026.xlsx"
TARGET = FIXTURES / "jogyeon_test_target_2027.xlsx"
ANSWER_KEY = FIXTURES / "injection_answer_key.xlsx"

# 엑셀 픽스처는 저장소에 올리지 않는다(.gitignore 의 *.xlsx).
# 클론 직후에는 파일이 없으므로, 없을 때 무엇을 해야 하는지 알려준다.
_HOW_TO_GET = {
    BASELINE.name: "python tests/fixtures/generate_synthetic_jogyeon.py",
    TARGET.name: "python tests/fixtures/generate_synthetic_jogyeon.py",
    ANSWER_KEY.name: "python tests/fixtures/generate_synthetic_jogyeon.py",
    LABEL_CASES.name: "python tests/fixtures/generate_label_tests.py",
}


def require(fixture: Path) -> Path:
    if not fixture.exists():
        raise FileNotFoundError(
            f"픽스처가 없습니다: {fixture}\n"
            f"  -> {_HOW_TO_GET.get(fixture.name, '담당자에게 문의')}"
        )
    return fixture


def run_module(namespace: dict) -> int:
    tests = [
        (name, fn)
        for name, fn in namespace.items()
        if name.startswith("test_") and callable(fn)
    ]
    failed = []
    for name, fn in tests:
        try:
            fn()
        except AssertionError as error:
            failed.append(name)
            print(f"\nFAIL  {name}\n{error}\n")
        except Exception:
            failed.append(name)
            print(f"\nERROR {name}")
            traceback.print_exc()
        else:
            print(f"OK    {name}")

    print(f"\n{len(tests) - len(failed)}/{len(tests)} 통과")
    return 1 if failed else 0
