"""직접 그린 위젯 — 둥근 카드·알약 단추·기능 타일.

tkinter 기본 위젯은 모서리가 각지고 테두리가 굵어, 시안 같은 화면을 만들 수
없다. 그래서 눈에 많이 띄는 것들 — 기능 타일, 분류 칩, 검색칸, 채운 단추,
세부설정 판 손잡이, 돋보기 — 은 캔버스에 직접 그린다. 모서리를 깎는 계산은
`layout.둥근네모점들` 에 있다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Callable

from . import icons, layout, theme

__all__ = [
    "둥근네모",
    "알약단추",
    "켬끔",
    "토막고르기",
    "채운단추",
    "미끄럼자",
    "둥근칸",
    "둥근상자",
    "고르는칸",
    "잡이",
    "돋보기",
    "타일",
]


def 둥근네모(
    캔버스: tk.Canvas,
    왼쪽: float,
    위: float,
    오른쪽: float,
    아래: float,
    반경: float,
    **옵션: Any,
) -> int:
    """모서리가 둥근 네모를 그리고 그린 것의 번호를 준다."""
    점들 = layout.둥근네모점들(왼쪽, 위, 오른쪽, 아래, 반경)
    return 캔버스.create_polygon(점들, smooth=True, splinesteps=16, **옵션)


def 그림자(
    캔버스: tk.Canvas,
    왼쪽: float,
    위: float,
    오른쪽: float,
    아래: float,
    반경: float,
    뒷색: str,
    겹: int = 3,
    번짐: float = 2.0,
) -> list[int]:
    """둥근네모 아래에 옅은 그림자를 몇 겹 깐다.

    tkinter 에는 투명도도 흐리기도 없다. 그래서 바깥으로 조금씩 키운 둥근네모를
    점점 옅은 색으로 겹쳐 그려 번지는 그림자를 흉내 낸다. 카드보다 **먼저**
    그려야 뒤에 깔린다.
    """
    그린것 = []
    for 번 in range(겹, 0, -1):
        키움 = 번 * 번짐 * 0.5
        내림 = 번 * 번짐 * 0.45
        그린것.append(
            둥근네모(
                캔버스,
                왼쪽 - 키움,
                위 - 키움 + 내림,
                오른쪽 + 키움,
                아래 + 키움 + 내림,
                반경 + 키움,
                fill=theme.그늘(뒷색, 0.055 / 번),
                outline="",
            )
        )
    return 그린것


def 바퀴묶기(위젯: tk.Misc, 함수: Callable[[Any], Any]) -> None:
    """마우스 바퀴를 묶는다. 윈도우는 MouseWheel, X11 은 Button-4/5 를 쓴다."""
    위젯.bind("<MouseWheel>", 함수)
    위젯.bind("<Button-4>", 함수)
    위젯.bind("<Button-5>", 함수)


class 알약단추(tk.Canvas):
    """알약 모양 단추. 고르면 파랗게 찬다. (분류 칩·자리 단추·토글에 쓴다)"""

    def __init__(
        self,
        부모: tk.Misc,
        글: str,
        누름: Callable[[], None],
        바탕색: str = theme.바탕,
        골라짐: bool = False,
        높이: int = 28,
        안여백: int = 13,
        글꼴크기: int = 9,
        최소너비: int = 0,
        끈색: str | None = None,
        테보임: bool = True,
    ) -> None:
        self._글꼴 = tkfont.Font(family=theme.글꼴, size=글꼴크기)
        폭 = max(최소너비, self._글꼴.measure(글) + 안여백 * 2)
        super().__init__(
            부모,
            width=폭,
            height=높이,
            bg=바탕색,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=0,
        )
        self._알약 = 둥근네모(
            self, 0.5, 0.5, 폭 - 0.5, 높이 - 0.5, (높이 - 1) / 2, fill=theme.카드, outline=""
        )
        self._글 = self.create_text(
            폭 / 2, 높이 / 2, text=글, font=self._글꼴, fill=theme.보통글
        )
        # 고르지 않았을 때의 채움. 흰 판 위에 놓는 켬/끔은 흰색으로 두면
        # 알약이 안 보여, 입력칸 색으로 채워 칸처럼 보이게 한다.
        self._끈색 = 끈색 or theme.카드
        self._테보임 = 테보임
        self._골라짐: bool | None = None
        self._가리킴 = False
        self.bind("<Button-1>", lambda _사건: 누름())
        self.bind("<Enter>", self._들어옴)
        self.bind("<Leave>", self._나감)
        self.고르기(골라짐)

    def 고르기(self, 참: bool) -> None:
        if 참 == self._골라짐:
            return
        self._골라짐 = bool(참)
        self._칠하기()

    def _들어옴(self, _사건: Any = None) -> None:
        self._가리킴 = True
        self._칠하기()

    def _나감(self, _사건: Any = None) -> None:
        self._가리킴 = False
        self._칠하기()

    def _칠하기(self) -> None:
        if self._골라짐:
            바탕 = theme.파랑진하게 if self._가리킴 else theme.파랑
            글색 = theme.카드
            테 = ""
        else:
            바탕 = theme.파랑옅게 if self._가리킴 else self._끈색
            글색 = theme.파랑 if self._가리킴 else theme.보통글
            # 흰 알약을 흰 카드·옅은 바탕 위에 놓으면 경계가 사라진다.
            테 = (theme.파랑 if self._가리킴 else theme.테두리) if self._테보임 else ""
        self.itemconfigure(self._알약, fill=바탕, outline=테)
        self.itemconfigure(self._글, fill=글색)

    def 글바꾸기(self, 글: str) -> None:
        self.itemconfigure(self._글, text=글)


class 켬끔(알약단추):
    """켜고 끄는 알약. `.get()` 으로 참·거짓을 돌려주어 입력칸으로 쓸 수 있다.

    ttk 체크단추는 네모 칸에 가위표가 그려져 이 화면에서 혼자 튄다.
    """

    def __init__(
        self,
        부모: tk.Misc,
        켜짐: bool = False,
        켠글: str = "사용함",
        끈글: str = "사용 안 함",
        높이: int = 28,
        안여백: int = 13,
        바탕색: str = theme.바탕,
    ) -> None:
        self._켠글, self._끈글 = 켠글, 끈글
        self._켜짐 = bool(켜짐)
        재는글꼴 = tkfont.Font(family=theme.글꼴, size=9)
        너비 = max(재는글꼴.measure(켠글), 재는글꼴.measure(끈글)) + 안여백 * 2
        super().__init__(
            부모,
            켠글 if self._켜짐 else 끈글,
            누름=self._뒤집기,
            바탕색=바탕색,
            골라짐=self._켜짐,
            높이=높이,
            안여백=안여백,
            최소너비=너비,
            끈색=theme.입력칸,  # 껐을 때도 칸으로 보이게
            테보임=False,  # 채운 칸이라 테까지 두르면 답답하다
        )

    def _뒤집기(self) -> None:
        self._켜짐 = not self._켜짐
        self.글바꾸기(self._켠글 if self._켜짐 else self._끈글)
        self.고르기(self._켜짐)

    def get(self) -> bool:  # noqa: N802 - 다른 입력칸(tk 변수)과 이름을 맞춘다
        return self._켜짐


class 토막고르기(tk.Canvas):
    """붙어 있는 토막 중 하나를 고르는 단추. (`좌` `우` 처럼 둘·셋 중 하나)

    알약을 따로따로 두면 둘이 남남처럼 보이는데, 실제로는 **하나를 고르는** 것이다.
    그래서 한 통에 담고 고른 토막만 파랗게 채운다.
    """

    def __init__(
        self,
        부모: tk.Misc,
        값들: list[str],
        값: str,
        바뀜: Callable[[str], None],
        바탕색: str = theme.카드,
        높이: int = 28,
        안여백: int = 13,
        글꼴크기: int = 9,
    ) -> None:
        self._글꼴 = tkfont.Font(family=theme.글꼴, size=글꼴크기)
        self._값들 = list(값들)
        칸너비 = max(self._글꼴.measure(하나) for 하나 in self._값들) + 안여백 * 2
        폭 = 칸너비 * len(self._값들) + 4
        super().__init__(
            부모,
            width=폭,
            height=높이,
            bg=바탕색,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=0,
        )
        self._칸너비 = 칸너비
        self._높이 = 높이
        self._바뀜 = 바뀜
        self._값 = 값 if 값 in self._값들 else self._값들[0]
        둥근네모(
            self, 0.5, 0.5, 폭 - 0.5, 높이 - 0.5, (높이 - 1) / 2, fill=theme.입력칸, outline=""
        )
        self._고른칸 = 둥근네모(
            self, 2, 2, 2 + 칸너비, 높이 - 2, (높이 - 4) / 2, fill=theme.파랑, outline=""
        )
        self._글들 = [
            self.create_text(
                2 + 칸너비 * (번 + 0.5),
                높이 / 2,
                text=하나,
                font=self._글꼴,
                fill=theme.보통글,
            )
            for 번, 하나 in enumerate(self._값들)
        ]
        self.bind("<Button-1>", self._눌림)
        self._칠하기()

    def _눌림(self, 사건: Any) -> None:
        번 = int((사건.x - 2) // self._칸너비)
        if 0 <= 번 < len(self._값들) and self._값들[번] != self._값:
            self.고르기(self._값들[번])
            self._바뀜(self._값)

    def 고르기(self, 값: str) -> None:
        if 값 not in self._값들:
            return
        self._값 = 값
        self._칠하기()

    def get(self) -> str:  # noqa: N802 - 다른 입력칸과 이름을 맞춘다
        return self._값

    def _칠하기(self) -> None:
        번 = self._값들.index(self._값)
        왼 = 2 + self._칸너비 * 번
        self.coords(
            self._고른칸,
            *layout.둥근네모점들(
                왼, 2, 왼 + self._칸너비, self._높이 - 2, (self._높이 - 4) / 2
            ),
        )
        for 자리, 글 in enumerate(self._글들):
            self.itemconfigure(글, fill=theme.카드 if 자리 == 번 else theme.보통글)


class 채운단추(tk.Canvas):
    """색으로 채운 둥근 단추. (시안의 `실행` · `결과 지우기` · `찾기`)

    ttk 단추는 모서리가 각지고 눌린 자리에 회색 테가 남아 시안의 모양이 나오지
    않는다. 알약단추와 달리 모서리를 반만 깎아(`반경비`) 네모난 느낌을 남긴다.
    """

    def __init__(
        self,
        부모: tk.Misc,
        글: str,
        누름: Callable[[], None],
        바탕색: str = theme.카드,
        채움: str = theme.파랑,
        글색: str = theme.카드,
        누른채움: str | None = None,
        높이: int = 38,
        안여백: int = 18,
        글꼴크기: int = 10,
        굵게: bool = True,
        최소너비: int = 0,
        반경비: float = 0.32,
        그늘: bool = False,
    ) -> None:
        self._글꼴 = tkfont.Font(
            family=theme.글꼴, size=글꼴크기, weight="bold" if 굵게 else "normal"
        )
        폭 = max(최소너비, self._글꼴.measure(글) + 안여백 * 2)
        곁 = 3 if 그늘 else 0  # 그늘이 잘리지 않게 canvas 를 조금 키운다
        super().__init__(
            부모,
            width=폭 + 곁 * 2,
            height=높이 + 곁 * 2,
            bg=바탕색,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=0,
        )
        self._채움, self._글색 = 채움, 글색
        self._누른채움 = 누른채움 or theme.섞기(채움, "#000000", 0.85)
        self._누름 = 누름
        self._잠김 = False
        self._가리킴 = False
        반경 = 높이 * 반경비
        if 그늘:
            그림자(self, 곁, 곁, 곁 + 폭, 곁 + 높이, 반경, 바탕색, 겹=3, 번짐=2.4)
        self._네모 = 둥근네모(
            self, 곁 + 0.5, 곁 + 0.5, 곁 + 폭 - 0.5, 곁 + 높이 - 0.5, 반경,
            fill=채움, outline="",
        )
        self._글 = self.create_text(
            곁 + 폭 / 2, 곁 + 높이 / 2, text=글, font=self._글꼴, fill=글색
        )
        self.bind("<Button-1>", self._눌림)
        self.bind("<Enter>", self._들어옴)
        self.bind("<Leave>", self._나감)

    def _눌림(self, _사건: Any = None) -> None:
        if not self._잠김:
            self._누름()

    def _들어옴(self, _사건: Any = None) -> None:
        self._가리킴 = True
        self._칠하기()

    def _나감(self, _사건: Any = None) -> None:
        self._가리킴 = False
        self._칠하기()

    def _칠하기(self) -> None:
        if self._잠김:
            self.itemconfigure(self._네모, fill=theme.꺼짐)
            self.itemconfigure(self._글, fill=theme.카드)
            return
        self.itemconfigure(
            self._네모, fill=self._누른채움 if self._가리킴 else self._채움
        )
        self.itemconfigure(self._글, fill=self._글색)

    def 잠그기(self, 참: bool) -> None:
        """일하는 동안 못 누르게 한다. (ttk 의 `state='disabled'` 자리)"""
        self._잠김 = bool(참)
        self.configure(cursor="watch" if self._잠김 else "hand2")
        self._칠하기()


class 잡이(tk.Canvas):
    """아래쪽 세부설정 판의 **둥근 윗머리** — 그림자 + 둥근 모서리 + 손잡이 막대.

    판이 격자 위로 올라온 종이처럼 보이게 한다. 가는 선 하나로 나누면 창을 칸막이로
    자른 옛 프로그램처럼 보이므로, 위로 번지는 옅은 그림자를 깔고 윗 모서리를
    둥글게 깎는다. 가운데 짧은 막대는 아래에서 올라온 판이라는 표시다.
    """

    def __init__(self, 부모: tk.Misc, 바탕색: str = theme.바탕, 높이: int = 20) -> None:
        super().__init__(
            부모, height=높이, bg=바탕색, highlightthickness=0, bd=0, takefocus=0
        )
        self._높이 = 높이
        self._뒷색 = 바탕색
        self._그린것: list[int] = []
        self.bind("<Configure>", self._크기바뀜)

    def _크기바뀜(self, 사건: Any) -> None:
        for 하나 in self._그린것:
            self.delete(하나)
        너비 = 사건.width
        가운데 = 너비 / 2
        위 = 6.0  # 그림자가 번질 자리
        반경 = 18.0
        그린것: list[int] = []
        # 위로 번지는 그림자 — 옅은 색을 겹쳐 흐린 느낌을 낸다.
        for 번 in range(3, 0, -1):
            그린것.append(
                둥근네모(
                    self,
                    -반경,
                    위 - 번 * 1.6,
                    너비 + 반경,
                    self._높이 + 반경,
                    반경,
                    fill=theme.그늘(self._뒷색, 0.05 / 번),
                    outline="",
                )
            )
        # 판 몸통 — 아래로 넉넉히 빼서 아래 프레임(흰색)과 이어 붙는다.
        그린것.append(
            둥근네모(
                self, 0, 위, 너비, self._높이 + 반경, 반경, fill=theme.카드, outline=""
            )
        )
        막대 = min(44, max(24, 너비 * 0.11))
        막대세로 = 위 + (self._높이 - 위) / 2
        그린것.append(
            둥근네모(
                self,
                가운데 - 막대 / 2,
                막대세로 - 2,
                가운데 + 막대 / 2,
                막대세로 + 2,
                2,
                fill=theme.섞기(theme.흐린글, theme.카드, 0.4),
                outline="",
            )
        )
        self._그린것 = 그린것


class 돋보기(tk.Canvas):
    """검색칸 왼쪽에 놓는 작은 돋보기. (그림 파일 없이 선으로 그린다)"""

    def __init__(self, 부모: tk.Misc, 바탕색: str = theme.카드, 크기: int = 16) -> None:
        super().__init__(
            부모,
            width=크기,
            height=크기,
            bg=바탕색,
            highlightthickness=0,
            bd=0,
            takefocus=0,
        )
        테 = max(1, 크기 // 12)
        지름 = 크기 * 0.62
        self.create_oval(
            테, 테, 지름, 지름, outline=theme.흐린글, width=테 + 1
        )
        self.create_line(
            지름 * 0.82,
            지름 * 0.82,
            크기 - 테,
            크기 - 테,
            fill=theme.흐린글,
            width=테 + 1,
            capstyle="round",
        )


class 미끄럼자(tk.Canvas):
    """직접 그린 미끄럼자 — 둥근 홈 + 파란 채움 + 흰 손잡이.

    ttk 의 것은 네모나고 빗금이 쳐져 있어 이 화면에 어울리지 않는다.
    """

    def __init__(
        self,
        부모: tk.Misc,
        최소: float,
        최대: float,
        값: float,
        바뀜: Callable[[float], None],
        너비: int = 96,
        높이: int = 24,
        바탕색: str = theme.바탕,
    ) -> None:
        super().__init__(
            부모,
            width=너비,
            height=높이,
            bg=바탕색,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=0,
        )
        self._최소, self._최대, self._바뀜 = 최소, 최대, 바뀜
        self._값 = 값
        self._손잡이지름 = 18
        self._왼쪽 = self._손잡이지름 / 2
        self._오른쪽 = 너비 - self._손잡이지름 / 2
        가운데 = 높이 / 2

        둥근네모(
            self, self._왼쪽, 가운데 - 3.5, self._오른쪽, 가운데 + 3.5, 3.5,
            fill=theme.입력칸, outline="",
        )
        self._채움 = 둥근네모(
            self, self._왼쪽, 가운데 - 3.5, self._왼쪽 + 1, 가운데 + 3.5, 3.5,
            fill=theme.파랑, outline="",
        )
        # 손잡이 밑에 옅은 그늘을 하나 깔아 떠 있는 느낼을 낸다.
        self._그늘 = self.create_oval(
            0, 0, 0, 0, fill=theme.그늘(바탕색, 0.22), outline=""
        )
        self._손잡이 = self.create_oval(
            0, 0, 0, 0, fill=theme.카드, outline=theme.파랑, width=2
        )
        self._가운데 = 가운데
        self.bind("<Button-1>", self._끌기)
        self.bind("<B1-Motion>", self._끌기)
        self.그리기()

    def 그리기(self) -> None:
        자리 = layout.미끄럼자리(self._값, self._왼쪽, self._오른쪽, self._최소, self._최대)
        절반 = self._손잡이지름 / 2
        self.coords(
            self._채움,
            *layout.둥근네모점들(
                self._왼쪽,
                self._가운데 - 3.5,
                max(자리, self._왼쪽 + 1),
                self._가운데 + 3.5,
                3.5,
            ),
        )
        self.coords(
            self._그늘,
            자리 - 절반,
            self._가운데 - 절반 + 1.5,
            자리 + 절반,
            self._가운데 + 절반 + 1.5,
        )
        self.coords(
            self._손잡이,
            자리 - 절반,
            self._가운데 - 절반,
            자리 + 절반,
            self._가운데 + 절반,
        )

    def 값넣기(self, 값: float) -> None:
        self._값 = min(self._최대, max(self._최소, 값))
        self.그리기()

    def _끌기(self, 사건: Any) -> None:
        self._값 = layout.미끄럼값(
            사건.x, self._왼쪽, self._오른쪽, self._최소, self._최대
        )
        self.그리기()
        self._바뀜(self._값)


class 둥근칸(tk.Canvas):
    """둥근 흰 상자. 안쪽 `속` 프레임에 위젯을 넣는다. (검색칸에 쓴다)"""

    def __init__(
        self,
        부모: tk.Misc,
        높이: int = 34,
        바탕색: str = theme.바탕,
        안색: str = theme.카드,
        옆여백: int = 12,
        그늘: bool = False,
    ) -> None:
        super().__init__(
            부모, height=높이, bg=바탕색, highlightthickness=0, bd=0, takefocus=0
        )
        self._높이 = 높이
        self._안색 = 안색
        self._옆여백 = 옆여백
        self._그늘 = 그늘
        self._그린것: list[int] = []
        self._네모: int | None = None
        self.속 = tk.Frame(self, bg=안색)
        self._창 = self.create_window(옆여백, 5, window=self.속, anchor="nw")
        self.bind("<Configure>", self._크기바뀜)

    def _크기바뀜(self, 사건: Any) -> None:
        for 하나 in self._그린것:
            self.delete(하나)
        self._그린것 = []
        if self._네모 is not None:
            self.delete(self._네모)
        if self._그늘:
            self._그린것 = 그림자(
                self,
                1,
                1,
                사건.width - 1,
                self._높이 - 2,
                (self._높이 - 1) / 2,
                self["bg"],
                겹=2,
                번짐=2.0,
            )
        self._네모 = 둥근네모(
            self,
            0.5,
            0.5,
            사건.width - 0.5,
            self._높이 - 0.5,
            (self._높이 - 1) / 2,
            fill=self._안색,
            outline="",
        )
        self.tag_lower(self._네모)
        for 하나 in self._그린것:
            self.tag_lower(하나)
        self.itemconfigure(
            self._창,
            width=max(10, 사건.width - self._옆여백 * 2),
            height=self._높이 - 10,
        )


class 둥근상자(tk.Frame):
    """크기에 따라 늘어나는 둥근 채움 상자. 안쪽 `속` 에 위젯을 넣는다.

    `둥근칸` 은 높이가 고정이라 한 줄 입력칸에만 쓴다. 여러 줄 입력·결과처럼
    남는 자리를 다 쓰는 칸은 이것을 쓴다. (캔버스 위에 프레임을 얹는다)
    """

    def __init__(
        self,
        부모: tk.Misc,
        바탕색: str = theme.카드,
        안색: str = theme.입력칸,
        반경: int = 12,
        안여백: int = 3,
    ) -> None:
        super().__init__(부모, bg=바탕색)
        self._반경, self._안색, self._안여백 = 반경, 안색, 안여백
        self.캔버스 = tk.Canvas(
            self, bg=바탕색, highlightthickness=0, bd=0, height=40, width=40
        )
        self.캔버스.pack(fill="both", expand=True)
        self.속 = tk.Frame(self.캔버스, bg=안색)
        self._창 = self.캔버스.create_window(안여백, 안여백, window=self.속, anchor="nw")
        self._네모: int | None = None
        self.캔버스.bind("<Configure>", self._크기바뀜)

    def _크기바뀜(self, 사건: Any) -> None:
        if self._네모 is not None:
            self.캔버스.delete(self._네모)
        self._네모 = 둥근네모(
            self.캔버스,
            0.5,
            0.5,
            사건.width - 0.5,
            사건.height - 0.5,
            self._반경,
            fill=self._안색,
            outline="",
        )
        self.캔버스.tag_lower(self._네모)
        self.캔버스.itemconfigure(
            self._창,
            width=max(10, 사건.width - self._안여백 * 2),
            height=max(10, 사건.height - self._안여백 * 2),
        )


class 고르는칸(tk.Canvas):
    """직접 그린 고르기 칸(드롭다운). `.get()` 으로 고른 값을 준다.

    `ttk.Combobox` 는 clam 테마에서도 네모난 화살표 단추와 각진 칸이 그대로라,
    이 화면에서 혼자 옛 프로그램처럼 보였다. 그래서 칸은 캔버스로 그리고,
    목록은 테두리 없는 작은 창(`Toplevel`)에 둥근 카드로 띄운다.
    """

    def __init__(
        self,
        부모: tk.Misc,
        값들: list[str],
        값: str = "",
        바탕색: str = theme.카드,
        높이: int = 34,
        옆여백: int = 12,
    ) -> None:
        super().__init__(
            부모,
            height=높이,
            bg=바탕색,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=0,
        )
        self._값들 = list(값들)
        self._값 = 값 if 값 in self._값들 else (self._값들[0] if self._값들 else "")
        self._높이 = 높이
        self._옆여백 = 옆여백
        self._글꼴 = tkfont.Font(family=theme.글꼴, size=10)
        self._네모: int | None = None
        self._글: int | None = None
        self._꺽쇠: list[int] = []
        self._목록창: tk.Toplevel | None = None
        self.bind("<Configure>", self._크기바뀜)
        self.bind("<Button-1>", lambda _사건: self.펼치기())

    # ------------------------------------------------------------ 칸 그리기
    def _크기바뀜(self, 사건: Any) -> None:
        for 하나 in [self._네모, self._글, *self._꺽쇠]:
            if 하나 is not None:
                self.delete(하나)
        self._네모 = 둥근네모(
            self,
            0.5,
            0.5,
            사건.width - 0.5,
            self._높이 - 0.5,
            self._높이 * 0.35,
            fill=theme.입력칸,
            outline="",
        )
        self._글 = self.create_text(
            self._옆여백,
            self._높이 / 2,
            text=self._값,
            anchor="w",
            font=self._글꼴,
            fill=theme.진한글,
        )
        꺽 = 사건.width - self._옆여백 - 4
        가운데 = self._높이 / 2
        self._꺽쇠 = [
            self.create_line(
                꺽 - 8,
                가운데 - 2,
                꺽 - 4,
                가운데 + 2.5,
                꺽,
                가운데 - 2,
                fill=theme.파랑,
                width=2,
                capstyle="round",
            )
        ]

    def get(self) -> str:  # noqa: N802 - 다른 입력칸(tk 변수)과 이름을 맞춘다
        return self._값

    def 값넣기(self, 값: str) -> None:
        self._값 = 값
        if self._글 is not None:
            self.itemconfigure(self._글, text=값)

    # ------------------------------------------------------------ 목록 띄우기
    def 펼치기(self) -> None:
        if self._목록창 is not None or not self._값들:
            self.접기()
            return
        줄높이 = 30
        폭 = max(self.winfo_width(), 120)
        높이 = 줄높이 * len(self._값들) + 10

        창 = tk.Toplevel(self)
        창.overrideredirect(True)  # 제목줄 없는 작은 창
        # 주 창이 '항상 위'(-topmost)면, topmost 가 아닌 목록은 주 창 **뒤에** 열린다.
        # 그러면 grab 이 걸려 있어 아무 클릭도 안 먹어 화면이 멈춘 것처럼 보인다.
        # 그래서 목록도 위로 띄우고, 부모 창에 딸린 창으로 표시한다.
        try:
            창.attributes("-topmost", True)
        except tk.TclError:  # pragma: no cover - 일부 플랫폼
            pass
        try:
            창.transient(self.winfo_toplevel())
        except tk.TclError:  # pragma: no cover
            pass
        창.configure(bg=theme.카드)
        창.geometry(
            f"{폭}x{높이}+{self.winfo_rootx()}+{self.winfo_rooty() + self._높이 + 3}"
        )
        판 = tk.Canvas(창, bg=theme.카드, highlightthickness=0, bd=0)
        판.pack(fill="both", expand=True)
        둥근네모(
            판,
            0.5,
            0.5,
            폭 - 0.5,
            높이 - 0.5,
            12,
            fill=theme.카드,
            outline=theme.섞기(theme.흐린글, theme.카드, 0.32),
        )

        self._칸들: list[tuple[int, int, str]] = []
        for 번, 하나 in enumerate(self._값들):
            위 = 5 + 번 * 줄높이
            고름 = 하나 == self._값
            네모 = 둥근네모(
                판,
                5,
                위,
                폭 - 5,
                위 + 줄높이 - 2,
                8,
                fill=theme.파랑옅게 if 고름 else theme.카드,
                outline="",
            )
            글 = 판.create_text(
                14,
                위 + (줄높이 - 2) / 2,
                text=하나,
                anchor="w",
                font=self._글꼴,
                fill=theme.파랑 if 고름 else theme.진한글,
            )
            self._칸들.append((네모, 글, 하나))

        판.bind("<Button-1>", lambda 사건: self._골랐다(사건, 판, 줄높이))
        판.bind("<Motion>", lambda 사건: self._가리킴(사건, 판, 줄높이))
        창.bind("<Escape>", lambda _사건: self.접기())
        창.lift()
        self._목록창 = 창
        # 바깥을 누르면 닫는다. 잡기(grab)는 쓰지 않는다 — 제목줄 없는(overrideredirect)
        # 창은 잡기 focus 를 못 받는 환경이 있어, 잡기만 걸린 채 아무 클릭도 안 먹어
        # 화면이 얼어붙는다(특히 주 창이 '항상 위' 일 때). 대신 앱 전체 클릭을 잠깐
        # 엿보다가, 목록 밖을 누르면 접는다.
        self._바깥표 = self.bind_all("<Button-1>", self._바깥눌림, add="+")

    def _몇번째(self, 사건: Any, 줄높이: int) -> int | None:
        번 = int((사건.y - 5) // 줄높이)
        return 번 if 0 <= 번 < len(self._값들) else None

    def _가리킴(self, 사건: Any, 판: tk.Canvas, 줄높이: int) -> None:
        지금 = self._몇번째(사건, 줄높이)
        for 번, (네모, 글, 하나) in enumerate(self._칸들):
            고름 = 하나 == self._값
            가리킴 = 번 == 지금
            판.itemconfigure(
                네모,
                fill=theme.파랑옅게 if (고름 or 가리킴) else theme.카드,
            )
            판.itemconfigure(글, fill=theme.파랑 if (고름 or 가리킴) else theme.진한글)

    def _골랐다(self, 사건: Any, _판: tk.Canvas, 줄높이: int) -> None:
        번 = self._몇번째(사건, 줄높이)
        if 번 is not None:
            self.값넣기(self._값들[번])
        self.접기()

    def _바깥눌림(self, 사건: Any) -> None:
        """목록 밖을 누르면 접는다. (목록 안 클릭은 `_골랐다` 가 처리한다)"""
        창 = self._목록창
        if 창 is None:
            return
        누른것 = getattr(사건, "widget", None)
        마디 = 누른것
        while 마디 is not None:
            if 마디 is 창:
                return  # 목록 안을 눌렀다 → 그대로 둔다
            마디 = getattr(마디, "master", None)
        self.접기()

    def 접기(self) -> None:
        창, self._목록창 = self._목록창, None
        표, self._바깥표 = getattr(self, "_바깥표", None), None
        if 표 is not None:
            try:
                self.unbind_all("<Button-1>")  # 우리 감시를 떼고
            except tk.TclError:  # pragma: no cover
                pass
        if 창 is not None:
            창.destroy()


class 타일(tk.Canvas):
    """기능 하나를 나타내는 둥근 흰 카드.

    카드 하나가 위젯 하나(캔버스)라서, 안쪽 글자로 마우스가 옮겨 가도 `<Leave>`
    가 새어 나오지 않는다. 그림은 카드 → 아이콘 배지 → 제목 → 딱지 차례로 얹는다.
    """

    def __init__(
        self,
        부모: tk.Misc,
        명령하나: Any,
        크기: int,
        누름: Callable[[Any], None],
        가리킴: Callable[[Any | None], None],
        바퀴: Callable[[Any], Any],
    ) -> None:
        super().__init__(
            부모,
            width=크기,
            height=크기,
            bg=theme.바탕,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=0,
        )
        self.명령 = 명령하나
        _글머리, 강조 = theme.분류모습(명령하나.분류)  # 색만 쓴다 (아이콘은 선으로 그린다)
        self._강조 = 강조
        self._골라짐 = False

        여백 = max(4,크기 // 18)
        안쪽 = 크기 - 여백
        반경 = max(11, int(크기 * 0.21))
        그림자(self, 여백, 여백, 안쪽, 안쪽, 반경, theme.바탕)
        self._카드 = 둥근네모(
            self, 여백, 여백, 안쪽, 안쪽, 반경, fill=theme.카드, outline=""
        )

        배지 = max(20, int(크기 * 0.31))
        배지위 = 여백 + max(5, int(크기 * 0.08))
        가운데 = 크기 / 2
        self._배지 = 둥근네모(
            self,
            가운데 - 배지 / 2,
            배지위,
            가운데 + 배지 / 2,
            배지위 + 배지,
            max(7, int(배지 * 0.32)),
            fill=theme.배지색(강조),
            outline="",
        )
        # 글자 기호(`§`, `▦`)는 글꼴에 따라 획 굵기가 제멋대로여서 오래돼 보인다.
        # 같은 굵기의 선 아이콘을 직접 그린다.
        self._아이콘 = icons.그리기(
            self,
            icons.분류아이콘(명령하나.분류),
            가운데,
            배지위 + 배지 / 2,
            배지 * 0.52,
            강조,
        )

        self._제목 = self.create_text(
            가운데,
            배지위 + 배지 + max(5, 크기 // 16),
            # 줄은 `layout.제목자르기` 가 미리 접어 준다. 캔버스 자동 줄바꿈에
            # 맡기면 띄어쓰기 자리에서 세 줄이 되어 아래 딱지를 가린다.
            text=layout.제목자르기(명령하나.제목, 크기),
            anchor="n",
            justify="center",
            fill=theme.진한글,
            font=(theme.글꼴, 9 if 크기 >= 96 else 8),
        )

        if 명령하나.필요:
            self._딱지그리기(크기, 여백, 안쪽, 가운데, 명령하나.필요)

        self.bind("<Button-1>", lambda _사건: 누름(명령하나))
        self.bind("<Enter>", lambda _사건: self._들어옴(가리킴))
        self.bind("<Leave>", lambda _사건: self._나감(가리킴))
        바퀴묶기(self, 바퀴)

    def _딱지그리기(
        self, 크기: int, 여백: int, 안쪽: int, 가운데: float, 필요: tuple[str, ...]
    ) -> None:
        """'선택·표 필요' 표시 — 큰 타일은 글자로, 작은 타일은 점으로."""
        if layout.딱지방식(크기) == "글자":
            self.create_text(
                가운데,
                안쪽 - 5,
                text="·".join(필요) + " 필요",
                anchor="s",
                fill=theme.흐린글,
                font=(theme.글꼴, 7),
            )
            return
        점 = 5
        오른쪽 = 안쪽 - 8
        self.create_oval(
            오른쪽 - 점, 여백 + 8, 오른쪽, 여백 + 8 + 점, fill=self._강조, outline=""
        )

    def 고르기(self, 참: bool) -> None:
        """고른 타일에 파란 테를 두른다.

        세부설정을 아래쪽에 띄워 둔 채 격자를 그대로 보여 주므로, 지금 어느
        기능을 만지고 있는지 카드로 알 수 있어야 한다.
        """
        참 = bool(참)
        if 참 == self._골라짐:
            return
        self._골라짐 = 참
        self._칠하기()

    def _칠하기(self, 가리킴중: bool = False) -> None:
        """시안대로 — 고르면 카드는 흰 채로 파란 테를 두르고, **배지가 꽉 찬다.**"""
        if self._골라짐:
            # 고른 상태는 분류색이 아니라 **주 파랑**으로 칠한다(시안). 지금
            # 만지는 것이 하나라는 뜻이므로 분류보다 그 사실이 먼저 보여야 한다.
            self.itemconfigure(self._카드, fill=theme.카드, outline=theme.파랑, width=2)
            self.itemconfigure(self._배지, fill=theme.파랑)
            icons.색칠(self, self._아이콘, theme.카드)
            self.itemconfigure(self._제목, fill=theme.파랑)
            return
        self.itemconfigure(
            self._카드,
            fill=theme.카드가리킴 if 가리킴중 else theme.카드,
            outline="",
            width=1,
        )
        self.itemconfigure(self._배지, fill=theme.배지색(self._강조))
        icons.색칠(self, self._아이콘, self._강조)
        self.itemconfigure(self._제목, fill=theme.진한글)

    def _들어옴(self, 가리킴: Callable[[Any | None], None]) -> None:
        self._칠하기(가리킴중=True)
        가리킴(self.명령)

    def _나감(self, 가리킴: Callable[[Any | None], None]) -> None:
        self._칠하기()
        가리킴(None)
