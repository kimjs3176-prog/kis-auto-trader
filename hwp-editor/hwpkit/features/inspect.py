"""공문서 규정 검사기.

공문서 작성 규정(행정업무운영 편람 기준)에서 실무자가 가장 자주 놓치는 항목만
골라 검사한다. **고치지 않고 목록으로 보여주는 것**이 기본이고, 계산으로 정답이
정해지는 것(날짜·시간·금액 표기)만 자동 고치기를 제공한다.

**문서 종류를 갈라 본다.** 항목기호 차례가 서로 다르기 때문이다.

| 종류 | 항목기호 차례 |
|---|---|
| 공문(기안문) | `1.` → `가.` → `1)` → `가)` → `(1)` → `(가)` → `①` → `㉮` |
| 보고서 | `□` → `○` → `-` → `※` |

전에는 보고서 체계 하나로만 검사해서, **공문을 규정대로 쓴 사람이 오히려 지적을
받았다.** 이제 `종류="자동"`(기본)이면 문서를 보고 스스로 가른다.

검사 로직은 순수 함수(`검사텍스트`)로 두어 한/글 없이 검증된다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.document import 문서
from ..core.errors import 입력오류
from ..text import dates, privacy
from ..text.numbers import 정수읽기
from ..text.transform import 찾아바꾸기규칙

__all__ = [
    "지적",
    "검사결과",
    "검사텍스트",
    "문서검사",
    "자동고치기",
    "규칙설명",
    "종류들",
    "문서종류판정",
    "기호차례",
]

#: 검사할 문서 종류
종류들 = ("자동", "공문", "보고서")

#: 종류별 항목기호 차례 (안내 문구용)
기호차례: dict[str, str] = {
    "공문": "1. → 가. → 1) → 가) → (1) → (가) → ① → ㉮",
    "보고서": "□ → ○ → - → ※",
}

#: 규칙 이름 → 설명 (도움말·UI 표시용)
규칙설명: dict[str, str] = {
    "날짜표기": "날짜는 '2025. 3. 9.' 처럼 숫자와 온점으로 적고 온점 뒤에 한 칸을 둡니다.",
    "시간표기": "시간은 '14:30' 처럼 24시각제로 적습니다.",
    "금액표기": "금액은 세 자리마다 쉼표를 넣습니다. (계약 금액은 한글 병기)",
    "항목기호": "항목은 차례대로 내려갑니다. 단계를 건너뛰지 않습니다.",
    "붙임표기": "'붙임  1. 자료명 1부.' 형식으로 적고 수량과 온점을 붙입니다.",
    "끝표시": "본문(붙임이 있으면 붙임) 뒤에 '끝.' 을 표시합니다.",
    "겹공백": "낱말 사이는 한 칸만 띄웁니다.",
    "용지여백": "공문은 A4 용지에 좌우 여백 20mm 를 권합니다.",
    "개인정보": "공개·배포 문서에는 개인정보를 남기지 않습니다.",
}

_등급순서 = {"필수": 0, "권장": 1, "확인": 2}

_표준날짜 = re.compile(r"^\d{4}\. \d{1,2}\. \d{1,2}\.$")
_날짜꼴 = re.compile(r"\b\d{4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2}\.?")
_시간꼴 = re.compile(r"\b(\d{1,2})\s*시\s*(\d{1,2})\s*분")
_금액꼴 = re.compile(r"\b(\d{4,})\s*(원|천원|백만원|억원)\b")
_겹공백 = re.compile(r"[가-힣a-zA-Z0-9)][ ]{2,}[가-힣a-zA-Z0-9(]")
_붙임줄 = re.compile(r"^\s*붙\s*임")
_끝앞2타 = re.compile(r"\s+끝\.\s*$")

#: 보고서 글머리 → 수준
_보고서기호 = (("□", 1), ("■", 1), ("○", 2), ("◦", 2), ("-", 3), ("※", 4))

#: 공문 항목기호 → 수준. 꼴이 정해져 있어 정규식으로 본다.
_공문기호 = (
    (re.compile(r"^\d{1,2}\.$"), 1),
    (re.compile(r"^[가-힣]\.$"), 2),
    (re.compile(r"^\d{1,2}\)$"), 3),
    (re.compile(r"^[가-힣]\)$"), 4),
    (re.compile(r"^\(\d{1,2}\)$"), 5),
    (re.compile(r"^\([가-힣]\)$"), 6),
    (re.compile(r"^[①-⑮]$"), 7),
    (re.compile(r"^[㉮-㉻]$"), 8),
)

#: 공문이라고 볼 만한 자취 (두문·결문)
_공문자취 = (
    re.compile(r"^\s*수신\s{1,4}\S"),
    re.compile(r"^\s*\(경유\)"),
    re.compile(r"^\s*제목\s{1,4}\S"),
    re.compile(r"^\s*시행\s"),
    re.compile(r"^\s*수신자\s"),
)

#: 두문·붙임 — 규정이 **2타**를 요구하는 자리다. 겹공백으로 지적하면 안 된다.
_두칸자리 = ("수신", "제목", "(경유)", "붙임", "발신", "결재")

#: 결문 줄 — 본문이 아니므로 '끝.' 을 여기서 찾으면 안 된다.
_결문머리 = ("수신자", "기안자", "검토자", "결재권자", "협조자", "시행", "접수", "우 ", "전화", "전송")


@dataclass(frozen=True)
class 지적:
    """검사에서 걸린 한 건."""

    규칙: str
    등급: str  # 필수 | 권장 | 확인
    줄번호: int
    원문: str
    안내: str
    고칠값: str | None = None  # 자동 고치기가 가능한 경우에만

    @property
    def 문구(self) -> str:
        말 = f"[{self.등급}] {self.줄번호}줄 {self.규칙}: {self.안내}"
        if self.원문:
            말 += f"  ({self.원문.strip()[:40]}"
            말 += f" → {self.고칠값})" if self.고칠값 else ")"
        return 말


@dataclass
class 검사결과:
    """검사 요약."""

    항목들: list[지적] = field(default_factory=list)
    개인정보: list[privacy.발견] = field(default_factory=list)
    문서정보: dict[str, str] = field(default_factory=dict)

    @property
    def 고칠수있는것(self) -> list[지적]:
        return [하나 for 하나 in self.항목들 if 하나.고칠값]

    @property
    def 문구(self) -> str:
        if not self.항목들 and not self.개인정보:
            return "규정에 어긋난 곳을 찾지 못했습니다."
        셈: dict[str, int] = {}
        for 하나 in self.항목들:
            셈[하나.등급] = 셈.get(하나.등급, 0) + 1
        머리 = ", ".join(f"{등급} {수}건" for 등급, 수 in sorted(셈.items()))
        줄들 = [f"검사 결과: {머리 or '없음'}"]
        if self.개인정보:
            줄들.append(f"개인정보: {privacy.요약(self.개인정보)}")
        if self.문서정보:
            줄들.append(
                "문서: " + ", ".join(f"{이름} {값}" for 이름, 값 in self.문서정보.items())
            )
        줄들.append("")
        줄들 += [하나.문구 for 하나 in self.항목들[:40]]
        남음 = len(self.항목들) - 40
        if 남음 > 0:
            줄들.append(f"… 그 밖에 {남음}건")
        if self.고칠수있는것:
            줄들.append("")
            줄들.append(
                f"'규정 자동 고치기' 를 누르면 표기 {len(self.고칠수있는것)}건을 바로 고칩니다."
            )
        return "\n".join(줄들)


def 문서종류판정(텍스트: str) -> str:
    """공문(기안문)인지 보고서인지 가른다.

    두문·결문 자취(`수신`·`제목`·`시행`)가 있으면 공문으로 본다. 없으면 글머리를
    세어 많은 쪽을 따른다. 둘 다 없으면 보고서로 둔다(이 프로그램의 기본 쓰임).
    """
    줄들 = re.split(r"\r\n|\r|\n", 텍스트 or "")
    자취 = sum(1 for 줄 in 줄들 for 꼴 in _공문자취 if 꼴.match(줄))
    if 자취 >= 2:
        return "공문"

    공문수 = sum(1 for 줄 in 줄들 if _공문수준(줄) is not None)
    보고서수 = sum(1 for 줄 in 줄들 if _보고서수준(줄) is not None)
    if 공문수 > 보고서수:
        return "공문"
    return "보고서"


def 검사텍스트(텍스트: str, 종류: str = "자동") -> list[지적]:
    """문서 본문 텍스트를 규정에 비추어 검사한다.

    `종류` 는 '자동' | '공문' | '보고서'. 항목기호 차례가 종류마다 다르다.
    """
    if 종류 not in 종류들:
        raise 입력오류(f"모르는 문서 종류: {종류}", f"가능: {', '.join(종류들)}")
    줄들 = re.split(r"\r\n|\r|\n", 텍스트 or "")
    고른종류 = 문서종류판정(텍스트) if 종류 == "자동" else 종류
    결과: list[지적] = []

    for 줄번호, 줄 in enumerate(줄들, start=1):
        결과 += _날짜검사(줄번호, 줄)
        결과 += _시간검사(줄번호, 줄)
        결과 += _금액검사(줄번호, 줄)
        결과 += _겹공백검사(줄번호, 줄, 고른종류)

    결과 += _항목기호검사(줄들, 고른종류)
    결과 += _붙임검사(줄들)
    결과 += _끝표시검사(줄들, 고른종류)
    결과.sort(key=lambda 하나: (하나.줄번호, _등급순서.get(하나.등급, 9)))
    return 결과


def _날짜검사(줄번호: int, 줄: str) -> list[지적]:
    결과 = []
    for m in _날짜꼴.finditer(줄):
        원문 = m.group()
        if _표준날짜.match(원문.strip()):
            continue
        값 = dates.날짜읽기(원문)
        고칠값 = dates.날짜서식(값, "점띄") if 값 else None
        결과.append(
            지적(
                규칙="날짜표기",
                등급="권장",
                줄번호=줄번호,
                원문=원문,
                안내=규칙설명["날짜표기"],
                고칠값=고칠값,
            )
        )
    return 결과


def _시간검사(줄번호: int, 줄: str) -> list[지적]:
    결과 = []
    for m in _시간꼴.finditer(줄):
        시, 분 = int(m.group(1)), int(m.group(2))
        if 시 > 23 or 분 > 59:
            continue
        결과.append(
            지적(
                규칙="시간표기",
                등급="권장",
                줄번호=줄번호,
                원문=m.group(),
                안내=규칙설명["시간표기"],
                고칠값=f"{시:02d}:{분:02d}",
            )
        )
    return 결과


def _금액검사(줄번호: int, 줄: str) -> list[지적]:
    결과 = []
    for m in _금액꼴.finditer(줄):
        수 = 정수읽기(m.group(1))
        if 수 is None or 수 < 1000:
            continue
        결과.append(
            지적(
                규칙="금액표기",
                등급="권장",
                줄번호=줄번호,
                원문=m.group(),
                안내=규칙설명["금액표기"],
                고칠값=f"{수:,}{m.group(2)}",
            )
        )
    return 결과


def _겹공백검사(줄번호: int, 줄: str, 종류: str = "보고서") -> list[지적]:
    # 표 안에서 자리를 맞추려고 일부러 띄우는 경우가 있어 '확인' 등급으로 둔다.
    # 공문의 '수신  ○○○', '붙임  1. …', '시행  …' 는 규정이 2타를 요구한다.
    if 종류 == "공문" and (_두칸자리인가(줄) or _결문줄인가(줄)):
        return []
    볼것 = _끝앞2타.sub("", 줄)  # '끝.' 앞 2타도 규정이 시키는 것이다
    if not _겹공백.search(볼것):
        return []
    return [
        지적(
            규칙="겹공백",
            등급="확인",
            줄번호=줄번호,
            원문=줄.strip()[:40],
            안내=규칙설명["겹공백"],
        )
    ]


def _보고서수준(줄: str) -> int | None:
    본문 = 줄.lstrip()
    for 기호, 수준 in _보고서기호:
        if 본문.startswith(기호 + " ") or 본문.startswith(기호 + "\t"):
            return 수준
    return None


def _공문수준(줄: str) -> int | None:
    """줄 앞의 항목기호를 보고 수준을 정한다. ('가. 나가는 길' → 2단계)"""
    본문 = 줄.lstrip()
    조각 = 본문.split(maxsplit=1)
    if len(조각) < 2 or not 조각[1].strip():
        return None
    for 꼴, 수준 in _공문기호:
        if 꼴.match(조각[0]):
            return 수준
    return None


def _줄수준(줄: str, 종류: str = "보고서") -> int | None:
    return _공문수준(줄) if 종류 == "공문" else _보고서수준(줄)


def _항목기호검사(줄들: list[str], 종류: str = "보고서") -> list[지적]:
    결과: list[지적] = []
    앞수준 = 0
    차례 = 기호차례.get(종류, 기호차례["보고서"])
    for 줄번호, 줄 in enumerate(줄들, start=1):
        수준 = _줄수준(줄, 종류)
        if 수준 is None:
            continue
        if 앞수준 and 수준 > 앞수준 + 1:
            결과.append(
                지적(
                    규칙="항목기호",
                    등급="권장",
                    줄번호=줄번호,
                    원문=줄.strip()[:40],
                    안내=(
                        f"{앞수준}단계 다음에 {수준}단계가 왔습니다."
                        f" {종류}는 {차례} 차례로 내려갑니다."
                    ),
                )
            )
        앞수준 = 수준
    return 결과


def _붙임검사(줄들: list[str]) -> list[지적]:
    결과: list[지적] = []
    for 줄번호, 줄 in enumerate(줄들, start=1):
        if not _붙임줄.match(줄):
            continue
        본문 = 줄.strip()
        빠진것 = []
        # 붙임이 하나뿐이면 번호를 붙이지 않는다(편람). 여럿일 때만 번호를 본다.
        여럿 = _붙임여럿인가(줄들, 줄번호)
        if 여럿 and not re.search(r"\d+\s*\.", 본문):
            빠진것.append("항목 번호(1.)")
        if not re.search(r"\d+\s*(부|매|건|권|점|통)\s*\.", 본문):
            빠진것.append("수량 표기(1부.)")
        if 빠진것:
            결과.append(
                지적(
                    규칙="붙임표기",
                    등급="권장",
                    줄번호=줄번호,
                    원문=본문[:40],
                    안내=f"{', '.join(빠진것)}이 없습니다. " + 규칙설명["붙임표기"],
                )
            )
    return 결과


def _붙임여럿인가(줄들: list[str], 줄번호: int) -> bool:
    """'붙임' 줄 다음에 '2. …' 같은 이어지는 항목이 있으면 여럿이다."""
    다음꼴 = re.compile(r"^\s+\d{1,2}\.\s")
    for 뒤 in 줄들[줄번호 : 줄번호 + 3]:
        if not 뒤.strip():
            continue
        return bool(다음꼴.match(뒤))
    return False


def _두칸자리인가(줄: str) -> bool:
    값 = 줄.lstrip()
    return any(값.startswith(하나) for 하나 in _두칸자리)


def _결문줄인가(줄: str) -> bool:
    값 = 줄.lstrip()
    return any(값.startswith(하나) for 하나 in _결문머리)


def _끝표시검사(줄들: list[str], 종류: str = "보고서") -> list[지적]:
    내용줄 = [(번호, 줄.strip()) for 번호, 줄 in enumerate(줄들, start=1) if 줄.strip()]
    if not 내용줄:
        return []

    # 공문은 '끝.' 뒤에 발신명의·결문이 이어진다. 문서 어딘가에 있으면 된 것이다.
    if 종류 == "공문":
        if any("끝." in 값 for _번호, 값 in 내용줄):
            return []
        본문줄 = [(번호, 값) for 번호, 값 in 내용줄 if not _결문줄인가(값)]
        마지막번호, 마지막 = (본문줄 or 내용줄)[-1]
        return [
            지적(
                규칙="끝표시",
                등급="권장",
                줄번호=마지막번호,
                원문=마지막[:40],
                안내=규칙설명["끝표시"],
            )
        ]

    마지막번호, 마지막 = 내용줄[-1]
    if 마지막.endswith("끝.") or "끝." in 마지막:
        return []
    return [
        지적(
            규칙="끝표시",
            등급="권장",
            줄번호=마지막번호,
            원문=마지막[:40],
            안내=규칙설명["끝표시"],
        )
    ]


def 문서검사(문서객체: 문서, 개인정보포함: bool = True, 종류: str = "자동") -> 검사결과:
    """열린 문서를 검사한다. 본문 규정 + 용지·여백 + (선택) 개인정보."""
    본문 = 문서객체.전체텍스트()
    결과 = 검사결과(항목들=검사텍스트(본문, 종류=종류))
    결과.문서정보["종류"] = 문서종류판정(본문) if 종류 == "자동" else 종류

    if 개인정보포함:
        결과.개인정보 = privacy.검사(본문)

    _용지검사(문서객체, 결과)
    return 결과


def _용지검사(문서객체: 문서, 결과: 검사결과) -> None:
    """용지·여백을 읽어 공문 기준과 비교한다. 읽지 못하면 건너뛴다."""
    from ..core import units

    try:
        with 문서객체.파라미터("PageSetup") as 값:
            쪽 = 값.Item("PageDef")
            폭 = units.hwp단위_mm(쪽.Item("PaperWidth"))
            높이 = units.hwp단위_mm(쪽.Item("PaperHeight"))
            좌 = units.hwp단위_mm(쪽.Item("LeftMargin"))
            우 = units.hwp단위_mm(쪽.Item("RightMargin"))
    except Exception:  # noqa: BLE001 - 문서 상태에 따라 못 읽을 수 있다
        return

    결과.문서정보["용지"] = f"{폭:.0f}×{높이:.0f}mm"
    결과.문서정보["좌우여백"] = f"{좌:.0f}/{우:.0f}mm"

    A4폭, A4높이 = units.A4
    가로세로 = sorted((폭, 높이))
    if abs(가로세로[0] - A4폭) > 3 or abs(가로세로[1] - A4높이) > 3:
        결과.항목들.append(
            지적(
                규칙="용지여백",
                등급="확인",
                줄번호=0,
                원문=f"{폭:.0f}×{높이:.0f}mm",
                안내=규칙설명["용지여백"],
            )
        )
    elif abs(좌 - 20) > 2 or abs(우 - 20) > 2:
        결과.항목들.append(
            지적(
                규칙="용지여백",
                등급="확인",
                줄번호=0,
                원문=f"좌 {좌:.0f}mm / 우 {우:.0f}mm",
                안내=규칙설명["용지여백"],
            )
        )


def 자동고치기(문서객체: 문서, 결과: 검사결과 | None = None, 규칙들: tuple[str, ...] = ()) -> int:
    """정답이 정해지는 표기(날짜·시간·금액)만 문서 전체에서 고친다.

    걸린 원문과 고칠 값이 1:1 로 정해진 것만 바꾸므로, 정규식 일괄 치환보다 안전하다.
    고친 표기 종류 수를 돌려준다.
    """
    from .find_replace import 문서전체바꾸기

    결과 = 결과 or 문서검사(문서객체, 개인정보포함=False)
    후보 = 결과.고칠수있는것
    if 규칙들:
        후보 = [하나 for 하나 in 후보 if 하나.규칙 in 규칙들]
    if not 후보:
        return 0

    짝: dict[str, str] = {}
    for 하나 in 후보:
        원문 = 하나.원문.strip()
        if 원문 and 하나.고칠값 and 원문 != 하나.고칠값:
            짝.setdefault(원문, 하나.고칠값)
    if not 짝:
        return 0

    규칙목록 = [찾아바꾸기규칙(찾기=찾기, 바꾸기=바꾸기) for 찾기, 바꾸기 in 짝.items()]
    문서전체바꾸기(문서객체, 규칙목록)
    return len(규칙목록)
