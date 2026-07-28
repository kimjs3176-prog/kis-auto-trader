"""가짜 한/글 COM 객체.

윈도우·한/글 없이도 문서 조작 계층과 기능 계층의 흐름을 검증하기 위한 대역이다.
원본 프로그램은 COM 호출과 로직이 붙어 있어 이런 검증이 불가능했다.

완전한 한/글 흉내가 목표가 아니라, 이 프로그램이 **어떤 액션에 어떤 값을 넘기는지**
확인하는 것이 목적이다.

인수 개수는 **실제 한/글 API 와 똑같이** 적어 둔다(기본값을 두지 않는다).
늦은 바인딩(`Dispatch`)에서는 생략 가능 인수를 파이썬이 채워 주지 않아,
하나라도 빠뜨리면 한/글이 "매개 변수의 개수가 잘못되었습니다"(0x8002000E) 로
거절한다. 대역이 느슨하면 그 실수가 윈도우에 가서야 드러난다.
"""

from __future__ import annotations

from typing import Any


class 가짜파라미터:
    """ParameterSet 대역. SetItem/Item 을 기록한다."""

    def __init__(self, 소유자: Any = None) -> None:
        self.항목: dict[str, Any] = {}
        self.소유자 = 소유자  # 이 HSet 을 가진 가짜세트 (기록용)

    def SetItem(self, 이름: str, 값: Any) -> None:
        self.항목[이름] = 값

    def Item(self, 이름: str) -> Any:
        return self.항목.get(이름)

    def CreateItemSet(self, 이름: str, _종류: str) -> "가짜파라미터":
        하위 = 가짜파라미터()
        self.항목[이름] = 하위
        return 하위

    def CreateItemArray(self, 이름: str, _개수: int) -> None:
        self.항목[이름] = 가짜파라미터()


class 가짜세트:
    """HParameterSet.HXxx 대역. 아무 속성이나 받아 준다."""

    def __init__(self) -> None:
        self.HSet = 가짜파라미터(소유자=self)
        self._값: dict[str, Any] = {}

    def __getattr__(self, 이름: str) -> Any:
        if 이름.startswith("_"):
            raise AttributeError(이름)
        하위 = self.__dict__.setdefault("_하위", {})
        if 이름 not in 하위:
            하위[이름] = 가짜세트()
        return 하위[이름]

    def __setattr__(self, 이름: str, 값: Any) -> None:
        if 이름 in ("HSet", "_값", "_하위"):
            super().__setattr__(이름, 값)
        else:
            self.__dict__.setdefault("_값", {})[이름] = 값

    def 값읽기(self, 이름: str, 기본값: Any = None) -> Any:
        return self.__dict__.get("_값", {}).get(이름, 기본값)

    def SetItem(self, 이름: Any, 값: Any) -> None:
        self.__dict__.setdefault("_값", {})[이름] = 값

    def Item(self, 이름: Any) -> Any:
        return self.__dict__.get("_값", {}).get(이름)

    def CreateItemArray(self, 이름: str, _개수: int) -> None:
        # 실제 한/글처럼, 만든 배열은 같은 이름의 속성으로 접근한다.
        self.__dict__.setdefault("_하위", {})[이름] = 가짜세트()


class 가짜액션:
    def __init__(self, 이름: str, 한글: "가짜한글") -> None:
        self.이름 = 이름
        self.한글 = 한글

    def CreateSet(self) -> 가짜파라미터:
        return 가짜파라미터()

    def GetDefault(self, _파라미터: 가짜파라미터) -> None:
        return None

    def Execute(self, 파라미터: 가짜파라미터) -> bool:
        self.한글.기록.append((self.이름, dict(파라미터.항목)))
        if self.이름 == "InsertText":
            self.한글._텍스트입력(str(파라미터.항목.get("Text", "")))
        return True


