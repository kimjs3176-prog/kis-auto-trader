"""보고서 렌더러 — 마크업을 한/글 서식 문서로 그린다.

기관별 서식 함수 871개를 없앨 수 있었던 이유가 이 파일이다.
`text/markup.py` 가 만든 요소 목록을 순서대로 그리기만 하면, 서식의 겉모습은
스타일 프리셋과 표 스타일이 결정한다.

    마크업 텍스트 → markup.파싱() → [요소] → 렌더() → 한/글 문서

원본 `마크다운()` 이 하던 일과 같지만,
* 기관마다 복제된 구성요소가 하나로 합쳐졌고,
* 표를 자동 인식하며,
* 실패하면 되돌리고(문서객체.한번에),
* 어떤 종류를 몇 개 그렸는지 결과를 돌려준다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..core.document import 문서
from ..core.errors import 입력오류
from ..text import markup

__all__ = ["렌더결과", "렌더", "템플릿목록", "템플릿마크업", "마크업미리보기"]

_템플릿파일 = Path(__file__).resolve().parent.parent / "presets" / "report_templates.json"


@dataclass
class 렌더결과:
    """그린 결과 요약."""

    요소수: int = 0
    표수: int = 0
    종류별: dict[str, int] = field(default_factory=dict)

    @property
    def 문구(self) -> str:
        조각 = ", ".join(f"{이름} {수}" for 이름, 수 in self.종류별.items())
        return f"{self.요소수}개 요소를 넣었습니다. ({조각})"


@lru_cache(maxsize=1)
def _템플릿읽기() -> dict:
    return json.loads(_템플릿파일.read_text(encoding="utf-8"))


def 템플릿목록() -> dict[str, str]:
    """보고서 유형 이름 → 설명.

    원본에 기관별로 흩어져 있던 정책·상황·검토·회의·행사·동향 보고 틀을
    기관 이름을 뗀 표준 유형으로 정리했다.
    """
    return {이름: 값.get("설명", "") for 이름, 값 in _템플릿읽기().get("유형", {}).items()}


def 템플릿마크업(이름: str) -> str:
    """보고서 유형의 골격 마크업을 돌려준다. 사용자가 내용만 채우면 된다."""
    유형 = _템플릿읽기().get("유형", {})
    if 이름 not in 유형:
        raise 입력오류(f"없는 보고서 유형: {이름}", f"가능: {', '.join(유형)}")
    return "\n".join(유형[이름].get("마크업", []))


def 마크업미리보기(마크업: str) -> str:
    """그리기 전에 무엇이 만들어질지 글로 보여준다. (UI 미리보기용)"""
    줄들 = []
    for 항 in markup.파싱(마크업):
        if isinstance(항, markup.표요소):
            줄들.append(f"[표] {항.행수}행 × {항.열수}열")
        elif 항.종류 == "빈줄":
            줄들.append("")
        else:
            번호 = f"{항.번호}. " if 항.번호 else ""
            줄들.append(f"[{항.종류}] {번호}{항.내용}")
    return "\n".join(줄들)


def 렌더(
    문서객체: 문서,
    마크업텍스트: str,
    새문서: bool = True,
    표스타일: str = "기본",
    용지: str = "A4",
    여백: str = "보고서",
) -> 렌더결과:
    """마크업을 한/글 문서로 그린다."""
    요소들 = markup.파싱(마크업텍스트)
    if not 요소들:
        raise 입력오류("그릴 내용이 없습니다.", "마크업을 입력하거나 보고서 유형을 고르세요.")

    from .format import 스타일적용
    from .page import 용지설정

    결과 = 렌더결과()

    with 문서객체.한번에("보고서 그리기"), 문서객체.화면정지():
        if 새문서:
            문서객체.새문서()
            용지설정(문서객체, 용지=용지, 여백값=여백)

        for 순번, 항 in enumerate(요소들):
            if isinstance(항, markup.표요소):
                _표그리기(문서객체, 항, 표스타일)
                결과.표수 += 1
            elif 항.종류 == "쪽나눔":
                문서객체.쪽나눔()
            elif 항.종류 == "빈줄":
                문서객체.문단()
            elif 항.종류 in ("참고", "강조"):
                _박스그리기(문서객체, 항)
            else:
                _문단그리기(문서객체, 항)
            결과.요소수 += 1
            결과.종류별[항.종류] = 결과.종류별.get(항.종류, 0) + 1

            if 순번 != len(요소들) - 1 and 항.종류 not in ("쪽나눔",):
                문서객체.문단()

        # 마지막 문단 서식은 본문으로 돌려놓는다.
        스타일적용(문서객체, "본문")
    return 결과


# --------------------------------------------------------------- 내부 구현
#: 마크업 종류 → 스타일 프리셋 이름
_스타일연결 = {
    "제목": "제목",
    "부제": "부제",
    "소제목": "소제목",
    "중제목": "중제목",
    "네모": "소제목",
    "원": "본문원",
    "바": "본문바",
    "별": "각주",
    "본문": "본문",
}

#: 종류별로 줄 앞에 붙는 글머리 기호
_기호연결 = {
    "소제목": "□ ",
    "중제목": "○ ",
    "네모": "□ ",
    "원": "○ ",
    "바": "- ",
    "별": "※ ",
}


def _문단그리기(문서객체: 문서, 항: markup.요소) -> None:
    from .format import 스타일적용

    스타일적용(문서객체, _스타일연결.get(항.종류, "본문"))
    기호 = _기호연결.get(항.종류, "")
    번호 = f"{항.번호}. " if (항.번호 and 항.종류 in ("소제목", "중제목")) else ""
    문서객체.문장입력(f"{기호}{번호}{항.내용}")


def _박스그리기(문서객체: 문서, 항: markup.요소) -> None:
    """참고/강조 상자 — 1×1 표로 그린다.

    원본의 `점선박스`, `누런점선박스`, `회색점선박스`, `서론박스`, `요지박스`,
    `꺽쇠박스`, `마름모박스` 를 두 가지(참고=점선 테두리, 강조=음영)로 합쳤다.
    """
    from . import table_ops
    from .format import 문단모양

    스타일 = "참고상자" if 항.종류 == "참고" else "강조상자"
    table_ops.표만들기(문서객체, 열수=1, 행수=1, 행높이=10)
    table_ops.표스타일적용(문서객체, 스타일, 머리글있음=False)
    table_ops.셀여백(문서객체, 상=1.5, 하=1.5, 좌=3, 우=3)
    문서객체.실행("Cancel")
    문서객체.이동하기("표처음셀")
    문단모양(문서객체, 정렬="왼쪽", 줄간격=150)
    라벨 = "※ " if 항.종류 == "참고" else ""
    문서객체.문장입력(f"{라벨}{항.내용}")
    문서객체.실행("CloseEx")  # 표 밖으로
    문서객체.실행("MoveLineEnd")


def _표그리기(문서객체: 문서, 항: markup.표요소, 스타일: str) -> None:
    from . import table_ops

    열수 = 항.열수
    table_ops.표만들기(문서객체, 열수=열수, 행수=항.행수)
    문서객체.실행("Cancel")
    문서객체.이동하기("표처음셀")
    for 행번호, 행 in enumerate(항.행들):
        for 열번호 in range(열수):
            값 = 행[열번호] if 열번호 < len(행) else ""
            문서객체.셀텍스트쓰기(값)
            마지막 = 행번호 == 항.행수 - 1 and 열번호 == 열수 - 1
            if not 마지막:
                문서객체.실행("TableRightCell")
    table_ops.표스타일적용(문서객체, 스타일, 머리글있음=항.머리글)
    문서객체.실행("Cancel")
    문서객체.실행("CloseEx")
    문서객체.실행("MoveLineEnd")
