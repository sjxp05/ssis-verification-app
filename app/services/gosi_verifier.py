import os
import re
import zipfile
import xml.etree.ElementTree as ET

# hwpx 본문 XML의 네임스페이스 (한글 hwpml 표준)
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"

# 앵커키워드
ANCHORS = {
    # 결제단가표로 넘길 값
    "활동보조": {"제목": "활동보조", "표안": ["시간당"]},
    "방문목욕": {"제목": "방문목욕", "표안": []},
    "방문간호": {"제목": "방문간호", "표안": []},
    "방문간호지시서": {"제목": "방문간호지시서", "표안": []},
    # 조견표 대조용
    "월한도액": {"제목": "월 한도액", "표안": ["활동지원급여 구간", "종합점수"]},
    "주간활동": {"제목": "월 한도액", "표안": ["주간활동 기본형"]},

    "인정조사기본급여": {"제목": "부 칙", "표안": ["활동지원등급", "기본급여"]},
    "추가급여": {"제목": "부 칙", "표안": ["추가급여"]},
}

# 결제단가표로 넘길 서비스 목록
PRICE_SERVICES = ["활동보조", "방문목욕", "방문간호", "방문간호지시서"]

# 조견표 파서에서 넘어오는 딕셔너리 형식
REF_KEY_FORMATS = {
    "기본형": "종합조사 월한도액 (기본형).{구간}구간",
    "확장형": "종합조사 월한도액 (확장형).{구간}구간",
}

REF_INJEONG_FORMAT = "인정조사 월한도액 (기본형).{등급}"
REF_ADD_FORMAT = "추가급여 월한도액.{항목}"

PRICE_KEY_ALIASES = {
    "활동보조.일반": "기본단가",
}

REF_IGNORE_KEYS = {"사업년도", "차수"}

# 탐색 문자열중 순서 바뀌어도 괜찮은 것들
_ADD_TIERS = (("400점이상", 0), ("380점미만", 2))
_ADD_BY_HOUSEHOLD = {
    "독거": ("최중증1인가구", "1등급1인가구", "2등급이하1인가구"),
    "가구구성원": ("최중증취약가구", "1등급취약가구", "2등급이하취약가구"),
}

# 탐색 문자열 중 순서가 중요한 것(변경 금지!!)
_ADD_BY_PHRASE = (
    ("나머지", "나머지가구구성원의직장생활등"),
    ("일시적으로부재", "보호자일시부재"),
    ("자립", "자립준비"),
    ("학교에다니는", "학교생활"),
    ("직장에다니는", "직장생활"),
    ("출산", "출산"),
)

# 금액으로 인정할 최소 자릿수
_MONEY = re.compile(r"([\d,]{4,})원")
_SEGMENT = re.compile(r"(\d+)\s*구간")
_CHAPTER = re.compile(r"^(제\s*\d+\s*장|부\s*칙)")
_ITEM = re.compile(r"^\d+\.")
_ITEM_MAX = 40  # 문맥에 남길 항목 문장 길이

# 검증 실패 시 담당자에게 안내할 문구
FIX_GUIDE = (
    "위에 적힌 출처를 고시 원문에서 확인하세요"
)

# 셀 안의 모든 텍스트 조각을 이어붙이는 함수
def _cell_text(tc):
    lines = []
    for p in tc.iter(f"{HP}p"):
        line = "".join(t.text or "" for t in p.iter(f"{HP}t")).strip()
        if line:
            lines.append(line)
    if lines:
        return "\n".join(lines)
    return "".join(t.text or "" for t in tc.iter(f"{HP}t")).strip()


# 공백·줄바꿈 처리
def _squeeze(text):
    return re.sub(r"\s+", "", text or "")


