# ui/widgets/gosi_document_viewer.py (새로 생성)
import re
from PyQt6.QtWidgets import QTextBrowser

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
        parts = [f"<style>{_DOC_CSS}</style>"]
        
        for block in self._visible_blocks():
            if block["종류"] == "문단":
                parts.append(f"<p class='{_para_class(block['글'])}'>{_escape(block['글'])}</p>")
                continue
                
            parts.append("<table>")
            for r, row in enumerate(block.get("격자", [])):
                hit = (target == (block["표번호"], r))
                parts.append("<tr>")
                for c, text in enumerate(row):
                    if r == 0:
                        css_class = "head"
                    elif hit:
                        css_class = "hit"
                    else:
                        css_class = ""
                        
                    anchor_tag = f"<a name='{_anchor(block['표번호'], r)}'></a>" if hit and c == 0 else ""
                    parts.append(f"<td class='{css_class}'>{anchor_tag}{_escape(text)}</td>")
                parts.append("</tr>")
            parts.append("</table>")

        self.setHtml("".join(parts))
        
        if target:
            self.scrollToAnchor(_anchor(*target))