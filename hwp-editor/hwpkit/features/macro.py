"""작업 묶음(매크로) — 자주 쓰는 순서를 한 번에 실행한다.

명령 표(`commands`)가 있으므로 "명령 번호 + 입력값" 목록만 저장하면 된다.
새 묶음을 만들 때 코드를 고칠 필요가 없다.

묶음 파일 (뒤에 있는 것이 앞의 것을 덮어쓴다)
  1. 패키지 안 `presets/macros.json`  (기본 제공)
  2. `%USERPROFILE%\\.hwpkit\\macros.json`  (개인 묶음)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..core.document import 문서
from ..core.errors import 입력오류

__all__ = ["단계", "묶음", "묶음목록", "묶음찾기", "검증", "실행", "개인묶음파일"]

_기본파일 = Path(__file__).resolve().parent.parent / "presets" / "macros.json"


def 개인묶음파일() -> Path:
    """개인 묶음 파일 경로."""
    뿌리 = Path(os.environ.get("USERPROFILE") or Path.home())
    return 뿌리 / ".hwpkit" / "macros.json"


@dataclass(frozen=True)
class 단계:
    """묶음 안의 한 단계."""

    명령: str
    값: dict = field(default_factory=dict)
    계속: bool = True  # 실패해도 다음 단계를 이어서 할지


@dataclass(frozen=True)
class 묶음:
    """작업 묶음 하나."""

    이름: str
    설명: str
    단계들: tuple[단계, ...]
    출처: str = "기본"


def _읽기(파일: Path, 출처: str) -> dict[str, 묶음]:
    if not 파일.is_file():
        return {}
    자료 = json.loads(파일.read_text(encoding="utf-8"))
    결과: dict[str, 묶음] = {}
    for 이름, 값 in (자료.get("묶음") or {}).items():
        단계들 = tuple(
            단계(
                명령=하나["명령"],
                값=하나.get("값", {}),
                계속=bool(하나.get("계속", True)),
            )
            for 하나 in 값.get("단계", [])
        )
        결과[이름] = 묶음(
            이름=이름, 설명=값.get("설명", ""), 단계들=단계들, 출처=출처
        )
    return 결과


def 묶음목록() -> dict[str, 묶음]:
    """쓸 수 있는 묶음 전체. (개인 묶음이 같은 이름의 기본 묶음을 덮어쓴다)"""
    결과 = _읽기(_기본파일, "기본")
    결과.update(_읽기(개인묶음파일(), "개인"))
    return 결과


def 묶음찾기(이름: str) -> 묶음:
    목록 = 묶음목록()
    if 이름 not in 목록:
        raise 입력오류(
            f"없는 작업 묶음입니다: {이름}",
            f"쓸 수 있는 묶음: {', '.join(목록) or '(없음)'}\n"
            f"개인 묶음은 여기에 적습니다: {개인묶음파일()}",
        )
    return 목록[이름]


def 검증(하나: 묶음, 명령찾기: Callable[[str], object] | None = None) -> list[str]:
    """묶음이 실행 가능한지 미리 확인한다. 문제 목록을 돌려준다(없으면 빈 목록).

    없는 명령, 없는 입력 이름, 선택지에 없는 값을 잡아낸다.
    """
    from .. import commands

    찾기함수 = 명령찾기 or commands.찾기
    문제: list[str] = []
    if not 하나.단계들:
        문제.append(f"'{하나.이름}' 에 단계가 없습니다.")

    for 번호, 단계하나 in enumerate(하나.단계들, start=1):
        try:
            명령하나 = 찾기함수(단계하나.명령)
        except 입력오류:
            문제.append(f"{번호}단계: 없는 명령 '{단계하나.명령}'")
            continue
        입력이름들 = {항목.이름: 항목 for 항목 in getattr(명령하나, "입력", ())}
        for 이름, 값 in (단계하나.값 or {}).items():
            항목 = 입력이름들.get(이름)
            if 항목 is None:
                문제.append(f"{번호}단계({단계하나.명령}): 없는 입력 '{이름}'")
                continue
            if 항목.종류 == "선택" and str(값) not in 항목.선택지:
                문제.append(
                    f"{번호}단계({단계하나.명령}): '{이름}' 값 '{값}' 은 고를 수 없습니다."
                )
    return 문제


def 실행(
    문서객체: 문서,
    이름: str,
    덮어쓸값: dict[str, dict] | None = None,
    알림: Callable[[str], None] | None = None,
) -> str:
    """묶음을 순서대로 실행하고 단계별 결과를 정리해 돌려준다.

    덮어쓸값 = {명령번호: {입력이름: 값}} 으로 그때그때 값을 바꿀 수 있다.
    """
    from .. import commands

    하나 = 묶음찾기(이름)
    문제 = 검증(하나)
    if 문제:
        raise 입력오류(
            f"'{이름}' 묶음을 실행할 수 없습니다.", "\n".join(문제)
        )

    줄들: list[str] = [f"[{하나.이름}] {하나.설명}".rstrip()]
    실패 = 0
    for 번호, 단계하나 in enumerate(하나.단계들, start=1):
        명령하나 = commands.찾기(단계하나.명령)
        값 = dict(단계하나.값)
        값.update((덮어쓸값 or {}).get(단계하나.명령, {}))
        if 알림:
            알림(f"{번호}/{len(하나.단계들)} {명령하나.제목}")
        try:
            결과 = 명령하나.실행(commands.맥락(문서객체=문서객체, 값=값, 알림=알림))
            첫줄 = (결과 or f"{명령하나.제목} 완료").splitlines()[0]
            줄들.append(f"○ {번호}. {명령하나.제목} — {첫줄}")
        except Exception as 오류:  # noqa: BLE001 - 한 단계 실패로 전체를 멈추지 않는다
            실패 += 1
            줄들.append(f"× {번호}. {명령하나.제목} — {오류}")
            if not 단계하나.계속:
                줄들.append("  (이 단계에서 멈추도록 설정돼 있어 중단했습니다)")
                break
    줄들.append("")
    줄들.append(f"{len(하나.단계들)}단계 중 {len(하나.단계들) - 실패}단계 성공")
    return "\n".join(줄들)