# "text" 문단텍스트와 "table" tbl요소 구분해 목록 반환
def _walk_document(root):
    items = []

    def rec(el):
        for child in el:
            if child.tag == f"{HP}tbl":
                items.append(("table", child))
            elif child.tag == f"{HP}p":
                if child.find(f".//{HP}tbl") is not None:
                    rec(child)  # 문단 안에 표가 있으면 더 내려가서 표를 찾는다
                else:
                    txt = "".join(t.text or "" for t in child.iter(f"{HP}t")).strip()
                    if txt:
                        items.append(("text", txt))
            else:
                rec(child)

    rec(root)
    return items


# 고시(hwpx)를 문서 순서대로 읽어 문단/표 블록 목록 반환
def parse_document(hwpx_path):
    blocks = []
    with zipfile.ZipFile(hwpx_path) as z:
        section_names = sorted(
            n for n in z.namelist() if re.match(r"Contents/section\d+\.xml", n)
        )
        if not section_names:
            raise ValueError(f"hwpx 안에 본문(section*.xml)이 없습니다: {hwpx_path}")

        table_no = 0
        chapter = None  # 현재 장 제목 (예: "제3장 급여비용 및 산정기준", "부칙")
        item = None  # 현재 번호 항목 (예: "1. 활동보조")
        for name in section_names:
            root = ET.fromstring(z.read(name))
            for kind, payload in _walk_document(root):
                if kind == "text":
                    if _CHAPTER.match(payload):
                        chapter = payload
                        item = None
                    elif _ITEM.match(payload):
                        # 항목이 긴 문장인 경우 앞부분만 저장
                        item = (payload if len(payload) <= _ITEM_MAX
                                else payload[:_ITEM_MAX] + "…")
                    blocks.append({"종류": "문단", "글": payload,
                                   "문맥": {"장": chapter, "항목": item}})
                else:
                    grid = [
                        [_cell_text(tc) for tc in tr.iter(f"{HP}tc")]
                        for tr in payload.iter(f"{HP}tr")
                    ]
                    width = max((len(r) for r in grid), default=0)
                    grid = [row + [""] * (width - len(row)) for row in grid]
                    blocks.append({
                        "종류": "표",
                        "섹션": name,
                        "표번호": table_no,
                        "격자": grid,
                        "문맥": {"장": chapter, "항목": item},
                    })
                    table_no += 1
    return blocks


# 고시의 모든 표를 문서 순서대로 반환
def parse_tables(hwpx_path):
    return [b for b in parse_document(hwpx_path) if b["종류"] == "표"]


# 표의 제목은 문맥(장 + 항목)을 하나의 문자열로 작성
def _heading(table):
    ctx = table["문맥"]
    return " ".join(x for x in [ctx.get("장"), ctx.get("항목")] if x)


# 서비스 이름으로 표 탐색
def find_table(tables, service, anchors=None):
    anchors = anchors or ANCHORS
    spec = anchors[service]
    title, inner = spec["제목"], spec["표안"]
    more_specific = [a["제목"] for n, a in anchors.items()
                     if n != service and a["제목"] != title and title in a["제목"]]

    squeezed_title = _squeeze(title)
    squeezed_inner = [_squeeze(k) for k in inner]
    squeezed_more = [_squeeze(x) for x in more_specific]

    hits = []
    for t in tables:
        heading = _squeeze(_heading(t))
        if squeezed_title not in heading:
            continue
        if any(other in heading for other in squeezed_more):
            continue
        flat = _squeeze(" ".join(c for row in t["격자"] for c in row))
        if all(k in flat for k in squeezed_inner):
            hits.append(t)

    if len(hits) != 1:
        listing = "\n".join(
            "  표{}: {} | 첫 행: {}".format(
                t["표번호"], _heading(t) or "(위치 불명)",
                " / ".join(c for c in t["격자"][0] if c)[:60] if t["격자"] else "(빈 표)")
            for t in tables
        )
        raise ValueError(
            f"'{service}' 표가 {len(hits)}개 발견되었습니다 (1개여야 함).\n"
        )
    return hits[0]


# 구두점 처리 및 int 추출
def _amounts(text):
    return [int(m.replace(",", "")) for m in _MONEY.findall(text)]


