"""공문(기안문) 만들기 — 조립된 줄을 한/글 문서에 그린다.

글을 만드는 일은 `text/official.py` 가 한다(한/글 없이 시험된다). 여기서는
그 결과를 문서에 앉히고, 기관 정보를 파일에 두고 꺼내 쓰고, 만든 직후 규정
검사를 돌린다.

온나라에 **직접 기안·상신하지 않는다.** 온나라 문서는 행정정보통신망 안에서만
돌고 바깥에 공개된 연동 규격이 없다. 이 프로그램은 온나라에 붙여넣거나 첨부할
기안문을 규정대로 만들어 주는 데까지를 맡는다. (`본문만=True` 로 만들면 두문·
결문 없이 제목·본문·붙임만 나와 온나라 편집기에 그대로 붙는다)
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from ..core.document import 문서
from ..core.errors import 입력오류
from ..text import official as 공문글
from ..text.official import 공문, 기관정보, 붙임

__all__ = [
    "유형목록",
    "유형틀",
    "설정파일",
    "기관정보읽기",
    "기관정보쓰기",
    "공문결과",
    "공문만들기",
    "붙임들읽기",
]

_유형파일 = Path(__file__).resolve().parent.parent / "presets" / "official.json"

#: 결문 잔줄은 본문보다 작게 (실제 기안문도 그렇다)
_결문크기 = 10.0


@lru_cache(maxsize=1)
def _유형읽기() -> dict:
    return json.loads(_유형파일.read_text(encoding="utf-8"))


def 유형목록() -> dict[str, str]:
    """문서 유형 이름 → 설명."""
    return {이름: 값.get("설명", "") for 이름, 값 in _유형읽기().get("유형", {}).items()}


def 유형틀(이름: str) -> dict:
    """유형의 제목·본문·붙임 골격. 사용자가 내용만 바꾸면 된다."""
    유형 = _유형읽기().get("유형", {})
    if 이름 not in 유형:
        raise 입력오류(f"없는 공문 유형: {이름}", f"가능: {', '.join(유형)}")
    값 = 유형[이름]
    return {
        "제목": 값.get("제목", ""),
        "본문": "\n".join(값.get("본문", [])),
        "붙임": "\n".join(값.get("붙임", [])),
    }


# --------------------------------------------------------------- 기관 정보
def 설정파일() -> Path:
    """기관 정보를 두는 곳. (`%USERPROFILE%\\.hwpkit\\official.json`)"""
    뿌리 = Path(os.environ.get("HWPKIT_HOME") or os.environ.get("USERPROFILE") or Path.home())
    폴더 = 뿌리 / ".hwpkit"
    폴더.mkdir(parents=True, exist_ok=True)
    return 폴더 / "official.json"


def 기관정보읽기() -> 기관정보:
    """저장해 둔 기관 정보. 없으면 빈 값."""
    경로 = 설정파일()
    if not 경로.is_file():
        return 기관정보()
    try:
        자료 = json.loads(경로.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 기관정보()
    쓸것 = {이름: str(자료.get(이름, "") or "") for 이름 in 기관정보().__dataclass_fields__}
    return 기관정보(**쓸것)


def 기관정보쓰기(값: 기관정보) -> Path:
    """기관 정보를 저장한다."""
    경로 = 설정파일()
    경로.write_text(
        json.dumps(asdict(값), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 경로


def 붙임들읽기(원문: str) -> tuple[붙임, ...]:
    """여러 줄로 적은 붙임을 목록으로. ('이름|2부' 또는 '이름 2부' 또는 '이름')"""
    목록 = []
    for 줄 in (원문 or "").splitlines():
        하나 = 붙임.읽기(줄)
        if 하나:
            목록.append(하나)
    return tuple(목록)


# ------------------------------------------------------------------ 그리기
@dataclass
class 공문결과:
    """만든 결과 요약."""

    줄수: int = 0
    항목수: int = 0
    붙임수: int = 0
    수신수: int = 0
    본문만: bool = False
    지적들: list[str] = field(default_factory=list)

    @property
    def 문구(self) -> str:
        머리 = "본문만 만들었습니다." if self.본문만 else "기안문을 만들었습니다."
        줄들 = [
            f"{머리} (본문 항목 {self.항목수}개, 붙임 {self.붙임수}개,"
            f" 수신 {self.수신수}곳, {self.줄수}줄)"
        ]
        if self.지적들:
            줄들.append("")
            줄들.append(f"규정 검사에서 {len(self.지적들)}건이 걸렸습니다.")
            줄들 += self.지적들[:15]
        else:
            줄들.append("규정 검사: 걸린 곳이 없습니다.")
        return "\n".join(줄들)


def 공문만들기(
    문서객체: 문서,
    문서값: 공문,
    기관: 기관정보 | None = None,
    새문서: bool = True,
    본문만: bool = False,
    글자크기: float = 15.0,
    폰트: str = "",
    검사: bool = True,
) -> 공문결과:
    """기안문을 문서에 그린다.

    실패하면 그때까지 넣은 것을 되돌린다(`문서객체.한번에`).
    """
    if not (문서값.제목 or "").strip():
        raise 입력오류("제목을 적어 주세요.", "공문은 제목 없이 만들 수 없습니다.")

    기관 = 기관 or 기관정보()
    줄들 = 공문글.공문줄들(문서값, 기관, 본문만=본문만)
    항목들 = 공문글.본문줄들(문서값.본문, 문서값.관련)

    from .format import 글자모양, 문단모양
    from .page import 용지설정

    with 문서객체.한번에("공문 만들기"), 문서객체.화면정지():
        if 새문서:
            문서객체.새문서()
            용지설정(문서객체, 용지="A4", 여백값="공문기본")

        for 순번, 줄 in enumerate(줄들):
            _줄그리기(문서객체, 줄, 문서값, 기관, 글자크기, 폰트, 본문만)
            if 순번 != len(줄들) - 1:
                문서객체.문단()

        글자모양(문서객체, 크기=글자크기, 진하게=False)
        문단모양(문서객체, 정렬="왼쪽")

    결과 = 공문결과(
        줄수=len(줄들),
        항목수=len(항목들),
        붙임수=len(문서값.붙임들),
        수신수=len(문서값.수신들),
        본문만=본문만,
    )
    if 검사:
        from .inspect import 검사텍스트

        결과.지적들 = [하나.문구 for 하나 in 검사텍스트("\n".join(줄들), 종류="공문")]
    return 결과


def _줄그리기(
    문서객체: 문서,
    줄: str,
    문서값: 공문,
    기관: 기관정보,
    글자크기: float,
    폰트: str,
    본문만: bool,
) -> None:
    """줄 하나를 자리에 맞는 서식으로 넣는다."""
    from .format import 글자모양, 문단모양

    값 = 줄.rstrip()
    기관명 = (기관.기관명 or "").strip()
    발신 = (기관.발신명의 or "").strip() or 기관명

    가운데 = (not 본문만) and 값 != "" and 값 in (기관명, 발신)
    잔줄 = (not 본문만) and _결문잔줄인가(값)

    글자모양(
        문서객체,
        폰트=폰트 or None,
        크기=_결문크기 if 잔줄 else (글자크기 + 3 if 가운데 else 글자크기),
        진하게=bool(가운데),
    )
    문단모양(문서객체, 정렬="가운데" if 가운데 else "왼쪽", 줄간격=160)
    if 값:
        문서객체.문장입력(값)


def _결문잔줄인가(줄: str) -> bool:
    """결문의 작은 글씨 줄(기안자·시행·주소·전화)인지."""
    머리 = ("기안자", "협조자", "시행", "접수", "우 ", "전화", "수신자")
    값 = 줄.lstrip()
    return any(값.startswith(하나) for 하나 in 머리)


def 오늘날짜() -> date:
    """시행일 기본값. (시험에서 갈아 끼우기 쉽게 함수로 둔다)"""
    return date.today()
