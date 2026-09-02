@echo off
rem ============================================================
rem  한글 문서 도우미 (HwpKit) - 윈도우 실행 파일 만들기
rem  이 파일을 두 번 눌러 실행하면 dist 폴더에 exe 가 만들어집니다.
rem  (한글이 깨져 보이면 이 파일을 메모장에서 "ANSI" 로 다시 저장하세요)
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo [1/5] 파이썬 확인
python --version >nul 2>&1
if errorlevel 1 (
  echo    파이썬이 없습니다. https://www.python.org 에서 3.10 이상을 설치하세요.
  echo    설치할 때 "Add python.exe to PATH" 를 켜 주세요.
  goto :fail
)
python -c "import struct,sys;sys.exit(0 if struct.calcsize('P')*8==64 else 1)"
if errorlevel 1 echo    알림: 32비트 파이썬입니다. 한/글이 64비트면 64비트 파이썬을 쓰세요.

echo [2/5] 빌드 환경 준비 (가상환경 .venv)
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto :fail
)
set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install --upgrade --quiet pip
if errorlevel 1 goto :fail
"%PY%" -m pip install --quiet -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [3/5] 시험 실행
"%PY%" -m pytest -q
if errorlevel 1 (
  echo    시험이 실패했습니다. 빌드를 멈춥니다.
  goto :fail
)

echo [4/5] 실행 파일 만들기
rem 폴더 형태로 만들려면 다음 줄 맨 앞의 rem 을 지우세요.
rem 폴더 형태는 시작이 빠르고 백신 오탐이 적습니다. (배포안내.md 참고)
rem set HWPKIT_ONEDIR=1
if exist build rmdir /s /q build
"%PY%" -m PyInstaller --noconfirm --clean hwpkit.spec
if errorlevel 1 goto :fail

echo [5/5] 마무리
set "RESULT=dist\한글문서도우미\한글문서도우미.exe"
if exist "dist\한글문서도우미.exe" set "RESULT=dist\한글문서도우미.exe"
if not exist "!RESULT!" (
  echo    실행 파일을 찾지 못했습니다. 위 메시지를 확인하세요.
  goto :fail
)
echo.
echo    완료: !RESULT!
for %%F in ("!RESULT!") do echo    크기: %%~zF 바이트
echo.
echo    다음 단계 (보안 경고를 없애려면)
echo      1) 코드 서명 인증서가 있으면:  sign_win.bat "!RESULT!"
echo      2) 인증서가 없으면 배포안내.md 의 "인증서 없이 배포할 때" 를 따르세요.
echo.
pause
exit /b 0

:fail
echo.
echo    빌드에 실패했습니다. 위 메시지를 확인하세요.
pause
exit /b 1
