"""직접 그린 위젯 — 둥근 카드·알약 단추·기능 타일.

tkinter 기본 위젯은 모서리가 각지고 테두리가 굵어, 토스 같은 화면을 만들 수
없다. 그래서 눈에 많이 띄는 것들(기능 타일·분류 칩·검색칸)은 캔버스에 직접
그린다. 모서리를 깎는 계산은 `layout.둥근네모점들` 에 있다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Callable

from . import layout, theme

__all__ = ["둥근네모", "알약단추", "켬끔", "미끄럼자", "둥근칸", "타일"]


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
        else:
            바탕 = theme.파랑옅게 if self._가리킴 else theme.카드
            글색 = theme.파랑 if self._가리킴 else theme.보통글
        self.itemconfigure(self._알약, fill=바탕)
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
    ) -> None:
        self._켠글, self._끈글 = 켠글, 끈글
        self._켜짐 = bool(켜짐)
        재는글꼴 = tkfont.Font(family=theme.글꼴, size=9)
        너비 = max(재는글꼴.measure(켠글), 재는글꼴.measure(끈글)) + 안여백 * 2
        super().__init__(
            부모,
            켠글 if self._켜짐 else 끈글,
            누름=self._뒤집기,
            골라짐=self._켜짐,
            높이=높이,
            안여백=안여백,
            최소너비=너비,
        )

    def _뒤집기(self) -> None:
        self._켜짐 = not self._켜짐
        self.글바꾸기(self._켠글 if self._켜짐 else self._끈글)
        self.고르기(self._켜짐)

    def get(self) -> bool:  # noqa: N802 - 다른 입력칸(tk 변수)과 이름을 맞춘다
        return self._켜짐


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
        self._손잡이지름 = 15
        self._왼쪽 = self._손잡이지름 / 2
        self._오른쪽 = 너비 - self._손잡이지름 / 2
        가운데 = 높이 / 2

        둥근네모(self, self._왼쪽, 가운데 - 3, self._오른쪽, 가운데 + 3, 3, fill=theme.테두리, outline="")
        self._채움 = 둥근네모(
            self, self._왼쪽, 가운데 - 3, self._왼쪽 + 1, 가운데 + 3, 3, fill=theme.파랑, outline=""
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
            *layout.둥근네모점들(self._왼쪽, self._가운데 - 3, max(자리, self._왼쪽 + 1), self._가운데 + 3, 3),
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
    ) -> None:
        super().__init__(
            부모, height=높이, bg=바탕색, highlightthickness=0, bd=0, takefocus=0
        )
        self._높이 = 높이
        self._안색 = 안색
        self._옆여백 = 옆여백
        self._네모: int | None = None
        self.속 = tk.Frame(self, bg=안색)
        self._창 = self.create_window(옆여백, 5, window=self.속, anchor="nw")
        self.bind("<Configure>", self._크기바뀜)

    def _크기바뀜(self, 사건: Any) -> None:
        if self._네모 is not None:
            self.delete(self._네모)
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
        self.itemconfigure(
            self._창,
            width=max(10, 사건.width - self._옆여백 * 2),
            height=self._높이 - 10,
        )


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
        글머리, 강조 = theme.분류모습(명령하나.분류)
        self._강조 = 강조

        여백 = max(2, 크기 // 26)
        안쪽 = 크기 - 여백
        self._카드 = 둥근네모(
            self, 여백, 여백, 안쪽, 안쪽, max(8, int(크기 * 0.17)), fill=theme.카드, outline=""
        )

        배지 = max(20, int(크기 * 0.30))
        배지위 = 여백 + max(6, int(크기 * 0.09))
        가운데 = 크기 / 2
        둥근네모(
            self,
            가운데 - 배지 / 2,
            배지위,
            가운데 + 배지 / 2,
            배지위 + 배지,
            max(6, int(배지 * 0.34)),
            fill=theme.배지색(강조),
            outline="",
        )
        self.create_text(
            가운데,
            배지위 + 배지 / 2,
            text=글머리,
            fill=강조,
            font=(theme.글꼴, max(9, int(배지 * 0.5))),
        )

        self.create_text(
            가운데,
            배지위 + 배지 + max(4, 크기 // 18),
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

    def _들어옴(self, 가리킴: Callable[[Any | None], None]) -> None:
        self.itemconfigure(self._카드, fill=theme.카드가리킴)
        가리킴(self.명령)

    def _나감(self, 가리킴: Callable[[Any | None], None]) -> None:
        self.itemconfigure(self._카드, fill=theme.카드)
        가리킴(None)
