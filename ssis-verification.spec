# -*- mode: python ; coding: utf-8 -*-
#
# onedir 빌드 스펙.
#
#   pyinstaller ssis-verification.spec
#
# 결과물: dist/ssis-verification/ssis-verification.exe
#
# rules/ 는 읽기 전용 기본 규칙 파일 번들이라 여기(datas)로 들어간다.
# 사용자가 실제로 고른 규칙 파일 경로 기록(.recent_paths_cache.json)은
# 쓰기 가능 영역(APPDATA)에 따로 저장되므로 번들 대상이 아니다.
# (app/services/recent_files.py, app/utils/appdata.py 참고)

from PyInstaller.utils.hooks import collect_all

datas = [
    ("rules", "rules"),
    ("app/resources/styles/app.qss", "resources/styles"),
    ("app/jogyeon_matcher/resources", "jogyeon_matcher/resources"),
]
binaries = []
hiddenimports = []

# onnxruntime / tokenizers 는 embedding_encoder.py 안에서 지연 import 되고
# 바이너리 확장 모듈을 포함하므로 collect_all로 데이터·바이너리까지 챙긴다.
for pkg in ("onnxruntime", "tokenizers"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["app/main.py"],
    pathex=["app"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="사회보장정보원_단가표검증_프로그램",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ssis-verification",
)
