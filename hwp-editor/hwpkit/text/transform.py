"""블록(선택 영역) 텍스트 변환 — 순수 함수 모음.

원본에 흩어져 있던 `블록한줄`, `블록여러줄`, `블록순환`, `셀순환`,
`블록여백정리`, `블록엔터정리`, `셀앞뒤붙임`, `셀찾아서바꾸기` 의 텍스트 처리
부분만 뽑아 한곳에 모았다. 한/글 조작과 분리되어 있으므로 그대로 테스트된다.

모든 함수는 `str -> str` 또는 `list[str] -> list[str]` 이며 원본을 변경하지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import numbers as 숫자모듈
from . import dates as 날짜모듈

__all__ = [
    "줄나누기",
    "줄합치기",
    "공백정리",
    "엔터정리",
    "앞뒤붙임",
    "맨앞제거",
    "맨뒤제거",
    "어절제거",
    "정렬",
    "중복제거",
    "번호매기기",
    "글머리교체",
    "찾아바꾸기규칙",
    "규칙적용",
    "표문장화",
    "문장표화",
    "한줄변환",
]

_줄구분 = re.compile(r"\r\n|\r|\n")


def 줄나누기(텍스트: str) -> list[str]:
    """한/글 블록 텍스트를 줄 목록으로 나눈다. (한/글은 문단 끝을 \\r 로 준다)"""
    return _줄구분.split(텍스트 or "")


def 줄합치기(줄들: list[str], 구분: str = "\r\n") -> str:
    return 구분.join(줄들)


def 공백정리(텍스트: str) -> str:
    """줄마다 앞뒤 공백을 없애고 연속 공백을 하나로 줄인다."""
    줄들 = [re.sub(r"[ \t ]+", " ", 줄).strip() for 줄 in 줄나누기(텍스트)]
    return 줄합치기(줄들)


def 엔터정리(텍스트: str, 빈줄유지: int = 0) -> str:
    """연속된 빈 줄을 정리한다. 빈줄유지=1 이면 빈 줄 하나까지는 남긴다."""
    결과: list[str] = []
    빈줄 = 0
    for 줄 in 줄나누기(텍스트):
        if 줄.strip():
            빈줄 = 0
            결과.append(줄)
        else:
            빈줄 += 1
            if 빈줄 <= 빈줄유지:
                결과.append("")
    return 줄합치기(결과)


def 앞뒤붙임(텍스트: str, 앞: str = "", 뒤: str = "", 빈줄건너뛰기: bool = True) -> str:
    """줄마다 앞/뒤에 문자열을 붙인다."""
    결과 = []
    for 줄 in 줄나누기(텍스트):
        if 빈줄건너뛰기 and not 줄.strip():
            결과.append(줄)
        else:
            결과.append(f"{앞}{줄}{뒤}")
    return 줄합치기(결과)


def 맨앞제거(텍스트: str, 글자수: int = 1) -> str:
    """줄마다 앞에서 지정한 글자 수를 지운다."""
    return 줄합치기([줄[글자수:] if 줄.strip() else 줄 for 줄 in 줄나누기(텍스트)])


def 맨뒤제거(텍스트: str, 글자수: int = 1) -> str:
    """줄마다 뒤에서 지정한 글자 수를 지운다."""
    return 줄합치기(
        [(줄[:-글자수] if 글자수 else 줄) if 줄.strip() else 줄 for 줄 in 줄나누기(텍스트)]
    )


def 어절제거(텍스트: str, 위치: str = "앞", 개수: int = 1) -> str:
    """줄마다 앞/뒤 어절(공백 단위)을 지운다."""
    결과 = []
    for 줄 in 줄나누기(텍스트):
        if not 줄.strip():
            결과.append(줄)
            continue
        어절 = 줄.split()
        남김 = 어절[개수:] if 위치 == "앞" else 어절[: max(0, len(어절) - 개수)]
        결과.append(" ".join(남김))
    return 줄합치기(결과)


def _정렬키(줄: str):
    수 = 숫자모듈.실수읽기(줄)
    return (0, 수, "") if 수 is not None else (1, 0, 줄)


def 정렬(텍스트: str, 방식: str = "오름차순") -> str:
    """줄 단위 정렬.

    방식: 오름차순 | 내림차순 | 짧은차순 | 긴차순 | 숫자순 | 숫자역순
    숫자가 있는 줄은 숫자 크기로, 없으면 가나다순으로 비교한다.
    """
    줄들 = [줄 for 줄 in 줄나누기(텍스트)]
    빈줄없이 = [줄 for 줄 in 줄들 if 줄.strip()]
    if 방식 == "오름차순":
        정렬됨 = sorted(빈줄없이)
    elif 방식 == "내림차순":
        정렬됨 = sorted(빈줄없이, reverse=True)
    elif 방식 == "짧은차순":
        정렬됨 = sorted(빈줄없이, key=lambda 줄: (len(줄), 줄))
    elif 방식 == "긴차순":
        정렬됨 = sorted(빈줄없이, key=lambda 줄: (-len(줄), 줄))
    elif 방식 == "숫자순":
        정렬됨 = sorted(빈줄없이, key=_정렬키)
    elif 방식 == "숫자역순":
        정렬됨 = sorted(빈줄없이, key=_정렬키, reverse=True)
    else:
        raise ValueError(f"모르는 정렬 방식: {방식}")
    return 줄합치기(정렬됨)


def 중복제거(텍스트: str, 공백무시: bool = True) -> str:
    """중복된 줄을 첫 등장 순서를 지키며 지운다."""
    본: set[str] = set()
    결과 = []
    for 줄 in 줄나누기(텍스트):
        키 = 줄.strip() if 공백무시 else 줄
        if not 키:
            continue
        if 키 in 본:
            continue
        본.add(키)
        결과.append(줄)
    return 줄합치기(결과)


def 번호매기기(텍스트: str, 서식: str = "{번호}. ", 시작: int = 1) -> str:
    """줄마다 번호를 붙인다. 서식에 {번호} 를 쓸 수 있다."""
    결과 = []
    번호 = 시작
    for 줄 in 줄나누기(텍스트):
        if not 줄.strip():
            결과.append(줄)
            continue
        결과.append(서식.replace("{번호}", str(번호)) + 줄)
        번호 += 1
    return 줄합치기(결과)


_글머리기호 = re.compile(
    r"^\s*(?:[□○◇◆■▷▶●∘\-\*※]|\d+[.)]|\(\d+\)|[가-하][.)]|\([가-하]\))\s*"
)


def 글머리교체(텍스트: str, 글머리: str = "", 들여쓰기: str = "") -> str:
    """줄 앞의 기존 글머리표를 떼고 새 글머리표를 붙인다."""
    결과 = []
    for 줄 in 줄나누기(텍스트):
        if not 줄.strip():
            결과.append(줄)
            continue
        본문 = _글머리기호.sub("", 줄).strip()
        결과.append(f"{들여쓰기}{글머리}{본문}")
    return 줄합치기(결과)


@dataclass(frozen=True)
class 찾아바꾸기규칙:
    """찾아바꾸기 한 건. 정규식/대소문자 구분 여부를 함께 담는다."""

    찾기: str
    바꾸기: str = ""
    정규식: bool = False
    대소문자구분: bool = False

    def 적용(self, 텍스트: str) -> str:
        if not self.찾기:
            return 텍스트
        if self.정규식:
            플래그 = 0 if self.대소문자구분 else re.IGNORECASE
            return re.sub(self.찾기, self.바꾸기, 텍스트, flags=플래그)
        if self.대소문자구분:
            return 텍스트.replace(self.찾기, self.바꾸기)
        # 대소문자를 무시하는 단순 치환. 바꿀 문자열의 백슬래시가 역참조로 해석되지
        # 않도록 함수 형태로 넘긴다.
        return re.sub(re.escape(self.찾기), lambda _: self.바꾸기, 텍스트, flags=re.IGNORECASE)


def 규칙적용(텍스트: str, 규칙들: list[찾아바꾸기규칙]) -> str:
    """여러 찾아바꾸기 규칙을 순서대로 적용한다."""
    결과 = 텍스트
    for 규칙 in 규칙들:
        결과 = 규칙.적용(결과)
    return 결과


def 표문장화(줄들: list[list[str]], 구분: str = " | ") -> str:
    """표 데이터를 문장으로 편다."""
    return 줄합치기([구분.join(칸.strip() for 칸 in 행) for 행 in 줄들])


def 문장표화(텍스트: str, 구분: str = "\t") -> list[list[str]]:
    """구분자로 나뉜 텍스트를 표 데이터(행×열)로 만든다.

    구분자가 탭/콤마/세로줄 중 무엇이든 '자동' 을 주면 가장 그럴듯한 것을 고른다.
    """
    줄들 = [줄 for 줄 in 줄나누기(텍스트) if 줄.strip()]
    if not 줄들:
        return []
    if 구분 == "자동":
        후보 = ["\t", "|", ",", ";"]
        점수 = {후: min(줄.count(후) for 줄 in 줄들) for 후 in 후보}
        구분 = max(점수, key=lambda 후: 점수[후])
        if 점수[구분] == 0:
            구분 = None  # 구분자가 없으면 한 열짜리 표
    if not 구분:
        return [[줄.strip()] for 줄 in 줄들]
    return [[칸.strip() for 칸 in 줄.split(구분)] for 줄 in 줄들]


#: 한 줄(또는 한 셀) 단위로 값을 바꾸는 변환기 모음.
#: 원본에서 버튼 하나씩 흩어져 있던 기능을 이름 -> 함수 표로 통합했다.
한줄변환: dict[str, callable] = {
    "콤마넣기": 숫자모듈.콤마넣기,
    "콤마빼기": 숫자모듈.콤마빼기,
    "금액문구": 숫자모듈.금액문구,
    "한글금액": lambda 값: 숫자모듈.한글금액(숫자모듈.정수읽기(값) or 0),
    "증감문구": lambda 값: 숫자모듈.증감문구(값) or 값,
    "증감문구소수": lambda 값: 숫자모듈.증감문구(값, 소수=True) or 값,
    "날짜공문": lambda 값: 날짜모듈.날짜변환(값, "공문") or 값,
    "날짜점": lambda 값: 날짜모듈.날짜변환(값, "점") or 값,
    "날짜점띄": lambda 값: 날짜모듈.날짜변환(값, "점띄") or 값,
    "날짜바": lambda 값: 날짜모듈.날짜변환(값, "바") or 값,
    "날짜한글": lambda 값: 날짜모듈.날짜변환(값, "한글") or 값,
    "생년월일": lambda 값: (
        날짜모듈.날짜서식(날짜모듈.주민번호_생년월일(값), "점")
        if 날짜모듈.주민번호_생년월일(값)
        else 값
    ),
    "만나이": lambda 값: (
        f"{날짜모듈.만나이(값)}세" if 날짜모듈.만나이(값) is not None else 값
    ),
    "개월수": lambda 값: (
        f"{날짜모듈.개월수(값)}개월" if 날짜모듈.개월수(값) is not None else 값
    ),
    "공백정리": lambda 값: re.sub(r"\s+", " ", 값).strip(),
    "괄호제거": lambda 값: re.sub(r"\([^)]*\)", "", 값).strip(),
    "숫자만": 숫자모듈.숫자만,
}


def 줄별변환(텍스트: str, 변환이름: str) -> str:
    """블록 안의 각 줄에 `한줄변환` 표의 변환기를 적용한다."""
    변환 = 한줄변환.get(변환이름)
    if 변환 is None:
        raise KeyError(f"모르는 변환: {변환이름}")
    결과 = []
    for 줄 in 줄나누기(텍스트):
        결과.append(변환(줄) if 줄.strip() else 줄)
    return 줄합치기(결과)
