"""숫자·금액 관련 순수 함수 모음.

COM(한/글)에 의존하지 않으므로 단독으로 테스트할 수 있다.
원본 프로그램의 `한글화`, `블록한줄`(콤마/금액), `증감계산`, `블록금액비율`을
정리·보강한 것이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

__all__ = [
    "숫자만",
    "정수읽기",
    "실수읽기",
    "콤마넣기",
    "콤마빼기",
    "한글금액",
    "금액문구",
    "증감결과",
    "증감문구",
    "비율분배",
    "조사_로으로",
]

_한글수 = ("", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구")
_한글단 = ("", "십", "백", "천")
_큰단위 = ("", "만", "억", "조", "경")


def 숫자만(값: str) -> str:
    """문자열에서 숫자만 남긴다. (예: '1,200원' -> '1200')"""
    return re.sub(r"[^0-9]", "", 값 or "")


def 정수읽기(값: str) -> int | None:
    """문자열에서 정수를 추출한다. 추출할 수 없으면 None."""
    본문 = re.sub(r"\([^)]*\)", "", 값 or "")  # 괄호 주석 제거
    부호 = -1 if re.search(r"[-△▲]\s*\d", 본문) else 1
    자리 = 숫자만(본문)
    if not 자리:
        return None
    return 부호 * int(자리)


def 실수읽기(값: str) -> Decimal | None:
    """문자열에서 소수를 포함한 수를 추출한다."""
    본문 = re.sub(r"[,\s]", "", 값 or "")
    m = re.search(r"-?\d+(?:\.\d+)?", 본문)
    if not m:
        return None
    try:
        return Decimal(m.group())
    except InvalidOperation:  # pragma: no cover - 정규식 통과 후에는 사실상 발생하지 않음
        return None


def 콤마넣기(값: str) -> str:
    """숫자에 천단위 구분 기호를 넣는다. 소수점 이하는 유지한다."""
    수 = 실수읽기(값)
    if 수 is None:
        return 값
    정수부, _, 소수부 = str(abs(수)).partition(".")
    결과 = f"{int(정수부):,}"
    if 소수부:
        결과 = f"{결과}.{소수부}"
    return f"-{결과}" if 수 < 0 else 결과


def 콤마빼기(값: str) -> str:
    """천단위 구분 기호를 제거한다."""
    return (값 or "").replace(",", "")


def 한글금액(숫자: int, 일붙임: bool = False) -> str:
    """정수를 한글 표기로 바꾼다. (예: 12000 -> '일만이천')

    원본의 `한글화`는 4자리 그룹 단위(만/억/조) 처리가 어긋나 '이십만' 같은 값에서
    단위가 빠지는 문제가 있었다. 여기서는 4자리씩 끊어 그룹별로 조립한다.

    일붙임=True 면 계약·금액 표기 관행에 맞춰 천/백/십 앞의 '일'을 살린다.
    (1200 -> 일천이백) 금액 문구를 만들 때 쓴다.
    """
    숫자 = int(숫자)
    if 숫자 == 0:
        return "영"
    부호 = "마이너스 " if 숫자 < 0 else ""
    숫자 = abs(숫자)

    그룹: list[str] = []
    자리 = 0
    while 숫자 > 0:
        숫자, 나머지 = divmod(숫자, 10000)
        if 나머지:
            그룹.append(_네자리한글(나머지, 일붙임) + _큰단위[자리])
        자리 += 1
        if 자리 >= len(_큰단위):  # pragma: no cover - 경(10^16) 초과 금액은 사용처가 없음
            break
    return 부호 + "".join(reversed(그룹))


def _네자리한글(숫자: int, 일붙임: bool = False) -> str:
    조각 = []
    문자열 = str(숫자)
    길이 = len(문자열)
    for i, 글자 in enumerate(문자열):
        값 = int(글자)
        if 값 == 0:
            continue
        단 = _한글단[길이 - 1 - i]
        # 십/백/천 앞의 '일'은 보통 생략한다(일십이 -> 십이).
        # 금액 표기에서는 위조를 막으려고 살려 쓴다(일천이백원).
        수 = "" if (값 == 1 and 단 and not 일붙임) else _한글수[값]
        조각.append(수 + 단)
    return "".join(조각)


def 금액문구(값: str) -> str:
    """금액을 공문 표기(`금 1,200원(금일천이백원)`)로 만든다."""
    수 = 정수읽기(값)
    if 수 is None:
        return 값
    return f"금 {수:,}원(금{한글금액(수, 일붙임=True)}원)"


@dataclass(frozen=True)
class 증감결과:
    """증감 계산 결과."""

    앞: Decimal
    뒤: Decimal
    단위: str
    변화량: Decimal
    변화율: Decimal
    방향: str  # '증가' | '감소' | '변화없음'
    기호: str  # '↑' | '↓' | ''
    소수자리: int


def _소수자리(*값들: str) -> int:
    자리 = 0
    for 값 in 값들:
        if "." in 값:
            자리 = max(자리, len(값.split(".", 1)[1]))
    return 자리


def 증감계산(원문: str) -> 증감결과 | None:
    """'1,000명 → 1,250명' 형태의 문자열에서 증감을 계산한다.

    구분자는 `→`, `->`, `~>`, `>` 를 모두 허용한다.
    """
    본문 = (원문 or "").split("로 ")[0].strip()
    구분 = re.split(r"→|->|~>|=>|>", 본문)
    if len(구분) < 2:
        return None
    앞원문, 뒤원문 = 구분[0], 구분[1]

    앞 = 실수읽기(앞원문)
    뒤 = 실수읽기(뒤원문)
    if 앞 is None or 뒤 is None:
        return None

    단위 = re.sub(r"[\d.,%\s]", "", 앞원문) or re.sub(r"[\d.,%\s]", "", 뒤원문)
    if "%" in 앞원문 or "%" in 뒤원문:
        단위 = "%"

    변화량 = 뒤 - 앞
    if 앞 == 0:
        변화율 = Decimal(0)
    else:
        변화율 = abs(변화량) / abs(앞) * 100

    if 변화량 > 0:
        방향, 기호 = "증가", "↑"
    elif 변화량 < 0:
        방향, 기호 = "감소", "↓"
    else:
        방향, 기호 = "변화없음", ""

    return 증감결과(
        앞=앞,
        뒤=뒤,
        단위=단위,
        변화량=abs(변화량),
        변화율=변화율,
        방향=방향,
        기호=기호,
        소수자리=_소수자리(str(앞), str(뒤)),
    )


def 조사_로으로(단어: str) -> str:
    """받침에 따라 '로' / '으로' 를 고른다."""
    if not 단어:
        return "으로"
    마지막 = 단어[-1]
    코드 = ord(마지막) - ord("가")
    if 코드 < 0 or 코드 > 11171:  # 한글 음절 범위를 벗어난 글자(영문·숫자 등)
        return "으로"
    종성 = 코드 % 28
    return "로" if 종성 in (0, 8) else "으로"  # 받침 없음 또는 'ㄹ'


def 증감문구(원문: str, 소수: bool = False) -> str | None:
    """증감 결과를 공문 문장으로 만든다.

    예: '1,000명→1,250명' -> '1,000명 → 1,250명으로 25% 증가(250명↑)'
    """
    결과 = 증감계산(원문)
    if 결과 is None:
        return None

    자리 = 결과.소수자리 if 소수 else 0

    def 표기(값: Decimal) -> str:
        수 = round(값, 자리) if 자리 else round(값)
        return f"{수:,}"

    단위 = 결과.단위
    변화단위 = "%p" if 단위 == "%" else 단위
    앞뒤 = f"{표기(결과.앞)}{단위} → {표기(결과.뒤)}{단위}"
    조사 = "로" if 단위 == "%" else 조사_로으로(단위)

    if 결과.방향 == "변화없음":
        return f"{앞뒤}{조사} 변화없음"
    비율 = round(결과.변화율, 자리) if 자리 else round(결과.변화율)
    return (
        f"{앞뒤}{조사} {비율}% {결과.방향}"
        f"({표기(결과.변화량)}{변화단위}{결과.기호})"
    )


def 비율분배(총액: str, 항목: list[tuple[str, float]]) -> str | None:
    """총액을 지정한 비율로 나눠 `총액(국비 700, 지방비 300)` 문구를 만든다.

    항목은 (이름, 가중치) 목록이며 가중치가 0인 항목은 제외한다.
    마지막 항목이 반올림 오차를 흡수하므로 합계가 항상 총액과 일치한다.
    """
    수 = 정수읽기(총액)
    if 수 is None:
        return None
    유효 = [(이름, float(값)) for 이름, 값 in 항목 if 값]
    전체 = sum(값 for _, 값 in 유효)
    if not 유효 or 전체 <= 0:
        return None

    조각: list[str] = []
    누계 = 0
    for 순번, (이름, 값) in enumerate(유효):
        if 순번 == len(유효) - 1:
            금액 = 수 - 누계
        else:
            금액 = round(수 * 값 / 전체)
            누계 += 금액
        조각.append(f"{이름} {금액:,}".strip())
    return f"{수:,}({', '.join(조각)})"
