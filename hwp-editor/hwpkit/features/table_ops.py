"""표 기능 — 만들기·서식·셀 편집·대량 계산.

원본에서 가장 중복이 심했던 영역이다.
`경남기본표`, `남해심플표`, `서울심플표`, `용인기본표`, `서교공3단표`, `5단표`,
`기본서식표`, `퍼센트표`, `차트표` … 표 생성 함수가 40개가 넘었고 내용은 거의 같았다.
이것을 `표만들기(열 수, 행 수, 스타일)` + `표스타일` 프리셋(presets/table_styles.json)
으로 합쳤다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..core import units
from ..core.document import 문서
from ..core.errors import 상태오류, 입력오류
from ..text import calc, transform
from ..text.numbers import 실수읽기

__all__ = [
    "표스타일목록",
    "표만들기",
    "표스타일적용",
    "테두리",
    "셀배경",
    "셀앞뒤붙임",
    "셀변환",
    "대량계산",
    "합계넣기",
    "셀너비자동",
    "제목행반복",
    "표를문장으로",
    "문장을표로",
]

_프리셋 = Path(__file__).resolve().parent.parent / "presets" / "table_styles.json"

_테두리종류 = {"없음": 0, "실선": 1, "점선": 3, "이중": 8}
_위치키 = {"상": "Top", "하": "Bottom", "좌": "Left", "우": "Right"}


@lru_cache(maxsize=1)
def 표스타일목록() -> dict[str, dict]:
    """이름 → 표 스타일 정의."""
    return json.loads(_프리셋.read_text(encoding="utf-8")).get("스타일", {})


# ------------------------------------------------------------------ 표 만들기
def 표만들기(
    문서객체: 문서,
    열수: int,
    행수: int,
    너비목록: list[float] | None = None,
    행높이: float = 8.0,
    전체너비: float | None = None,
    글자처럼: bool = True,
) -> None:
    """표를 만든다. 너비를 주지 않으면 본문 너비를 열 수로 균등 분할한다."""
    if 열수 < 1 or 행수 < 1:
        raise 입력오류("행과 열은 1 이상이어야 합니다.")

    from .page import 본문너비

    if 너비목록:
        if len(너비목록) != 열수:
            raise 입력오류(f"너비 목록은 {열수}개여야 합니다.")
        너비들 = list(너비목록)
    else:
        전체 = 전체너비 or 본문너비(문서객체)
        칸 = round(전체 / 열수, 1)
        너비들 = [칸] * 열수

    with 문서객체.한번에("표 만들기"):
        with 문서객체.세트파라미터("TableCreate", "HTableCreation") as 세트:
            세트.Rows = 행수
            세트.Cols = 열수
            세트.WidthType = 2  # 칸 너비를 직접 지정
            세트.HeightType = 1  # 줄 높이를 직접 지정
            세트.CreateItemArray("ColWidth", 열수)
            for 번호, 너비 in enumerate(너비들):
                세트.ColWidth.SetItem(번호, units.mm(너비))
            세트.CreateItemArray("RowHeight", 행수)
            for 번호 in range(행수):
                세트.RowHeight.SetItem(번호, units.mm(행높이))
            세트.TableProperties.TreatAsChar = 1 if 글자처럼 else 0


def 표스타일적용(문서객체: 문서, 이름: str, 머리글있음: bool = True) -> None:
    """선택한 표(또는 커서가 있는 표)에 스타일 프리셋을 적용한다."""
    정의 = 표스타일목록().get(이름)
    if 정의 is None:
        raise 입력오류(
            f"없는 표 스타일: {이름}", f"쓸 수 있는 스타일: {', '.join(표스타일목록())}"
        )
    문서객체.표확인()

    from .format import 글자모양, 문단모양

    with 문서객체.한번에(f"표 스타일 {이름}"):
        # 1) 표 전체
        문서객체.실행("Cancel")
        문서객체.실행("TableCellBlock")
        문서객체.실행("TableCellBlockExtend")
        문서객체.실행("TableCellBlockExtend")
        글자모양(
            문서객체,
            폰트=정의.get("폰트"),
            크기=정의.get("크기"),
        )
        문단모양(문서객체, 정렬=정의.get("정렬", "가운데"), 줄간격=정의.get("줄간격", 150))
        바깥 = 정의.get("바깥테두리", {})
        테두리(
            문서객체,
            굵기=바깥.get("굵기", 4),
            종류=바깥.get("종류", "실선"),
            색=tuple(바깥.get("색", (0, 0, 0))),
        )
        안쪽 = 정의.get("안쪽선", {})
        내부선(
            문서객체,
            가로=_테두리종류.get(안쪽.get("가로", "실선"), 1),
            세로=_테두리종류.get(안쪽.get("세로", "실선"), 1),
            굵기=안쪽.get("굵기", 1),
        )
        배경 = 정의.get("배경")
        if 배경:
            셀배경(문서객체, tuple(배경))

        # 2) 머리글 행
        머리 = 정의.get("머리글", {})
        if 머리글있음 and 머리:
            문서객체.실행("Cancel")
            문서객체.이동하기("표처음셀")
            문서객체.이동하기("셀처음")
            문서객체.실행("TableCellBlock")
            문서객체.실행("TableCellBlockExtend")
            문서객체.실행("TableColEnd")
            if 머리.get("배경"):
                셀배경(문서객체, tuple(머리["배경"]))
            글자모양(
                문서객체,
                진하게=머리.get("진하게", True),
                글자색=tuple(머리["글자색"]) if 머리.get("글자색") else None,
            )
            아래선 = 머리.get("아래선")
            if 아래선:
                한줄테두리(문서객체, "하", 아래선.get("굵기", 4), 아래선.get("종류", "실선"))
        문서객체.취소()


# ------------------------------------------------------------------- 테두리
def 테두리(
    문서객체: 문서,
    굵기: int = 1,
    종류: str = "실선",
    색: tuple[int, int, int] = (0, 0, 0),
    위치: str = "상하좌우",
) -> None:
    """선택한 셀의 바깥 테두리를 설정한다."""
    if 종류 not in _테두리종류:
        raise 입력오류(f"모르는 선 종류: {종류}", f"가능: {', '.join(_테두리종류)}")
    문서객체.표확인()
    with 문서객체.파라미터("CellBorderFill") as 값:
        for 한글자, 영문 in _위치키.items():
            if 한글자 in 위치:
                값.SetItem(f"BorderWidth{영문}", 굵기)
                값.SetItem(f"BorderType{영문}", _테두리종류[종류])
                값.SetItem(f"BorderColor{영문}", units.rgb(*색))


def 한줄테두리(문서객체: 문서, 위치: str, 굵기: int = 1, 종류: str = "실선") -> None:
    """한쪽 테두리만 바꾼다. (원본 `표테두리단일선` 통합)"""
    테두리(문서객체, 굵기=굵기, 종류=종류, 위치=위치)


def 내부선(문서객체: 문서, 가로: int = 1, 세로: int = 1, 굵기: int = 1) -> None:
    """표 안쪽 가로·세로선을 설정한다."""
    with 문서객체.파라미터("CellBorderFill") as 값:
        값.SetItem("TypeHorz", 가로)
        값.SetItem("TypeVert", 세로)
        값.SetItem("WidthHorz", 굵기)
        값.SetItem("WidthVert", 굵기)


def 셀배경(문서객체: 문서, 색: tuple[int, int, int]) -> None:
    """선택한 셀 배경색을 칠한다."""
    문서객체.표확인()
    with 문서객체.세트파라미터("CellFill", "HCellBorderFill") as 세트:
        채움 = 세트.FillAttr
        채움.type = 문서객체.한글.BrushType("NullBrush|WinBrush")
        채움.WinBrushFaceColor = units.rgb(*색)
        채움.WinBrushHatchColor = units.rgb(*색)
        채움.WinBrushFaceStyle = 문서객체.한글.HatchStyle("None")
        채움.WindowsBrush = 1


def 셀배경지우기(문서객체: 문서) -> None:
    with 문서객체.세트파라미터("CellFill", "HCellBorderFill") as 세트:
        세트.FillAttr.type = 문서객체.한글.BrushType("NullBrush")


# --------------------------------------------------------------- 셀 편집
def 셀앞뒤붙임(문서객체: 문서, 앞: str = "", 뒤: str = "", 지울글자수: int = 0) -> int:
    """선택한 셀들의 값 앞뒤에 문자열을 붙인다. 바꾼 셀 수를 돌려준다."""
    범위 = 문서객체.셀블록범위()
    바뀐 = 0
    with 문서객체.한번에("셀 앞뒤 붙임"), 문서객체.화면정지():
        for _목록 in 문서객체.셀순회(범위):
            원문 = 문서객체.셀텍스트().strip()
            if not 원문:
                continue
            값 = 원문[지울글자수:] if 지울글자수 else 원문
            새값 = f"{앞}{값}{뒤}"
            if 새값 != 원문:
                문서객체.셀텍스트쓰기(새값)
                바뀐 += 1
    문서객체.취소()
    return 바뀐


def 셀변환(문서객체: 문서, 변환이름: str) -> int:
    """선택한 셀들에 `한줄변환`(콤마·금액·날짜·나이 등)을 적용한다."""
    변환 = transform.한줄변환.get(변환이름)
    if 변환 is None:
        raise 입력오류(
            f"모르는 변환: {변환이름}", f"쓸 수 있는 변환: {', '.join(transform.한줄변환)}"
        )
    범위 = 문서객체.셀블록범위()
    바뀐 = 0
    with 문서객체.한번에(f"셀 {변환이름}"), 문서객체.화면정지():
        for _목록 in 문서객체.셀순회(범위):
            원문 = 문서객체.셀텍스트().strip()
            if not 원문:
                continue
            새값 = 변환(원문)
            if 새값 != 원문:
                문서객체.셀텍스트쓰기(새값)
                바뀐 += 1
    문서객체.취소()
    return 바뀐


def 대량계산(문서객체: 문서, 수식: str, 자리수: int = 0, 콤마: bool = True) -> int:
    """선택한 셀마다 수식을 계산해 값을 채운다.

    수식에서 `값` 은 그 셀의 현재 숫자를 뜻한다. 예)
      * `값 * 1.1`      → 10% 인상
      * `값 / 1000`     → 천원 단위로
      * `값 * 0.7`      → 국비 70%

    원본 `표대량계산창` 은 셀 순서를 목록 번호로 직접 계산해 병합된 셀이 있으면
    엉뚱한 칸에 값을 썼다. 여기서는 셀을 하나씩 실제로 이동하며 처리한다.
    """
    if "값" not in 수식:
        raise 입력오류("수식에 '값' 을 넣어야 합니다.", "예: 값 * 1.1")
    범위 = 문서객체.셀블록범위()
    바뀐 = 0
    with 문서객체.한번에("표 대량 계산"), 문서객체.화면정지():
        for _목록 in 문서객체.셀순회(범위):
            원문 = 문서객체.셀텍스트().strip()
            숫자 = 실수읽기(원문)
            if 숫자 is None:
                continue
            결과 = calc.수식계산(수식.replace("값", str(숫자)), 자리수)
            문서객체.셀텍스트쓰기(calc.수표기(결과, 콤마))
            바뀐 += 1
    문서객체.취소()
    return 바뀐


def 합계넣기(문서객체: 문서, 방식: str = "합계") -> None:
    """선택한 셀 범위의 합계·평균을 한/글 표 계산식으로 넣는다."""
    식 = {"합계": "SUM", "평균": "AVERAGE", "최대": "MAX", "최소": "MIN"}
    if 방식 not in 식:
        raise 입력오류(f"모르는 계산: {방식}", f"가능: {', '.join(식)}")
    범위 = 문서객체.셀블록범위()
    시작 = 범위.시작.이름
    끝 = 범위.끝.이름
    with 문서객체.파라미터("TableFormula") as 값:
        값.SetItem("Command", f"={식[방식]}({시작}:{끝})??%g;;")


def 셀너비자동(문서객체: 문서) -> None:
    """내용에 맞게 셀 너비를 조절한다."""
    문서객체.표확인()
    문서객체.실행("TableCellWidthAuto")


def 제목행반복(문서객체: 문서) -> None:
    """표가 여러 쪽으로 넘어갈 때 첫 행을 반복한다."""
    문서객체.표확인()
    with 문서객체.파라미터("TablePropertyDialog") as 값:
        값.SetItem("ShapeType", 3)
        값.SetItem("RepeatHeader", 1)
        값.SetItem("PageBreak", 1)
        셀 = 값.CreateItemSet("ShapeTableCell", "Cell")
        셀.SetItem("Header", 1)


def 셀여백(문서객체: 문서, 상: float = 0, 하: float = 0, 좌: float = 0, 우: float = 0) -> None:
    """셀 안쪽 여백(mm)을 지정한다."""
    문서객체.표확인()
    with 문서객체.파라미터("TablePropertyDialog") as 값:
        값.SetItem("ShapeType", 3)
        값.SetItem("ShapeCellSize", 0)
        값.SetItem("CellMarginTop", units.mm(상))
        값.SetItem("CellMarginBottom", units.mm(하))
        값.SetItem("CellMarginLeft", units.mm(좌))
        값.SetItem("CellMarginRight", units.mm(우))


def 표를문장으로(문서객체: 문서, 구분: str = " | ") -> None:
    """표를 문장으로 푼다."""
    문서객체.표확인()
    with 문서객체.파라미터("TableTableToString") as 값:
        값.SetItem("DelimiterType", 3)  # 사용자 지정
        값.SetItem("UserDefine", 구분)


def 문장을표로(문서객체: 문서, 구분: str = "자동", 스타일: str = "기본") -> None:
    """선택한 텍스트를 표로 만든다. (원본에 없던 방향 — 붙여넣은 자료 정리에 쓴다)"""
    원문 = 문서객체.선택텍스트()
    행들 = transform.문장표화(원문, 구분)
    if not 행들:
        raise 상태오류("표로 만들 내용이 없습니다.")
    열수 = max(len(행) for 행 in 행들)

    with 문서객체.한번에("문장을 표로"):
        문서객체.문장입력("")  # 선택 영역 삭제
        표만들기(문서객체, 열수=열수, 행수=len(행들))
        문서객체.이동하기("표처음셀")
        for 행번호, 행 in enumerate(행들):
            for 열번호 in range(열수):
                값 = 행[열번호] if 열번호 < len(행) else ""
                문서객체.셀텍스트쓰기(값)
                if not (행번호 == len(행들) - 1 and 열번호 == 열수 - 1):
                    문서객체.실행("TableRightCell")
        if 스타일:
            표스타일적용(문서객체, 스타일)
