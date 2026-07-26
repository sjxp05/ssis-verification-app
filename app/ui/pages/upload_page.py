from __future__ import annotations


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QWidget
)
class UploadPage(QWidget):
    """탭 1: 파일 업로드."""
    validateRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        page, col = _centered_scroll_page(640)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        crumb = QLabel("①  파일 업로드   ›   검증 실행   ›   결과 확인 및 수정")
        crumb.setStyleSheet(f"font-size:11px; color:{T.MUTED_FG};")
        title = QLabel("파일 업로드")
        title.setStyleSheet(f"font-size:20px; font-weight:600; color:{T.FG};")
        sub = QLabel("사업지침 PDF와 조견표 엑셀 파일을 업로드하면 자동으로 데이터를 검증합니다.")
        sub.setStyleSheet(f"font-size:13px; color:{T.MUTED_FG};")
        col.addWidget(crumb)
        col.addWidget(title)
        col.addWidget(sub)

        self.card_guide = UploadCard(
            "사업지침 (Business Guidebook)",
            "PDF 형식의 사업지침 문서 · 규칙 추출 및 검증 기준으로 활용",
            [".pdf"], "📄")
        self.card_sheet = UploadCard(
            "조견표 (Quick Reference)",
            "Excel 형식의 조견표 파일 · 셀 단위로 사업지침과 대조 검증",
            [".xlsx", ".xls"], "▦")
        self.card_guide.fileSelected.connect(self._refresh)
        self.card_sheet.fileSelected.connect(self._refresh)
        col.addWidget(self.card_guide)
        col.addWidget(self.card_sheet)

        self.btn_validate = primary_button("🔍  데이터 검증 시작  →", 44)
        self.btn_validate.setEnabled(False)
        self.btn_validate.clicked.connect(self.validateRequested.emit)
        col.addWidget(self.btn_validate)
        self.hint = QLabel("두 파일을 모두 업로드해야 검증을 시작할 수 있습니다.")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(f"font-size:11px; color:{T.MUTED_FG};")
        col.addWidget(self.hint)
        col.addStretch()

    def _refresh(self):
        ready = bool(self.card_guide.file and self.card_sheet.file)
        self.btn_validate.setEnabled(ready)
        self.hint.setVisible(not ready)

    def set_busy(self, busy: bool):
        self.btn_validate.setEnabled(not busy)
        self.btn_validate.setText("⟳  사업지침과 조견표 대조 중..." if busy else "🔍  데이터 검증 시작  →")
