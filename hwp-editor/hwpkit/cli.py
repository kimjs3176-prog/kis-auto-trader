"""명령줄 인터페이스 — 자동화·예약 실행용.

원본은 GUI 로만 쓸 수 있어서, 매달 반복되는 일(폴더 PDF 변환, 부서명 일괄 수정,
메일머지)을 사람이 앉아서 눌러야 했다. 같은 명령 표를 CLI 에서도 쓴다.

    python -m hwpkit                      # 화면 띄우기
    python -m hwpkit 목록                  # 기능 목록
    python -m hwpkit 목록 --분류 표
    python -m hwpkit 도움 표.대량계산
    python -m hwpkit 실행 도구.날짜변환 날짜=2025-3-9 서식=공문 넣기=0
    python -m hwpkit 실행 일괄.PDF 폴더=C:\\보고서 하위폴더=1

한글 입력이 깨지는 콘솔에서는 영문 별칭을 쓸 수 있다.
    hwpkit list / help <번호> / run <번호> 이름=값 / gui / check
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import commands
from .core.connection import 사용가능, 한글연결
from .core.document import 문서
from .core.errors import 한글오류

__all__ = ["주실행"]


def _출력글자표맞추기() -> None:
    """콘솔 글자표가 한글을 표현하지 못해도 죽지 않게 한다.

    영문 윈도우(cp1252)나 일부 cmd 설정에서는 한글을 출력하는 순간
    UnicodeEncodeError 로 프로그램이 끝나 버린다. UTF-8 로 바꾸고, 그래도 표현할 수
    없는 글자는 물음표로 대체한다.
    """
    for 흐름 in (sys.stdout, sys.stderr):
        재설정 = getattr(흐름, "reconfigure", None)
        if 재설정 is None:
            continue
        try:
            재설정(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - 재설정 불가한 흐름
            pass


def _인자만들기() -> argparse.ArgumentParser:
    바탕 = argparse.ArgumentParser(
        prog="hwpkit",
        description="한글 문서 도우미 — 한/글 문서 작업 자동화",
    )
    바탕.add_argument("--자세히", action="store_true", help="자세한 기록 보기")
    하위 = 바탕.add_subparsers(dest="명령어")

    # 콘솔 글자표(코드페이지)에 따라 한글 인자가 깨지는 환경이 있어 영문 별칭도 받는다.
    목록 = 하위.add_parser("목록", aliases=["list"], help="기능 목록 보기")
    목록.add_argument("--분류", default=None, help=f"분류: {', '.join(commands.분류순서)}")
    목록.add_argument("--찾기", default=None, help="낱말로 걸러 보기")

    도움 = 하위.add_parser("도움", aliases=["help"], help="기능 하나의 사용법 보기")
    도움.add_argument("번호", help="기능 번호 (예: 표.대량계산)")

    실행 = 하위.add_parser("실행", aliases=["run"], help="기능 실행")
    실행.add_argument("번호", help="기능 번호")
    실행.add_argument("값", nargs="*", help="이름=값 형태의 입력")

    하위.add_parser("화면", aliases=["gui"], help="화면(UI) 띄우기")
    하위.add_parser("점검", aliases=["check"], help="실행 환경·한글 연결 점검")
    return 바탕


def _값파싱(조각들: list[str]) -> dict[str, str]:
    값들: dict[str, str] = {}
    for 조각 in 조각들:
        if "=" not in 조각:
            raise SystemExit(f"입력은 '이름=값' 형태로 주세요: {조각}")
        이름, 값 = 조각.split("=", 1)
        값들[이름.strip()] = 값
    return 값들


def _목록보이기(분류: str | None, 찾기: str | None) -> int:
    후보 = commands.검색(찾기, 최대=500) if 찾기 else commands.전체명령()
    if 분류:
        후보 = [하나 for 하나 in 후보 if 하나.분류 == 분류]
    if not 후보:
        print("해당하는 기능이 없습니다.")
        return 1
    현재분류 = None
    for 하나 in sorted(후보, key=lambda 명: (commands.분류순서.index(명.분류), 명.제목)):
        if 하나.분류 != 현재분류:
            현재분류 = 하나.분류
            print(f"\n[{현재분류}]")
        표시 = f"  {하나.번호:22s} {하나.제목}"
        if 하나.필요:
            표시 += f"  ({'·'.join(하나.필요)} 필요)"
        print(표시)
    print(f"\n모두 {len(후보)}개")
    return 0


def _도움보이기(번호: str) -> int:
    하나 = commands.찾기(번호)
    print(f"{하나.번호}  {하나.제목}  [{하나.분류}]")
    if 하나.설명:
        print(f"\n{하나.설명}")
    if 하나.필요:
        print(f"\n먼저 준비: {', '.join(하나.필요)}")
    if 하나.입력:
        print("\n입력")
        for 항목 in 하나.입력:
            기본 = f" (기본값: {항목.기본값})" if 항목.기본값 != "" else ""
            선택 = f" [{', '.join(항목.선택지)}]" if 항목.선택지 else ""
            print(f"  {항목.이름:12s} {항목.표시}{선택}{기본}")
            if 항목.설명:
                print(f"               {항목.설명}")
        보기 = " ".join(f"{항목.이름}=…" for 항목 in 하나.입력)
        print(f"\n예) python -m hwpkit 실행 {하나.번호} {보기}")
    else:
        print(f"\n예) python -m hwpkit 실행 {하나.번호}")
    return 0


def _점검() -> int:
    from .core.connection import 진단

    print(진단())
    가능, _이유 = 사용가능()
    if not 가능:
        return 1
    try:
        연결 = 한글연결()
        연결.연결()
        print()
        print(f"결론: 연결 성공 (한/글 {연결.버전})")
        print(f"  새로 띄움: {'예' if 연결.새로띄움 else '아니오(실행 중인 창에 연결)'}")
        return 0
    except 한글오류 as 오류:
        print()
        print(f"결론: 연결 실패 — {오류.메시지}")
        if 오류.도움말:
            print(오류.도움말)
        return 1


def _실행하기(번호: str, 값들: dict[str, str]) -> int:
    하나 = commands.찾기(번호)
    문서객체 = 문서(한글연결())
    맥락값 = commands.맥락(
        문서객체=문서객체, 값=값들, 알림=lambda 말: print(f"  … {말}")
    )
    try:
        결과 = 하나.실행(맥락값)
    except 한글오류 as 오류:
        print(f"[안내] {오류.메시지}")
        if 오류.도움말:
            print(오류.도움말)
        return 1
    print(결과 if isinstance(결과, str) else f"{하나.제목} 완료")
    return 0


def 주실행(인자들: list[str] | None = None) -> int:
    _출력글자표맞추기()
    바탕 = _인자만들기()
    설정 = 바탕.parse_args(인자들)
    logging.basicConfig(
        level=logging.DEBUG if 설정.자세히 else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    별칭 = {"list": "목록", "help": "도움", "run": "실행", "gui": "화면", "check": "점검"}
    명령어 = 별칭.get(설정.명령어, 설정.명령어)
    if 명령어 in (None, "화면"):
        from .ui.app import 실행하기

        실행하기()
        return 0
    if 명령어 == "목록":
        return _목록보이기(설정.분류, 설정.찾기)
    if 명령어 == "도움":
        return _도움보이기(설정.번호)
    if 명령어 == "점검":
        return _점검()
    if 명령어 == "실행":
        return _실행하기(설정.번호, _값파싱(설정.값))
    바탕.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(주실행())
