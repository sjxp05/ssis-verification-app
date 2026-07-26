class MainWindow(QMainWindow):
    TAB_UPLOAD, TAB_VALIDATION, TAB_ERRORS, TAB_UNITPRICE, TAB_UNITVALID = range(5)
    TAB_LABELS = ["⬆ 파일 업로드", "▦ 조견표 검증", "⚠ 오류 목록", "▤ 단가표 생성", "✔ 단가표 검증"]

    def __init__(self, backend: "BackendHooks"):
        super().__init__()
        self.backend = backend
        self.quick: Optional[SheetData] = None   # 조견표 검증 결과
        self.unit: Optional[SheetData] = None    # 단가표 검증 결과
        self.setWindowTitle("데이터 검증 자동화 시스템")
        self.resize(1280, 800)
        self.setStyleSheet(f"QMainWindow{{background:{T.BACKGROUND};}}")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_tabbar())

        # 페이지 생성
        self.page_upload = UploadPage()
        self.page_validation = ValidationPage()
        self.page_errors = ErrorListPage()
        self.page_unitprice = UnitPricePage()
        self.page_unitvalid = UnitValidationPage()

        self.stack = QStackedWidget()
        for p in (self.page_upload, self.page_validation, self.page_errors,
                  self.page_unitprice, self.page_unitvalid):
            self.stack.addWidget(p)
        root.addWidget(self.stack, 1)
        root.addWidget(self._build_footer())

        self._connect_signals()
        self.go(self.TAB_UPLOAD)

    # ── 시그널 연결 ──────────────────────────────────────────
    def _connect_signals(self):
        self.page_upload.validateRequested.connect(self.run_validation)

        self.page_validation.fixRequested.connect(lambda e, v: self.fix_error(self.quick, e, v))
        self.page_validation.fixAllRequested.connect(lambda: self.fix_all(self.quick))
        self.page_validation.saveRequested.connect(lambda: self.save_sheet(self.quick))

        self.page_errors.fixRequested.connect(lambda e, v: self.fix_error(self.quick, e, v))
        self.page_errors.fixAllRequested.connect(lambda: self.fix_all(self.quick))
        self.page_errors.saveRequested.connect(lambda: self.save_sheet(self.quick))
        self.page_errors.rowActivated.connect(self._jump_to_error)

        self.page_unitprice.generateRequested.connect(self.run_generate)
        self.page_unitprice.downloadRequested.connect(self.download_unit_price)
        self.page_unitprice.validateRequested.connect(self.run_unit_validation)

        self.page_unitvalid.goGenerate.connect(lambda: self.go(self.TAB_UNITPRICE))
        self.page_unitvalid.validation.fixRequested.connect(lambda e, v: self.fix_error(self.unit, e, v))
        self.page_unitvalid.validation.fixAllRequested.connect(lambda: self.fix_all(self.unit))
        self.page_unitvalid.validation.saveRequested.connect(lambda: self.save_sheet(self.unit))

    # ── 헤더/탭바/푸터 ───────────────────────────────────────
    def _build_header(self) -> QWidget:
        head = QFrame()
        head.setFixedHeight(48)
        head.setStyleSheet(f"background:{T.PRIMARY};")
        l = QHBoxLayout(head)
        l.setContentsMargins(20, 0, 20, 0)
        l.setSpacing(10)
        logo = QLabel("▦")
        logo.setFixedSize(28, 28)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background:rgba(255,255,255,0.15); color:white; border-radius:4px; font-size:14px;")
        title = QLabel("데이터 검증 자동화 시스템")
        title.setStyleSheet("color:white; font-size:13px; font-weight:600;")
        l.addWidget(logo)
        l.addWidget(title)
        l.addStretch()
        self.hdr_err = QLabel()
        self.hdr_err.setStyleSheet("background:rgba(239,68,68,0.2); color:#fecaca;"
                                   " border:1px solid rgba(248,113,113,0.3); border-radius:4px;"
                                   " padding:3px 8px; font-size:11px;")
        self.hdr_fix = QLabel()
        self.hdr_fix.setStyleSheet("background:rgba(34,197,94,0.2); color:#bbf7d0;"
                                   " border:1px solid rgba(74,222,128,0.3); border-radius:4px;"
                                   " padding:3px 8px; font-size:11px;")
        self.hdr_err.hide()
        self.hdr_fix.hide()
        date = QLabel("🕒 " + QDate.currentDate().toString("yyyy. MM. dd."))
        date.setStyleSheet("color:rgba(255,255,255,0.5); font-size:11px;")
        l.addWidget(self.hdr_err)
        l.addWidget(self.hdr_fix)
        l.addWidget(date)
        return head

    def _build_tabbar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(f"background:{T.CARD}; border-bottom:1px solid {T.BORDER};")
        l = QHBoxLayout(bar)
        l.setContentsMargins(20, 0, 20, 0)
        l.setSpacing(0)
        self.tabs: list[QPushButton] = []
        for i, txt in enumerate(self.TAB_LABELS):
            b = QPushButton(txt)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(42)
            b.clicked.connect(lambda _, ix=i: self.go(ix))
            l.addWidget(b)
            self.tabs.append(b)
        l.addStretch()
        return bar

    def _build_footer(self) -> QWidget:
        foot = QFrame()
        foot.setFixedHeight(28)
        foot.setStyleSheet(f"background:{T.MUTED}; border-top:1px solid {T.BORDER};")
        l = QHBoxLayout(foot)
        l.setContentsMargins(20, 0, 20, 0)
        l.setSpacing(16)
        self.foot_status = QLabel("○ 대기 중")
        self.foot_status.setStyleSheet(f"font-size:11px; color:{T.MUTED_FG};")
        self.foot_files = QLabel()
        self.foot_files.setStyleSheet(f"font-size:11px; color:{T.MUTED_FG};")
        ver = QLabel("공공기관 데이터 검증 자동화 시스템 v1.0")
        ver.setStyleSheet(f"font-size:11px; color:{T.MUTED_FG};")
        l.addWidget(self.foot_status)
        l.addWidget(self.foot_files)
        l.addStretch()
        l.addWidget(ver)
        return foot

    def go(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self.tabs):
            active = i == index
            if active:
                b.setStyleSheet(f"QPushButton{{background:transparent; color:{T.PRIMARY}; border:none;"
                                f" border-bottom:2px solid {T.PRIMARY}; font-size:12px; font-weight:600;"
                                f" padding:0 16px;}}")
            else:
                b.setStyleSheet(f"QPushButton{{background:transparent; color:{T.MUTED_FG}; border:none;"
                                f" border-bottom:2px solid transparent; font-size:12px; padding:0 16px;}}"
                                f"QPushButton:hover{{color:{T.FG};}}")

    # ── 동작 (백엔드 호출 → UI 반영) ──────────────────────────
    def run_validation(self):
        """탭 1: 검증 실행."""
        guide = self.page_upload.card_guide.file
        sheet = self.page_upload.card_sheet.file
        if not (guide and sheet):
            return
        self.page_upload.set_busy(True)
        try:
            # TODO: 오래 걸리는 작업이면 QThread/QThreadPool 로 감싸서 UI 프리징 방지
            self.quick = self.backend.validate_quick_reference(guide.path, sheet.path)
        except Exception as ex:
            QMessageBox.critical(self, "검증 실패", str(ex))
            return
        finally:
            self.page_upload.set_busy(False)
        self.page_validation.set_data(self.quick)
        self.page_errors.set_data(self.quick)
        self.refresh_status()
        self.go(self.TAB_VALIDATION)

    def fix_error(self, data: Optional[SheetData], err: ValidationError, value: str):
        """오류 1건 수정. value="" 이면 expected 로 자동 수정."""
        if not data:
            return
        err.fixed = True
        err.current = value or err.expected
        # TODO: 수정 내역을 백엔드에도 반영해야 하면 여기서 호출 (예: backend.apply_fix(err))
        self._refresh_views(data)

    def fix_all(self, data: Optional[SheetData]):
        if not data:
            return
        for e in data.open_errors:
            e.fixed = True
            e.current = e.expected
        # TODO: 일괄 수정 백엔드 반영이 필요하면 여기서 호출
        self._refresh_views(data)

    def save_sheet(self, data: Optional[SheetData]):
        if not data:
            return
        path, _ = QFileDialog.getSaveFileName(self, "파일 저장", data.filename, "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.backend.save_fixed_sheet(data, path)
            QMessageBox.information(self, "저장 완료", f"파일이 저장되었습니다.\n{path}")
        except Exception as ex:
            QMessageBox.critical(self, "저장 실패", str(ex))

    def run_generate(self):
        """탭 4: 단가표 생성."""
        self.page_unitprice.set_busy("generate", True)
        try:
            # TODO: 오래 걸리면 QThread 처리
            headers, rows, filename, size_text = self.backend.generate_unit_price(self.quick)
        except Exception as ex:
            QMessageBox.critical(self, "생성 실패", str(ex))
            return
        finally:
            self.page_unitprice.set_busy("generate", False)
        self.page_unitprice.set_preview(headers, rows)
        self.page_unitprice.set_generated(filename, size_text)

    def download_unit_price(self):
        path, _ = QFileDialog.getSaveFileName(self, "다운로드", "unit_price_list.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.backend.export_unit_price(path)
            QMessageBox.information(self, "저장 완료", f"파일이 저장되었습니다.\n{path}")
        except Exception as ex:
            QMessageBox.critical(self, "저장 실패", str(ex))

    def run_unit_validation(self):
        """탭 4 → 5: 단가표 검증."""
        self.page_unitprice.set_busy("validate", True)
        try:
            # TODO: 오래 걸리면 QThread 처리
            self.unit = self.backend.validate_unit_price()
        except Exception as ex:
            QMessageBox.critical(self, "검증 실패", str(ex))
            return
        finally:
            self.page_unitprice.set_busy("validate", False)
        self.page_unitvalid.show_validation(self.unit)
        self.go(self.TAB_UNITVALID)

    # ── 화면 갱신 ────────────────────────────────────────────
    def _refresh_views(self, data: SheetData):
        if data is self.quick:
            self.page_validation.refresh()
            self.page_errors.refresh()
        elif data is self.unit:
            self.page_unitvalid.validation.refresh()
        self.refresh_status()

    def _jump_to_error(self, err: ValidationError):
        self.go(self.TAB_VALIDATION)
        self.page_validation.open_detail(err)

    def refresh_status(self):
        """헤더 배지 / 푸터 / 단가표 페이지 상태 동기화."""
        if not self.quick:
            return
        n_open, n_fixed = len(self.quick.open_errors), len(self.quick.fixed_errors)
        self.hdr_err.setVisible(n_open > 0)
        self.hdr_err.setText(f"⨯ 오류 {n_open}건")
        self.hdr_fix.setVisible(n_fixed > 0)
        self.hdr_fix.setText(f"✔ 수정 {n_fixed}건")
        self.foot_status.setText("● 검증 완료")
        self.foot_status.setStyleSheet(f"font-size:11px; color:{T.GREEN};")
        files = []
        if self.page_upload.card_guide.file:
            files.append("📄 " + self.page_upload.card_guide.file.name)
        if self.page_upload.card_sheet.file:
            files.append("▦ " + self.page_upload.card_sheet.file.name)
        self.foot_files.setText("    ".join(files))
        self.page_unitprice.set_ready(True, len(self.quick.errors), n_fixed)


# ═════════════════════════════════════════════════════════════════════════════
# [6] BackendHooks — ★ 백엔드 로직 연결 지점 (여기만 채우면 됨) ★
# ═════════════════════════════════════════════════════════════════════════════
class BackendHooks:
    """
    구현된 백엔드 로직을 이 클래스의 메서드에 연결하세요.
    각 메서드는 UI가 그대로 소비할 수 있는 형태(SheetData / ValidationError)를 반환합니다.
    실패 시 예외를 던지면 UI가 에러 다이얼로그를 띄웁니다.
    """

    def validate_quick_reference(self, guide_pdf_path: str, sheet_xlsx_path: str) -> SheetData:
        """사업지침 + 조견표 → 검증 결과."""
        # TODO: 백엔드 검증 로직 호출 후 결과를 SheetData 로 변환하여 반환
        #   return SheetData(
        #       filename=os.path.basename(sheet_xlsx_path),
        #       sheet_name="...",
        #       headers=[...],                # 표 헤더
        #       rows=[[...], ...],            # 표 데이터 (문자열 2차원 리스트)
        #       errors=[ValidationError(...), ...],
        #   )
        raise NotImplementedError("validate_quick_reference 를 구현하세요.")

    def save_fixed_sheet(self, data: SheetData, save_path: str) -> None:
        """수정 완료된 시트를 엑셀로 저장."""
        # TODO: data.rows + data.errors(수정값 반영됨) 를 엑셀로 기록
        raise NotImplementedError("save_fixed_sheet 를 구현하세요.")

    def generate_unit_price(self, quick: Optional[SheetData]) -> tuple[list[str], list[list[str]], str, str]:
        """단가표 생성. 반환: (headers, rows, 파일명, 크기 텍스트)."""
        # TODO: 검증된 조견표 기반 단가표 생성 로직 호출
        raise NotImplementedError("generate_unit_price 를 구현하세요.")

    def export_unit_price(self, save_path: str) -> None:
        """생성된 단가표 엑셀 파일 내보내기."""
        # TODO: 생성 결과를 save_path 에 기록
        raise NotImplementedError("export_unit_price 를 구현하세요.")

    def validate_unit_price(self) -> SheetData:
        """생성된 단가표 검증 결과."""
        # TODO: 단가표 검증 로직 호출 후 SheetData 반환
        raise NotImplementedError("validate_unit_price 를 구현하세요.")