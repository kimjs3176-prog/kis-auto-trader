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
    "한줄글자수",
    "미끄럼값",
    "미끄럼자리",
    "딱지방식",
    "둥근네모점들",
    "투명도다듬기",
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

기본설정: dict[str, Any] = {
    "자리": "우",
    "두께": {"좌": 380, "우": 380, "상": 300, "하": 300},
    "항상위": False,
    "타일크기": 96,
    "투명도": 100,
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


def 한줄글자수(타일크기: int) -> int:
    """타일 한 줄에 들어가는 한글 글자 수. (96픽셀에 일곱 자)"""
    return max(4, int(타일크기 / 96 * 7))


def _낱말로접기(말: str, 한줄: int) -> list[str]:
    """띄어쓰기를 지키며 줄을 접는다. 한 낱말이 한 줄보다 길면 그 낱말을 자른다."""
    줄들: list[str] = []
    현재 = ""
    for 낱말 in 말.split():
        while len(낱말) > 한줄:  # '개인정보가리기' 처럼 긴 낱말은 잘라서라도 넣는다
            if 현재:
                줄들.append(현재)
                현재 = ""
            줄들.append(낱말[:한줄])
            낱말 = 낱말[한줄:]
        후보 = f"{현재} {낱말}".strip()
        if len(후보) <= 한줄:
            현재 = 후보
        else:
            if 현재:
                줄들.append(현재)
            현재 = 낱말
    if 현재:
        줄들.append(현재)
    return 줄들


def 제목자르기(제목: str, 타일크기: int, 줄수: int = 2) -> str:
    """타일에 넣을 제목을 두 줄로 접는다. 넘치면 말줄임표.

    글자 수만 세면 안 된다. tkinter 는 **띄어쓰기 자리에서** 줄을 접기 때문에,
    '선택 영역 개인정보 가리기'(13자)처럼 짧아도 세 줄이 되어 아래 '선택 필요'
    딱지를 가리는 일이 생긴다. 그래서 여기서 미리 접어 두고, 캔버스에는 자동
    줄바꿈 없이 그대로 그린다.
    """
    한줄 = 한줄글자수(타일크기)
    말 = (제목 or "").strip()
    줄들 = _낱말로접기(말, 한줄)
    if len(줄들) <= 줄수:
        return "\n".join(줄들)

    # '블록 값 변환(콤마·금액·날짜·나이)' 처럼 괄호로 덧붙인 설명이 있으면
    # 그 앞까지만 남긴다. 글자 수로 자르는 것보다 뜻이 살아 있다.
    앞 = 말.split("(", 1)[0].strip()
    if 앞 and 앞 != 말:
        줄인것 = _낱말로접기(앞, 한줄)
        if len(줄인것) <= 줄수:
            return "\n".join(줄인것)
        줄들 = 줄인것

    남길것 = 줄들[:줄수]
    남길것[-1] = 남길것[-1][: max(1, 한줄 - 1)].rstrip() + "…"
    return "\n".join(남길것)


def 딱지방식(타일크기: int) -> str:
    """'선택 필요' 를 글자로 적을지, 점 하나로 찍을지.

    작은 타일에는 제목 두 줄을 넣고 나면 글자 딱지를 놓을 자리가 없다.
    그럴 때는 카드 오른쪽 위에 작은 점만 찍고, 자세한 것은 상태줄에 맡긴다.
    """
    return "글자" if 타일크기 >= 96 else "점"


def 둥근네모점들(
    왼쪽: float, 위: float, 오른쪽: float, 아래: float, 반경: float
) -> list[float]:
    """모서리가 둥근 네모를 그릴 점 목록.

    tkinter 에는 둥근 네모가 없어서 `create_polygon(..., smooth=True)` 로 그린다.
    모서리마다 점을 세 개씩(시작·꼭짓점·끝) 두면 그 꼭짓점이 곡선으로 깎인다.
    """
    반경 = max(0.0, min(반경, (오른쪽 - 왼쪽) / 2, (아래 - 위) / 2))
    return [
        왼쪽 + 반경, 위,
        오른쪽 - 반경, 위,
        오른쪽, 위,
        오른쪽, 위 + 반경,
        오른쪽, 아래 - 반경,
        오른쪽, 아래,
        오른쪽 - 반경, 아래,
        왼쪽 + 반경, 아래,
        왼쪽, 아래,
        왼쪽, 아래 - 반경,
        왼쪽, 위 + 반경,
        왼쪽, 위,
    ]


def 미끄럼값(
    가로: float, 왼쪽: float, 오른쪽: float, 최소: float, 최대: float
) -> float:
    """미끄럼자에서 마우스 자리(가로)를 값으로 바꾼다. 양 끝을 넘지 않는다."""
    폭 = 오른쪽 - 왼쪽
    if 폭 <= 0:
        return 최소
    몫 = min(1.0, max(0.0, (가로 - 왼쪽) / 폭))
    return 최소 + 몫 * (최대 - 최소)


def 미끄럼자리(값: float, 왼쪽: float, 오른쪽: float, 최소: float, 최대: float) -> float:
    """값을 미끄럼자 손잡이의 가로 자리로 바꾼다. (`미끄럼값` 의 반대)"""
    나비 = 최대 - 최소
    몫 = 0.0 if 나비 <= 0 else min(1.0, max(0.0, (값 - 최소) / 나비))
    return 왼쪽 + 몫 * (오른쪽 - 왼쪽)


최소투명도 = 40  # 이보다 옅어지면 글씨를 읽을 수 없다.


def 투명도다듬기(값: Any) -> int:
    """투명도(불투명 정도, %)를 40~100 안으로 가둔다."""
    try:
        숫자 = int(round(float(값)))
    except (TypeError, ValueError):
        return 기본설정["투명도"]
    return max(최소투명도, min(100, 숫자))


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
        "투명도": 기본설정["투명도"],
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

    설정["투명도"] = 투명도다듬기(날것.get("투명도", 기본설정["투명도"]))
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