class 가짜HAction:
    def __init__(self, 한글: "가짜한글") -> None:
        self.한글 = 한글

    def Run(self, 이름: str) -> bool:
        self.한글.실행기록.append(이름)
        if 이름 == "BreakPara":
            self.한글._텍스트입력("\r")
        elif 이름 == "Cancel":
            self.한글.선택중 = False
        elif 이름 in ("TableCellBlock", "TableCellBlockExtend", "SelectAll"):
            self.한글.선택중 = True
        elif 이름 == "MoveSelParaEnd":
            self.한글._문단선택()
        elif 이름 in ("MoveNextParaBegin", "MoveNextPara"):
            self.한글._다음문단()
        elif 이름 in ("TableRightCell", "TableRightCellAppend"):
            self.한글._옆셀(1)
        elif 이름 == "TableLeftCell":
            self.한글._옆셀(-1)
        elif 이름 == "TableLowerCell":
            self.한글._아래셀(1)
        elif 이름 == "TableUpperCell":
            self.한글._아래셀(-1)
        elif 이름 == "TableInsertLowerRow":
            self.한글._줄추가()
        elif 이름 == "TableInsertRightColumn":
            self.한글._칸추가()
        elif 이름 == "CloseEx":
            self.한글.CellShape = None
            self.한글.셀값 = {}
            self.한글.셀주소 = {}
        return True

    def GetDefault(self, 이름: str, _세트: Any) -> None:
        self.한글.실행기록.append(f"GetDefault:{이름}")

    def Execute(self, 이름: str, 세트: Any) -> bool:
        대상 = getattr(세트, "소유자", None) or 세트
        self.한글.세트기록.append((이름, 대상))
        if 이름 == "TableCreate":
            self.한글._표만들기(
                행수=int(대상.값읽기("Rows", 1) or 1),
                열수=int(대상.값읽기("Cols", 1) or 1),
            )
        return True


class 가짜HParameterSet:
    def __getattr__(self, 이름: str) -> 가짜세트:
        하위 = self.__dict__.setdefault("_하위", {})
        if 이름 not in 하위:
            하위[이름] = 가짜세트()
        return 하위[이름]


class 가짜창:
    def __init__(self) -> None:
        self.Visible = True


class 가짜창모음:
    def __init__(self) -> None:
        self._창 = 가짜창()

    def Item(self, _번호: int) -> 가짜창:
        return self._창


