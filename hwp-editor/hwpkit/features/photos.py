"""사진 대장 만들기 — 폴더의 사진을 표에 격자로 배치한다.

출장·현장점검 보고서에서 손이 가장 많이 가는 작업이다. 원본에도 `사진표만들기`,
`비전표` 같은 함수가 있었지만 사진을 한 장씩 직접 넣어야 했고 캡션도 없었다.

여기서는 폴더를 지정하면
* 사진을 이름·촬영시각 순으로 모으고,
* 지정한 열 수로 격자 표를 만들어 셀 크기에 맞춰 넣고,
* 사진 아래 칸에 캡션(번호·파일명·날짜)을 채운다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..core.document import 문서
from ..core.errors import 입력오류

__all__ = ["사진", "사진모으기", "캡션만들기", "대장만들기", "지원확장자"]

지원확장자 = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp")


@dataclass(frozen=True)
class 사진:
    """넣을 사진 한 장."""

    경로: Path
    시각: datetime

    @property
    def 이름(self) -> str:
        return self.경로.stem


def 사진모으기(
    폴더: str | Path,
    정렬: str = "이름",
    하위폴더포함: bool = False,
    최대장수: int | None = None,
) -> list[사진]:
    """폴더에서 사진 파일을 모은다.

    정렬: 이름 | 날짜 (날짜는 파일 수정 시각 기준)
    """
    뿌리 = Path(폴더)
    if not 뿌리.is_dir():
        raise 입력오류(f"폴더가 없습니다: {뿌리}")

    대상 = 뿌리.rglob("*") if 하위폴더포함 else 뿌리.glob("*")
    모음: list[사진] = []
    for 파일 in 대상:
        if 파일.suffix.lower() not in 지원확장자 or 파일.name.startswith(("~", ".")):
            continue
        모음.append(사진(경로=파일, 시각=datetime.fromtimestamp(파일.stat().st_mtime)))

    if 정렬 == "날짜":
        모음.sort(key=lambda 하나: (하나.시각, _자연순(하나.경로.name)))
    elif 정렬 == "이름":
        모음.sort(key=lambda 하나: _자연순(하나.경로.name))
    else:
        raise 입력오류(f"모르는 정렬: {정렬}", "이름 또는 날짜 중에서 고르세요.")

    if not 모음:
        raise 입력오류(
            f"사진을 찾지 못했습니다: {뿌리}",
            f"쓸 수 있는 형식: {', '.join(지원확장자)}",
        )
    return 모음[:최대장수] if 최대장수 else 모음


def _자연순(이름: str):
    """사진1, 사진2, 사진10 순서가 뒤바뀌지 않게 숫자를 숫자로 비교한다."""
    return [
        int(조각) if 조각.isdigit() else 조각.lower()
        for 조각 in re.split(r"(\d+)", 이름)
    ]


def 캡션만들기(하나: 사진, 서식: str = "{번호}. {이름}", 번호: int = 1) -> str:
    """캡션 문구를 만든다. 쓸 수 있는 자리: {번호} {이름} {날짜} {시각} {파일명}"""
    return (
        (서식 or "{번호}")
        .replace("{번호}", str(번호))
        .replace("{이름}", 하나.이름)
        .replace("{파일명}", 하나.경로.name)
        .replace("{날짜}", 하나.시각.strftime("%Y. %m. %d."))
        .replace("{시각}", 하나.시각.strftime("%H:%M"))
    )


def 대장만들기(
    문서객체: 문서,
    사진들: list[사진],
    열수: int = 2,
    사진높이: float = 60.0,
    캡션서식: str = "{번호}. {이름}",
    표스타일: str = "기본",
) -> str:
    """사진 격자 표를 만들어 넣는다.

    표 구성: (사진 행, 캡션 행)을 사진 줄 수만큼 반복한다.
    """
    if not 사진들:
        raise 입력오류("넣을 사진이 없습니다.")
    if 열수 < 1:
        raise 입력오류("열 수는 1 이상이어야 합니다.")

    from . import table_ops
    from .format import 글자모양, 문단모양

    줄수 = (len(사진들) + 열수 - 1) // 열수
    행수 = 줄수 * 2  # 사진 행 + 캡션 행

    with 문서객체.한번에("사진 대장 만들기"), 문서객체.화면정지():
        table_ops.표만들기(문서객체, 열수=열수, 행수=행수, 행높이=사진높이 / 2)
        문서객체.이동하기("표처음셀")

        번호 = 0
        for 줄 in range(줄수):
            이번줄 = 사진들[줄 * 열수 : (줄 + 1) * 열수]

            # 사진 행
            for 자리 in range(열수):
                if 자리 < len(이번줄):
                    문서객체.셀선택()
                    문서객체.사진넣기(str(이번줄[자리].경로))
                if not (줄 == 줄수 - 1 and 자리 == 열수 - 1 and 행수 == 1):
                    문서객체.실행("TableRightCell")

            # 캡션 행
            for 자리 in range(열수):
                if 자리 < len(이번줄):
                    번호 += 1
                    문단모양(문서객체, 정렬="가운데")
                    글자모양(문서객체, 크기=10)
                    문서객체.셀텍스트쓰기(
                        캡션만들기(이번줄[자리], 캡션서식, 번호)
                    )
                마지막칸 = 줄 == 줄수 - 1 and 자리 == 열수 - 1
                if not 마지막칸:
                    문서객체.실행("TableRightCell")

        table_ops.표스타일적용(문서객체, 표스타일, 머리글있음=False)
        문서객체.실행("Cancel")
        문서객체.실행("CloseEx")
        문서객체.실행("MoveLineEnd")

    return f"사진 {len(사진들)}장을 {열수}열 대장으로 넣었습니다."
