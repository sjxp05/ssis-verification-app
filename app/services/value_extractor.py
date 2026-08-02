import pandas as pd
from itertools import product

from models.dto import UploadedFile

JOGYEON_SHEET_NAMES = ["인정조사", "산정특례", "종합조사"]


class ValueExtractor:
    # 인정조사 시트 읽고 A값, 본인부담금 상한액, 본인부담률 등 값 반환
    def _read_ij_value(self, file_path, sheet_name):
        # 파일 열기
        df = pd.read_excel(
            io=file_path,
            sheet_name=sheet_name,
            engine="openpyxl",
            header=None,
        )

        ij_data = {
            "기본단가": None,
            "A값": None,
            "본인부담금 상한액": None,
            "인정조사 본인부담률 (기본급여)": [],
            "인정조사 본인부담률 (추가급여)": [],
            "인정조사 월한도액 (기본형)": [],
            "인정조사 월한도액 (확장형)": [],
        }

        # 기본단가
        for row, col in zip(*((df == "기본단가").to_numpy().nonzero())):
            ij_data["기본단가"] = df.iat[row, col + 1]

        # A값
        mask = df.astype(str).apply(lambda x: x.str.contains("A값", na=False))
        for row, col in zip(*mask.to_numpy().nonzero()):
            ij_data["A값"] = df.iat[row, col + 1]
            ij_data["본인부담금 상한액"] = df.iloc[row, col + 2]

        # 부담률
        for row, col in zip(*((df == "기본 부담률").to_numpy().nonzero())):
            for i in range(1, 5):
                ij_data["인정조사 본인부담률 (기본급여)"].append(df.iat[row, col + i])
                ij_data["인정조사 본인부담률 (추가급여)"].append(
                    df.iat[row + 1, col + i]
                )

        # 월 한도액(기본/확장)
        TARGET_GRADES = ["1등급", "2등급", "3등급", "4등급"]
        IJ_ROW_MAP = {}
        grade_cell = ()
        for row, col in zip(*((df == "활동지원등급").to_numpy().nonzero())):
            grade_cell = (row + 2, col)

        for i in range(5):
            cell_val = str(df.iat[grade_cell[0] + i, grade_cell[1]]).strip()
            if cell_val in TARGET_GRADES:
                IJ_ROW_MAP[cell_val] = i  # 엑셀상의 실제 오프셋(위치) 저장

        for grade_name, offset in IJ_ROW_MAP.items():
            ij_data["인정조사 월한도액 (기본형)"].append(
                df.iat[grade_cell[0] + offset, grade_cell[1] + 3]
            )
            ij_data["인정조사 월한도액 (확장형)"].append(
                df.iat[grade_cell[0] + offset, grade_cell[1] + 4]
            )

        return ij_data

    # 산정 특례
    def _read_sj_value(self, file_path, sheet_name):
        # 파일 열기
        df = pd.read_excel(
            io=file_path,
            sheet_name=sheet_name,
            engine="openpyxl",
            header=None,
        )
        sj_data = {
            "종합조사/산정특례 본인부담률": [],
            "추가급여 월한도액": {
                "최중증1인가구": None,
                "1등급1인가구": None,
                "2등급이하1인가구": None,
                "최중증취약가구": None,
                "1등급취약가구": None,
                "2등급이하취약가구": None,
                "출산": None,
                "자립준비": None,
                "학교생활": None,
                "직장생활": None,
                "보호자일시부재": None,
                "나머지가구구성원의직장생활등": None,
            },
        }

        # 부담률
        rate_cell = ()
        mask = df.astype(str).apply(lambda x: x.str.contains("기준중위소득", na=False))
        rows, cols = mask.to_numpy().nonzero()
        if len(rows) > 0:
            rate_cell = (rows[0] + 1, cols[0])

        for i in range(4):
            sj_data["종합조사/산정특례 본인부담률"].append(
                df.iat[rate_cell[0], rate_cell[1] + i]
            )

        # 추가급여 월 한도액
        TARGET_KEYWORDS = [
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
        ]
        SJ_COL_MAP = {}
        target_cell = ()
        mask = df.astype(str).apply(lambda x: x.str.contains("최중증1인가구", na=False))
        rows, cols = mask.to_numpy().nonzero()

        if len(rows) > 0:
            target_cell = (rows[0], cols[0])

        for i in range(20):
            try:
                cell_val = str(df.iat[target_cell[0], target_cell[1] + i])
                clean_val = cell_val.replace(" ", "").replace("\n", "").strip()

                if clean_val in TARGET_KEYWORDS:
                    SJ_COL_MAP[clean_val] = i
            except IndexError:
                break

        for keyword in TARGET_KEYWORDS:
            if keyword in SJ_COL_MAP:
                offset = SJ_COL_MAP[keyword]
                sj_data["추가급여 월한도액"][keyword] = df.iat[
                    target_cell[0] + 1, target_cell[1] + offset
                ]
            else:
                sj_data["추가급여 월한도액"][keyword] = 0  # 못 찾은 경우 0

        return sj_data

    # 종합조사 헬퍼함수
    def _extract_jh_data(self, df, keyword, target_grades):

        for row, col in zip(*((df == keyword).to_numpy().nonzero())):
            base_r, base_c = row + 1, col + 17
            break

        result = []
        col_map = {}

        for r_offset in [-2, -1, 0]:
            for c in range(len(df.columns)):
                val = (
                    str(df.iat[base_r + r_offset, c]).replace(" ", "").replace("\n", "")
                )
                if val in target_grades:
                    col_map[val] = c

        for g in range(15):
            target_zone = f"{g+1}등급"
            actual_c = col_map.get(target_zone)

            if actual_c is None:
                raise ValueError(
                    f"종합조사 엑셀 표에서 '{target_zone}' 텍스트를 찾을 수 없습니다."
                )

            result.append(df.iat[base_r, actual_c])

        return result

    # 종합 조사
    def _read_jh_value(self, file_path, sheet_name):
        # 파일 열기
        df = pd.read_excel(
            io=file_path,
            sheet_name=sheet_name,
            engine="openpyxl",
            header=None,
        )

        jh_data = {"종합조사 월한도액 (기본형)": [], "종합조사 월한도액 (확장형)": []}

        # 월 한도액(기본/확장)
        TARGET_GRADES = [f"{i}등급" for i in range(1, 16)]

        jh_data["종합조사 월한도액 (기본형)"] = self._extract_jh_data(
            df, "주간활동 기본형", TARGET_GRADES
        )
        jh_data["종합조사 월한도액 (확장형)"] = self._extract_jh_data(
            df, "주간활동 확장형", TARGET_GRADES
        )

        return jh_data

    def extract_jogyeon_values(self, file: UploadedFile):
        print(file)

        ij_data = self._read_ij_value(file.path, JOGYEON_SHEET_NAMES[0])
        sj_data = self._read_sj_value(file.path, JOGYEON_SHEET_NAMES[1])
        jh_data = self._read_jh_value(file.path, JOGYEON_SHEET_NAMES[2])

        return {
            "기본단가": ij_data["기본단가"],
            "A값": ij_data["A값"],
            "본인부담금 상한액": ij_data["본인부담금 상한액"],
            "인정조사 본인부담률 (기본급여)": ij_data["인정조사 본인부담률 (기본급여)"],
            "인정조사 본인부담률 (추가급여)": ij_data["인정조사 본인부담률 (추가급여)"],
            "종합조사/산정특례 본인부담률": sj_data["종합조사/산정특례 본인부담률"],
            "인정조사 월한도액 (기본형)": ij_data["인정조사 월한도액 (기본형)"],
            "인정조사 월한도액 (확장형)": ij_data["인정조사 월한도액 (확장형)"],
            "종합조사 월한도액 (기본형)": jh_data["종합조사 월한도액 (기본형)"],
            "종합조사 월한도액 (확장형)": jh_data["종합조사 월한도액 (확장형)"],
            "추가급여 월한도액": sj_data["추가급여 월한도액"],
        }
