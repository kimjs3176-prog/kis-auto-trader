"""화면 배치 계산 — 그림 그리는 부분(tkinter)과 떼어 놓은 순수 계산.

사이드 패널은 화면 가장자리(상·하·좌·우)에 붙고, 주요 기능은 작은 사각 타일을
격자로 늘어놓는다. 창 크기가 바뀔 때마다 "몇 칸으로 펼칠지", "칩을 몇 줄로
접을지", "가장자리에 붙였을 때 창 자리는 어디인지" 를 계산해야 하는데,
그 계산만 여기 모아 두었다. tkinter 없이도 시험할 수 있다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "자리들",
    "세로자리",
    "가로자리",
    "타일크기들",
    "창자리",
    "창자리계산",
    "두께다듬기",
    "칸수",
    "줄나누기",
    "제목자르기",
    "분류모습",
    "다음타일크기",
    "기본설정",
    "설정경로",
    "설정다듬기",
    "설정불러오기",
    "설정저장",
]

#: 패널을 붙일 수 있는 자리.
자리들 = ("좌", "우", "상", "하")
세로자리 = ("좌", "우")  # 길쭉하게 서는 자리 — 두께 = 너비
가로자리 = ("상", "하")  # 넓적하게 눕는 자리 — 두께 = 높이

최소두께 = 220
최대두께비 = 0.6  # 화면의 60% 를 넘지 않게 한다.
기본여백 = 48  # 작업 표시줄에 가리지 않도록 남겨 두는 자리

타일크기들 = (76, 96, 120)

#: 분류 → (타일에 넣을 글머리, 강조색). 글머리는 KS X 1001 안의 기호만 써서
#: 한글 글꼴(맑은 고딕·굴림)에서 네모로 깨지지 않게 했다.
분류모습 = {
    "블록 편집": ("¶", "#2f6fed"),
    "표": ("▦", "#0f9d58"),
    "서식": ("◎", "#8b5cf6"),
    "문서": ("§", "#d97706"),
    "보고서 만들기": ("▣", "#e0407a"),
    "양식·메일머지": ("◇", "#0d9488"),
    "일괄 처리": ("▶", "#4f46e5"),
    "도구": ("◈", "#64748b"),
}
_모름모습 = ("■", "#64748b")

기본설정: dict[str, Any] = {
    "자리": "우",
    "두께": {"좌": 380, "우": 380, "상": 300, "하": 300},
    "항상위": False,
    "타일크기": 96,
}


# ---------------------------------------------------------------- 창 자리
@dataclass(frozen=True)
class 창자리:
    """가장자리에 붙인 창의 크기와 위치."""

    너비: int
    높이: int
    왼쪽: int
    위: int

    @property
    def 지오메트리(self) -> str:
        """tkinter `geometry()` 에 그대로 넣는 문자열."""
        return f"{self.너비}x{self.높이}+{self.왼쪽}+{self.위}"


def 두께다듬기(자리이름: str, 두께: int, 화면너비: int, 화면높이: int) -> int:
    """패널 두께를 화면 크기에 맞게 가둔다.

    너무 얇으면 타일이 한 칸도 안 들어가고, 너무 두꺼우면 사이드 패널이 아니라
    그냥 큰 창이 된다.
    """
    바탕 = 화면너비 if 자리이름 in 세로자리 else 화면높이
    한계 = max(int(바탕 * 최대두께비), 최소두께)
    try:
        값 = int(두께)
    except (TypeError, ValueError):
        값 = 최소두께
    return max(최소두께, min(값, 한계))


def 창자리계산(
    자리이름: str,
    화면너비: int,
    화면높이: int,
    두께: int,
    여백: int = 기본여백,
) -> 창자리:
    """붙일 자리·화면 크기·두께로부터 창 자리를 얻는다."""
    if 자리이름 not in 자리들:
        raise ValueError(f"모르는 자리입니다: {자리이름}")
    두께 = 두께다듬기(자리이름, 두께, 화면너비, 화면높이)
    if 자리이름 in 세로자리:
        높이 = max(200, 화면높이 - 여백)
        왼쪽 = 0 if 자리이름 == "좌" else max(0, 화면너비 - 두께)
        return 창자리(너비=두께, 높이=높이, 왼쪽=왼쪽, 위=0)
    위 = 0 if 자리이름 == "상" else max(0, 화면높이 - 두께 - 여백)
    return 창자리(너비=화면너비, 높이=두께, 왼쪽=0, 위=위)


# ---------------------------------------------------------------- 격자
def 칸수(가용너비: int, 타일크기: int, 사이: int = 8) -> int:
    """가로로 타일 몇 개가 들어가는지. 최소 한 칸은 보장한다."""
    한칸 = 타일크기 + 사이
    if 한칸 <= 0:
        return 1
    return max(1, int((가용너비 + 사이) // 한칸))


def 줄나누기(너비들: Sequence[int], 가용너비: int, 사이: int = 4) -> list[list[int]]:
    """너비가 제각각인 칩을 몇 줄로 접을지 정한다. 값은 자리(index) 목록."""
    줄들: list[list[int]] = []
    현재: list[int] = []
    쓴너비 = 0
    for 자리, 너비 in enumerate(너비들):
        더할 = 너비 if not 현재 else 너비 + 사이
        if 현재 and 쓴너비 + 더할 > 가용너비:
            줄들.append(현재)
            현재 = [자리]
            쓴너비 = 너비
        else:
            현재.append(자리)
            쓴너비 += 더할
    if 현재:
        줄들.append(현재)
    return 줄들


def 제목자르기(제목: str, 타일크기: int) -> str:
    """작은 사각 타일에 넣을 만큼만 남긴다. 넘치면 말줄임표.

    96픽셀 타일에 두 줄까지가 알맞다(세 줄이 되면 아래 '선택 필요' 딱지를 가린다).
    한 줄에 대략 일곱 자가 들어가므로 열네 자를 기준으로 삼았다.
    """
    최대 = max(5, int(타일크기 / 96 * 14))
    말 = (제목 or "").strip()
    if len(말) <= 최대:
        return 말
    # '블록 값 변환(콤마·금액·날짜·나이)' 처럼 괄호로 덧붙인 설명이 있으면
    # 그 앞까지만 남긴다. 글자 수로 자르는 것보다 뜻이 살아 있다.
    앞 = 말.split("(", 1)[0].strip()
    if 0 < len(앞) <= 최대:
        return 앞
    return 말[: 최대 - 1].rstrip() + "…"


def 분류모습얻기(분류: str) -> tuple[str, str]:
    """분류 → (글머리, 강조색). 모르는 분류도 안전하게 받아 준다."""
    return 분류모습.get(분류, _모름모습)


def 다음타일크기(현재: int) -> int:
    """타일 크기를 작게 → 보통 → 크게 → 작게 로 돌린다."""
    if 현재 not in 타일크기들:
        return 타일크기들[0]
    자리 = 타일크기들.index(현재)
    return 타일크기들[(자리 + 1) % len(타일크기들)]


# ---------------------------------------------------------------- 설정 저장
def 설정경로() -> Path:
    """`%USERPROFILE%\\.hwpkit\\ui.json` (윈도우 밖에서는 홈 폴더)."""
    뿌리 = Path(os.environ.get("USERPROFILE") or Path.home())
    return 뿌리 / ".hwpkit" / "ui.json"


def 설정다듬기(날것: Any) -> dict[str, Any]:
    """파일에서 읽은 값을 믿지 않고 하나씩 확인한다."""
    설정: dict[str, Any] = {
        "자리": 기본설정["자리"],
        "두께": dict(기본설정["두께"]),
        "항상위": 기본설정["항상위"],
        "타일크기": 기본설정["타일크기"],
    }
    if not isinstance(날것, dict):
        return 설정

    자리 = 날것.get("자리")
    if 자리 in 자리들:
        설정["자리"] = 자리

    두께 = 날것.get("두께")
    if isinstance(두께, dict):
        for 이름, 값 in 두께.items():
            if 이름 not in 자리들:
                continue
            try:
                설정["두께"][이름] = max(최소두께, int(값))
            except (TypeError, ValueError):
                continue

    설정["항상위"] = bool(날것.get("항상위", 기본설정["항상위"]))

    크기 = 날것.get("타일크기")
    if 크기 in 타일크기들:
        설정["타일크기"] = 크기
    return 설정


def 설정불러오기(경로: Path | None = None) -> dict[str, Any]:
    """저장해 둔 화면 설정을 읽는다. 없거나 깨졌으면 기본값."""
    파일 = 경로 or 설정경로()
    try:
        날것 = json.loads(파일.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 설정다듬기(None)
    return 설정다듬기(날것)


def 설정저장(설정: dict[str, Any], 경로: Path | None = None) -> bool:
    """화면 설정을 남긴다. 저장하지 못해도 프로그램은 그대로 돈다."""
    파일 = 경로 or 설정경로()
    다듬은 = 설정다듬기(설정)
    try:
        파일.parent.mkdir(parents=True, exist_ok=True)
        파일.write_text(
            json.dumps(다듬은, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        return False
    return True


def 정렬순서(명령들: Iterable[Any], 분류순서: Sequence[str]) -> list[Any]:
    """타일에 늘어놓을 차례 — 분류 순서 → 제목 순."""
    차례 = {이름: 자리 for 자리, 이름 in enumerate(분류순서)}
    return sorted(
        명령들, key=lambda 하나: (차례.get(하나.분류, len(차례)), 하나.제목)
    )
