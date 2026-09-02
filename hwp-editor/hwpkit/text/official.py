"""공문(기안문) 조립 — 순수 로직.

행정업무운영 편람의 기안문 형식을 글로 만든다. 한/글을 부르지 않으므로 리눅스에서도
그대로 시험한다. 실제로 문서에 그리는 일은 `features/official.py` 가 한다.

**보고서와 공문은 항목기호 체계가 다르다.** 이 프로그램이 원래 다루던 보고서는
`□ → ○ → - → ※` 를 쓰지만, 기안문은 다음 차례를 쓴다.

    1.  →  가.  →  1)  →  가)  →  (1)  →  (가)  →  ①  →  ㉮

그래서 규정 검사기도 문서 종류를 갈라 봐야 한다(`features/inspect.py`).

여기서 대신 지켜 주는 것들
* 들여쓴 깊이만 보고 **기호를 차례대로 매긴다.** 단계를 건너뛸 수 없다.
* 같은 수준에 항목이 **하나뿐이면 기호를 붙이지 않는다.** (편람 규정)
* 하위 항목은 상위 항목 자리에서 **2타 들여쓴다.**
* 붙임은 번호·수량·온점을 붙이고, 하나뿐이면 번호를 붙이지 않는다.
* `끝.` 은 붙임이 있으면 마지막 붙임 뒤, 없으면 본문 뒤에 2타 띄우고 붙인다.
* 수신처가 여럿이면 두문을 `수신자 참조` 로 바꾸고 결문에 수신자 줄을 만든다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from . import dates

__all__ = [
    "기관정보",
    "붙임",
    "공문",
    "항목기호",
    "본문항목",
    "본문줄들",
    "붙임줄들",
    "수신줄",
    "두문줄들",
    "결문줄들",
    "공문줄들",
    "미리보기",
    "공개구분들",
    "기호체계",
]

#: 편람의 항목기호 차례. 수준 1 부터.
기호체계 = ("1.", "가.", "1)", "가)", "(1)", "(가)", "①", "㉮")

#: 공개 구분 (정보공개법)
공개구분들 = ("공개", "부분공개", "비공개")

_한글차례 = "가나다라마바사아자차카타파하"
_원숫자 = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
_원한글 = "㉮㉯㉰㉱㉲㉳㉴㉵㉶㉷㉸㉹㉺㉻"

#: 사람이 이미 붙여 놓은 글머리. 다시 매기기 전에 떼어 낸다.
_앞기호 = re.compile(
    r"^\s*(?:"
    r"[□■○◦●\-–—*※·]|"  # 보고서 기호
    r"\(?\d{1,2}\)|\d{1,2}\.|"  # 1) (1) 1.
    r"\(?[가-힣]\)|[가-힣]\.|"  # 가) (가) 가.
    r"[①-⑮]|[㉮-㉻]"
    r")\s+"
)
_수량꼴 = re.compile(r"(\d+\s*(?:부|매|건|권|점|통))\s*\.?$")
_들여쓰기 = re.compile("^[ \t\u00a0]*")


@dataclass(frozen=True)
class 기관정보:
    """결문에 들어가는 기관 정보. 한 번 설정해 두고 계속 쓴다."""

    기관명: str = ""
    부서: str = ""
    발신명의: str = ""
    우편번호: str = ""
    주소: str = ""
    누리집: str = ""
    전화: str = ""
    전송: str = ""
    전자우편: str = ""

    @property
    def 비었나(self) -> bool:
        return not (self.기관명 or self.발신명의)


@dataclass(frozen=True)
class 붙임:
    """붙임 하나. 수량을 안 적으면 '1부'."""

    이름: str
    수량: str = "1부"

    @staticmethod
    def 읽기(줄: str) -> "붙임 | None":
        """'명단|2부' 또는 '명단 2부' 또는 '명단' 을 붙임으로 읽는다."""
        값 = (줄 or "").strip().rstrip(".")
        if not 값:
            return None
        값 = _앞기호.sub("", 값).strip()
        if "|" in 값:
            이름, _, 수량 = 값.partition("|")
            이름, 수량 = 이름.strip(), 수량.strip()
            return 붙임(이름=이름, 수량=수량 or "1부") if 이름 else None
        m = _수량꼴.search(값)
        if m:
            이름 = 값[: m.start()].strip()
            if 이름:
                return 붙임(이름=이름, 수량=re.sub(r"\s+", "", m.group(1)))
        return 붙임(이름=값)

    @property
    def 문구(self) -> str:
        return f"{self.이름} {self.수량}."


@dataclass
class 공문:
    """기안문 한 건에 들어갈 값."""

    제목: str = ""
    수신들: tuple[str, ...] = ()
    경유: str = ""
    관련: str = ""
    본문: str = ""
    붙임들: tuple[붙임, ...] = ()
    시행일: date | None = None
    문서번호: str = ""
    공개구분: str = "공개"
    기안자: str = ""
    검토자: str = ""
    결재권자: str = ""
    협조자: str = ""

    @property
    def 수신여럿(self) -> bool:
        return len(self.수신들) >= 2


@dataclass(frozen=True)
class 본문항목:
    """본문 한 줄. 기호는 이미 매겨진 상태다."""

    수준: int
    기호: str
    내용: str

    @property
    def 줄(self) -> str:
        """들여쓰기까지 붙인 완성된 줄. (하위는 상위 자리에서 2타)"""
        들여 = " " * (2 * (self.수준 - 1))
        머리 = f"{self.기호} " if self.기호 else ""
        return f"{들여}{머리}{self.내용}"


# ------------------------------------------------------------------ 기호
def 항목기호(수준: int, 순번: int) -> str:
    """수준(1부터)과 그 수준에서의 순번(1부터)에 맞는 기호를 만든다.

    편람 차례를 따른다 — 1. / 가. / 1) / 가) / (1) / (가) / ① / ㉮
    """
    수준 = max(1, min(수준, len(기호체계)))
    순번 = max(1, 순번)
    if 수준 == 1:
        return f"{순번}."
    if 수준 == 2:
        return f"{_한글순번(순번)}."
    if 수준 == 3:
        return f"{순번})"
    if 수준 == 4:
        return f"{_한글순번(순번)})"
    if 수준 == 5:
        return f"({순번})"
    if 수준 == 6:
        return f"({_한글순번(순번)})"
    if 수준 == 7:
        return _원숫자[(순번 - 1) % len(_원숫자)]
    return _원한글[(순번 - 1) % len(_원한글)]


def _한글순번(순번: int) -> str:
    """1→가, 15→가가 … 열넷을 넘으면 두 글자로 잇는다."""
    자리 = len(_한글차례)
    if 순번 <= 자리:
        return _한글차례[순번 - 1]
    앞, 뒤 = divmod(순번 - 1, 자리)
    return _한글차례[앞 - 1] + _한글차례[뒤]


# ------------------------------------------------------------------ 본문
def 본문줄들(본문: str, 관련: str = "") -> list[본문항목]:
    """사람이 쓴 본문을 공문 항목으로 다시 매긴다.

    들여쓴 깊이(공백 2칸 또는 탭 하나)만 보고 수준을 정한다. 이미 붙어 있는
    글머리(□ ○ - 1. 가. …)는 떼어 내고 규정 차례로 다시 매긴다. 단계를 건너뛰어
    적었더라도 결과는 항상 한 단계씩만 내려간다.
    """
    조각들: list[tuple[int, str]] = []
    if 관련.strip():
        조각들.append((1, f"관련: {관련.strip()}"))

    깊이표: list[int] = []
    for 원줄 in re.split(r"\r\n|\r|\n", 본문 or ""):
        if not 원줄.strip():
            continue
        깊이 = _깊이재기(원줄)
        내용 = _앞기호.sub("", 원줄.strip()).strip()
        if not 내용:
            continue
        수준 = _수준정하기(깊이표, 깊이)
        조각들.append((수준, 내용))

    return _기호매기기(조각들)


def _깊이재기(줄: str) -> int:
    """줄 앞 공백의 너비. 탭은 두 칸으로 센다."""
    앞 = _들여쓰기.match(줄).group()
    return sum(2 if 글자 == "\t" else 1 for 글자 in 앞)


def _수준정하기(깊이표: list[int], 깊이: int) -> int:
    """깊이를 쌓아 두고 몇 번째 수준인지 정한다. (건너뛰기 없음)"""
    while 깊이표 and 깊이 < 깊이표[-1]:
        깊이표.pop()
    if 깊이표 and 깊이 == 깊이표[-1]:
        return len(깊이표)
    if not 깊이표 or 깊이 > 깊이표[-1]:
        깊이표.append(깊이)
    return len(깊이표)


def _기호매기기(조각들: list[tuple[int, str]]) -> list[본문항목]:
    """수준별로 순번을 매긴다. 같은 수준에 형제가 없으면 기호를 붙이지 않는다."""
    형제수: dict[tuple[int, ...], int] = {}
    길: list[int] = []  # 지금까지의 순번 경로
    자리들: list[tuple[tuple[int, ...], int, str]] = []

    for 수준, 내용 in 조각들:
        del 길[수준 - 1 :]
        while len(길) < 수준 - 1:
            길.append(1)  # 윗단계 없이 시작하면 1번으로 본다
        부모 = tuple(길)
        순번 = 형제수.get(부모, 0) + 1
        형제수[부모] = 순번
        길.append(순번)
        자리들.append((부모, 수준, 내용))

    항목들: list[본문항목] = []
    순번표: dict[tuple[int, ...], int] = {}
    for 부모, 수준, 내용 in 자리들:
        순번 = 순번표.get(부모, 0) + 1
        순번표[부모] = 순번
        홀로 = 형제수.get(부모, 0) == 1
        기호 = "" if 홀로 else 항목기호(수준, 순번)
        항목들.append(본문항목(수준=수준, 기호=기호, 내용=내용))
    return 항목들


# ------------------------------------------------------------------ 붙임
def 붙임줄들(붙임들: tuple[붙임, ...] | list[붙임], 끝표시: bool = True) -> list[str]:
    """붙임 표시문을 만든다.

    하나면 번호를 붙이지 않고, 여럿이면 번호를 매긴다. 마지막 뒤에 `끝.` 을 둔다.
    """
    목록 = [하나 for 하나 in 붙임들 if 하나 and 하나.이름.strip()]
    if not 목록:
        return []
    줄들: list[str] = []
    if len(목록) == 1:
        줄들.append(f"붙임  {목록[0].문구}")
    else:
        for 번호, 하나 in enumerate(목록, start=1):
            머리 = "붙임  " if 번호 == 1 else " " * 6
            줄들.append(f"{머리}{번호}. {하나.문구}")
    if 끝표시:
        줄들[-1] += "  끝."
    return 줄들


def 끝붙이기(줄: str) -> str:
    """본문 마지막 줄에 2타 띄우고 `끝.` 을 붙인다."""
    값 = (줄 or "").rstrip()
    return f"{값}  끝." if 값 else "끝."


# ------------------------------------------------------------------ 두문·결문
def 수신줄(수신들: tuple[str, ...] | list[str]) -> str:
    """두문의 수신 줄. 여럿이면 '수신자 참조'."""
    목록 = [하나.strip() for 하나 in 수신들 if 하나 and 하나.strip()]
    if not 목록:
        return "수신  내부결재"
    if len(목록) == 1:
        return f"수신  {목록[0]}"
    return "수신  수신자 참조"


def 수신들읽기(원문: str) -> tuple[str, ...]:
    """쉼표·줄바꿈으로 적은 수신처를 목록으로."""
    조각들 = re.split(r"[,\n\r]+", 원문 or "")
    return tuple(하나.strip() for 하나 in 조각들 if 하나.strip())


def 두문줄들(문서: 공문, 기관: 기관정보) -> list[str]:
    줄들: list[str] = []
    if 기관.기관명.strip():
        줄들.append(기관.기관명.strip())
        줄들.append("")
    줄들.append(수신줄(문서.수신들))
    if 문서.경유.strip():
        줄들.append(f"(경유)  {문서.경유.strip()}")
    줄들.append(f"제목  {문서.제목.strip()}")
    return 줄들


def 결문줄들(문서: 공문, 기관: 기관정보) -> list[str]:
    """발신명의부터 아래로. 값이 없는 줄은 만들지 않는다."""
    줄들: list[str] = []
    발신 = 기관.발신명의.strip() or 기관.기관명.strip()
    if 발신:
        줄들 += ["", 발신, ""]

    if 문서.수신여럿:
        줄들.append("수신자  " + ", ".join(문서.수신들))
        줄들.append("")

    결재 = [
        f"기안자 {문서.기안자.strip()}" if 문서.기안자.strip() else "",
        f"검토자 {문서.검토자.strip()}" if 문서.검토자.strip() else "",
        f"결재권자 {문서.결재권자.strip()}" if 문서.결재권자.strip() else "",
    ]
    결재줄 = "   ".join(하나 for 하나 in 결재 if 하나)
    if 결재줄:
        줄들.append(결재줄)
    if 문서.협조자.strip():
        줄들.append(f"협조자 {문서.협조자.strip()}")

    줄들.append(_시행줄(문서, 기관))

    주소줄 = _주소줄(기관)
    if 주소줄:
        줄들.append(주소줄)
    잇는줄 = _연락줄(문서, 기관)
    if 잇는줄:
        줄들.append(잇는줄)
    return 줄들


def _시행줄(문서: 공문, 기관: 기관정보) -> str:
    번호 = 문서.문서번호.strip() or (기관.부서.strip() + "-" if 기관.부서.strip() else "")
    날짜 = dates.날짜서식(문서.시행일 or date.today(), "점띄")
    시행 = f"시행  {번호}({날짜})" if 번호 else f"시행  ({날짜})"
    return f"{시행}      접수"


def _주소줄(기관: 기관정보) -> str:
    조각 = []
    if 기관.우편번호.strip():
        조각.append(f"우 {기관.우편번호.strip()}")
    if 기관.주소.strip():
        조각.append(기관.주소.strip())
    줄 = "  ".join(조각)
    if 기관.누리집.strip():
        줄 = f"{줄} / {기관.누리집.strip()}" if 줄 else 기관.누리집.strip()
    return 줄


def _연락줄(문서: 공문, 기관: 기관정보) -> str:
    조각 = []
    if 기관.전화.strip():
        조각.append(f"전화 {기관.전화.strip()}")
    if 기관.전송.strip():
        조각.append(f"전송 {기관.전송.strip()}")
    줄 = "  ".join(조각)
    뒤 = [하나 for 하나 in (기관.전자우편.strip(), 문서.공개구분.strip() or "공개") if 하나]
    return " / ".join([줄] + 뒤) if 줄 else " / ".join(뒤)


# ------------------------------------------------------------------ 전체
def 공문줄들(문서: 공문, 기관: 기관정보 | None = None, 본문만: bool = False) -> list[str]:
    """기안문 전체를 줄 목록으로 만든다.

    `본문만=True` 면 두문·결문을 빼고 제목·본문·붙임만 만든다. 온나라처럼 두문과
    결문을 시스템이 채우는 곳에 붙여넣을 때 쓴다.
    """
    기관 = 기관 or 기관정보()
    줄들: list[str] = []
    if not 본문만:
        줄들 += 두문줄들(문서, 기관)
        줄들.append("")
    elif 문서.제목.strip():
        줄들.append(f"제목  {문서.제목.strip()}")
        줄들.append("")

    항목들 = 본문줄들(문서.본문, 문서.관련)
    본문칸 = [하나.줄 for 하나 in 항목들]
    붙임칸 = 붙임줄들(문서.붙임들)

    if 본문칸 and not 붙임칸:
        본문칸[-1] = 끝붙이기(본문칸[-1])
    줄들 += 본문칸

    if 붙임칸:
        줄들.append("")
        줄들 += 붙임칸
    if not 본문칸 and not 붙임칸:
        줄들.append("끝.")

    if not 본문만:
        줄들 += 결문줄들(문서, 기관)
    return 줄들


def 미리보기(문서: 공문, 기관: 기관정보 | None = None, 본문만: bool = False) -> str:
    """만들어질 문서를 글로 보여준다. (그리기 전에 확인용)"""
    return "\n".join(공문줄들(문서, 기관, 본문만))
