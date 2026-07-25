"""찾아바꾸기 — 문서 전체 / 선택 블록 / 표 셀을 한 방식으로 처리한다.

원본에는 `블록바꾸기창`, `셀찾아바꾸기창`, `맨앞필터창`, `정규표현식()` 이
따로 있었고 규칙은 최대 3개까지만 입력할 수 있었다(찾기1~찾기3).
여기서는 규칙을 목록으로 받아 개수 제한이 없고, 세 범위 모두 같은 규칙을 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.document import 문서
from ..core.errors import 입력오류
from ..text.transform import 규칙적용, 찾아바꾸기규칙

__all__ = ["바꾸기결과", "문서전체바꾸기", "블록바꾸기", "셀바꾸기", "찾기"]


@dataclass
class 바꾸기결과:
    """바꾼 건수 요약."""

    범위: str
    규칙수: int
    바뀐칸: int = 0
    바뀐건: int = 0

    @property
    def 문구(self) -> str:
        if self.범위 == "문서전체":
            return f"문서 전체에서 {self.바뀐건}건 바꿨습니다."
        return f"{self.범위} {self.바뀐칸}칸에서 {self.바뀐건}건 바꿨습니다."


def _규칙정리(규칙들: list[찾아바꾸기규칙]) -> list[찾아바꾸기규칙]:
    유효 = [규칙 for 규칙 in 규칙들 if 규칙.찾기]
    if not 유효:
        raise 입력오류("찾을 내용을 입력하세요.")
    return 유효


def 문서전체바꾸기(문서객체: 문서, 규칙들: list[찾아바꾸기규칙]) -> 바꾸기결과:
    """한/글의 AllReplace 액션으로 문서 전체를 바꾼다.

    본문 텍스트를 직접 읽어 다시 쓰는 방식과 달리 서식·표·글상자를 건드리지 않는다.
    """
    유효 = _규칙정리(규칙들)
    결과 = 바꾸기결과(범위="문서전체", 규칙수=len(유효))
    with 문서객체.한번에("문서 전체 찾아바꾸기"):
        for 규칙 in 유효:
            with 문서객체.파라미터("AllReplace") as 값:
                값.SetItem("FindString", 규칙.찾기)
                값.SetItem("ReplaceString", 규칙.바꾸기)
                값.SetItem("IgnoreMessage", 1)
                값.SetItem("Direction", 0)  # 문서 처음부터
                값.SetItem("FindType", 1)
                값.SetItem("ReplaceMode", 1)  # 모두 바꾸기
                값.SetItem("IgnoreFindString", 0)
                값.SetItem("IgnoreReplaceString", 0)
                값.SetItem("MatchCase", 1 if 규칙.대소문자구분 else 0)
                값.SetItem("FindRegExp", 1 if 규칙.정규식 else 0)
            결과.바뀐건 += 1
    return 결과


def 블록바꾸기(문서객체: 문서, 규칙들: list[찾아바꾸기규칙]) -> 바꾸기결과:
    """선택한 블록 안에서만 바꾼다. (블록 텍스트를 읽어 규칙 적용 후 되쓰기)"""
    유효 = _규칙정리(규칙들)
    원문 = 문서객체.선택텍스트()
    바뀐 = 규칙적용(원문, 유효)
    결과 = 바꾸기결과(범위="블록", 규칙수=len(유효), 바뀐칸=1)
    if 바뀐 == 원문:
        return 결과
    with 문서객체.한번에("블록 찾아바꾸기"):
        문서객체.선택교체(바뀐)
    결과.바뀐건 = 1
    return 결과


def 셀바꾸기(문서객체: 문서, 규칙들: list[찾아바꾸기규칙]) -> 바꾸기결과:
    """선택한 표 셀들에서만 바꾼다. 셀마다 값을 읽어 규칙을 적용한다."""
    유효 = _규칙정리(규칙들)
    범위 = 문서객체.셀블록범위()
    결과 = 바꾸기결과(범위="셀", 규칙수=len(유효))
    with 문서객체.한번에("셀 찾아바꾸기"), 문서객체.화면정지():
        for _목록 in 문서객체.셀순회(범위):
            원문 = 문서객체.셀텍스트()
            바뀐 = 규칙적용(원문, 유효)
            결과.바뀐칸 += 1
            if 바뀐 != 원문:
                문서객체.셀텍스트쓰기(바뀐)
                결과.바뀐건 += 1
    문서객체.취소()
    return 결과


def 찾기(문서객체: 문서, 내용: str, 정규식: bool = False, 뒤로: bool = False) -> None:
    """다음 일치 지점으로 이동한다. (원본 `정규표현식()` 통합)"""
    if not 내용:
        raise 입력오류("찾을 내용을 입력하세요.")
    with 문서객체.파라미터("RepeatFind") as 값:
        값.SetItem("FindString", 내용)
        값.SetItem("Direction", 1 if 뒤로 else 0)
        값.SetItem("IgnoreMessage", 1)
        값.SetItem("FindType", 1)
        값.SetItem("FindRegExp", 1 if 정규식 else 0)
