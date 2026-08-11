# 조견표 라벨 대조 흐름
#
# 값을 읽기 전에 작년 조견표와 문구를 대조하고, 달라진 곳을 담당자가 확인하게 한다.
# 서식이 바뀐 걸 모른 채 값을 읽으면 조용히 틀린 값이 나오기 때문이다.
#
# UploadPage 가 '문서 읽기 시작'을 누를 때 run() 을 부른다.
# 진행해도 되면 True, 담당자가 중단을 택하면 False 를 돌려준다.
#
# 건너뛰는 경우에도 반드시 이유를 알린다. 조용히 통과시키면 기능이 꺼진 것과
# 구분되지 않는다.

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from jogyeon_matcher import match_workbooks
from jogyeon_matcher.audit import decision_log
from models.dto import UploadedFile
from services import recent_files
from ui.dialogs.review_dialog import ReviewDialog

# 대조 기준이 되는 작년 조견표 경로를 기억해 두는 키
BASELINE_KEY = "jogyeon_baseline"


class LabelReviewFlow:
    def __init__(self, parent: QWidget | None = None):
        self._parent = parent

    def run(self, sheet: UploadedFile) -> bool:
        baseline = self._baseline_path(sheet.path)
        if baseline is None:
            self._remember(sheet.path)
            return True

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report = match_workbooks(baseline, sheet.path)
        except Exception as error:
            return self._ask_continue_after_failure(error)
        finally:
            QApplication.restoreOverrideCursor()

        if not report.review_items and not report.structural_alerts and not report.value_anomalies:
            self._remember(sheet.path)
            QMessageBox.information(
                self._parent,
                "라벨 대조 완료",
                f"{baseline.name} 과(와) 대조했습니다.\n"
                f"문구 {report.summary.total_labels}개가 모두 일치해 확인할 항목이 없습니다.",
            )
            return True

        dialog = ReviewDialog(report, baseline, sheet.path, self._parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        for decision in dialog.decisions():
            decision_log.record(decision)
        self._remember(sheet.path)
        return True

    # --- 기준 파일 ---------------------------------------------------------
    def _baseline_path(self, target: Path) -> Path | None:
        stored = recent_files.get_recent_path(BASELINE_KEY)
        if stored is not None and stored != Path(target).resolve():
            return stored

        if stored is not None:
            # 기억된 파일과 같은 파일을 올린 경우. 대조 상대가 자기 자신이라 의미가 없다.
            question = (
                f"올리신 파일이 작년 조견표로 기억된 파일과 같습니다.\n({stored.name})\n\n"
                "대조할 것이 없어 건너뜁니다.\n다른 파일을 기준으로 대조하시겠습니까?"
            )
        else:
            question = (
                "작년 조견표와 대조하면 문구가 바뀐 항목을 미리 확인할 수 있습니다.\n"
                "작년 파일을 선택하시겠습니까?"
            )

        answer = QMessageBox.question(
            self._parent,
            "작년 조견표 대조",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return None

        path, _ = QFileDialog.getOpenFileName(
            self._parent, "작년 조견표 선택", "", "Excel 파일 (*.xlsx)"
        )
        return Path(path) if path else None

    def _remember(self, path: Path) -> None:
        # 올해 파일이 내년의 기준이 된다.
        recent_files.set_recent_path(BASELINE_KEY, path)

    def _ask_continue_after_failure(self, error: Exception) -> bool:
        answer = QMessageBox.warning(
            self._parent,
            "라벨 대조 실패",
            f"작년 조견표와 대조하지 못했습니다.\n{error}\n\n대조 없이 값을 읽을까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
