"""한글 문서 도우미 (HwpKit) — 한/글(HWP) 문서 작업 자동화 도구.

첨부된 원본 프로그램(범정부오피스, PyInstaller + tkinter + 한컴 COM)을 분석해
중요 기능만 남기고 구조를 다시 세운 개선판이다.

계층
    core/      한/글 COM 연결·문서 조작 (얇게)
    text/      순수 계산·변환 로직 (COM 없이 테스트됨)
    features/  실제 기능 (블록·표·서식·문서·보고서·양식·일괄처리)
    presets/   스타일·표·순화사전·보고서 유형 (데이터로 분리)
    commands   기능 등록표 — UI 와 CLI 가 같은 표를 쓴다
    ui/        단일 창 + 명령 팔레트
"""

from __future__ import annotations

__all__ = ["__version__", "버전"]

__version__ = "2.0.0"
버전 = __version__
