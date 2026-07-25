@echo off
rem ============================================================
rem  코드 서명 - 윈도우 보안 경고("알 수 없는 발행자")를 없애는 정식 방법
rem
rem  준비물
rem    · 코드 서명(Code Signing) 인증서 - OV 또는 EV
rem    · signtool.exe - Windows SDK 의 "Signing Tools" 에 들어 있습니다
rem
rem  사용법
rem    sign_win.bat "dist\한글문서도우미.exe"
rem
rem  인증서 지정 (한 가지만 고르면 됩니다)
rem    A. PFX 파일:  set HWPKIT_PFX=C:\경로\인증서.pfx  그리고  set HWPKIT_PFX_PW=암호
rem    B. 인증서 저장소/USB 토큰:  set HWPKIT_CERT_NAME=발행 대상 이름 일부
rem ============================================================
setlocal
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=dist\한글문서도우미.exe"
if not exist "%TARGET%" (
  echo 서명할 파일이 없습니다: %TARGET%
  goto :fail
)

where signtool >nul 2>&1
if errorlevel 1 (
  echo signtool 을 찾지 못했습니다.
  echo Windows SDK 의 Signing Tools 를 설치하거나,
  echo "Developer Command Prompt for VS" 에서 이 파일을 실행하세요.
  goto :fail
)

rem 시간 도장 - 인증서가 만료된 뒤에도 서명이 유효하게 남습니다.
set "TSA=http://timestamp.digicert.com"

if not "%HWPKIT_PFX%"=="" (
  echo [서명] PFX 파일로 서명합니다: %HWPKIT_PFX%
  signtool sign /fd sha256 /td sha256 /tr "%TSA%" /f "%HWPKIT_PFX%" /p "%HWPKIT_PFX_PW%" /d "한글 문서 도우미" "%TARGET%"
  if errorlevel 1 goto :fail
) else if not "%HWPKIT_CERT_NAME%"=="" (
  echo [서명] 인증서 저장소의 "%HWPKIT_CERT_NAME%" 로 서명합니다.
  signtool sign /fd sha256 /td sha256 /tr "%TSA%" /n "%HWPKIT_CERT_NAME%" /a /d "한글 문서 도우미" "%TARGET%"
  if errorlevel 1 goto :fail
) else (
  echo 인증서를 지정하지 않았습니다. 아래 중 하나를 먼저 설정하세요.
  echo    set HWPKIT_PFX=C:\경로\인증서.pfx  ^&  set HWPKIT_PFX_PW=암호
  echo    set HWPKIT_CERT_NAME=인증서 발행 대상 이름
  goto :fail
)

echo [확인] 서명 검증
signtool verify /pa /v "%TARGET%"
if errorlevel 1 goto :fail

echo.
echo 서명을 마쳤습니다: %TARGET%
echo   · "알 수 없는 발행자" 경고는 사라집니다.
echo   · OV 인증서는 평판이 쌓이기까지 며칠간 SmartScreen 안내가 더 뜰 수 있습니다.
echo     EV 인증서는 처음부터 뜨지 않습니다.
echo.
echo 파일 해시(정보보안 예외 등록 요청에 쓰세요)
powershell -NoProfile -Command "Get-FileHash '%TARGET%' -Algorithm SHA256 | Format-List Algorithm,Hash"
pause
exit /b 0

:fail
echo.
echo 서명에 실패했습니다.
pause
exit /b 1
