"""용지·여백·쪽번호·머리말/꼬리말.

원본은 `문서여백A4`, `문서여백B4`, `문서여백A4가로`, `문서여백새페이지` … 로
용지마다 함수를 따로 뒀다. 여기서는 `용지설정()` 하나에 프리셋을 얹었다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import units
from ..core.document import 문서
from ..core.errors import 입력오류

__all__ = ["여백", "여백프리셋", "용지설정", "쪽번호넣기", "쪽번호지우기", "머리말", "꼬리말", "본문너비"]


@dataclass(frozen=True)
class 여백:
    """용지 여백(mm)."""

    왼쪽: float = 20.0
    오른쪽: float = 20.0
    위: float = 15.0
    아래: float = 15.0
    머리: float = 10.0
    꼬리: float = 10.0


#: 자주 쓰는 여백 프리셋. (공문서 작성 기준을 기본값으로)
여백프리셋: dict[str, 여백] = {
    "공문기본": 여백(20, 20, 15, 15, 10, 10),
    "넓게": 여백(25, 25, 20, 20, 15, 15),
    "좁게": 여백(15, 15, 10, 10, 8, 8),
    "보고서": 여백(20, 20, 20, 15, 12, 10),
    "한장보고": 여백(15, 15, 12, 12, 8, 8),
}


def 용지설정(
    문서객체: 문서,
    용지: str = "A4",
    여백값: 여백 | str = "공문기본",
    적용범위: int = 3,
) -> None:
    """용지 크기와 여백을 설정한다.

    적용범위: 0=현재 구역, 2=문서 전체, 3=새 구역(원본 `문서여백` 기본값과 동일)
    """
    if 용지 not in units.용지:
        raise 입력오류(f"모르는 용지: {용지}", f"쓸 수 있는 용지: {', '.join(units.용지)}")
    설정 = 여백프리셋[여백값] if isinstance(여백값, str) else 여백값
    if isinstance(여백값, str) and 여백값 not in 여백프리셋:
        raise 입력오류(f"모르는 여백 프리셋: {여백값}")

    너비, 높이 = units.용지[용지]
    가로 = 용지.endswith("가로")

    with 문서객체.세트파라미터("PageSetup", "HSecDef") as 세트:
        쪽 = 세트.PageDef
        쪽.PaperWidth = units.mm(너비)
        쪽.PaperHeight = units.mm(높이)
        쪽.Landscape = 1 if 가로 else 0
        쪽.LeftMargin = units.mm(설정.왼쪽)
        쪽.RightMargin = units.mm(설정.오른쪽)
        쪽.TopMargin = units.mm(설정.위)
        쪽.BottomMargin = units.mm(설정.아래)
        쪽.HeaderLen = units.mm(설정.머리)
        쪽.FooterLen = units.mm(설정.꼬리)
        세트.HSet.SetItem("ApplyClass", 24)
        세트.HSet.SetItem("ApplyTo", 적용범위)


def 본문너비(문서객체: 문서, 용지: str = "A4") -> float:
    """현재 문서의 실제 본문 너비(mm)를 읽어온다.

    표 너비를 자동으로 맞출 때 쓴다. 원본은 함수마다 `205 - 문단여백측정()`,
    `196 - ...`, `161 - ...` 처럼 상수를 다르게 박아 두어 여백을 바꾸면 표가
    본문을 넘쳤다.
    """
    try:
        with 문서객체.파라미터("PageSetup") as 값:
            쪽 = 값.Item("PageDef")
            좌 = units.hwp단위_mm(쪽.Item("LeftMargin"))
            우 = units.hwp단위_mm(쪽.Item("RightMargin"))
            폭 = units.hwp단위_mm(쪽.Item("PaperWidth"))
        return round(max(폭 - 좌 - 우, 10.0), 1)
    except Exception:  # noqa: BLE001 - 읽기 실패하면 용지 기준으로 계산
        기본 = 여백프리셋["공문기본"]
        return units.본문너비(용지, 기본.왼쪽, 기본.오른쪽)


def 쪽번호넣기(문서객체: 문서, 위치: str = "가운데아래", 시작번호: int | None = None) -> None:
    """쪽번호를 넣는다."""
    자리 = {
        "왼쪽아래": 4,
        "가운데아래": 5,
        "오른쪽아래": 6,
        "왼쪽위": 1,
        "가운데위": 2,
        "오른쪽위": 3,
    }
    if 위치 not in 자리:
        raise 입력오류(f"모르는 쪽번호 위치: {위치}", f"가능: {', '.join(자리)}")
    with 문서객체.파라미터("PageNumPos") as 값:
        값.SetItem("DrawPos", 자리[위치])
    if 시작번호 is not None:
        with 문서객체.파라미터("PageNumberModify") as 값:
            값.SetItem("Number", 시작번호)


def 쪽번호지우기(문서객체: 문서) -> None:
    문서객체.실행("PageNumPosDelete")


def 머리말(문서객체: 문서, 내용: str, 정렬: str = "오른쪽") -> None:
    """머리말을 넣는다."""
    from .format import 문단모양

    문서객체.실행("HeaderFooter")  # 머리말/꼬리말 편집 상태로 들어간다
    문단모양(문서객체, 정렬=정렬)
    문서객체.문장입력(내용)
    문서객체.실행("CloseEx")


def 꼬리말(문서객체: 문서, 내용: str, 정렬: str = "가운데") -> None:
    """꼬리말을 넣는다."""
    from .format import 문단모양

    문서객체.실행("HeaderFooter")
    문단모양(문서객체, 정렬=정렬)
    문서객체.문장입력(내용)
    문서객체.실행("CloseEx")
