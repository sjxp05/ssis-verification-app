# 조견표 라벨 대조 흐름
#
# 값을 읽기 전에 작년 조견표와 문구를 대조하고, 달라진 곳을 담당자가 확인하게 한다.
# 서식이 바뀐 걸 모른 채 값을 읽으면 조용히 틀린 값이 나오기 때문이다.
#
# UploadPage 가 '문서 읽기 시작'을 누를 때 run(sheet, on_done) 을 부른다.
# match_workbooks() 가 무거워 GUI 스레드를 막지 않도록 백그라운드에서 돌리고,
# 끝나면 on_done(True|False) 를 콜백으로 부른다. 진행해도 되면 True, 담당자가
# 중단을 택하면 False.
#
# 건너뛰는 경우에도 반드시 이유를 알린다. 조용히 통과시키면 기능이 꺼진 것과
# 구분되지 않는다.

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

# 대조 기준이 되는 작년 조견표 경로를 기억해 두는 키
BASELINE_KEY = "jogyeon_baseline"


class _MatchSignals(QObject):
    finished = pyqtSignal(int, object)  # generation, MatchReport
    failed = pyqtSignal(int, str)  # generation, 사유


# match_workbooks() 를 GUI 스레드 밖에서 돌린다. upload_page._ExtractTask 와 같은 패턴.
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


class LabelReviewFlow:
    def __init__(self, parent: QWidget | None = None):
        self._parent = parent
        self._pool = QThreadPool.globalInstance()
        self._generation = 0

    # on_done(True): 값을 읽어도 된다 / on_done(False): 담당자가 중단을 택했다
    def run(self, sheet: UploadedFile, on_done: Callable[[bool], None]) -> None:
        baseline = self._baseline_path(sheet.path)
        if baseline is None:
            self._remember(sheet.path)
            on_done(True)
            return

        self._generation += 1
        generation = self._generation
        target_path = sheet.path

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        task = _MatchTask(baseline, target_path, generation)
        task.signals.finished.connect(
            lambda gen, report: self._on_matched(gen, baseline, target_path, report, on_done)
        )
        task.signals.failed.connect(
            lambda gen, message: self._on_match_failed(gen, message, on_done)
        )
        self._pool.start(task)

    def _on_matched(
        self,
        generation: int,
        baseline: Path,
        target_path: Path,
        report: MatchReport,
        on_done: Callable[[bool], None],
    ) -> None:
        if generation != self._generation:
            return  # 검토 도중 다른 파일로 바뀐 경우: 낡은 결과이므로 무시
        QApplication.restoreOverrideCursor()

        if not report.review_items and not report.structural_alerts and not report.value_anomalies:
            self._remember(target_path)
            QMessageBox.information(
                self._parent,
                "라벨 대조 완료",
                f"{baseline.name} 과(와) 대조했습니다.\n"
                f"문구 {report.summary.total_labels}개가 모두 일치해 확인할 항목이 없습니다.",
            )
            on_done(True)
            return

        dialog = ReviewDialog(report, baseline, target_path, self._parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            on_done(False)
            return

        for decision in dialog.decisions():
            decision_log.record(decision)
        self._remember(target_path)
        on_done(True)

    def _on_match_failed(
        self, generation: int, message: str, on_done: Callable[[bool], None]
    ) -> None:
        if generation != self._generation:
            return
        QApplication.restoreOverrideCursor()
        on_done(self._ask_continue_after_failure(message))

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

    def _ask_continue_after_failure(self, message: str) -> bool:
        answer = QMessageBox.warning(
            self._parent,
            "라벨 대조 실패",
            f"작년 조견표와 대조하지 못했습니다.\n{message}\n\n대조 없이 값을 읽을까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
