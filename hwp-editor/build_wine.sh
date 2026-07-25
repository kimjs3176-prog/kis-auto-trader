#!/usr/bin/env bash
# ============================================================
#  윈도우 exe 를 리눅스에서 만들기 (Wine + 윈도우 CPython)
#
#  윈도우 PC 가 없을 때 쓰는 경로입니다. 결과물은 진짜 윈도우 실행 파일(PE32+)이며,
#  부트로더도 PyInstaller 의 윈도우 wheel 에서 나온 것이라 윈도우에서 그대로 돕니다.
#
#  준비물: wine64, curl, tar  (sudo apt-get install -y --no-install-recommends wine64)
#  사용법: bash build_wine.sh   →  dist_wine/한글문서도우미.exe
# ============================================================
set -euo pipefail

여기="$(cd "$(dirname "$0")" && pwd)"
작업="${HWPKIT_WINE_WORK:-/tmp/hwpkit-wine}"
파이썬버전="3.11.9"
빌드날짜="20240415"   # python-build-standalone 릴리스 태그
받을주소="https://github.com/astral-sh/python-build-standalone/releases/download/${빌드날짜}/cpython-${파이썬버전}+${빌드날짜}-x86_64-pc-windows-msvc-install_only.tar.gz"

command -v wine64 >/dev/null 2>&1 || WINE=/usr/lib/wine/wine64
WINE="${WINE:-$(command -v wine64)}"
[ -x "$WINE" ] || { echo "wine64 를 찾을 수 없습니다. apt-get install wine64 로 설치하세요."; exit 1; }

mkdir -p "$작업"
cd "$작업"

# 1) tkinter 가 포함된 윈도우 CPython 내려받기 (nuget 의 python 패키지에는 tkinter 가 없다)
if [ ! -x python/python.exe ]; then
  echo "[1/4] 윈도우 CPython ${파이썬버전} 내려받기"
  curl -sSL --max-time 600 -o pbs.tar.gz "$받을주소"
  tar xzf pbs.tar.gz
fi

export WINEPREFIX="$작업/wineprefix"
export WINEDEBUG=-all
export WINEDLLOVERRIDES="mscoree,mshtml="
export PYTHONLEGACYWINDOWSSTDIO=1   # Wine 에서 표준출력 초기화 오류 방지
export PYTHONUTF8=1
mkdir -p "$WINEPREFIX"

# 2) 빌드 도구 설치
echo "[2/4] PyInstaller·pywin32·openpyxl 설치"
"$WINE" python/python.exe -m pip install --quiet --no-warn-script-location \
  --disable-pip-version-check pyinstaller pywin32 openpyxl 2>&1 | tail -2

# 3) 소스 복사 — Wine 은 한글이 섞인 경로·파일 이름을 제대로 다루지 못하므로
#    ASCII 경로에서 ASCII 이름으로 빌드한 뒤 마지막에 이름을 되돌린다.
echo "[3/4] 빌드"
rm -rf src && mkdir -p src
tar -C "$여기" --exclude=.venv --exclude=build --exclude=dist --exclude=__pycache__ \
    --exclude=.pytest_cache -cf - . | tar -C src -xf -
sed -i 's/이름 = "한글문서도우미"/이름 = "HwpKit"/' src/hwpkit.spec
( cd src && "$WINE" ../python/python.exe -m PyInstaller --noconfirm --clean --log-level WARN hwpkit.spec )

# 4) 결과물 정리
echo "[4/4] 결과물 정리"
mkdir -p "$여기/dist_wine"
cp src/dist/HwpKit.exe "$여기/dist_wine/한글문서도우미.exe"
cd "$여기/dist_wine"
echo
echo "완료: $여기/dist_wine/한글문서도우미.exe"
file 한글문서도우미.exe
sha256sum 한글문서도우미.exe
echo
echo "이 파일은 서명되지 않았습니다. 보안 경고 대응은 배포안내.md 를 보세요."
