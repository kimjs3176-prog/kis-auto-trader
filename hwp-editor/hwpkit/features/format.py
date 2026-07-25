"""글자·문단 서식.

원본은 `폰트()`, `글자크기()`, `맑은고딕11`, `헤드라인16` … 처럼 조합마다 메서드와
버튼을 따로 두어 글자 관련 함수만 100개가 넘었다. 여기서는 인자 하나로 받는
`글자모양()` / `문단모양()` 두 함수와, 자주 쓰는 조합을 담은 **스타일 프리셋**
(presets/styles.json) 으로 통합했다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..core import units
from ..core.document import 문서
from ..core.errors import 입력오류

__all__ = [
    "글자모양",
    "문단모양",
    "형광펜",
    "형광펜지우기",
    "스타일적용",
    "스타일목록",
    "글머리적용",
    "글머리목록",
    "서식초기화",
]

_프리셋 = Path(__file__).resolve().parent.parent / "presets" / "styles.json"

_정렬코드 = {
    "왼쪽": "ParagraphShapeAlignLeft",
    "가운데": "ParagraphShapeAlignCenter",
    "오른쪽": "ParagraphShapeAlignRight",
    "양쪽": "ParagraphShapeAlignJustify",
    "배분": "ParagraphShapeAlignDistribute",
}


@lru_cache(maxsize=1)
def _프리셋읽기() -> dict:
    return json.loads(_프리셋.read_text(encoding="utf-8"))


def 스타일목록() -> dict[str, dict]:
    """이름 → 스타일 정의. UI 목록에 그대로 쓴다."""
    return _프리셋읽기().get("스타일", {})


def 글머리목록() -> dict[str, dict]:
    """이름 → 글머리 정의."""
    return _프리셋읽기().get("글머리", {})


def 글자모양(
    문서객체: 문서,
    폰트: str | None = None,
    크기: float | None = None,
    진하게: bool | None = None,
    기울임: bool | None = None,
    밑줄: bool | None = None,
    글자색: tuple[int, int, int] | None = None,
    장평: int | None = None,
    자간: int | None = None,
) -> None:
    """선택 영역(또는 이후 입력)의 글자모양을 바꾼다. 주지 않은 항목은 그대로 둔다."""
    with 문서객체.파라미터("CharShape") as 값:
        if 폰트:
            # 한/글은 언어별 폰트를 따로 갖는다. 모두 같은 폰트로 맞춘다.
            for 언어 in (
                "Hangul", "Latin", "Hanja", "Japanese", "Other", "Symbol", "User",
            ):
                값.SetItem(f"FaceName{언어}", 폰트)
                값.SetItem(f"FontType{언어}", 1)
        if 크기 is not None:
            값.SetItem("Height", units.pt(크기))
        if 진하게 is not None:
            값.SetItem("Bold", 1 if 진하게 else 0)
        if 기울임 is not None:
            값.SetItem("Italic", 1 if 기울임 else 0)
        if 밑줄 is not None:
            값.SetItem("UnderlineType", 1 if 밑줄 else 0)
        if 글자색 is not None:
            값.SetItem("TextColor", units.rgb(*글자색))
        if 장평 is not None:
            값.SetItem("Ratio", 장평)
        if 자간 is not None:
            값.SetItem("Spacing", 자간)


def 문단모양(
    문서객체: 문서,
    정렬: str | None = None,
    줄간격: int | None = None,
    위여백: float | None = None,
    아래여백: float | None = None,
    왼쪽여백: float | None = None,
    오른쪽여백: float | None = None,
    내어쓰기: float | None = None,
    낱말줄바꿈: bool | None = None,
) -> None:
    """문단모양을 바꾼다. 여백 단위는 mm, 줄간격은 % 다."""
    if 정렬 is not None:
        if 정렬 not in _정렬코드:
            raise 입력오류(f"모르는 정렬: {정렬}")
        문서객체.실행(_정렬코드[정렬])

    항목 = {
        "줄간격": 줄간격,
        "위여백": 위여백,
        "아래여백": 아래여백,
        "왼쪽여백": 왼쪽여백,
        "오른쪽여백": 오른쪽여백,
        "내어쓰기": 내어쓰기,
        "낱말줄바꿈": 낱말줄바꿈,
    }
    if all(값 is None for 값 in 항목.values()):
        return

    with 문서객체.파라미터("ParagraphShape") as 값:
        if 줄간격 is not None:
            값.SetItem("LineSpacingType", 0)  # 0 = 글자에 따라(%)
            값.SetItem("LineSpacing", 줄간격)
        if 위여백 is not None:
            값.SetItem("TopMargin", units.mm(위여백))
        if 아래여백 is not None:
            값.SetItem("BottomMargin", units.mm(아래여백))
        if 왼쪽여백 is not None:
            값.SetItem("LeftMargin", units.mm(왼쪽여백))
        if 오른쪽여백 is not None:
            값.SetItem("RightMargin", units.mm(오른쪽여백))
        if 내어쓰기 is not None:
            값.SetItem("Indentation", units.mm(내어쓰기))
        if 낱말줄바꿈 is not None:
            값.SetItem("BreakNonLatinWord", 1 if 낱말줄바꿈 else 0)


def 형광펜(문서객체: 문서, 색: tuple[int, int, int]) -> None:
    """선택 영역에 형광펜을 칠한다."""
    with 문서객체.세트파라미터("MarkPenShape", "HMarkpenShape") as 세트:
        세트.Color = units.rgb(*색)


def 형광펜지우기(문서객체: 문서) -> None:
    문서객체.실행("MarkPenClear")


def 서식초기화(문서객체: 문서) -> None:
    """글자·문단 서식을 기본으로 돌린다. (원본 '글자모양 초기화' 버튼 통합)"""
    문서객체.실행("CharShapeNormal")
    글자모양(문서객체, 장평=100, 자간=0)
    문단모양(문서객체, 정렬="양쪽", 줄간격=160, 위여백=0, 아래여백=0, 내어쓰기=0)


def 스타일적용(문서객체: 문서, 이름: str) -> None:
    """프리셋 스타일(제목/소제목/본문/각주 등)을 한 번에 적용한다."""
    정의 = 스타일목록().get(이름)
    if 정의 is None:
        raise 입력오류(f"없는 스타일: {이름}", f"쓸 수 있는 스타일: {', '.join(스타일목록())}")

    글자색 = 정의.get("글자색")
    글자모양(
        문서객체,
        폰트=정의.get("폰트"),
        크기=정의.get("크기"),
        진하게=정의.get("진하게"),
        글자색=tuple(글자색) if 글자색 else None,
        장평=정의.get("장평"),
        자간=정의.get("자간"),
    )
    문단모양(
        문서객체,
        정렬=정의.get("정렬"),
        줄간격=정의.get("줄간격"),
        위여백=정의.get("위여백"),
        아래여백=정의.get("아래여백"),
        왼쪽여백=정의.get("왼쪽여백"),
        내어쓰기=정의.get("내어쓰기"),
    )


def 글머리적용(문서객체: 문서, 이름: str) -> str:
    """글머리 프리셋의 서식을 적용하고 붙일 기호를 돌려준다.

    실제 기호 붙이기는 텍스트 변환(features/block.py)에서 처리한다.
    서식과 기호 정의를 한 곳(presets/styles.json)에 모아 두는 것이 요점이다.
    """
    정의 = 글머리목록().get(이름)
    if 정의 is None:
        raise 입력오류(f"없는 글머리: {이름}", f"쓸 수 있는 글머리: {', '.join(글머리목록())}")
    글자모양(
        문서객체,
        폰트=정의.get("폰트"),
        크기=정의.get("크기"),
        진하게=정의.get("진하게"),
    )
    문단모양(
        문서객체,
        줄간격=정의.get("줄간격", 160),
        내어쓰기=정의.get("내어쓰기"),
        위여백=정의.get("위여백"),
    )
    return 정의.get("기호", "")