class 가짜한글:
    """한/글 COM 객체 대역."""

    Version = "10.9.0.0 (가짜)"

    def __init__(
        self,
        선택텍스트: str = "",
        셀값: dict[int, str] | None = None,
        셀주소: dict[int, str] | None = None,
    ) -> None:
        self.기록: list[tuple[str, dict]] = []          # (액션, 파라미터)
        self.실행기록: list[str] = []                    # HAction.Run
        self.세트기록: list[tuple[str, Any]] = []        # HAction.Execute
        self.본문: str = 선택텍스트
        self.선택값: str = 선택텍스트
        self.선택중: bool = bool(선택텍스트)
        self.셀값: dict[int, str] = dict(셀값 or {})
        self.셀주소: dict[int, str] = dict(셀주소 or {})
        self.현재목록: int = min(self.셀값) if self.셀값 else 0
        self.현재문단: int = 0
        self.CellShape: Any = 1 if self.셀값 else None
        self.HAction = 가짜HAction(self)
        self.HParameterSet = 가짜HParameterSet()
        self.XHwpWindows = 가짜창모음()
        self.저장기록: list[tuple[str, str]] = []
        self.필드값: dict[str, str] = {}
        self.필드이름: list[str] = []
        self.열린파일: str = ""
        self.등록모듈: list[tuple[str, str]] = []
        self.넣은그림: list[tuple[str, int]] = []

    # -------------------------------------------------------- 문단 순회 대역
    @property
    def 문단들(self) -> list[str]:
        """본문을 문단으로 나눈 것. (한/글은 문단 끝을 \\r 로 준다)"""
        return (self.본문 or "").replace("\r\n", "\r").split("\r")

    def _문단선택(self) -> None:
        """MoveSelParaEnd — 지금 문단 끝까지 선택한다."""
        문단 = self.문단들
        if 0 <= self.현재문단 < len(문단):
            self.선택값 = 문단[self.현재문단]
            self.선택중 = bool(self.선택값)

    def _다음문단(self) -> None:
        """MoveNextParaBegin — 다음 문단으로. 마지막이면 그대로 있는다."""
        if self.현재문단 + 1 < len(self.문단들):
            self.현재문단 += 1

    def GetPos(self):
        return (0, self.현재문단, 0)

    def SetPos(self, 목록: int, 문단: int, _위치: int) -> bool:
        self.현재목록 = 목록
        self.현재문단 = 문단
        return True

    # ------------------------------------------------------------ 내부
    def _텍스트입력(self, 값: str) -> None:
        if self.셀값 and self.CellShape:
            현재 = self.셀값.get(self.현재목록, "")
            self.셀값[self.현재목록] = 값 if self.선택중 else 현재 + 값
        else:
            self.본문 = 값 if self.선택중 else self.본문 + 값
        self.선택중 = False

    def _표만들기(self, 행수: int, 열수: int) -> None:
        """TableCreate 액션이 실행되면 표 안에 들어간 상태를 흉내 낸다."""
        self.셀값 = {}
        self.셀주소 = {}
        번호 = 1
        for 행 in range(1, 행수 + 1):
            for 열 in range(1, 열수 + 1):
                self.셀값[번호] = ""
                self.셀주소[번호] = f"{chr(ord('A') + 열 - 1)}{행}"
                번호 += 1
        self.현재목록 = 1
        self.CellShape = 1

    def _주소풀기(self, 주소: str) -> tuple[int, int]:
        """'B3' → (열 2, 행 3)"""
        열글자 = "".join(글자 for 글자 in 주소 if 글자.isalpha())
        행글자 = "".join(글자 for 글자 in 주소 if 글자.isdigit())
        열 = 0
        for 글자 in 열글자:
            열 = 열 * 26 + (ord(글자.upper()) - ord("A") + 1)
        return 열, int(행글자 or 1)

    def _주소만들기(self, 열: int, 행: int) -> str:
        문자 = ""
        값 = 열
        while 값 > 0:
            값, 나머지 = divmod(값 - 1, 26)
            문자 = chr(ord("A") + 나머지) + 문자
        return f"{문자}{행}"

    def _번호찾기(self, 열: int, 행: int) -> int | None:
        찾는주소 = self._주소만들기(열, 행)
        for 번호, 주소 in self.셀주소.items():
            if 주소 == 찾는주소:
                return 번호
        return None

    def _옆셀(self, 걸음: int) -> None:
        열, 행 = self._주소풀기(self.셀주소.get(self.현재목록, "A1"))
        번호 = self._번호찾기(열 + 걸음, 행)
        if 번호 is None:  # 줄 끝이면 다음 줄 첫 칸으로 (한/글과 같은 동작)
            번호 = self._번호찾기(1, 행 + 걸음)
        if 번호 is not None:
            self.현재목록 = 번호

    def _아래셀(self, 걸음: int) -> None:
        열, 행 = self._주소풀기(self.셀주소.get(self.현재목록, "A1"))
        번호 = self._번호찾기(열, 행 + 걸음)
        if 번호 is not None:
            self.현재목록 = 번호

    def _줄추가(self) -> None:
        """현재 줄 아래에 빈 줄을 넣는다. (마지막 줄 아래 추가만 흉내 낸다)"""
        _열, 행 = self._주소풀기(self.셀주소.get(self.현재목록, "A1"))
        열수 = max(self._주소풀기(주소)[0] for 주소 in self.셀주소.values())
        마지막행 = max(self._주소풀기(주소)[1] for 주소 in self.셀주소.values())
        if 행 != 마지막행:
            return
        다음번호 = max(self.셀값, default=0) + 1
        for 열 in range(1, 열수 + 1):
            self.셀값[다음번호] = ""
            self.셀주소[다음번호] = self._주소만들기(열, 행 + 1)
            다음번호 += 1

    def _칸추가(self) -> None:
        """현재 칸 오른쪽에 빈 칸을 넣는다. (마지막 열 오른쪽 추가만 흉내 낸다)"""
        열, _행 = self._주소풀기(self.셀주소.get(self.현재목록, "A1"))
        열수 = max(self._주소풀기(주소)[0] for 주소 in self.셀주소.values())
        행수 = max(self._주소풀기(주소)[1] for 주소 in self.셀주소.values())
        if 열 != 열수:
            return
        다음번호 = max(self.셀값, default=0) + 1
        for 행 in range(1, 행수 + 1):
            self.셀값[다음번호] = ""
            self.셀주소[다음번호] = self._주소만들기(열수 + 1, 행)
            다음번호 += 1

    def InsertPicture(
        self,
        경로: str,
        _포함,
        _크기옵션,
        _뒤집기,
        _워터마크,
        _효과,
        _너비,
        _높이,
    ) -> bool:
        self.넣은그림.append((경로, self.현재목록))
        if self.셀값 and self.CellShape:
            self.셀값[self.현재목록] = f"[그림:{경로}]"
        return True

    # ------------------------------------------------------------ COM 대역
    def CreateAction(self, 이름: str) -> 가짜액션:
        return 가짜액션(이름, self)

    def RegisterModule(self, 가: str, 나: str) -> bool:
        self.등록모듈.append((가, 나))
        return True

    def GetTextFile(self, _형식: str, 옵션: str) -> str:
        if 옵션 == "saveblock":
            if self.셀값 and self.CellShape:
                return self.셀값.get(self.현재목록, "")
            return self.선택값
        return self.본문

    def GetSelectedPos(self):
        if not self.선택중 and not self.셀값:
            return (False, 0, 0, 0, 0, 0, 0)
        if self.셀값:
            번호들 = sorted(self.셀값)
            return (True, 번호들[0], 0, 0, 번호들[-1], 0, 1)
        return (True, 0, 0, 0, 0, 0, len(self.선택값))

    def GetPosBySet(self) -> 가짜파라미터:
        자리 = 가짜파라미터()
        자리.SetItem("List", self.현재목록)
        자리.SetItem("Para", 0)
        자리.SetItem("Pos", 0)
        return 자리

    def SetPosBySet(self, 자리: 가짜파라미터) -> bool:
        self.현재목록 = int(자리.Item("List") or 0)
        return True

    def MovePos(self, 코드: int, _문단, _위치) -> bool:
        if 코드 == 2:  # 문서 처음
            self.현재문단 = 0
        elif 코드 == 3:  # 문서 끝
            self.현재문단 = max(len(self.문단들) - 1, 0)
        return True

    def KeyIndicator(self):
        주소 = self.셀주소.get(self.현재목록, "A1")
        return (0, 0, 0, 0, 0, 0, f"({주소})")

    def InitScan(
        self, _옵션, _범위, _시작문단, _시작위치, _끝문단, _끝위치
    ) -> bool:
        self._스캔남음 = True
        return True

    def GetText(self):
        if getattr(self, "_스캔남음", False):
            self._스캔남음 = False
            return (1, self.선택값)
        return (0, "")

    def ReleaseScan(self) -> bool:
        return True

    def PutFieldText(self, 이름: str, 값: str) -> bool:
        self.필드값[이름] = 값
        return True

    def GetFieldList(self, _번호: int, _옵션: int) -> str:
        return "\x02".join(self.필드이름)

    def Open(self, 경로: str, _형식: str, _옵션: str) -> bool:
        self.열린파일 = 경로
        return True

    def Save(self, _확인: bool = True) -> bool:
        self.저장기록.append((self.열린파일, "HWP"))
        return True

    def SaveAs(self, 경로: str, 형식: str, _옵션: str) -> bool:
        self.저장기록.append((경로, 형식))
        return True

    def Clear(self, _옵션: int = 3) -> bool:
        self.본문 = ""
        return True

    def Quit(self) -> bool:
        return True

    def FindCtrl(self) -> bool:
        self.CellShape = None  # 다음 개체가 없다고 본다
        return True

    def MiliToHwpUnit(self, 값: float) -> int:
        return int(값 * 7200 / 25.4)

    def RGBColor(self, 빨강: int, 초록: int, 파랑: int) -> int:
        return 빨강 | (초록 << 8) | (파랑 << 16)

    def BrushType(self, 이름: str) -> str:
        return 이름

    def HatchStyle(self, 이름: str) -> str:
        return 이름

    @property
    def Path(self) -> str:
        return self.열린파일


class 가짜연결:
    """`core.connection.한글연결` 대역."""

    def __init__(self, 한글: 가짜한글) -> None:
        self._한글 = 한글
        self.새로띄움 = False
        self.보임 = True

    @property
    def 한글(self) -> 가짜한글:
        return self._한글

    @property
    def 버전(self) -> str:
        return self._한글.Version

    def 연결(self) -> 가짜한글:
        return self._한글

    def 보이기(self, 켜기: bool = True) -> None:
        self.보임 = bool(켜기)

    def 닫기(self, 문서저장: bool = False) -> None:
        return None


def 문서만들기(**인자) -> tuple[Any, 가짜한글]:
    """테스트용 문서 객체와 가짜 한/글을 함께 만든다."""
    from hwpkit.core.document import 문서

    한글 = 가짜한글(**인자)
    return 문서(가짜연결(한글)), 한글
