"""개인정보 탐지·마스킹 (순수 함수).

공개·배포 전에 문서에 남은 주민등록번호·연락처·계좌번호 등을 찾아내고, 원하면
가림 처리까지 한다. 원본 프로그램에는 없던 기능이다.

거짓 탐지를 줄이려고 두 가지를 지킨다.
1. 긴 종류를 먼저 검사하고, 이미 잡힌 자리는 다시 잡지 않는다.
   (예: 주민등록번호를 전화번호나 계좌번호로 다시 잡지 않음)
2. 형식만 맞으면 무조건 잡지 않고, 뜻이 맞는지 확인한다.
   (예: 주민등록번호는 월·일과 성별 자리를 검사)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

__all__ = ["종류", "발견", "종류목록", "검사", "마스킹", "이름마스킹", "요약"]


@dataclass(frozen=True)
class 종류:
    """개인정보 한 종류."""

    이름: str
    정규식: re.Pattern[str]
    가리기: Callable[[str], str]
    설명: str = ""
    확인: Callable[[re.Match[str]], bool] | None = None


def _가운데가리기(값: str, 앞: int, 뒤: int) -> str:
    """숫자·글자 자리를 앞/뒤만 남기고 별표로 바꾼다."""
    글자들 = list(값)
    대상 = [번호 for 번호, 글자 in enumerate(글자들) if glyph_숫자또는글자(글자)]
    for 번호 in 대상[앞 : len(대상) - 뒤 if 뒤 else len(대상)]:
        글자들[번호] = "*"
    return "".join(글자들)


def glyph_숫자또는글자(글자: str) -> bool:
    return 글자.isdigit() or 글자.isalpha()


def _주민번호확인(m: re.Match[str]) -> bool:
    자리 = re.sub(r"[^0-9]", "", m.group())
    if len(자리) != 13:
        return False
    월, 일, 성별 = int(자리[2:4]), int(자리[4:6]), 자리[6]
    return 1 <= 월 <= 12 and 1 <= 일 <= 31 and 성별 in "1234567890"


def _전화확인(m: re.Match[str]) -> bool:
    자리 = re.sub(r"[^0-9]", "", m.group())
    return 9 <= len(자리) <= 11


def _계좌확인(m: re.Match[str]) -> bool:
    자리 = re.sub(r"[^0-9]", "", m.group())
    # 계좌번호는 보통 10~16자리다. 8자리 이하(날짜 등)와 17자리 이상은 뺀다.
    return 10 <= len(자리) <= 16


def 종류목록() -> tuple[종류, ...]:
    """검사할 개인정보 종류. 앞에 있는 것을 먼저 검사한다."""
    return (
        종류(
            이름="주민등록번호",
            정규식=re.compile(r"\d{6}\s*[-–]\s*\d{7}"),
            가리기=lambda 값: re.sub(r"(\d{6}\s*[-–]\s*\d)\d{6}", r"\1******", 값),
            설명="외국인등록번호도 같은 형식입니다.",
            확인=_주민번호확인,
        ),
        종류(
            이름="카드번호",
            정규식=re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"),
            가리기=lambda 값: _가운데가리기(값, 4, 4),
        ),
        종류(
            이름="휴대전화",
            정규식=re.compile(r"\b01[016789][-. ]?\d{3,4}[-. ]?\d{4}\b"),
            가리기=lambda 값: _가운데가리기(값, 3, 4),
            확인=_전화확인,
        ),
        종류(
            이름="일반전화",
            정규식=re.compile(r"\b0\d{1,2}[-. ]\d{3,4}[-. ]\d{4}\b"),
            가리기=lambda 값: _가운데가리기(값, 3, 4),
            확인=_전화확인,
        ),
        종류(
            이름="이메일",
            정규식=re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
            가리기=lambda 값: _이메일가리기(값),
        ),
        종류(
            이름="계좌번호",
            정규식=re.compile(r"\b\d{2,6}[- ]\d{2,6}[- ]\d{2,7}(?:[- ]\d{1,6})?\b"),
            가리기=lambda 값: _가운데가리기(값, 3, 2),
            설명="형식이 비슷한 문서번호가 함께 잡힐 수 있어 확인이 필요합니다.",
            확인=_계좌확인,
        ),
        종류(
            이름="차량번호",
            정규식=re.compile(r"\b(?:[가-힣]{2}\s?)?\d{2,3}[가-힣]\s?\d{4}\b"),
            가리기=lambda 값: _가운데가리기(값, 2, 2),
        ),
        종류(
            이름="여권번호",
            정규식=re.compile(r"\b[MSRODmsrod]\d{8}\b"),
            가리기=lambda 값: _가운데가리기(값, 2, 2),
        ),
    )


def _이메일가리기(값: str) -> str:
    앞, _, 뒤 = 값.partition("@")
    남김 = 앞[:1] if len(앞) > 2 else 앞
    return f"{남김}{'*' * max(len(앞) - len(남김), 1)}@{뒤}"


@dataclass(frozen=True)
class 발견:
    """찾아낸 개인정보 한 건."""

    종류이름: str
    줄번호: int
    시작: int
    끝: int
    원문: str
    가린값: str
    설명: str = ""

    @property
    def 문구(self) -> str:
        말 = f"{self.줄번호}줄: [{self.종류이름}] {self.원문} → {self.가린값}"
        return f"{말}  ※{self.설명}" if self.설명 else 말


def 검사(텍스트: str, 종류들: tuple[종류, ...] | None = None) -> list[발견]:
    """텍스트에서 개인정보를 찾아 위치와 가릴 값을 함께 돌려준다."""
    종류들 = 종류들 or 종류목록()
    결과: list[발견] = []
    for 줄번호, 줄 in enumerate(re.split(r"\r\n|\r|\n", 텍스트 or ""), start=1):
        차지: list[tuple[int, int]] = []
        for 하나 in 종류들:
            for m in 하나.정규식.finditer(줄):
                if 하나.확인 and not 하나.확인(m):
                    continue
                if any(시 < m.end() and m.start() < 끝 for 시, 끝 in 차지):
                    continue  # 앞선(더 확실한) 종류가 이미 잡은 자리
                차지.append((m.start(), m.end()))
                결과.append(
                    발견(
                        종류이름=하나.이름,
                        줄번호=줄번호,
                        시작=m.start(),
                        끝=m.end(),
                        원문=m.group(),
                        가린값=하나.가리기(m.group()),
                        설명=하나.설명,
                    )
                )
    결과.sort(key=lambda 하나: (하나.줄번호, 하나.시작))
    return 결과


def 마스킹(
    텍스트: str, 종류이름들: tuple[str, ...] | None = None
) -> tuple[str, list[발견]]:
    """찾은 개인정보를 가린 값으로 바꾼다.

    종류이름들을 주면 그 종류만 가린다. (예: 계좌번호는 확인 후 직접 처리)
    """
    발견들 = 검사(텍스트)
    대상 = [
        하나 for 하나 in 발견들 if 종류이름들 is None or 하나.종류이름 in 종류이름들
    ]
    줄들 = re.split(r"\r\n|\r|\n", 텍스트 or "")
    줄별: dict[int, list[발견]] = {}
    for 하나 in 대상:
        줄별.setdefault(하나.줄번호, []).append(하나)

    for 줄번호, 목록 in 줄별.items():
        줄 = 줄들[줄번호 - 1]
        for 하나 in sorted(목록, key=lambda 값: 값.시작, reverse=True):
            줄 = 줄[: 하나.시작] + 하나.가린값 + 줄[하나.끝 :]
        줄들[줄번호 - 1] = 줄
    return "\r\n".join(줄들), 대상


def 이름마스킹(이름: str) -> str:
    """사람 이름의 가운데를 가린다. (홍길동 → 홍*동, 김철 → 김*)"""
    글자 = (이름 or "").strip()
    if len(글자) <= 1:
        return 글자
    if len(글자) == 2:
        return 글자[0] + "*"
    return 글자[0] + "*" * (len(글자) - 2) + 글자[-1]


def 요약(발견들: list[발견]) -> str:
    """종류별 건수를 한 줄로 정리한다."""
    if not 발견들:
        return "개인정보로 보이는 내용을 찾지 못했습니다."
    셈: dict[str, int] = {}
    for 하나 in 발견들:
        셈[하나.종류이름] = 셈.get(하나.종류이름, 0) + 1
    조각 = ", ".join(f"{이름} {수}건" for 이름, 수 in 셈.items())
    return f"모두 {len(발견들)}건 ({조각})"