# 고시 내의 금액의 출처 정보와 원문 위치
def _make_source(hwpx_path, table, row, col, label, raw):
    return {
        "파일": os.path.basename(hwpx_path),
        "섹션": table.get("섹션"),
        "표번호": table["표번호"],
        "행": row,
        "열": col,
        "라벨": label,
        "원문": raw,
        "문맥": table["문맥"],
    }


# 활동보조 테이블 파서
def _read_hwaldong(hwpx_path, table):
    result = {}
    for r, row in enumerate(table["격자"]):
        label = row[0] if row else ""
        raw = " ".join(row)
        nums = _amounts(raw)
        if not nums:
            continue
        if len(nums) != 2:
            raise ValueError(
                f"활동보조 행에서 금액 2개(시간당+가산수당)를 기대했으나 {nums}: {raw}")

        squeezed = _squeeze(label)
        if "심야" in squeezed:
            key = "심야"
        elif "공휴일" in squeezed or "근로자의날" in squeezed:
            key = "공휴일"
        else:
            key = "일반"
        if key in result:
            raise ValueError(f"활동보조 '{key}' 분류가 중복 추출되었습니다: {label}")
        result[key] = {
            "금액": nums[0],
            "가산수당": nums[1],
            "출처": _make_source(hwpx_path, table, r, 1, label, raw),
        }
    if set(result) != {"일반", "심야", "공휴일"}:
        raise ValueError(f"활동보조에서 일반/심야/공휴일을 기대했으나: {sorted(result)}")
    return result


# 방문목욕 테이블 파서
def _read_mokyok(hwpx_path, table):
    result = {}
    for r, row in enumerate(table["격자"]):
        label = row[0] if row else ""
        raw = " ".join(row)
        nums = _amounts(raw)
        if not nums:
            continue
        if len(nums) != 1:
            raise ValueError(f"방문목욕 행에서 금액 1개를 기대했으나 {nums}: {raw}")
        squeezed = _squeeze(label)
        if "이동목욕용" in squeezed and "차량내에서" in squeezed:
            key = "차량내입욕"
        elif "가정내에서" in squeezed:
            key = "가정내입욕"
        else:
            raise ValueError(f"방문목욕 분류를 인식할 수 없습니다: {label}")
        if key in result:
            raise ValueError(f"방문목욕 '{key}' 분류가 중복 추출되었습니다: {label}")
        result[key] = {"금액": nums[0],
                       "출처": _make_source(hwpx_path, table, r, 1, label, raw)}
    if set(result) != {"차량내입욕", "가정내입욕"}:
        raise ValueError(f"방문목욕에서 차량내/가정내입욕을 기대했으나: {sorted(result)}")
    return result


# 방문간호 테이블 파서
def _read_ganho(hwpx_path, table):
    result = {}
    for r, row in enumerate(table["격자"]):
        label = row[0] if row else ""
        raw = " ".join(row)
        nums = _amounts(raw)
        if not nums:
            continue
        if len(nums) != 1:
            raise ValueError(f"방문간호 행에서 금액 1개를 기대했으나 {nums}: {raw}")
        squeezed = _squeeze(label)
        if "30분미만" in squeezed:
            key = "30분미만"
        elif "60분미만" in squeezed:
            key = "30분이상60분미만"
        elif "60분이상" in squeezed:
            key = "60분이상"
        else:
            raise ValueError(f"방문간호 시간 구간을 인식할 수 없습니다: {label}")
        if key in result:
            raise ValueError(f"방문간호 '{key}' 구간이 중복 추출되었습니다: {label}")
        result[key] = {"금액": nums[0],
                       "출처": _make_source(hwpx_path, table, r, 1, label, raw)}
    if set(result) != {"30분미만", "30분이상60분미만", "60분이상"}:
        raise ValueError(f"방문간호에서 시간 구간 3개를 기대했으나: {sorted(result)}")
    return result


