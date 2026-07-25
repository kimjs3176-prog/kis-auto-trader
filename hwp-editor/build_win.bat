@echo off
rem 윈도우 실행 파일 만들기 (원본과 같은 PyInstaller 방식)
rem 원본은 버튼 PNG 17MB 때문에 27MB 였지만, 이 버전은 이미지가 없어 훨씬 작습니다.
setlocal
chcp 65001 >nul

python -m pip install --upgrade pip pyinstaller || goto :error
python -m pip install -r requirements.txt || goto :error
python -m pytest || goto :error

pyinstaller --noconfirm --clean ^
  --name 한글문서도우미 ^
  --onefile ^
  --windowed ^
  --add-data "hwpkit\presets;hwpkit\presets" ^
  --hidden-import win32com.client ^
  --hidden-import pythoncom ^
  --hidden-import pywintypes ^
  run.py || goto :error

echo.
echo 완료: dist\한글문서도우미.exe
goto :eof

:error
echo.
echo 빌드에 실패했습니다. 위 메시지를 확인하세요.
exit /b 1
