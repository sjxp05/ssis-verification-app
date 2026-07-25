"""실행 진입점.

실제로는 table_builder 안에서 파싱·계산 파이프라인을 호출하면 된다.
여기서는 화면 확인용 예시 데이터를 만든다.
"""

from __future__ import annotations

import sys

import pandas as pd
from PyQt6.QtWidgets import QApplication

from resources.styles import theme
from ui.main_window import MainWindow

# 조견표 파싱 Mock Data
EXTRACTED = {
    "copay_cap": 216_000,
    "base_unit_price": 17_270,
    "copay_rate_da": 4,
    "copay_rate_ra": 6,
    "copay_rate_ma": 8,
    "copay_rate_ba": 10,
    "monthly_limit_1": 8_293_000,
    "monthly_limit_2": 7_774_000,
    "monthly_limit_3": 7_257_000,
    "monthly_limit_4": 6_739_000,
    "monthly_limit_5": 6_221_000,
    "monthly_limit_6": 5_703_000,
    "monthly_limit_7": 5_181_000,
    "monthly_limit_8": 4_665_000,
}

# 엑셀 뷰어 Mock Data
GRADES = [
    ("D001", "1등급(가형)", 942_480, 942_480, 0, "소득구분1"),
    ("D002", "1등급(나형)", 942_480, 923_030, 18_850, "소득구분2"),
    ("D003", "1등급(다형)", 942_480, 913_754, 28_274, "소득구분3"),
    ("D004", "1등급(라형)", 942_480, 904_479, 37_699, "소득구분4"),
    ("D005", "1등급(마형)", 942_480, 942_480, 0, "소득구분5"),
    ("D006", "1등급(바형)", 942_480, 942_480, 0, "소득구분6"),
    ("D007", "2등급(가형)", 884_640, 884_640, 0, "소득구분1"),
    ("D008", "2등급(나형)", 884_640, 866_880, 17_693, "소득구분2"),
]


def build_tables(values: dict) -> dict[int, tuple[pd.DataFrame, pd.DataFrame]]:
    """확인된 상수로 단가표 DataFrame 과 셀별 산식을 만든다."""
    rate = values.get("copay_rate_ra") or 6
    cap = values.get("copay_cap") or 216_000

    rows = [
        {
            "안": i + 1,
            "등급코드": code,
            "등급명": name,
            "바우처구분": "포인트",
            "지원량(pt)": amount,
            "정부지원금": gov,
            "본인부담금": copay,
            "재판정": "불가능",
            "소득구분": income,
        }
        for i, (code, name, amount, gov, copay, income) in enumerate(GRADES)
    ]
    df = pd.DataFrame(rows)

    formulas = pd.DataFrame("", index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        formulas.at[i, "지원량(pt)"] = (
            "지원량 = 월한도액 ÷ 기본단가 × 100\n"
            f"= {row['지원량(pt)']:,} pt\n"
            "출처: 고시 별표1"
        )
        formulas.at[i, "본인부담금"] = (
            f"본인부담금 = min(지원량 × {rate}%, 상한액 {cap:,})\n"
            "→ rounddown(·, -2)  ← 100원 단위 절사\n"
            f"= {row['본인부담금']:,}원\n"
            "근거: 정답표에서 귀납 (문서에 없는 규칙)"
        )
        formulas.at[i, "정부지원금"] = (
            "정부지원금 = 지원량 − 본인부담금\n"
            f"= {row['지원량(pt)']:,} − {row['본인부담금']:,}\n"
            f"= {row['정부지원금']:,}원"
        )

    empty = pd.DataFrame(
        columns=["안", "항목코드", "항목명", "지원량(pt)", "정부지원금"]
    )
    return {0: (df, formulas), 1: (empty, None)}


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.load_stylesheet())

    window = MainWindow(table_builder=build_tables)
    window.set_extracted_values(EXTRACTED)
    # 실제 앱에서는 메인 메뉴 / 업로드 화면으로 연결한다
    window.homeRequested.connect(window.close)
    window.uploadRequested.connect(lambda: print("조견표 업로드 화면으로"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