# 방문간호지시서 테이블 파서
def _read_jisiseo(hwpx_path, table):
    result = {}
    for r, row in enumerate(table["격자"]):
        label = row[0] if row else ""
        raw = " ".join(row)
        nums = _amounts(raw)
        if not nums:
            continue
        squeezed = _squeeze(label)
        if "의료법" in squeezed or "의료기관" in squeezed:
            org = "의료기관"
        elif "지역보건법" in squeezed or "보건소" in squeezed:
            org = "보건기관"
        else:
            raise ValueError(f"지시서 발급기관을 인식할 수 없습니다: {label}")
        ways = []
        
        for m in re.finditer(r"(대상자가.*?방문|의사가\s*가정을\s*방문)",
                             " ".join(label.split())):
            ways.append("방문" if m.group().startswith("대상자") else "의사내방")
        if len(ways) != len(nums):
            raise ValueError(
                f"지시서 '{org}'에서 경우 {len(ways)}개와 금액 {len(nums)}개가 "
                f"일치하지 않습니다: {raw}")
        for way, amount in zip(ways, nums):
            key = f"{org}_{way}"
            if key in result:
                raise ValueError(f"지시서 '{key}' 분류가 중복 추출되었습니다: {label}")
            result[key] = {"금액": amount,
                           "출처": _make_source(hwpx_path, table, r, 1, label, raw)}
    expected = {"의료기관_방문", "의료기관_의사내방",
                "보건기관_방문", "보건기관_의사내방"}
    if set(result) != expected:
        raise ValueError(f"지시서에서 {sorted(expected)}를 기대했으나: {sorted(result)}")
    return result


# 활동지원급여 월 한도액 테이블 파서
def _read_wolhando(hwpx_path, table):
    result = {}
    for r, row in enumerate(table["격자"]):
        m = _SEGMENT.search(row[0] if row else "")
        nums = _amounts(" ".join(row))
        if not m or not nums:
            continue
        if len(nums) != 1:
            raise ValueError(f"월 한도액 행에서 금액 1개를 기대했으나 {nums}: {row}")
        result[int(m.group(1))] = {
            "금액": nums[0], "종합점수": row[1] if len(row) > 1 else "",
            "출처": _make_source(hwpx_path, table, r, 2, row[0], " ".join(row))}
    if not result:
        raise ValueError("활동지원급여 월 한도액 표에서 구간을 하나도 읽지 못했습니다.")
    return result


def _read_injeong(hwpx_path, table):
    columns = {}
    for row in table["격자"]:
        found = {}
        for c, cell in enumerate(row):
            m = re.search(r"(\d+)\s*등급", _squeeze(cell))
            if m and c > 0:
                found.setdefault(f"{m.group(1)}등급", c)
        if len(found) >= 2:
            columns = found
            break
    if not columns:
        raise ValueError("인정조사 기본급여 표에서 등급 머리행을 찾지 못했습니다.")

    result = {}
    for r, row in enumerate(table["격자"]):
        if "기본급여" not in _squeeze(row[0] if row else ""):
            continue
        for grade, c in columns.items():
            nums = _amounts(row[c] if c < len(row) else "")
            if len(nums) != 1:
                raise ValueError(
                    f"인정조사 기본급여 '{grade}' 칸에서 금액 1개를 기대했으나 {nums}")
            result[grade] = {
                "금액": nums[0],
                "출처": _make_source(hwpx_path, table, r, c,
                                   f"기본급여 {grade}", " ".join(row)),
            }
    if not result:
        raise ValueError("인정조사 기본급여 행을 찾지 못했습니다.")
    return result


def _add_item_name(label):
    squeezed = _squeeze(label)
    for phrase, name in _ADD_BY_PHRASE:
        if phrase in squeezed:
            return name
    for mark, names in _ADD_BY_HOUSEHOLD.items():
        if mark not in squeezed:
            continue
        for phrase, index in _ADD_TIERS:
            if phrase in squeezed:
                return names[index]
        return names[1]  # 380~399점 구간
    return None


