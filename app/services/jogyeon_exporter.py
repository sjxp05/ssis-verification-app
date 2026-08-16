#수정된 조견표 저장용도
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

def export_modified_jogyeon(
        src_path:str|Path,
        dst_path:str|Path,
        cell_map:dict[str,tuple[str,int,int]],
        changed:dict[str,object],
)->list[tuple[str,str]]:
    wb=load_workbook(src_path)
    skipped:list[tuple[str,str]]=[]

    for key,value in changed.items():
        loc=cell_map.get(key)
        if loc is None:
            skipped.append((key,"조견표 내 위치가 기록되지 않음"))
            continue
        sheet_name,r,c=loc
        if sheet_name not in wb.sheetnames:
            skipped.append((key,f"시트를 찾을 수 없음: {sheet_name}"))
            continue
        cell=wb[sheet_name].cell(row=r+1,column=c+1)
        if isinstance(cell.value,str) and cell.value.startswith("="):
            skipped.append((key,"수식으로 계산되는 셀이기에 직접 수정 불가"))
            continue
        cell.value=value

    wb.save(dst_path)
    return skipped