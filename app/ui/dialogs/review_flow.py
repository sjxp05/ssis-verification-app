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
from utils.date import yearConfig

# 대조 기준이 되는 조견표 경로를 기억해 두는 키
BASELINE_KEY = "jogyeon_baseline"

# 전년도 조견표들을 확인하는 키
JOGYEON_KEY = "jogyeon"


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

        # 현재 파일을 다른 파일과 대조한 기록이 없는 경우
        if baseline is None:
            # 이전 년도 조견표들을 모두 검색해서 가장 가까운 연도의 것을 찾음
            baseline = recent_files.search_jogyeon_history(
                yearConfig.SYSTEM_YEAR, JOGYEON_KEY
            )

            # TODO: 이전 년도 조견표가 있는 경우 (대조한 기록은 없음) 선택할 수 있게 하기
            #   - search_jogyeon_history()에서 {year: Path} 형태로 반환하도록 바꾸기
            #   - 받은 dict 중 선택하거나, 다른 파일 선택 옵션 열어두기
            #   - 다른 파일 선택을 누른 경우 파일 선택기 열어주기

        if baseline is None:
            # 대조할 파일을 찾지 못한 경우
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

        # 대조 파일 경로 저장하기
        recent_files.set_recent_path(
            yearConfig.SYSTEM_YEAR, BASELINE_KEY, baseline_path
        )

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
        baseline: Path,
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

    def _remember(self, path: Path) -> None:
        # 다음 연도의 기준 파일로 저장한다.
        recent_files.set_recent_path(yearConfig.SYSTEM_YEAR + 1, BASELINE_KEY, path)