def _read_add_benefit(hwpx_path, table):
    result = {}
    for r, row in enumerate(table["격자"]):
        label = row[0] if row else ""
        nums = _amounts(" ".join(row))
        if not nums:
            continue
        name = _add_item_name(label)
        if name is None:
            raise ValueError(f"추가급여 항목을 알아보지 못했습니다: {label}")
        if len(nums) != 1:
            raise ValueError(f"추가급여 '{name}' 행에서 금액 1개를 기대했으나 {nums}")
        if name in result:
            raise ValueError(f"추가급여 '{name}' 항목이 중복 추출되었습니다: {label}")
        result[name] = {
            "금액": nums[0],
            "출처": _make_source(hwpx_path, table, r, 1, label, " ".join(row)),
        }
    if not result:
        raise ValueError("추가급여 표에서 항목을 하나도 읽지 못했습니다.")
    return result


# 주간활동 서비스 테이블 파서
def _read_jugan(hwpx_path, table):
    result = {}
    for r, row in enumerate(table["격자"]):
        m = _SEGMENT.search(row[0] if row else "")
        nums = _amounts(" ".join(row))
        if not m or not nums:
            continue
        if len(nums) != 2:
            raise ValueError(
                f"주간활동 행에서 금액 2개(기본형+확장형)를 기대했으나 {nums}: {row}")
        segment = int(m.group(1))
        result[segment] = {
            "기본형": {"금액": nums[0],
                     "출처": _make_source(hwpx_path, table, r, 1, row[0],
                                        " ".join(row))},
            "확장형": {"금액": nums[1],
                     "출처": _make_source(hwpx_path, table, r, 2, row[0],
                                        " ".join(row))},
        }
    if not result:
        raise ValueError("주간활동 조정 한도액 표에서 구간을 하나도 읽지 못했습니다.")
    return result


_LABEL_MAX = 20


# 화면 라벨에 넣기 전에 줄바꿈·연속 공백 처리
def _one_line(text, limit=_LABEL_MAX):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


# 고시 위치를 한 줄로 작성
def where_text(source):
    ctx = source.get("문맥") or {}
    parts = [x for x in (ctx.get("장"), ctx.get("항목")) if x]
    parts.append(f"표{source['표번호']} 행{source['행']}")
    label = _one_line(source.get("라벨"))
    if label:
        parts.append(label)
    return " › ".join(parts)


# 금액, 출처 한 줄로 작성
def show_price(item):
    return f'{item["금액"]:,}원  —  {where_text(item["출처"])}'


def _issue(항목, 메시지, 출처=None):
    return {"항목": 항목, "메시지": 메시지, "출처": 출처}


# 서비스단가 미니검증기
def validate_prices(prices, limits=None):
    issues = []

    # 모든 금액은 양수
    for service, items in prices.items():
        for key, item in items.items():
            if item["금액"] <= 0:
                issues.append(_issue(f"{service}/{key}",
                                     f"금액이 0 이하입니다. 현재 값: {show_price(item)}",
                                     item["출처"]))

    # 방문간호: 제공시간이 길수록 금액이 커야 함
    g = prices.get("방문간호") or {}
    order = ["30분미만", "30분이상60분미만", "60분이상"]
    if all(k in g for k in order):
        values = [g[k]["금액"] for k in order]
        if values != sorted(values) or len(set(values)) != 3:
            issues.append(_issue(
                "방문간호",
                "금액이 시간 구간 순으로 증가하지 않습니다.\n"
                + "\n".join(f"·  {k}  {show_price(g[k])}" for k in order),
                g[order[0]]["출처"]))

    # 활동보조: 심야/공휴일은 일반보다 높고, 가산수당은 기본 단가보다 작아야 함
    h = prices.get("활동보조") or {}
    if "일반" in h:
        low = [k for k in ("심야", "공휴일")
               if k in h and h[k]["금액"] < h["일반"]["금액"]]
        if low:
            issues.append(_issue(
                "활동보조",
                "심야/공휴일 금액이 일반보다 낮습니다.\n"
                + "\n".join(f"·  {k}  {show_price(h[k])}" for k in ["일반"] + low),
                h[low[0]]["출처"]))
        for key, item in h.items():
            if item.get("가산수당", 0) >= item["금액"]:
                issues.append(_issue(
                    f"활동보조/{key}",
                    f"가산수당({item['가산수당']:,}원)이 시간당 금액 이상입니다.\n"
                    f"·  {show_price(item)}", item["출처"]))

    # 월 한도액을 함께 읽었다면 고시 안에서의 앞뒤 확인
    if limits:
        issues.extend(_validate_limits(limits))
    return issues

