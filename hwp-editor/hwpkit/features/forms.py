"""사용자 양식(.hwp/.hwpx) 관리.

기관별로 코드에 박아 넣었던 서식은 전부 없앴다. 대신 **쓰는 사람이 자기 기관·
회사 양식 파일을 등록**해 쓰는 구조로 바꿨다. 새 양식을 추가할 때 코드를 고치지
않아도 된다.

양식 폴더 (앞에 있는 것을 먼저 찾는다)
  1. 환경변수 `HWPKIT_FORMS` 로 지정한 폴더
  2. `%USERPROFILE%\\.hwpkit\\forms`  (개인 양식)
  3. 패키지 안 `presets/forms`        (기본 제공)

양식에 누름틀(필드)을 심어 두면 `필드채우기` 로 값이 자동으로 들어간다.
필드가 없으면 `{{제목}}` 같은 자리표시자를 찾아바꾸기로 채운다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..core.document import 문서
from ..core.errors import 입력오류
from ..text.transform import 찾아바꾸기규칙

__all__ = ["양식", "양식폴더들", "양식목록", "양식찾기", "양식열기", "양식채우기", "개인양식폴더"]

_확장자 = (".hwp", ".hwpx", ".hwt")
_자리표시자 = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


@dataclass(frozen=True)
class 양식:
    """등록된 양식 하나."""

    이름: str
    경로: Path
    출처: str  # '개인' | '기본' | '지정폴더'

    @property
    def 설명(self) -> str:
        return f"{self.이름} ({self.출처})"


def 개인양식폴더() -> Path:
    """개인 양식 폴더 경로. 없으면 만든다."""
    뿌리 = Path(os.environ.get("USERPROFILE") or Path.home())
    폴더 = 뿌리 / ".hwpkit" / "forms"
    폴더.mkdir(parents=True, exist_ok=True)
    return 폴더


def 양식폴더들() -> list[tuple[Path, str]]:
    """찾을 폴더 목록을 우선순위대로 돌려준다."""
    목록: list[tuple[Path, str]] = []
    지정 = os.environ.get("HWPKIT_FORMS")
    if 지정:
        for 조각 in 지정.split(os.pathsep):
            if 조각.strip():
                목록.append((Path(조각.strip()), "지정폴더"))
    목록.append((개인양식폴더(), "개인"))
    목록.append((Path(__file__).resolve().parent.parent / "presets" / "forms", "기본"))
    return 목록


def 양식목록() -> list[양식]:
    """쓸 수 있는 양식을 모두 모은다. 같은 이름은 앞 폴더가 이긴다."""
    결과: list[양식] = []
    본이름: set[str] = set()
    for 폴더, 출처 in 양식폴더들():
        if not 폴더.is_dir():
            continue
        for 파일 in sorted(폴더.rglob("*")):
            if 파일.suffix.lower() not in _확장자 or 파일.name.startswith("~"):
                continue
            if 파일.stem in 본이름:
                continue
            본이름.add(파일.stem)
            결과.append(양식(이름=파일.stem, 경로=파일, 출처=출처))
    return 결과


def 양식찾기(이름: str) -> 양식:
    """이름으로 양식을 찾는다."""
    후보 = [양 for 양 in 양식목록() if 양.이름 == 이름]
    if not 후보:
        가능 = ", ".join(양.이름 for 양 in 양식목록()) or "(등록된 양식 없음)"
        raise 입력오류(
            f"'{이름}' 양식을 찾을 수 없습니다.",
            f"양식 폴더에 파일을 넣으세요: {개인양식폴더()}\n등록된 양식: {가능}",
        )
    return 후보[0]


def 양식열기(문서객체: 문서, 이름: str) -> Path:
    """양식을 새 문서로 연다. (원본을 덮어쓰지 않도록 읽기 후 사본으로 다룬다)"""
    대상 = 양식찾기(이름)
    문서객체.열기(str(대상.경로))
    return 대상.경로


def 자리표시자목록(문서객체: 문서) -> list[str]:
    """양식에서 채워야 할 항목 이름을 모은다.

    누름틀(필드)이 있으면 그것을, 없으면 본문의 `{{이름}}` 자리표시자를 쓴다.
    """
    필드 = 문서객체.필드목록()
    if 필드:
        return 필드
    본문 = 문서객체.전체텍스트()
    이름들: list[str] = []
    for m in _자리표시자.finditer(본문):
        이름 = m.group(1).strip()
        if 이름 and 이름 not in 이름들:
            이름들.append(이름)
    return 이름들


def 양식채우기(문서객체: 문서, 값들: dict[str, str]) -> int:
    """열려 있는 양식에 값을 채운다. 채운 항목 수를 돌려준다.

    누름틀이 있으면 필드로 채우고, 없으면 `{{이름}}` 을 찾아 바꾼다.
    """
    if not 값들:
        raise 입력오류("채울 값이 없습니다.")

    필드 = set(문서객체.필드목록())
    필드값 = {이름: 값 for 이름, 값 in 값들.items() if 이름 in 필드}
    남은 = {이름: 값 for 이름, 값 in 값들.items() if 이름 not in 필드}

    채움 = 문서객체.필드채우기(필드값) if 필드값 else 0

    if 남은:
        from .find_replace import 문서전체바꾸기

        규칙들 = [
            찾아바꾸기규칙(찾기=f"{{{{{이름}}}}}", 바꾸기="" if 값 is None else str(값))
            for 이름, 값 in 남은.items()
        ]
        문서전체바꾸기(문서객체, 규칙들)
        채움 += len(규칙들)
    return 채움
