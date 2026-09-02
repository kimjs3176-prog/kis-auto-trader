"""블록 계산기 — 문자열 수식을 안전하게 계산한다.

원본 `블록계산`은 후위식 변환 로직이 예외 처리 없이 흩어져 있어 잘못된 수식에서
그대로 죽었다. 여기서는 토크나이저·조작자 우선순위·Decimal 연산을 분리하고
`eval` 을 쓰지 않는다.
"""

from __future__ import annotations

import re
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext

__all__ = ["계산오류", "수식계산", "수식정리", "블록수식문구", "수표기"]


class 계산오류(ValueError):
    """수식을 계산할 수 없을 때."""


_토큰 = re.compile(r"\d+(?:\.\d+)?|[()+\-*/%×÷]|\s+")
_우선순위 = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2}
_치환 = {"×": "*", "÷": "/", "－": "-", "＋": "+", "∼": "-", "~": "-"}


def 수식정리(원문: str) -> str:
    """사람이 쓴 수식을 계산 가능한 형태로 다듬는다.

    - 천단위 콤마 제거, 전각 연산자 정규화
    - 숫자 뒤 단위(원, 명, %, 개 등)와 괄호 주석 제거
    """
    값 = 원문 or ""
    값 = re.sub(r"\r|\n", " ", 값)
    for 원, 새 in _치환.items():
        값 = 값.replace(원, 새)
    값 = re.sub(r"(?<=\d),(?=\d{3})", "", 값)  # 1,200 -> 1200
    값 = re.sub(r"[가-힣a-zA-Z원명개%₩]", "", 값)
    return 값.strip()


def _토큰화(수식: str) -> list[str]:
    결과: list[str] = []
    위치 = 0
    for m in _토큰.finditer(수식):
        if m.start() != 위치:
            raise 계산오류(f"계산할 수 없는 문자: {수식[위치:m.start()]!r}")
        위치 = m.end()
        조각 = m.group()
        if not 조각.strip():
            continue
        결과.append(조각)
    if 위치 != len(수식):
        raise 계산오류(f"계산할 수 없는 문자: {수식[위치:]!r}")
    if not 결과:
        raise 계산오류("계산할 내용이 없습니다.")
    return 결과


def _후위식(토큰들: list[str]) -> list[str]:
    출력: list[str] = []
    스택: list[str] = []
    직전 = None
    for 토큰 in 토큰들:
        if 토큰 in _우선순위:
            # 단항 부호: 수식 맨 앞이나 '(' 또는 다른 연산자 뒤에 오는 +/-
            if 토큰 in "+-" and (직전 is None or 직전 == "(" or 직전 in _우선순위):
                출력.append("0")
            while 스택 and 스택[-1] != "(" and _우선순위[스택[-1]] >= _우선순위[토큰]:
                출력.append(스택.pop())
            스택.append(토큰)
        elif 토큰 == "(":
            스택.append(토큰)
        elif 토큰 == ")":
            while 스택 and 스택[-1] != "(":
                출력.append(스택.pop())
            if not 스택:
                raise 계산오류("괄호가 맞지 않습니다.")
            스택.pop()
        else:
            출력.append(토큰)
        직전 = 토큰
    while 스택:
        연산자 = 스택.pop()
        if 연산자 == "(":
            raise 계산오류("괄호가 맞지 않습니다.")
        출력.append(연산자)
    return 출력


def 수식계산(원문: str, 자리수: int | None = None) -> Decimal:
    """문자열 수식을 계산한다. 사칙연산·나머지·괄호·단항부호를 지원한다."""
    토큰들 = _토큰화(수식정리(원문))
    스택: list[Decimal] = []
    with localcontext() as 문맥:
        문맥.prec = 34
        for 토큰 in _후위식(토큰들):
            if 토큰 in _우선순위:
                if len(스택) < 2:
                    raise 계산오류("연산자에 필요한 값이 부족합니다.")
                뒤, 앞 = 스택.pop(), 스택.pop()
                try:
                    if 토큰 == "+":
                        스택.append(앞 + 뒤)
                    elif 토큰 == "-":
                        스택.append(앞 - 뒤)
                    elif 토큰 == "*":
                        스택.append(앞 * 뒤)
                    elif 토큰 == "/":
                        스택.append(앞 / 뒤)
                    else:
                        스택.append(앞 % 뒤)
                except (DivisionByZero, InvalidOperation) as 오류:
                    raise 계산오류("0으로 나눌 수 없습니다.") from 오류
            else:
                try:
                    스택.append(Decimal(토큰))
                except InvalidOperation as 오류:  # pragma: no cover
                    raise 계산오류(f"숫자로 볼 수 없습니다: {토큰}") from 오류
    if len(스택) != 1:
        raise 계산오류("수식 형태가 올바르지 않습니다.")
    결과 = 스택[0]
    if 자리수 is not None:
        결과 = round(결과, 자리수)
    return 결과


def 수표기(값: Decimal, 콤마: bool = True) -> str:
    """계산 결과를 사람이 읽는 형태로 만든다.

    Decimal.normalize() 는 3600 을 '3.6E+3' 으로 만들기 때문에 정수는 따로 다룬다.
    """
    if 값 == 값.to_integral_value():
        값 = 값.to_integral_value()
    else:
        값 = 값.normalize()
    return f"{값:,}" if 콤마 else str(값)


def 블록수식문구(원문: str, 자리수: int = 0, 콤마: bool = True) -> str:
    """블록 안의 수식을 계산해 `수식 = 결과` 문구로 만든다."""
    결과 = 수식계산(원문, 자리수)
    return f"{원문.strip()} = {수표기(결과, 콤마)}"
