import sys
sys.path.insert(0, "app")   # app 폴더의 모듈을 import할 수 있게

from models.dto import UploadedFile
from services.jogyeon_value_extractor import ValueExtractor

ex = ValueExtractor()
tabs = ex.extract_jogyeon_values(UploadedFile.from_path(r"C:\Users\bearf\OneDrive\바탕 화면\조견표_2026.xlsx"))

for k in ex.cell_map():
    if "종합조사 월한도액" in k:
        print("mark됨:", repr(k))

for tab in tabs:
    for k, v in tab.items():
        if "종합조사 월한도액" in k and isinstance(v, dict):
            for sub in v:
                print("필드 키:", repr(f"{k}.{sub}"))