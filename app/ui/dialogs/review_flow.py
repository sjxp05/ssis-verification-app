# 조견표 라벨 대조 시 파일 선택 및 대조 결과를 알림창으로 표시

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from jogyeon_matcher import match_workbooks
from jogyeon_matcher.audit import decision_log
from jogyeon_matcher.contracts.schemas import MatchReport
from models.dto import UploadedFile
from services import recent_files
from ui.dialogs.review_dialog import ReviewDialog
from utils.date import yearConfig

# 이번 년도 대조 이력이 있는 조견표 경로를 기억해 두는 키
JOGYEON_KEY = "jogyeon"
BASELINE_KEY = "jogyeon_baseline"


class _MatchSignals(QObject):
    finished = pyqtSignal(int, object)  # generation, MatchReport
    failed = pyqtSignal(int, str)  # generation, 오류 발생 원인


# match_workbooks()를 별도 스레드에서 실행
class _MatchTask(QRunnable):
    def __init__(self, baseline_path: Path, target_path: Path, generation: int) -> None:
        super().__init__()
        self.signals = _MatchSignals()
        self._baseline_path = baseline_path
        self._target_path = target_path
        self._generation = generation

    def run(self) -> None:
        try:
            report = match_workbooks(self._baseline_path, self._target_path)
        except Exception as error:
            self.signals.failed.emit(
                self._generation, str(error) or type(error).__name__
            )
        else:
            self.signals.finished.emit(self._generation, report)


class _QuestionBox(QMessageBox):
    def __init__(
        self,
        parent: QWidget,
        title: str,
        question: str,
        warning: bool = False,
        select_btn_text: str = "파일 선택",
        skip_btn_text: str = "건너뛰기",
    ):
        super().__init__(parent)
        self.setIcon(QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Question)
        self.setWindowTitle(title)
        self.setText(question)
        self.select_btn = self.addButton(
            select_btn_text, QMessageBox.ButtonRole.YesRole
        )
        self.addButton(skip_btn_text, QMessageBox.ButtonRole.NoRole)
        self.setDefaultButton(self.select_btn)


class LabelReviewFlow:
    def __init__(self, parent: QWidget | None = None):
        self._parent = parent
        self._pool = QThreadPool.globalInstance()
        self._generation = 0

    # on_done(True): 값을 읽어도 된다 / on_done(False): 담당자가 중단을 택했다
    def run(self, sheet: UploadedFile, on_done: Callable[[bool], None]) -> None:
        # 기존에 사용한 대조 파일이 있는지 확인
        baseline = recent_files.get_recent_path(yearConfig.SYSTEM_YEAR, BASELINE_KEY)
        # 이미 해당 년도에 조견표 대조를 한 기록이 있는지
        match_history = recent_files.get_recent_path(
            yearConfig.SYSTEM_YEAR, JOGYEON_KEY
        )

        if baseline is None or match_history != sheet.path:
            # 대조할 파일이 없거나 기록과 다른 파일을 업로드한 경우
            question = (
                "이전 년도 조견표와 대조하면 문구가 바뀐 항목을 미리 확인할 수 있습니다.\n"
                "대조할 파일을 선택하시겠습니까?"
            )
        elif baseline == Path(sheet.path).resolve():
            # 이 파일을 기준으로 다른 파일을 대조한 기록이 있는 경우
            question = (
                f"올리신 파일을 대조 기준으로 사용한 기록이 있어 건너뛸 수 있습니다.\n({baseline.name})\n\n"
                "다른 파일을 기준으로 대조하시겠습니까?"
            )
        else:
            # 다른 파일과 대조한 기록이 있는 경우
            question = (
                f"이전 년도 조견표와 대조한 기록이 있어 건너뛸 수 있습니다.\n({baseline.name})\n\n"
                "다른 파일을 기준으로 대조하시겠습니까?"
            )

        selected_path = self._select_baseline_file("조견표 문구 대조", question)
        if selected_path is None:
            # 건너뛰기를 선택하면 대조 없이 값을 바로 읽도록 신호 보내기
            on_done(True)
            return

        self._start_matching(selected_path, sheet.path, on_done)

    def _start_matching(
        self, baseline_path: Path, target_path: Path, on_done: Callable[[bool], None]
    ) -> None:
        self._generation += 1
        generation = self._generation

        # 커서 모양을 원형 대기 커서로 바꾸기
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        task = _MatchTask(baseline_path, target_path, generation)
        task.signals.finished.connect(
            lambda gen, report: self._on_matched(
                gen, baseline_path, target_path, report, on_done
            )
        )
        task.signals.failed.connect(
            lambda gen, message: self._on_match_failed(
                gen, message, target_path, on_done
            )
        )
        self._pool.start(task)

    def _on_matched(
        self,
        generation: int,
        baseline_path: Path,
        target_path: Path,
        report: MatchReport,
        on_done: Callable[[bool], None],
    ) -> None:
        # 커서 복원
        QApplication.restoreOverrideCursor()

        # 검토 도중 다른 파일로 바뀐 경우 무효 처리
        if generation != self._generation:
            return

        if (
            not report.review_items
            and not report.structural_alerts
            and not report.value_anomalies
        ):
            QMessageBox.information(
                self._parent,
                "라벨 대조 완료",
                f"{baseline_path.name} 과(와) 대조했습니다.\n"
                f"문구 {report.summary.total_labels}개가 모두 일치해 확인할 항목이 없습니다.",
            )
            on_done(True)
            return

        dialog = ReviewDialog(report, baseline_path, target_path, self._parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            on_done(False)
            return

        for decision in dialog.decisions():
            decision_log.record(decision)

        # 대조 파일 경로 저장하기
        recent_files.set_recent_path(
            yearConfig.SYSTEM_YEAR, BASELINE_KEY, baseline_path
        )

        on_done(True)

    def _on_match_failed(
        self,
        generation: int,
        message: str,
        target_path: Path,
        on_done: Callable[[bool], None],
    ) -> None:
        # 커서 복원
        QApplication.restoreOverrideCursor()

        # 검토 도중 다른 파일로 바뀐 경우 무효 처리
        if generation != self._generation:
            return

        question = f"조견표 대조에 실패했습니다.\n{message}\n\n대조할 파일을 다시 선택하시겠습니까?"

        selected_path = self._select_baseline_file(
            "문구 대조 실패", question, warning=True, select_btn_text="파일 다시 선택"
        )
        if selected_path is None:
            on_done(True)
            return

        self._start_matching(selected_path, target_path, on_done)

    # --- 대조 파일 선택하기 ---------------------------------------------------------
    # 선택한 파일의 Path / 파일을 선택하지 않으면 None 반환
    def _select_baseline_file(
        self,
        title: str,
        question: str,
        warning: bool = False,
        select_btn_text: str = "파일 선택",
    ):
        box = _QuestionBox(self._parent, title, question, warning, select_btn_text)
        box.exec()
        if box.clickedButton() != box.select_btn:
            return None

        path, _ = QFileDialog.getOpenFileName(
            self._parent, "대조할 조견표 선택", "", "Excel 파일 (*.xlsx)"
        )
        return Path(path) if path else None
