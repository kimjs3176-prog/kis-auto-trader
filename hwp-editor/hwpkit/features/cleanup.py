"""문서 정리 — 남의 문서를 받아 손볼 때 쓰는 기능들.

원본 `전체문단스타일제거`, `전체표스타일제거`, `그림용량옵션/지정`,
`블록여백정리`, `블록엔터정리` 를 모아 정리하고, 문서 전체 대상 정리를 더했다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.document import 문서
from ..text import transform
from ..text.transform import 찾아바꾸기규칙

__all__ = [
    "서식정리",
    "문단서식초기화",
    "표서식초기화",
    "공백정리",
    "빈줄정리",
    "그림용량줄이기",
    "정리요약",
]


@dataclass
class 정리요약:
    """정리 결과."""

    항목: list[str]

    @property
    def 문구(self) -> str:
        return "정리 완료: " + ", ".join(self.항목) if self.항목 else "정리할 것이 없었습니다."


def 문단서식초기화(문서객체: 문서) -> None:
    """문서 전체의 문단·글자 서식을 기본으로 돌린다."""
    from .format import 서식초기화

    with 문서객체.한번에("문단 서식 초기화"):
        문서객체.실행("SelectAll")
        문서객체.실행("StyleClearCharShape")
        서식초기화(문서객체)
        문서객체.취소()


def 표서식초기화(문서객체: 문서, 스타일: str = "기본") -> int:
    """문서 안 모든 표에 같은 스타일을 다시 입힌다. 처리한 표 수를 돌려준다."""
    from . import table_ops

    처리 = 0
    with 문서객체.한번에("표 서식 초기화"), 문서객체.화면정지():
        문서객체.이동하기("문서처음")
        while True:
            문서객체.한글.FindCtrl()  # 다음 개체(표·그림 등)로 이동
            if not 문서객체.표안:
                break
            table_ops.표스타일적용(문서객체, 스타일)
            처리 += 1
            문서객체.실행("CloseEx")
            if 처리 > 200:  # 안전장치
                break
    return 처리


def 공백정리(문서객체: 문서, 문서전체: bool = False) -> None:
    """겹친 공백·문단 끝 공백을 없앤다."""
    from .find_replace import 문서전체바꾸기

    if 문서전체:
        문서전체바꾸기(
            문서객체,
            [
                찾아바꾸기규칙(찾기=r"[ ]{2,}", 바꾸기=" ", 정규식=True),
                찾아바꾸기규칙(찾기=r"[ ]+$", 바꾸기="", 정규식=True),
                찾아바꾸기규칙(찾기=r"\s+([,.)])", 바꾸기=r"\1", 정규식=True),
            ],
        )
        return
    원문 = 문서객체.선택텍스트()
    바뀐 = transform.공백정리(원문)
    if 바뀐 != 원문:
        with 문서객체.한번에("공백 정리"):
            문서객체.선택교체(바뀐)


def 빈줄정리(문서객체: 문서, 빈줄유지: int = 0, 문서전체: bool = False) -> None:
    """이어진 빈 줄을 정리한다."""
    from .find_replace import 문서전체바꾸기

    if 문서전체:
        찾기 = r"\n{%d,}" % (빈줄유지 + 2)
        문서전체바꾸기(
            문서객체,
            [찾아바꾸기규칙(찾기=찾기, 바꾸기="\n" * (빈줄유지 + 1), 정규식=True)],
        )
        return
    원문 = 문서객체.선택텍스트()
    바뀐 = transform.엔터정리(원문, 빈줄유지)
    if 바뀐 != 원문:
        with 문서객체.한번에("빈 줄 정리"):
            문서객체.선택교체(바뀐)


def 그림용량줄이기(문서객체: 문서, 해상도: int = 150) -> None:
    """문서 안 그림 해상도를 낮춰 파일 용량을 줄인다."""
    with 문서객체.파라미터("PictureSaveAsOption") as 값:
        값.SetItem("DelCutting", 1)
        값.SetItem("ResizeImage", 1)
        값.SetItem("SaveType", 0)
        값.SetItem("SaveDpiX", 해상도)
        값.SetItem("SaveDpiY", 해상도)
    문서객체.실행("PictureSaveAsAll")


def 서식정리(
    문서객체: 문서,
    문단초기화: bool = True,
    표초기화: bool = True,
    공백: bool = True,
    빈줄: bool = True,
) -> 정리요약:
    """받은 문서를 한 번에 다듬는다. (일괄 처리에서도 이 함수를 쓴다)"""
    한일: list[str] = []
    if 문단초기화:
        문단서식초기화(문서객체)
        한일.append("문단 서식")
    if 표초기화:
        수 = 표서식초기화(문서객체)
        한일.append(f"표 {수}개")
    if 공백:
        공백정리(문서객체, 문서전체=True)
        한일.append("공백")
    if 빈줄:
        빈줄정리(문서객체, 문서전체=True)
        한일.append("빈 줄")
    return 정리요약(항목=한일)
