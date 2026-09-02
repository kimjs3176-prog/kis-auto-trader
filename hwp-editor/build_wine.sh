#!/usr/bin/env bash
# ============================================================
#  윈도우 exe 를 리눅스에서 만들기 (Wine + 윈도우 CPython)
#
#  윈도우 PC 가 없을 때 쓰는 경로입니다. 결과물은 진짜 윈도우 실행 파일(PE32+)이며,
#  부트로더도 PyInstaller 의 윈도우 wheel 에서 나온 것이라 윈도우에서 그대로 돕니다.
#
#  준비물: wine64, curl, tar  (sudo apt-get install -y --no-install-recommends wine64)
#  사용법: bash build_wine.sh              →  dist_wine/한글문서도우미.exe (한 파일)
#          HWPKIT_ONEDIR=1 bash build_wine.sh →  dist_wine/한글문서도우미/ (폴더 형태)
#
#  폴더 형태는 실행할 때 임시 폴더에 자신을 풀지 않아 **백신 오탐이 훨씬 적고**
#  시작도 빠르다. 사내 배포라면 폴더 형태를 zip 으로 묶어 나눠 주는 편이 낫다.
#
#  변수 이름은 반드시 영문으로 씁니다. bash 는 한글 변수 이름을 변수로 보지 않고
#  명령으로 실행하려 들어 "command not found" 로 죽습니다. (설명·메시지는 한글)
# ============================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${HWPKIT_WINE_WORK:-/tmp/hwpkit-wine}"
PYVER="3.11.9"
PBS_TAG="20240415" # python-build-standalone 릴리스 태그
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PYVER}+${PBS_TAG}-x86_64-pc-windows-msvc-install_only.tar.gz"

WINE="${WINE:-$(command -v wine64 || true)}"
[ -n "$WINE" ] || WINE=/usr/lib/wine/wine64
[ -x "$WINE" ] || {
  echo "wine64 를 찾을 수 없습니다. apt-get install -y --no-install-recommends wine64 로 설치하세요."
  exit 1
}

mkdir -p "$WORK"
cd "$WORK"

# 1) tkinter 가 포함된 윈도우 CPython 내려받기 (nuget 의 python 패키지에는 tkinter 가 없다)
if [ ! -x python/python.exe ]; then
  echo "[1/4] 윈도우 CPython ${PYVER} 내려받기"
  curl -sSL --max-time 900 -o pbs.tar.gz "$PBS_URL"
  tar xzf pbs.tar.gz
fi

export WINEPREFIX="$WORK/wineprefix"
export WINEDEBUG=-all
export WINEDLLOVERRIDES="mscoree,mshtml="
export PYTHONLEGACYWINDOWSSTDIO=1 # Wine 에서 표준출력 초기화 오류 방지
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
tar -C "$HERE" --exclude=.venv --exclude=build --exclude=dist --exclude=dist_wine \
  --exclude=__pycache__ --exclude=.pytest_cache -cf - . | tar -C src -xf -
sed -i 's/이름 = "한글문서도우미"/이름 = "HwpKit"/' src/hwpkit.spec
# 출력은 반드시 **파이프**로 넘긴다. 로그를 파일로 바로 받으면(`> build.log`)
# Wine 의 파이썬이 그 핸들을 열지 못해 다음과 같이 죽는다.
#   Fatal Python error: init_sys_streams: can't initialize sys standard streams
#   OSError: [WinError 6] Invalid handle
(cd src && "$WINE" ../python/python.exe -m PyInstaller --noconfirm --clean --log-level WARN hwpkit.spec 2>&1) | cat

# 4) 결과물 정리
echo "[4/4] 결과물 정리"
mkdir -p "$HERE/dist_wine"
cd "$HERE/dist_wine"

if [ "${HWPKIT_ONEDIR:-}" = "1" ]; then
  rm -rf "한글문서도우미"
  cp -r "$WORK/src/dist/HwpKit" "한글문서도우미"
  mv "한글문서도우미/HwpKit.exe" "한글문서도우미/한글문서도우미.exe"
  # 사내 공유 폴더로 나눠 주기 좋게 zip 으로도 묶어 둔다.
  rm -f "한글문서도우미.zip"
  if command -v zip >/dev/null 2>&1; then
    zip -qr "한글문서도우미.zip" "한글문서도우미"
  fi
  echo
  echo "완료(폴더 형태): $HERE/dist_wine/한글문서도우미/한글문서도우미.exe"
  file "한글문서도우미/한글문서도우미.exe"
  sha256sum "한글문서도우미/한글문서도우미.exe"
  [ -f "한글문서도우미.zip" ] && echo "zip: $HERE/dist_wine/한글문서도우미.zip"
else
  cp "$WORK/src/dist/HwpKit.exe" "한글문서도우미.exe"
  echo
  echo "완료: $HERE/dist_wine/한글문서도우미.exe"
  file 한글문서도우미.exe
  sha256sum 한글문서도우미.exe
fi
echo
echo "이 파일은 서명되지 않았습니다. 보안 경고 대응은 배포안내.md 를 보세요."
echo "(폴더 형태가 백신 오탐이 가장 적습니다: HWPKIT_ONEDIR=1 bash build_wine.sh)"
