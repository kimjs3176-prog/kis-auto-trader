"""공문서 규정 검사기.

공문서 작성 규정(행정업무운영 편람 기준)에서 실무자가 가장 자주 놓치는 항목만
골라 검사한다. **고치지 않고 목록으로 보여주는 것**이 기본이고, 계산으로 정답이
정해지는 것(날짜·시간·금액 표기)만 자동 고치기를 제공한다.

검사 로직은 순수 함수(`검사텍스트`)로 두어 한/글 없이 검증된다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.document import 문서
from ..text import dates, privacy
from ..text.numbers import 정수읽기
from ..text.transform import 찾아바꾸기규칙

__all__ = ["지적", "검사결과", "검사텍스트", "문서검사", "자동고치기", "규칙설명"]

#: 규칙 이름 → 설명 (도움말·UI 표시용)
규칙설명: dict[str, str] = {
    "날짜표기": "날짜는 '2025. 3. 9.' 처럼 숫자와 온점으로 적고 온점 뒤에 한 칸을 둡니다.",
    "시간표기": "시간은 '14:30' 처럼 24시각제로 적습니다.",
    "금액표기": "금액은 세 자리마다 쉼표를 넣습니다. (계약 금액은 한글 병기)",
    "항목기호": "항목은 □ → ○ → - → ※ 순서로 내려갑니다. 단계를 건너뛰지 않습니다.",
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
_기호수준 = (("□", 1), ("■", 1), ("○", 2), ("◦", 2), ("-", 3), ("※", 4))


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


def 검사텍스트(텍스트: str) -> list[지적]:
    """문서 본문 텍스트를 규정에 비추어 검사한다."""
    줄들 = re.split(r"\r\n|\r|\n", 텍스트 or "")
    결과: list[지적] = []

    for 줄번호, 줄 in enumerate(줄들, start=1):
        결과 += _날짜검사(줄번호, 줄)
        결과 += _시간검사(줄번호, 줄)
        결과 += _금액검사(줄번호, 줄)
        결과 += _겹공백검사(줄번호, 줄)

    결과 += _항목기호검사(줄들)
    결과 += _붙임검사(줄들)
    결과 += _끝표시검사(줄들)
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


def _겹공백검사(줄번호: int, 줄: str) -> list[지적]:
    # 표 안에서 자리를 맞추려고 일부러 띄우는 경우가 있어 '확인' 등급으로 둔다.
    if not _겹공백.search(줄):
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


def _줄수준(줄: str) -> int | None:
    본문 = 줄.lstrip()
    for 기호, 수준 in _기호수준:
        if 본문.startswith(기호 + " ") or 본문.startswith(기호 + "\t"):
            return 수준
    return None


def _항목기호검사(줄들: list[str]) -> list[지적]:
    결과: list[지적] = []
    앞수준 = 0
    for 줄번호, 줄 in enumerate(줄들, start=1):
        수준 = _줄수준(줄)
        if 수준 is None:
            continue
        if 앞수준 and 수준 > 앞수준 + 1:
            결과.append(
                지적(
                    규칙="항목기호",
                    등급="권장",
                    줄번호=줄번호,
                    원문=줄.strip()[:40],
                    안내=f"{앞수준}단계 다음에 {수준}단계가 왔습니다. " + 규칙설명["항목기호"],
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
        if not re.search(r"\d+\s*\.", 본문):
            빠진것.append("항목 번호(1.)")
        if not re.search(r"\d+\s*(부|매|건)\s*\.", 본문):
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


def _끝표시검사(줄들: list[str]) -> list[지적]:
    내용줄 = [(번호, 줄.strip()) for 번호, 줄 in enumerate(줄들, start=1) if 줄.strip()]
    if not 내용줄:
        return []
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


def 문서검사(문서객체: 문서, 개인정보포함: bool = True) -> 검사결과:
    """열린 문서를 검사한다. 본문 규정 + 용지·여백 + (선택) 개인정보."""
    본문 = 문서객체.전체텍스트()
    결과 = 검사결과(항목들=검사텍스트(본문))

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
