# ui/widgets/gosi_document_viewer.py (새로 생성)
import re
from PyQt6.QtWidgets import QTextBrowser
from PyQt6.QtCore import QTimer

_DOC_CSS = """
    .chapter { font-size: 16px; font-weight: bold; color: #2c3e50; margin-top: 16px; }
    .item { font-size: 14px; font-weight: bold; color: #34495e; margin-top: 12px; }
    .body { font-size: 13px; color: #333333; line-height: 1.5; }
    table { border-collapse: collapse; width: 100%; margin-top: 8px; margin-bottom: 16px; }
    td { border: 1px solid #bdc3c7; padding: 6px; font-size: 12px; }
    .head { background-color: #ecf0f1; font-weight: bold; text-align: center; }
    .hit { background-color: #fff2cc; font-weight: bold; color: #d35400; }
    a { text-decoration: none; color: inherit; }
"""

def _escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _anchor(table_no: int, row: int) -> str:
    return f"cell-{table_no}-{row}"

def _para_class(text: str) -> str:
    if re.match(r"^(제\s*\d+\s*장|부\s*칙)", text):
        return "chapter"
    if re.match(r"^\d+\.", text):
        return "item"
    return "body"


class GosiDocumentViewer(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NoticeDocument")
        self.setOpenExternalLinks(False)
        self._blocks = []
        self._chapters = []  # 현재 화면에 보여줄 장(章)

    def set_blocks(self, blocks: list[dict], chapters: tuple[str, ...] | None = None):
        # 블록과 장 필터를 함께 바꿀 때는 한 번만 렌더하도록 chapters 를 같이 받는다.
        # set_blocks 후 set_visible_chapters 를 잇달아 부르면 큰 문서를 두 번 렌더한다.
        self._blocks = blocks
        if chapters is not None:
            self._chapters = chapters
        self.render_document()

    def set_visible_chapters(self, chapters: tuple[str, ...]):
        self._chapters = chapters
        self.render_document()

    def _visible_blocks(self) -> list[dict]:
        if not self._chapters:
            return self._blocks
        return [b for b in self._blocks
                if any(c in (b["문맥"].get("장") or "") for c in self._chapters)]

    def render_document(self, highlight: dict | None = None) -> None:
        if not self._blocks:
            self.setHtml(f"<style>{_DOC_CSS}</style><p class='body'>고시 파일을 불러오면 원문이 표시됩니다.</p>")
            return

        target = ((highlight["표번호"], highlight["행"]) if highlight else None)
        parts = [
            f"<style>{_DOC_CSS}</style>",
            """
            <div style='background-color: #fff8e1; border: 1px solid #ffe082; color: #b08d00; 
                        padding: 12px; margin-bottom: 20px; border-radius: 6px; font-size: 12px; line-height: 1.5;'>
                <b>※ 뷰어 이용 안내</b><br>
                본 화면은 HWPX 원문 데이터를 추출하여 재구성한 <b>참고용 뷰어</b>입니다.<br>
                변환 방식의 한계로 인해 <b>일부 표의 셀 병합 및 특수문자가 고시 원본과 다르게 보일 수 있습니다.</b><br>
                정확한 문서 형태 및 레이아웃은 원본 한글 파일을 확인해 주세요.
            </div>
            """
        ]
        
        for block in self._visible_blocks():
            if block["종류"] == "문단":
                parts.append(f"<p class='{_para_class(block['글'])}'>{_escape(block['글'])}</p>")
                continue
                
            parts.append("<table>")
            for r, row in enumerate(block.get("격자", [])):
                hit = (target == (block["표번호"], r))
                parts.append("<tr>")
                for c, cell_info in enumerate(row):
                    text = cell_info if isinstance(cell_info, str) else cell_info.get("text", "")
                    css_class = "head" if r == 0 else ("hit" if hit else "")

                    cell_html = _escape(text)
                    if "가산수당" in cell_html and not cell_html.startswith("가산수당"):
                        cell_html = cell_html.replace("가산수당", "<br>가산수당")

                    anchor_tag = f"<a name='{_anchor(block['표번호'], r)}'></a>" if hit and c == 0 else ""
                    parts.append(f"<td class='{css_class}'>{anchor_tag}{cell_html}</td>")
                parts.append("</tr>")
            parts.append("</table>")

        self.setHtml("".join(parts))

        # 편의 기능 추가: 앵커태그로 스크롤 이동시 화면 가운데로 정렬
        if target:
            self.scrollToAnchor(_anchor(*target))

            def center_scroll():
                scroll_bar = self.verticalScrollBar()
                offset = scroll_bar.pageStep() // 2 
                
                new_pos = max(0, scroll_bar.value() - offset)
                scroll_bar.setValue(new_pos)
            
            QTimer.singleShot(0, center_scroll)