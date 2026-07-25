"""실행 파일 진입점 (PyInstaller 가 이 파일을 묶는다)."""

from __future__ import annotations

import sys

from hwpkit.cli import 주실행

if __name__ == "__main__":
    sys.exit(주실행(sys.argv[1:] or None))
