# xlsx 시트의 '값이 있는 마지막 행' 사전 탐지

from __future__ import annotations

import os
import re
import zipfile
from functools import lru_cache
from pathlib import Path

import xml.etree.ElementTree as ET

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

_ROW_R = re.compile(rb'<row [^>]*?\br="(\d+)"')


# 시트별 값이 있는 마지막 행 번호 반환
def true_row_counts(path: str | Path) -> dict[str, int]:
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


# workbook.xml 과 관계 파일에서 시트 이름 -> 시트 XML 경로
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
    pos = max(xml.rfind(b"</v>"), xml.rfind(b"</is>"))
    if pos < 0:
        return 0
    start = xml.rfind(b"<row ", 0, pos)
    if start < 0:
        return 0
    matched = _ROW_R.match(xml, start)
    return int(matched.group(1)) if matched else 0
