# xlsx 시트의 '값이 있는 마지막 행' 사전 탐지
#
# 서식만 남은 빈 행이 시트 끝(1,048,576행)까지 부풀어 있는 조견표가 실제로 있다
# (실측: 인정조사 시트 XML 58~81MB, 실데이터는 234행). openpyxl 은 이 빈 행들을
# 전부 파싱하느라 시트당 10초 가까이 쓴다.
#
# 값 셀(<v>, <is>)이 나오는 마지막 행 번호를 시트 XML 바이트에서 직접 찾아
# pd.read_excel(nrows=...) 로 그 뒤를 아예 읽지 않게 한다. pandas 는 어차피 끝의
# 빈 행을 잘라내므로 결과 프레임은 동일하다(같은 파일로 실측 검증: 9.6s -> 0.26s,
# DataFrame.equals == True).
#
# 어떤 단계에서든 실패하면 빈 dict 를 돌려주고, 호출부는 nrows 없이 전체를 읽는
# 기존 경로로 돌아간다. 탐지가 틀려도 '더 많이 읽는' 쪽으로만 틀릴 수 있다.

from __future__ import annotations

import os
import re
import zipfile
from functools import lru_cache
from pathlib import Path

import xml.etree.ElementTree as ET

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# 행 요소는 엑셀·openpyxl 모두 r 속성을 쓴다. 없으면 탐지 포기(전체 읽기 폴백).
_ROW_R = re.compile(rb'<row [^>]*?\br="(\d+)"')


def true_row_counts(path: str | Path) -> dict[str, int]:
    """시트 이름 -> 값이 있는 마지막 행 번호(1부터). 탐지 실패 시 해당 시트 누락."""
    try:
        stat = os.stat(path)
        return dict(_scan_cached(str(path), stat.st_mtime_ns, stat.st_size))
    except Exception:
        return {}


@lru_cache(maxsize=8)
def _scan_cached(path: str, _mtime_ns: int, _size: int) -> dict[str, int]:
    try:
        with zipfile.ZipFile(path) as z:
            counts = {}
            for name, member in _sheet_targets(z).items():
                last = _last_data_row(z.read(member))
                if last > 0:
                    counts[name] = last
            return counts
    except Exception:
        return {}


# workbook.xml 과 관계 파일에서 시트 이름 -> 시트 XML 경로를 얻는다
def _sheet_targets(z: zipfile.ZipFile) -> dict[str, str]:
    rels = {
        rel.get("Id"): rel.get("Target", "")
        for rel in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    }
    members = set(z.namelist())
    targets = {}
    for sheet in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{_NS}sheet"):
        target = rels.get(sheet.get(f"{_R_NS}id"), "")
        if not target:
            continue
        member = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
        if member in members:
            targets[sheet.get("name")] = member
    return targets


def _last_data_row(xml: bytes) -> int:
    # <v>(숫자·공유문자열·불리언·수식 캐시값)와 <is>(직접 문자열)가 값의 전부다.
    # 서식만 있는 셀·행에는 이 요소가 없다.
    pos = max(xml.rfind(b"</v>"), xml.rfind(b"</is>"))
    if pos < 0:
        return 0
    start = xml.rfind(b"<row ", 0, pos)
    if start < 0:
        return 0
    matched = _ROW_R.match(xml, start)
    return int(matched.group(1)) if matched else 0