# 주간활동 기본형 - 월 한도액 테이블 두개가 동일한지 확인
def _validate_limits(limits):
    issues = []
    base = limits.get("활동지원급여") or {}
    day = limits.get("주간활동") or {}

    for segment in sorted(set(base) & set(day)):
        if base[segment]["금액"] != day[segment]["기본형"]["금액"]:
            issues.append(_issue(
                f"{segment}구간",
                "활동지원급여 본표와 주간활동 기본형이 다릅니다 "
                "(기본형은 '차감 없음'이라 같아야 합니다).\n"
                f"·  본표    {show_price(base[segment])}\n"
                f"·  기본형  {show_price(day[segment]['기본형'])}",
                base[segment]["출처"]))

    for segment, item in day.items():
        if item["확장형"]["금액"] > item["기본형"]["금액"]:
            issues.append(_issue(
                f"{segment}구간",
                "확장형이 기본형보다 큽니다 (확장형은 주간활동 시간만큼 차감된 금액).\n"
                f"·  기본형  {show_price(item['기본형'])}\n"
                f"·  확장형  {show_price(item['확장형'])}",
                item["확장형"]["출처"]))

    injeong = limits.get("인정조사기본급여") or {}
    grades = sorted(injeong, key=lambda g: int(re.sub(r"\D", "", g) or 0))
    amounts = [injeong[g]["금액"] for g in grades]
    if amounts and (amounts != sorted(amounts, reverse=True)
                    or len(set(amounts)) != len(amounts)):
        issues.append(_issue(
            "인정조사 기본급여",
            "등급 순으로 금액이 줄지 않습니다.\n"
            + "\n".join(f"·  {g}  {show_price(injeong[g])}" for g in grades),
            injeong[grades[0]]["출처"]))

    ordered = [
        base[s]["금액"]
        for s in sorted(base, key=lambda s: int(re.sub(r"\D", "", s) or 0))
    ]
    if ordered != sorted(ordered, reverse=True) or len(set(ordered)) != len(ordered):
        issues.append(_issue("활동지원급여",
                             "월 한도액이 구간 순으로 감소하지 않습니다."))
    return issues


# 월 한도액을 조견표 파서와 동일한 형식의 딕셔너리 모양으로 펴기
def flatten_limits(limits):
    flat = {}
    for segment, item in (limits.get("주간활동") or {}).items():
        for kind, key_format in REF_KEY_FORMATS.items():
            if kind in item:
                flat[key_format.format(구간=segment)] = item[kind]
    for grade, item in (limits.get("인정조사기본급여") or {}).items():
        flat[REF_INJEONG_FORMAT.format(등급=grade)] = item
    for name, item in (limits.get("추가급여") or {}).items():
        flat[REF_ADD_FORMAT.format(항목=name)] = item
    return flat


def flatten_prices(prices):
    return {f"{service}.{key}": item
            for service, items in (prices or {}).items()
            for key, item in items.items()
            if f"{service}.{key}" in PRICE_KEY_ALIASES}


def _norm_key(key):
    return re.sub(r"[\s()（）\[\]「」『』·・,\.\-_/]", "", str(key))


