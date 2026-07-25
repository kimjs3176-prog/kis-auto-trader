"""공문 언어순화 — 어려운 한자어·일본어투·권위적 표현을 다듬는다.

원본 `공문언어순화창` / `순화검색` / `순화추천` 은 사전이 코드에 묻혀 있어
낱말을 추가할 수 없었다. 여기서는 사전을 `presets/refine.json` 으로 빼고,
검사 결과를 위치와 함께 돌려주어 UI 가 목록으로 보여줄 수 있게 했다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

__all__ = ["순화항목", "지적", "사전읽기", "검사", "자동순화", "사전추가"]

_사전경로 = Path(__file__).resolve().parent.parent / "presets" / "refine.json"


@dataclass(frozen=True)
class 순화항목:
    """사전 한 줄. 대상 표현과 권장 표현, 분류를 담는다."""

    대상: str
    권장: tuple[str, ...]
    분류: str = "어려운 말"
    설명: str = ""

    @property
    def 첫권장(self) -> str:
        return self.권장[0] if self.권장 else self.대상


@dataclass(frozen=True)
class 지적:
    """검사 결과 한 건."""

    항목: 순화항목
    줄번호: int
    시작: int
    끝: int
    원문: str

    @property
    def 문구(self) -> str:
        권장 = " / ".join(self.항목.권장)
        return f"{self.줄번호}줄: '{self.원문}' → '{권장}' ({self.항목.분류})"


@lru_cache(maxsize=1)
def 사전읽기(경로: str | None = None) -> tuple[순화항목, ...]:
    """순화 사전을 읽어온다. (결과는 캐시된다)"""
    파일 = Path(경로) if 경로 else _사전경로
    자료 = json.loads(파일.read_text(encoding="utf-8"))
    항목들 = []
    for 줄 in 자료.get("항목", []):
        권장 = 줄.get("권장", [])
        if isinstance(권장, str):
            권장 = [권장]
        항목들.append(
            순화항목(
                대상=줄["대상"],
                권장=tuple(권장),
                분류=줄.get("분류", "어려운 말"),
                설명=줄.get("설명", ""),
            )
        )
    # 긴 표현을 먼저 검사해야 '금 일백원' 같은 부분 일치 오검출을 피한다.
    return tuple(sorted(항목들, key=lambda 항: len(항.대상), reverse=True))


def 검사(텍스트: str, 사전: tuple[순화항목, ...] | None = None) -> list[지적]:
    """텍스트에서 순화 대상 표현을 찾아 위치와 함께 돌려준다."""
    사전 = 사전 or 사전읽기()
    결과: list[지적] = []
    for 줄번호, 줄 in enumerate(re.split(r"\r\n|\r|\n", 텍스트 or ""), start=1):
        차지: list[tuple[int, int]] = []
        for 항목 in 사전:
            for m in re.finditer(re.escape(항목.대상), 줄):
                if any(시 < m.end() and m.start() < 끝 for 시, 끝 in 차지):
                    continue  # 이미 더 긴 표현으로 잡힌 자리
                차지.append((m.start(), m.end()))
                결과.append(
                    지적(
                        항목=항목,
                        줄번호=줄번호,
                        시작=m.start(),
                        끝=m.end(),
                        원문=m.group(),
                    )
                )
    결과.sort(key=lambda 지: (지.줄번호, 지.시작))
    return 결과


def 자동순화(텍스트: str, 사전: tuple[순화항목, ...] | None = None) -> tuple[str, list[지적]]:
    """사전의 첫 권장 표현으로 한 번에 바꾼다.

    바꾼 결과와 무엇을 바꿨는지 목록을 함께 돌려준다.
    """
    사전 = 사전 or 사전읽기()
    지적들 = 검사(텍스트, 사전)
    줄들 = re.split(r"\r\n|\r|\n", 텍스트 or "")
    줄별: dict[int, list[지적]] = {}
    for 지 in 지적들:
        줄별.setdefault(지.줄번호, []).append(지)

    for 줄번호, 목록 in 줄별.items():
        줄 = 줄들[줄번호 - 1]
        for 지 in sorted(목록, key=lambda 지: 지.시작, reverse=True):
            줄 = 줄[: 지.시작] + 지.항목.첫권장 + 줄[지.끝 :]
        줄들[줄번호 - 1] = 줄
    return "\r\n".join(줄들), 지적들


def 사전추가(대상: str, 권장: list[str], 분류: str = "우리 부서 용어", 경로: str | None = None) -> None:
    """사전에 낱말을 추가한다. (부서에서 쓰는 표현을 늘릴 수 있게)"""
    파일 = Path(경로) if 경로 else _사전경로
    자료 = json.loads(파일.read_text(encoding="utf-8"))
    자료.setdefault("항목", []).append({"대상": 대상, "권장": 권장, "분류": 분류})
    파일.write_text(
        json.dumps(자료, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    사전읽기.cache_clear()
