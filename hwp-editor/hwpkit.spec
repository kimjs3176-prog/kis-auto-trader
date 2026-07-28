# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 설정.

원본(범정부오피스)과 같은 방식으로 하나의 실행 파일을 만들되, 백신 오탐과 보안
경고를 줄이는 설정을 함께 넣었다.

* UPX 압축을 쓰지 않는다 — 압축된 실행 파일은 백신이 가장 먼저 의심한다.
* 버전·제조사 정보(version_info.txt)와 아이콘을 심는다 — 정보 없는 파일은
  Defender SmartScreen 평판이 더 나쁘다.
* 관리자 권한을 요구하지 않는다(asInvoker) — 권한 상승 창이 뜨지 않는다.
* 콘솔 창을 띄우지 않는다(windowed).

두 가지 형태로 만들 수 있다. 환경변수 HWPKIT_ONEDIR=1 이면 폴더 형태.

    pyinstaller --noconfirm --clean hwpkit.spec          (한 파일)
    set HWPKIT_ONEDIR=1 && pyinstaller --noconfirm --clean hwpkit.spec   (폴더)

폴더 형태는 실행할 때 임시 폴더에 풀지 않아 **시작이 빠르고 백신 오탐도 적다**.
사내 공유 폴더로 배포한다면 폴더 형태를 권한다.
"""

import os

한파일 = os.environ.get("HWPKIT_ONEDIR", "") not in ("1", "true", "True")
이름 = "한글문서도우미"

분석 = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("hwpkit/presets", "hwpkit/presets"),  # 스타일·표·보고서 유형·순화 사전
    ],
    hiddenimports=[
        "win32com.client",
        "win32com.client.gencache",
        "pythoncom",
        "pywintypes",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 쓰지 않는 큰 묶음을 빼서 파일을 작게 만든다(오탐도 줄어든다).
    excludes=[
        # pythonwin(win32ui)은 쓰지 않는데 MFC DLL(mfc140u.dll)을 끌고 와 경고를 낸다.
        "pythonwin",
        "win32ui",
        "win32uiole",
        "numpy",
        "pandas",
        "matplotlib",
        "PyQt5",
        "PySide6",
        "IPython",
        "pytest",
        "setuptools",
        "pip",
    ],
    noarchive=False,
    optimize=0,
)

묶음 = PYZ(분석.pure)

공통 = dict(
    name=이름,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 백신 오탐의 가장 큰 원인 — 켜지 말 것
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/hwpkit.ico",
    version="version_info.txt",
    uac_admin=False,  # 관리자 권한 요구하지 않음(asInvoker)
)

if 한파일:
    실행파일 = EXE(
        묶음,
        분석.scripts,
        분석.binaries,
        분석.datas,
        [],
        runtime_tmpdir=None,
        **공통,
    )
else:
    실행파일 = EXE(묶음, 분석.scripts, [], exclude_binaries=True, **공통)
    묶음폴더 = COLLECT(
        실행파일,
        분석.binaries,
        분석.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=이름,
    )
