# -*- coding: utf-8 -*-
"""
파이프라인 E2E 실험용 합성 조견표 생성기
산출물 3종:
  1) jogyeon_test_baseline_2026.xlsx : 깨끗한 기준 조견표
  2) jogyeon_test_target_2027.xlsx   : 오류 주입판 (A1~A5, C1~C6, 구조·값 이상)
  3) injection_answer_key.xlsx        : 주입 지점별 정답지(셀 좌표·기대 동작·탐지 계층)
시드 고정 — 재현 가능. 수식 없음(값만) → recalc 불필요.
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

AR = Font(name="Arial"); BOLD = Font(name="Arial", bold=True)
HEAD = PatternFill("solid", fgColor="D9E1F2")
INJ = PatternFill("solid", fgColor="FFF2CC")   # 주입 셀(대상 파일에서 시각 표시)
OUT = str(Path(__file__).resolve().parent) + "/"   # tests/fixtures/ 에 덮어쓴다

KEY = []  # 정답지 행
def log(inj_id, cat, sub, sheet, cell, base, target, expected, layer, note=""):
    KEY.append([inj_id, cat, sub, sheet, cell, base, target, expected, layer, note])

def W(ws, cell, val, bold=False, inj=False):
    c = ws[cell]; c.value = val
    c.font = BOLD if bold else AR
    if bold: c.fill = HEAD
    if inj: c.fill = INJ
    return c

# ────────────────────────────────────────────── 공통 데이터
IJ_HOURS = [118.2, 94.2, 71.2, 47.2]
IJ_CAPS  = [2041000, 1627000, 1230000, 815000]
BANDS = ["기초", "차상위", "50% 이하", "100% 이하", "150% 이하", "150% 초과"]
ADD_BASE = ["학교생활", "직장생활", "출산", "자립준비", "보호자일시부재",
            "1등급1인가구", "2등급이하1인가구", "최중증취약가구"]
ADD_HOURS = {a: h for a, h in zip(ADD_BASE, [10.1, 40.2, 30.3, 20.2, 20.2, 80.2, 20.2, 91.0])}
ZONE_TOP, ZONE_STEP = 6480000, 405000

def build(target: bool):
    wb = Workbook()

    # ── 시트 1: 고시 본문 — 나란히 붙은 표 2개 (L2 경계 탐지 과제)
    ws = wb.active; ws.title = "고시 본문"
    W(ws, "A1", "기본단가", bold=True); W(ws, "B1", 13500)
    W(ws, "A2", "가산단가", bold=True); W(ws, "B2", 20250)
    W(ws, "D1", "구간", bold=True); W(ws, "E1", "월한도액", bold=True)
    for i in range(15):
        amt = ZONE_TOP - ZONE_STEP * i
        if target and i == 6:                      # [J19] 7구간 > 6구간 : 단조성 파괴
            amt = ZONE_TOP - ZONE_STEP * 5 + 100000
            W(ws, f"D{2+i}", f"{i+1}구간"); W(ws, f"E{2+i}", amt, inj=True)
        else:
            W(ws, f"D{2+i}", f"{i+1}구간"); W(ws, f"E{2+i}", amt)

    # ── 시트 2: 인정조사 — 헤더 블록 + 기본급여 표 + 추가급여 표
    ws = wb.create_sheet("인정조사")
    W(ws, "B1", "기본 단가(원)" if target else "기본단가", bold=True, inj=target)
    W(ws, "C1", 17790 if target else 17270)
    W(ws, "B2", "2027 A값" if target else "A값", bold=True, inj=target)
    W(ws, "C2", 3189062 if target else 3089062)
    W(ws, "E1", "（본인부담금 상한액）" if target else "(본인부담금 상한액)", bold=True, inj=target)
    W(ws, "F1", 158900 if target else 154400)
    W(ws, "E2", "기본 부담률", bold=True); W(ws, "F2", 0.06)
    W(ws, "E3", "추가 부담률", bold=True); W(ws, "F3", 0.02)   # C1 충돌 프로브 상대

    # 기본급여 표 (5행~)
    hdr = ["활동지원등급",
           "지원시간\u00a0" if target else "지원시간",
           "월\u200b 한도액" if target else "월 한도액"] + BANDS
    if target:
        hdr[3] = "기초"; hdr[4] = "차상휘"          # A5 오타
        hdr[6] = "100 % 이하"                       # C2 밴드 표기(형제 공존)
        hdr[8] = "150%초과"                          # C3 반의어(150% 이하 공존)
    inj_cols = {1, 2, 4, 6, 8} if target else set()
    for j, h in enumerate(hdr):
        W(ws, ws.cell(5, 2 + j).coordinate, h, bold=True, inj=(j in inj_cols))
    for i in range(4):
        r = 6 + i
        W(ws, f"B{r}", f"{i+1}등급")
        hours = IJ_HOURS[i] * 60 if target else IJ_HOURS[i]   # [J14] 단위 이동(시간→분)
        W(ws, f"C{r}", round(hours, 1), inj=target)
        W(ws, f"D{r}", IJ_CAPS[i])
        for j in range(6):
            W(ws, ws.cell(r, 5 + j).coordinate,
              "면제" if j == 0 else (20000 if j == 1 else IJ_CAPS[i] // (20 - 2 * j)))

    # 추가급여 표 (12행~)
    title = "월한도액(추가급여)" if target else "추가급여 월한도액"   # A4 어순
    W(ws, "B12", title, bold=True, inj=target)
    add_hdr = ["구분", "지원시간",
               "자기부담금" if target else "본인부담금"]              # A2 동의어
    for j, h in enumerate(add_hdr):
        W(ws, ws.cell(13, 2 + j).coordinate, h, bold=True, inj=(target and j == 2))
    items = list(ADD_BASE)
    if target:
        items.remove("출산")                     # [J11] 라벨 삭제
        items.append("긴급돌봄")                  # [J10] 신규 라벨(미매칭 유도)
    for i, it in enumerate(items):
        r = 14 + i
        W(ws, f"B{r}", it, inj=(target and it == "긴급돌봄"))
        W(ws, f"C{r}", ADD_HOURS.get(it, 15.0))
        W(ws, f"D{r}", int(ADD_HOURS.get(it, 15.0) * 17270))

    # ── 시트 3: 산정특례
    ws = wb.create_sheet("산정특례")
    W(ws, "B1", "기본단가", bold=True); W(ws, "C1", 17790 if target else 17270)  # B1 항등 컨트롤
    W(ws, "B2", "Ａ값" if target else "A값", bold=True, inj=target)              # C4 전각
    W(ws, "C2", 3189062 if target else 3089062)
    W(ws, "B3", "기본부담률(%)" if target else "기본 부담률", bold=True, inj=target)  # A1
    W(ws, "C3", 0.06)
    W(ws, "B4", "(본인부담금 상한액)", bold=True); W(ws, "C4", 158900 if target else 154400)
    if target:
        W(ws, "B5", "추가급여 상한액", bold=True, inj=True)   # [J15] '상한액' 스코프 내 2회
        W(ws, "C5", 79450)

    # ── 시트 4: 종합조사 — 15구간 × 기본형/확장형
    ws = wb.create_sheet("종합조사")
    if target:   # [J18] 열 순서 교체(라벨·값 동반) — 텍스트 완전일치는 전부 통과됨
        heads = ["구간", "주간활동 확장형", "주간활동 기본형"]
    else:
        heads = ["구간", "주간활동 기본형", "주간활동 확장형"]
    for j, h in enumerate(heads):
        W(ws, ws.cell(1, 1 + j).coordinate, h, bold=True, inj=(target and j > 0))
    for i in range(15):
        basic = 5940000 - 405000 * i
        ext = max(basic - 432000, 0)
        r = 2 + i
        W(ws, f"A{r}", f"{i+1}구간")
        if target:
            W(ws, f"B{r}", ext); W(ws, f"C{r}", basic)
        else:
            W(ws, f"B{r}", basic); W(ws, f"C{r}", ext)

    for s in wb.worksheets:
        for col, w in zip("ABCDEFGHIJK", [4, 26, 14, 14, 12, 22, 12, 12, 12, 12, 12]):
            s.column_dimensions[col].width = w
    return wb

# ────────────────────────────────────────────── 정답지 기록
log("J01", "A.일반변형", "A1.표기(단위·공백)", "인정조사", "B1", "기본단가", "기본 단가(원)",
    "정규화 후 완전일치 → auto_pass, 검토 큐 미진입", "L3-a 정규화")
log("J02", "A.일반변형", "A1.전각괄호", "인정조사", "E1", "(본인부담금 상한액)", "（본인부담금 상한액）",
    "NFKC 해소 → auto_pass", "L1 정제 + L3-a")
log("J03", "A.일반변형", "A3.확장", "인정조사", "B2", "A값", "2027 A값",
    "needs_review, 기준 'A값'이 top3 내", "L3-c 하이브리드")
log("J04", "A.일반변형", "A2.동의어", "인정조사", "D13", "본인부담금", "자기부담금",
    "needs_review, top3 내 — BM25 겹침 낮음, 임베딩이 견인해야 함", "L3-c 임베딩")
log("J05", "A.일반변형", "A5.오타", "인정조사", "F5", "차상위", "차상휘",
    "needs_review, top3 내", "L3-c 문자 n-gram")
log("J06", "C.우회·적대", "C4.ZWSP", "인정조사", "D5", "월 한도액", "월[ZWSP] 한도액",
    "L1에서 제거 → auto_pass. no_match·오매칭 절대 금지", "L1 Cf/Cc 제거")
log("J07", "C.우회·적대", "C4.NBSP", "인정조사", "C5", "지원시간", "지원시간[NBSP]",
    "L1 제거 → auto_pass", "L1")
log("J08", "C.우회·적대", "C2.숫자판별자", "인정조사", "H5", "100% 이하", "100 % 이하",
    "규칙 파서로 (≤100) 구간 동등 → 정확 매칭. 형제 밴드(50/150)로 오매칭 금지", "L3-b 파서 + L4 거부권")
log("J09", "C.우회·적대", "C3.반의어", "인정조사", "J5", "150% 초과", "150%초과",
    "파서로 (>150) 판정. '150% 이하'(I5 공존)로 오매칭 시 반의어 사전이 차단해야 함", "L3-b + L4 반의어")
log("J10", "B.컨트롤", "신규 라벨", "인정조사", "B21", "(기준에 없음)", "긴급돌봄",
    "unmatched → 전 후보 점수<컷오프, 직접입력 유도", "L4 컷오프")
log("J11", "B.컨트롤", "라벨 삭제", "인정조사", "(행 삭제)", "출산", "(없음)",
    "역방향 점검: 기준 '출산'이 대상에 미대응 + 추가급여 표 행 수 7→8(삭제1·추가1) 지문 diff", "L2 지문 + 역방향 매칭")
log("J12", "A.일반변형", "A4.어순", "인정조사", "B12", "추가급여 월한도액", "월한도액(추가급여)",
    "needs_review, top3 내", "L3-c")
log("J13", "C.우회·적대", "C5.부분문자열(자연 공존)", "인정조사", "B6/B19",
    "1등급 ↔ 1등급1인가구", "(양쪽 파일 공통)",
    "완전일치 우선·최장 일치로 상호 오염 금지 — '1등급' 입력이 '1등급1인가구'에 매칭되면 실패", "L2 유일성 + L4")
log("J14", "C.우회·적대", "C6-b.단위 이동", "인정조사", "C6:C9", "지원시간(시간, 47~119)", "분 단위(2832~7092), 라벨 불변",
    "라벨 검증 전부 통과(사각지대). 값 범위 체크(0~130)가 VALUE_ANOMALY로 잡아야 함", "값 수준 검증")
log("J15", "C.우회·적대", "C5.중복 앵커", "산정특례", "B4+B5", "(본인부담금 상한액) 1회", "'상한액' 포함 셀 2개",
    "표 스코프 내 앵커 유일성 위반 → 하드 에러 또는 CONTESTED 플래그. 첫 번째 셀 자동 채택은 실패", "L2 유일성 불변식")
log("J16", "C.우회·적대", "C4.전각 호모글리프", "산정특례", "B2", "A값", "Ａ값(전각 A)",
    "NFKC 해소 → auto_pass", "L1")
log("J17", "A.일반변형", "A1.표기", "산정특례", "B3", "기본 부담률", "기본부담률(%)",
    "정규화 후 auto_pass — 단, %는 판별자이므로 '(%)' 주석 제거 규칙의 정밀성 검증", "L3-a")
log("J18", "C.우회·적대", "C6-a.열 순서 교체", "종합조사", "B1:C1", "[기본형, 확장형]", "[확장형, 기본형] (값 동반 교체)",
    "라벨 텍스트 완전일치 전부 통과(사각지대). 구조 지문의 헤더 순서열 비교가 HEADER_ORDER_CHANGED를 발보해야 함", "L2 구조 지문")
log("J19", "값 이상", "단조성 파괴", "고시 본문", "E8", "7구간=4050000(감소열)", "6구간보다 +100000 큼",
    "MONOTONICITY_BROKEN 경고", "값 수준 검증")
log("J20", "B.컨트롤", "C1.정규화 충돌 프로브", "인정조사", "E2/E3", "기본 부담률 vs 추가 부담률", "(양쪽 파일 공통)",
    "수식어 제거형 과잉 정규화 시 두 라벨 충돌 → pairwise-distinct 기동 검사가 거부해야 함", "L3-a 불변식")
log("J21", "B.컨트롤", "B1.항등", "산정특례", "B1", "기본단가", "기본단가(불변)",
    "auto_pass 대조군 — 값(17270→17790)만 변한 정상 갱신. 라벨 검증이 값 변화에 반응하면 안 됨", "전 계층")
log("J22", "B.컨트롤", "L2 경계 탐지", "고시 본문", "A1:B2 + D1:E17", "나란한 표 2개", "(양쪽 파일 공통)",
    "두 TableRegion으로 분리돼야 함. 하나의 표로 오인하면 이후 전 단계 오염", "L2 표 분리")

# ────────────────────────────────────────────── 저장
build(False).save(OUT + "jogyeon_test_baseline_2026.xlsx")
build(True).save(OUT + "jogyeon_test_target_2027.xlsx")

wb = Workbook(); ws = wb.active; ws.title = "주입정답지"
cols = ["inj_id", "카테고리", "세부유형", "시트", "셀/영역", "기준(2026)", "대상(2027)",
        "기대 파이프라인 동작", "탐지 계층", "비고"]
ws.append(cols)
for c in ws[1]:
    c.font = BOLD; c.fill = HEAD
for row in KEY:
    ws.append(row + [""] * (len(cols) - len(row)))
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.font = AR; c.alignment = Alignment(vertical="top", wrap_text=True)
    if str(row[1].value).startswith("C."):
        for c in row:
            c.fill = PatternFill("solid", fgColor="FCE4EC")
for i, w in enumerate([7, 12, 22, 10, 14, 26, 30, 46, 22, 10], 1):
    ws.column_dimensions[ws.cell(1, i).column_letter].width = w
ws.freeze_panes = "A2"
wb.save(OUT + "injection_answer_key.xlsx")
print(f"주입 {len(KEY)}건 완료 — baseline / target / answer_key 저장")