# 조견표에서 온 값을 금액(int)으로 맞춰서 일치여부 처리
def _as_amount(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(round(value))
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


# 고시 값과 조견표 값 대조
def compare_with_reference(limits, reference, prices=None):
    reference = reference or {}
    gosi = flatten_limits(limits)
    gosi.update(flatten_prices(prices))

    ref_index = {}
    for ref_key in reference:
        ref_index.setdefault(_norm_key(ref_key), ref_key)
    used_ref_keys = set()

    rows, mismatched, missing = [], 0, 0

    for key in sorted(gosi, key=_sort_key):
        item = gosi[key]
        matched_key = None
        for candidate in (key, PRICE_KEY_ALIASES.get(key)):
            if candidate and candidate in reference:
                matched_key = candidate
                break
        else:
            for candidate in (key, PRICE_KEY_ALIASES.get(key)):
                if candidate and _norm_key(candidate) in ref_index:
                    matched_key = ref_index[_norm_key(candidate)]
                    break
        if matched_key is not None:
            used_ref_keys.add(matched_key)
        raw = reference.get(matched_key) if matched_key is not None else None
        ref_value = _as_amount(raw)
        if raw is None:
            state = "조견표에 없음"
            missing += 1
        elif ref_value == item["금액"]:
            state = "일치"
        else:
            state = "불일치"
            mismatched += 1
        rows.append({"항목": key, "조견표": ref_value if ref_value is not None else raw,
                     "고시": item["금액"], "결과": state, "출처": item["출처"]})

    return {
        "행": rows,
        "일치": sum(1 for r in rows if r["결과"] == "일치"),
        "불일치": mismatched,
        "조견표에 없음": missing,
        "대조 안 함": sorted(set(reference) - used_ref_keys - REF_IGNORE_KEYS),
    }


def _sort_key(key):
    m = _SEGMENT.search(key)
    return (key[:key.rfind(".")] if "." in key else key,
            int(m.group(1)) if m else 0)


# 고시에서 서비스별 단가를 추출
def read_gosi_prices(hwpx_path, tables=None, issues=None):
    tables = tables if tables is not None else parse_tables(hwpx_path)
    readers = {"활동보조": _read_hwaldong, "방문목욕": _read_mokyok,
               "방문간호": _read_ganho, "방문간호지시서": _read_jisiseo}
    prices = {}
    for name in PRICE_SERVICES:
        try:
            prices[name] = readers[name](hwpx_path, find_table(tables, name))
        except ValueError as error:
            if issues is None:
                raise
            issues.append(_issue(f"{name} 단가 추출", str(error)))
    return prices


# 고시에서 월 한도액 읽기 (조견표 대조용).
def read_gosi_limits(hwpx_path, tables=None, issues=None):
    tables = tables if tables is not None else parse_tables(hwpx_path)
    readers = {"활동지원급여": ("월한도액", _read_wolhando),
               "주간활동": ("주간활동", _read_jugan),
               "인정조사기본급여": ("인정조사기본급여", _read_injeong),
               "추가급여": ("추가급여", _read_add_benefit)}
    limits = {}
    for name, (anchor, reader) in readers.items():
        try:
            limits[name] = reader(hwpx_path, find_table(tables, anchor))
        except ValueError as error:
            if issues is None:
                raise
            issues.append(_issue(f"{name} 월 한도액 추출", str(error)))
    return limits


# 고시 읽기 함수(메인로직)
def read_gosi(hwpx_path, reference=None, flow="notice_verify"):
    blocks = parse_document(hwpx_path)
    tables = [b for b in blocks if b["종류"] == "표"]

    prices, limits, issues = {}, {}, []
    prices = read_gosi_prices(hwpx_path, tables, issues)

    if flow == "notice_verify":
        limits = read_gosi_limits(hwpx_path, tables, issues)
        issues.extend(validate_prices(prices, limits))
        compare_result = compare_with_reference(limits, reference, prices)
    else:
        issues.extend(validate_prices(prices, None))
        compare_result = {}

    return {
        "파일": hwpx_path,
        "블록": blocks,
        "단가": prices,
        "월한도액": limits, 
        "검증": issues,
        "대조": compare_result
    }