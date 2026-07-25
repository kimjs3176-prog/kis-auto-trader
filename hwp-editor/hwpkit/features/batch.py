"""폴더 일괄 처리 — 원본에 없던, 실무에서 가장 아쉬웠던 기능.

원본 `전체편집창` 은 열려 있는 문서 하나에 '문단 스타일 제거 / 표 스타일 제거'
두 가지만 할 수 있었다. 여기서는 폴더 안 모든 한/글 문서에

* 찾아바꾸기(규칙 여러 개, 정규식 가능)
* 서식 정리
* 필드 채우기
* PDF 변환

를 한 번에 적용하고, 무엇이 성공/실패했는지 보고서를 돌려준다.
`미리보기=True` 로 두면 **파일을 고치지 않고** 무엇이 바뀔지만 알려준다.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from ..core.document import 문서
from ..core.errors import 입력오류
from ..text.transform import 규칙적용, 찾아바꾸기규칙

__all__ = ["일괄작업", "일괄결과", "파일찾기", "일괄실행"]

_확장자 = (".hwp", ".hwpx")


@dataclass
class 일괄작업:
    """일괄로 무엇을 할지 정한다."""

    바꾸기규칙: Sequence[찾아바꾸기규칙] = ()
    필드값: dict[str, str] = field(default_factory=dict)
    서식정리: bool = False
    PDF변환: bool = False
    저장: bool = True
    #: 결과를 원본 대신 이 폴더에 쓴다. (원본 보존)
    출력폴더: str | None = None

    @property
    def 할일없음(self) -> bool:
        return not (self.바꾸기규칙 or self.필드값 or self.서식정리 or self.PDF변환)


@dataclass
class 파일결과:
    경로: Path
    성공: bool = True
    바뀐건: int = 0
    메모: str = ""


@dataclass
class 일괄결과:
    작업수: int = 0
    파일들: list[파일결과] = field(default_factory=list)

    @property
    def 성공수(self) -> int:
        return sum(1 for 하나 in self.파일들 if 하나.성공)

    @property
    def 실패수(self) -> int:
        return sum(1 for 하나 in self.파일들 if not 하나.성공)

    @property
    def 문구(self) -> str:
        말 = f"{len(self.파일들)}개 파일 중 {self.성공수}개 처리"
        if self.실패수:
            말 += f", {self.실패수}개 실패"
        return 말

    def 보고서(self) -> str:
        줄들 = [self.문구, ""]
        for 하나 in self.파일들:
            표시 = "○" if 하나.성공 else "×"
            줄들.append(f"{표시} {하나.경로.name} {하나.메모}".rstrip())
        return "\n".join(줄들)


def 파일찾기(
    폴더: str | Path, 하위폴더포함: bool = True, 이름패턴: str = "*"
) -> list[Path]:
    """폴더에서 한/글 문서를 찾는다. 임시파일(~$)은 건너뛴다."""
    뿌리 = Path(폴더)
    if not 뿌리.is_dir():
        raise 입력오류(f"폴더가 없습니다: {뿌리}")
    대상 = 뿌리.rglob("*") if 하위폴더포함 else 뿌리.glob("*")
    결과 = [
        파일
        for 파일 in sorted(대상)
        if 파일.suffix.lower() in _확장자
        and not 파일.name.startswith(("~", "."))
        and fnmatch.fnmatch(파일.name, 이름패턴)
    ]
    return 결과


def 일괄실행(
    문서객체: 문서,
    폴더: str | Path,
    작업: 일괄작업,
    하위폴더포함: bool = True,
    이름패턴: str = "*",
    미리보기: bool = False,
    진행알림: Callable[[int, int, Path], None] | None = None,
) -> 일괄결과:
    """폴더의 모든 문서에 작업을 적용한다."""
    if 작업.할일없음:
        raise 입력오류("할 작업을 하나 이상 골라 주세요.")

    파일들 = 파일찾기(폴더, 하위폴더포함, 이름패턴)
    if not 파일들:
        raise 입력오류(f"처리할 한/글 문서가 없습니다: {폴더}")

    결과 = 일괄결과(작업수=len(파일들))
    출력 = Path(작업.출력폴더) if 작업.출력폴더 else None
    if 출력:
        출력.mkdir(parents=True, exist_ok=True)

    문서객체.연결.보이기(False)
    try:
        for 순번, 파일 in enumerate(파일들, start=1):
            if 진행알림:
                진행알림(순번, len(파일들), 파일)
            하나 = 파일결과(경로=파일)
            try:
                문서객체.열기(str(파일), 읽기전용=미리보기)
                하나.바뀐건 = _한파일처리(문서객체, 작업, 파일, 출력, 미리보기)
                하나.메모 = (
                    f"(미리보기) 바뀔 곳 {하나.바뀐건}군데"
                    if 미리보기
                    else f"{하나.바뀐건}건 처리"
                )
            except Exception as 오류:  # noqa: BLE001
                하나.성공 = False
                하나.메모 = f"실패: {오류}"
            finally:
                문서객체.문서닫기(저장=False)
            결과.파일들.append(하나)
    finally:
        문서객체.연결.보이기(True)
    return 결과


def _한파일처리(
    문서객체: 문서,
    작업: 일괄작업,
    파일: Path,
    출력: Path | None,
    미리보기: bool,
) -> int:
    from .cleanup import 서식정리
    from .find_replace import 문서전체바꾸기

    바뀐건 = 0

    if 작업.바꾸기규칙:
        if 미리보기:
            원문 = 문서객체.전체텍스트()
            바뀐 = 규칙적용(원문, list(작업.바꾸기규칙))
            바뀐건 += 0 if 바뀐 == 원문 else _다른줄수(원문, 바뀐)
        else:
            문서전체바꾸기(문서객체, list(작업.바꾸기규칙))
            바뀐건 += len(작업.바꾸기규칙)

    if 미리보기:
        return 바뀐건

    if 작업.필드값:
        바뀐건 += 문서객체.필드채우기(작업.필드값)
    if 작업.서식정리:
        서식정리(문서객체)
        바뀐건 += 1

    if 작업.저장:
        # 출력폴더를 주면 원본을 그대로 두고 사본에 결과를 쓴다.
        대상 = (출력 / 파일.name) if 출력 else 파일
        문서객체.다른이름저장(str(대상), "HWPX" if 대상.suffix.lower() == ".hwpx" else "HWP")
    if 작업.PDF변환:
        대상 = (출력 or 파일.parent) / (파일.stem + ".pdf")
        문서객체.PDF저장(str(대상))
        바뀐건 += 1
    return 바뀐건


def _다른줄수(원문: str, 바뀐: str) -> int:
    """미리보기용 — 몇 줄이 달라지는지 센다."""
    앞 = 원문.splitlines()
    뒤 = 바뀐.splitlines()
    차이 = sum(1 for 하나, 둘 in zip(앞, 뒤) if 하나 != 둘)
    return 차이 + abs(len(앞) - len(뒤))
