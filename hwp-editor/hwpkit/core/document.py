"""문서 조작 계층 — 한/글 COM 을 다루는 얇고 안전한 창구.

원본은 `기본한컴` 한 클래스에 871개 메서드가 섞여 있었다(연결·글자모양·표·
기관별 서식이 모두 한 파일). 여기서는 다음만 담당한다.

* 액션 실행과 파라미터셋 처리 (반복 코드 제거)
* 선택 영역 읽기/쓰기, 커서 위치 저장·복원
* 표 안에서의 위치·범위 파악
* 파일 열기/저장/PDF 내보내기
* **작업 묶음(트랜잭션)** — 도중에 실패하면 되돌리기를 시도한다

서식·기능은 이 계층 위에 `features/` 로 올린다.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from . import units
from .connection import 한글연결
from .errors import 상태오류, 입력오류

__all__ = ["문서", "셀주소", "셀범위"]

로그 = logging.getLogger(__name__)

#: 한/글 MovePos 이동 코드 (원본이 쓰던 값과 같다)
이동 = {
    "문서처음": 2,
    "문서끝": 3,
    "문단처음": 6,
    "문단끝": 7,
    "표처음셀": 106,
    "셀처음": 104,
    "셀끝": 105,
    "표끝셀": 107,
    "스캔시작": 201,
}

#: 되돌리기를 한 번에 몇 번까지 시도할지 (무한 되돌리기 방지)
_되돌리기한계 = 300


@dataclass(frozen=True)
class 셀주소:
    """표 안의 셀 위치. (A1 → 열=1, 행=1)"""

    열: int
    행: int

    @property
    def 이름(self) -> str:
        문자 = ""
        값 = self.열
        while 값 > 0:
            값, 나머지 = divmod(값 - 1, 26)
            문자 = chr(ord("A") + 나머지) + 문자
        return f"{문자}{self.행}"

    @staticmethod
    def 읽기(문자열: str) -> "셀주소 | None":
        m = re.fullmatch(r"\(?([A-Z]+)(\d+)\)?", (문자열 or "").strip().upper())
        if not m:
            return None
        열 = 0
        for 글자 in m.group(1):
            열 = 열 * 26 + (ord(글자) - ord("A") + 1)
        return 셀주소(열=열, 행=int(m.group(2)))


@dataclass(frozen=True)
class 셀범위:
    """선택된 셀 블록의 사각 범위.

    `주소별목록` 이 있으면 'B3' 같은 주소로 셀을 바로 찾을 수 있다. 병합된 셀이
    있어 주소가 빠진 자리는 지도에 없으므로, 부르는 쪽에서 빈 칸으로 다루면 된다.
    """

    시작: 셀주소
    끝: 셀주소
    목록번호: tuple[int, ...] = ()
    주소별목록: dict[str, int] = field(default_factory=dict)

    @property
    def 행수(self) -> int:
        return self.끝.행 - self.시작.행 + 1

    @property
    def 열수(self) -> int:
        return self.끝.열 - self.시작.열 + 1

    @property
    def 셀수(self) -> int:
        return len(self.목록번호) or self.행수 * self.열수


class 문서:
    """열려 있는 한/글 문서를 다루는 창구."""

    def __init__(self, 연결: 한글연결 | None = None) -> None:
        self.연결 = 연결 or 한글연결()
        self._편집수 = 0

    # ------------------------------------------------------------------ 기본
    @property
    def 한글(self) -> Any:
        """원본 COM 객체. 감싸지 않은 기능이 필요할 때 직접 쓸 수 있다."""
        return self.연결.한글

    @property
    def 편집수(self) -> int:
        """이 객체를 통해 실행한 편집 횟수(되돌리기 계산에 쓴다)."""
        return self._편집수

    def 실행(self, 액션: str, 횟수: int = 1) -> None:
        """파라미터가 필요 없는 액션을 실행한다. (예: 'BreakPara')"""
        for _ in range(max(1, 횟수)):
            self.한글.HAction.Run(액션)
        self._편집수 += max(1, 횟수)

    @contextlib.contextmanager
    def 파라미터(self, 액션: str, 세트: str | None = None) -> Iterator[Any]:
        """액션 파라미터셋을 채우고 실행하는 공통 절차.

        원본은 액션마다 6줄(`CreateAction`→`CreateSet`→`GetDefault`→`SetItem`→
        `Execute`)을 되풀이했다. 이제 이렇게 쓴다::

            with 문서.파라미터("CharShape") as 값:
                값.SetItem("Height", units.pt(15))
        """
        액션객체 = self.한글.CreateAction(액션)
        파라 = 액션객체.CreateSet()
        액션객체.GetDefault(파라)
        yield 파라
        액션객체.Execute(파라)
        self._편집수 += 1

    @contextlib.contextmanager
    def 세트파라미터(self, 액션: str, 세트이름: str) -> Iterator[Any]:
        """`HParameterSet` 을 직접 만져야 하는 액션용. (표 만들기, 용지 설정 등)"""
        세트 = getattr(self.한글.HParameterSet, 세트이름)
        self.한글.HAction.GetDefault(액션, 세트.HSet)
        yield 세트
        self.한글.HAction.Execute(액션, 세트.HSet)
        self._편집수 += 1

    # ------------------------------------------------------------- 문자 입력
    def 문장입력(self, 내용: str) -> None:
        """현재 위치에 텍스트를 넣는다. 선택 영역이 있으면 대체한다."""
        if 내용 is None:
            return
        with self.파라미터("InsertText") as 값:
            값.SetItem("Text", 내용)

    def 문단(self, 횟수: int = 1) -> None:
        self.실행("BreakPara", 횟수)

    def 쪽나눔(self) -> None:
        self.실행("BreakPage")

    def 취소(self) -> None:
        """선택·편집 상태를 푼다."""
        self.실행("Cancel")

    def 되돌리기(self, 횟수: int = 1) -> None:
        self.실행("Undo", min(횟수, _되돌리기한계))

    def 다시실행(self, 횟수: int = 1) -> None:
        self.실행("Redo", 횟수)

    # ------------------------------------------------------------ 선택 영역
    def 선택있나(self) -> bool:
        """블록(선택 영역)이 있는지 확인한다."""
        try:
            결과 = self.한글.GetSelectedPos()
        except Exception:  # noqa: BLE001 # pragma: no cover
            return False
        if not 결과 or not 결과[0]:
            return False
        # (성공, s목록, s문단, s위치, e목록, e문단, e위치)
        return 결과[1:4] != 결과[4:7]

    def 선택텍스트(self, 필수: bool = True) -> str:
        """선택 영역의 텍스트를 읽는다.

        `GetTextFile('TEXT', 'saveblock')` 을 먼저 쓰고, 실패하면 원본과 같은
        InitScan 방식으로 넘어간다. 선택이 없을 때 문서 전체를 잘못 읽어오는 일이
        없도록 먼저 선택 여부를 확인한다.
        """
        if not self.선택있나():
            if 필수:
                raise 상태오류(
                    "선택한 내용이 없습니다.",
                    "한/글에서 바꿀 부분을 마우스로 끌어 선택한 뒤 다시 누르세요.",
                )
            return ""
        try:
            텍스트 = self.한글.GetTextFile("TEXT", "saveblock")
            if 텍스트:
                return 텍스트.replace("\r\n", "\r")
        except Exception as 오류:  # noqa: BLE001
            로그.debug("GetTextFile 실패, InitScan 으로 대체: %s", 오류)
        return self._스캔텍스트(선택만=True)

    def 전체텍스트(self) -> str:
        """문서 전체 텍스트를 읽는다."""
        try:
            텍스트 = self.한글.GetTextFile("TEXT", "")
            if 텍스트:
                return 텍스트
        except Exception as 오류:  # noqa: BLE001
            로그.debug("GetTextFile 실패, InitScan 으로 대체: %s", 오류)
        return self._스캔텍스트(선택만=False)

    def _스캔텍스트(self, 선택만: bool) -> str:
        한글 = self.한글
        조각: list[str] = []
        한글.InitScan(1 if 선택만 else 0, 255)
        try:
            while True:
                상태, 텍스트 = 한글.GetText()
                if 텍스트:
                    조각.append(텍스트)
                if 상태 <= 1:  # 0: 내용 없음, 1: 끝
                    break
        finally:
            한글.ReleaseScan()
        return "".join(조각)

    def 선택교체(self, 내용: str) -> None:
        """선택 영역을 주어진 텍스트로 바꾼다.

        여러 문단을 넣을 때는 `InsertText` 가 줄바꿈을 무시하므로 문단을 나눠 넣는다.
        """
        줄들 = re.split(r"\r\n|\r|\n", 내용)
        self.문장입력(줄들[0])
        for 줄 in 줄들[1:]:
            self.문단()
            self.문장입력(줄)

    @contextlib.contextmanager
    def 위치보존(self) -> Iterator[None]:
        """작업 뒤 커서를 원래 자리로 돌려놓는다."""
        try:
            자리 = self.한글.GetPosBySet()
        except Exception:  # noqa: BLE001 # pragma: no cover
            자리 = None
        try:
            yield
        finally:
            if 자리 is not None:
                with contextlib.suppress(Exception):
                    self.한글.SetPosBySet(자리)

    def 이동하기(self, 이름: str) -> None:
        """`이동` 표의 이름으로 커서를 옮긴다."""
        코드 = 이동.get(이름)
        if 코드 is None:
            raise 입력오류(f"모르는 이동 위치: {이름}")
        self.한글.MovePos(코드)

    # ----------------------------------------------------------------- 표
    @property
    def 표안(self) -> bool:
        """커서가 표 안에 있는지."""
        try:
            return bool(self.한글.CellShape)
        except Exception:  # noqa: BLE001 # pragma: no cover
            return False

    def 표확인(self) -> None:
        if not self.표안:
            raise 상태오류(
                "표 안에서 쓰는 기능입니다.",
                "표의 셀을 선택하거나 셀 안에 커서를 두고 다시 누르세요.",
            )

    def 현재셀(self) -> 셀주소 | None:
        """커서가 있는 셀의 주소."""
        try:
            표시 = self.한글.KeyIndicator()
        except Exception:  # noqa: BLE001 # pragma: no cover
            return None
        if not 표시:
            return None
        return 셀주소.읽기(str(표시[-1]))

    def 셀블록범위(self) -> 셀범위:
        """선택된 셀 블록의 범위를 구한다.

        원본 `셀정보` 는 셀 주소를 문자 하나로만 계산해 Z열을 넘기면 어긋났고,
        블록의 시작이 항상 왼쪽 위라고 가정해 **↖ 방향으로 끌면 오작동**했다.
        여기서는 목록 번호를 훑어 셀 주소를 모으고 최소·최대로 사각 범위를 잡으므로
        끄는 방향과 무관하다.
        """
        self.표확인()
        한글 = self.한글
        try:
            선택 = 한글.GetSelectedPos()
        except Exception as 오류:  # noqa: BLE001 # pragma: no cover
            raise 상태오류("셀 선택 정보를 읽을 수 없습니다.") from 오류
        if not 선택 or not 선택[0]:
            현재 = self.현재셀()
            if 현재 is None:
                raise 상태오류("셀 위치를 알 수 없습니다.")
            return 셀범위(시작=현재, 끝=현재)

        시작목록, 끝목록 = sorted((int(선택[1]), int(선택[4])))
        주소들: list[셀주소] = []
        번호들: list[int] = []
        with self.위치보존():
            for 목록 in range(시작목록, 끝목록 + 1):
                자리 = 한글.GetPosBySet()
                자리.SetItem("List", 목록)
                자리.SetItem("Para", 0)
                자리.SetItem("Pos", 0)
                if not 한글.SetPosBySet(자리):
                    continue
                주소 = self.현재셀()
                if 주소 is not None:
                    주소들.append(주소)
                    번호들.append(목록)

        if not 주소들:
            raise 상태오류("선택한 셀을 확인하지 못했습니다.")
        시작 = 셀주소(열=min(주.열 for 주 in 주소들), 행=min(주.행 for 주 in 주소들))
        끝 = 셀주소(열=max(주.열 for 주 in 주소들), 행=max(주.행 for 주 in 주소들))
        지도 = {주소.이름: 번호 for 주소, 번호 in zip(주소들, 번호들)}
        return 셀범위(시작=시작, 끝=끝, 목록번호=tuple(번호들), 주소별목록=지도)

    def 셀로이동(self, 목록번호: int) -> bool:
        """목록 번호(셀 식별자)로 커서를 옮긴다."""
        한글 = self.한글
        자리 = 한글.GetPosBySet()
        자리.SetItem("List", 목록번호)
        자리.SetItem("Para", 0)
        자리.SetItem("Pos", 0)
        return bool(한글.SetPosBySet(자리))

    def 셀주소로이동(self, 범위: 셀범위, 열: int, 행: int) -> bool:
        """범위 안의 (열, 행) 셀로 커서를 옮긴다. 그 자리가 없으면 False."""
        번호 = 범위.주소별목록.get(셀주소(열=열, 행=행).이름)
        return self.셀로이동(번호) if 번호 is not None else False

    def 셀선택(self) -> None:
        """현재 셀 하나를 블록으로 잡는다."""
        self.실행("Cancel")
        self.실행("TableCellBlock")

    def 셀텍스트(self) -> str:
        """현재 셀의 텍스트를 읽는다."""
        self.셀선택()
        return self.선택텍스트(필수=False)

    def 셀텍스트쓰기(self, 내용: str) -> None:
        """현재 셀의 내용을 바꾼다."""
        self.셀선택()
        self.문장입력(내용)

    def 셀순회(self, 범위: 셀범위 | None = None) -> Iterator[int]:
        """선택된 셀들을 하나씩 돌며 목록 번호를 넘겨준다.

        호출한 쪽은 `문서.셀텍스트()` / `셀텍스트쓰기()` 로 그 셀을 다루면 된다.
        """
        범위 = 범위 or self.셀블록범위()
        for 목록 in 범위.목록번호 or ():
            if self.셀로이동(목록):
                yield 목록

    def 사진넣기(self, 경로: str, 셀맞춤: bool = True) -> None:
        """현재 위치(또는 선택한 셀)에 그림을 넣는다.

        InsertPicture 인자는 (경로, 문서에포함, 크기옵션, 뒤집기, 워터마크, 효과) 다.
        크기옵션 3 = 셀 크기에 맞춤 — 사진 대장을 만들 때 필요하다.
        """
        경로 = os.path.abspath(경로)
        if not os.path.isfile(경로):
            raise 입력오류(f"그림 파일이 없습니다: {경로}")
        self.한글.InsertPicture(경로, 1, 3 if 셀맞춤 else 0, 0, 0, 0)
        self._편집수 += 1
        self.실행("ParagraphShapeAlignCenter")

    def 현재쪽(self) -> int | None:
        """커서가 있는 쪽 번호. 알 수 없으면 None.

        한/글의 KeyIndicator 는 (성공, 구역, 쪽, 단, 줄, 칸 …) 형태로 알려져 있지만
        버전에 따라 구성이 달라질 수 있다. 확실하지 않으면 추측하지 않고 None 을
        돌려주고, 부르는 쪽에서 쪽번호 없이 처리한다.
        """
        try:
            표시 = self.한글.KeyIndicator()
        except Exception:  # noqa: BLE001
            return None
        정수들 = [값 for 값 in (표시 or ()) if isinstance(값, int)]
        if len(정수들) < 3:
            return None
        쪽 = 정수들[2]
        return 쪽 if isinstance(쪽, int) and 쪽 > 0 else None

    # --------------------------------------------------------------- 필드
    def 필드목록(self) -> list[str]:
        """문서에 심어진 누름틀·필드 이름 목록."""
        try:
            원문 = self.한글.GetFieldList(1, 0) or ""
        except Exception as 오류:  # noqa: BLE001
            로그.debug("필드 목록 조회 실패: %s", 오류)
            return []
        이름들 = []
        for 조각 in re.split(r"[\x02\n]", 원문):
            이름 = 조각.split("{{")[0].strip()
            if 이름 and 이름 not in 이름들:
                이름들.append(이름)
        return 이름들

    def 필드채우기(self, 값들: dict[str, str]) -> int:
        """필드 이름 → 값 으로 문서를 채운다. 채운 개수를 돌려준다."""
        채움 = 0
        for 이름, 값 in 값들.items():
            try:
                self.한글.PutFieldText(이름, "" if 값 is None else str(값))
                채움 += 1
            except Exception as 오류:  # noqa: BLE001
                로그.warning("필드 '%s' 채우기 실패: %s", 이름, 오류)
        self._편집수 += 1
        return 채움

    def 필드심기(self, 이름: str) -> None:
        """현재 위치에 누름틀(필드)을 심는다."""
        with self.파라미터("InsertFieldTemplate") as 값:
            값.SetItem("TemplateDirection", 이름)
            값.SetItem("TemplateName", 이름)

    # --------------------------------------------------------------- 파일
    def 새문서(self) -> None:
        self.실행("FileNew")

    def 열기(self, 경로: str, 읽기전용: bool = False) -> None:
        """문서를 연다."""
        경로 = os.path.abspath(경로)
        if not os.path.isfile(경로):
            raise 입력오류(f"파일이 없습니다: {경로}")
        옵션 = "forceopen:true" + (";readonly:true" if 읽기전용 else "")
        if not self.한글.Open(경로, "", 옵션):
            raise 입력오류(f"파일을 열지 못했습니다: {경로}")

    def 저장(self) -> None:
        self.한글.Save(True)

    def 다른이름저장(self, 경로: str, 형식: str = "HWP") -> str:
        """다른 이름으로 저장한다. 형식: HWP | HWPX | PDF | TEXT | HWPML2X"""
        경로 = os.path.abspath(경로)
        폴더 = os.path.dirname(경로)
        if 폴더:
            os.makedirs(폴더, exist_ok=True)
        형식 = 형식.upper()
        if not self.한글.SaveAs(경로, 형식, ""):
            raise 입력오류(f"저장하지 못했습니다: {경로}")
        return 경로

    def PDF저장(self, 경로: str) -> str:
        """PDF 로 내보낸다."""
        if not 경로.lower().endswith(".pdf"):
            경로 += ".pdf"
        return self.다른이름저장(경로, "PDF")

    def 문서닫기(self, 저장: bool = False) -> None:
        """현재 문서를 닫는다. (일괄처리에서 다음 파일로 넘어갈 때)"""
        try:
            self.한글.Clear(1 if 저장 else 3)
        except Exception as 오류:  # noqa: BLE001
            로그.debug("문서 닫기 실패: %s", 오류)

    @property
    def 현재파일(self) -> str:
        try:
            return str(self.한글.Path or "")
        except Exception:  # noqa: BLE001 # pragma: no cover
            return ""

    # ------------------------------------------------------- 작업 묶음
    @contextlib.contextmanager
    def 한번에(self, 이름: str = "작업") -> Iterator[None]:
        """여러 편집을 한 묶음으로 실행한다.

        도중에 오류가 나면 그때까지의 편집을 되돌린다. 원본은 서식 생성 중간에
        실패하면 반쯤 그려진 표가 문서에 남았다.
        """
        시작 = self._편집수
        try:
            yield
        except Exception:
            되돌릴수 = self._편집수 - 시작
            if 되돌릴수 > 0:
                로그.warning("'%s' 실패 → 편집 %d건을 되돌립니다.", 이름, 되돌릴수)
                with contextlib.suppress(Exception):
                    self.되돌리기(되돌릴수)
            raise

    @contextlib.contextmanager
    def 화면정지(self) -> Iterator[None]:
        """화면 갱신을 멈춰 일괄 작업 속도를 올린다."""
        한글 = self.한글
        with contextlib.suppress(Exception):
            한글.SetMessageBoxMode(0x00000020)  # 확인 창 자동 처리
        try:
            with contextlib.suppress(Exception):
                한글.XHwpDocuments.Item(0).XHwpDocumentInfo.RedrawEnable = False
            yield
        finally:
            with contextlib.suppress(Exception):
                한글.XHwpDocuments.Item(0).XHwpDocumentInfo.RedrawEnable = True

    # ------------------------------------------------------------- 도우미
    def mm(self, 값: float) -> int:
        """밀리미터 → HWPUNIT (COM 호출 없이 계산한다)"""
        return units.mm(값)

    def 색(self, 빨강: int, 초록: int, 파랑: int) -> int:
        return units.rgb(빨강, 초록, 파랑)
