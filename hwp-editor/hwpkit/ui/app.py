"""화면 — 화면 가장자리에 붙는 사이드 패널 + 기능 타일 격자.

원본 UI
    · 창 100개 이상(기능마다 Toplevel), 탭 19개, 버튼 PNG 이미지 17MB
    · 버튼 위치를 좌표로 직접 지정(x=150, y=300 …)
    · 한/글 창을 가려서, 문서를 보며 기능을 누르기 어려웠다

바뀐 화면
    · **사이드 패널**: 상·하·좌·우 중 하나를 골라 화면 가장자리에 붙인다.
      한/글 문서를 옆에 두고 쓰라고 만든 자리다. 고른 자리는 다음에도 기억한다.
    · **항상 위 · 투명도**: 문서를 가리지 않게 늘 위에 띄우고, 옅게 비쳐 보이게
      할 수 있다. 둘 다 도구줄에서 바로 조절한다.
    · **타일 격자**: 주요 기능을 둥근 흰 카드로 늘어놓는다. 분류마다 아이콘 배지
      색이 달라, 목록을 읽지 않고 눈으로 찾는다. 패널 너비에 맞춰 칸 수가 저절로
      바뀌고, 타일 크기는 '칸' 단추로 세 단계로 바꾼다.
    · 검색칸에 낱말을 넣으면 타일이 즉시 걸러진다(명령 팔레트).
    · 타일을 누르면 **격자를 그대로 둔 채 아래쪽에 세부설정 판**이 열린다. 고른
      타일에는 파란 테가 둘려, 무엇을 만지는 중인지 한눈에 보인다. 입력칸은
      `commands.입력항목` 정의만 보고 자동으로 만든다 — 기능마다 창을 따로
      만들지 않는다.

배색·모양은 받은 시안(ProDoc Assistant)을 따랐다(`theme.py`) — 살짝 파란 바탕,
흰 카드, 진한 남색빛 파랑 하나, **테두리 대신 옅은 파랑으로 채운 입력칸**, 옅은
그림자로 만드는 깊이(`theme.그늘`).

ttk 위젯은 clam 테마에서도 각진 칸과 네모난 화살표 단추가 그대로여서, 눈에 띄는
것은 모두 캔버스에 직접 그린다(`widgets.py`) — 카드·칩·채운 단추·고르기 칸·
토막 고르기·미끄럼자·시트 손잡이·돋보기. 분류 아이콘도 글자 기호 대신 선으로
그린다(`icons.py`). 창 자리·칸 수 같은 계산은 `layout.py` 에 따로 두어 tkinter
없이 시험한다.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Callable

from .. import commands
from ..core.connection import 사용가능, 한글연결
from ..core.document import 문서
from ..core.errors import 오류풀이, 한글오류
from . import layout, theme
from .widgets import (
    고르는칸,
    돋보기,
    켬끔,
    둥근칸,
    둥근상자,
    미끄럼자,
    바퀴묶기,
    알약단추,
    잡이,
    채운단추,
    타일,
    토막고르기,
)

__all__ = ["실행하기", "본창"]

_제목 = "한글 문서 도우미"
_자리글 = "기능 검색 (예: 표, 콤마, PDF)"

class 스크롤틀(tk.Frame):
    """세로로 구르는 상자. 안쪽 `내용` 프레임에 위젯을 넣는다."""

    def __init__(self, 부모: tk.Misc, 바탕색: str = theme.바탕) -> None:
        super().__init__(부모, bg=바탕색)
        # 캔버스 기본 크기(265픽셀)를 그대로 두면 grid 에서 그만큼 자리를 먼저
        # 차지해 버려, 몫(weight)을 아무리 줘도 다른 칸이 밀린다. 작게 요청하고
        # 남는 자리는 sticky·weight 로 받는다.
        self.캔버스 = tk.Canvas(
            self, bg=바탕색, highlightthickness=0, bd=0, height=60, width=60
        )
        self.띠 = ttk.Scrollbar(self, orient="vertical", command=self.캔버스.yview)
        self.캔버스.configure(yscrollcommand=self.띠.set)
        self.캔버스.pack(side="left", fill="both", expand=True)
        self.띠.pack(side="right", fill="y")

        self.내용 = tk.Frame(self.캔버스, bg=바탕색)
        self._창 = self.캔버스.create_window((0, 0), window=self.내용, anchor="nw")
        self.내용.bind("<Configure>", self._내용바뀜)
        self.캔버스.bind("<Configure>", self._캔버스바뀜)

        self.너비알림: Callable[[int], None] | None = None
        바퀴묶기(self.캔버스, self.바퀴)
        바퀴묶기(self.내용, self.바퀴)

    def _내용바뀜(self, _사건: Any = None) -> None:
        self.캔버스.configure(scrollregion=self.캔버스.bbox("all"))

    def _캔버스바뀜(self, 사건: Any) -> None:
        self.캔버스.itemconfigure(self._창, width=사건.width)
        if self.너비알림 is not None:
            self.너비알림(사건.width)

    def 바퀴(self, 사건: Any) -> str:
        번호 = getattr(사건, "num", None)
        if 번호 == 4:
            걸음 = -1
        elif 번호 == 5:
            걸음 = 1
        else:
            걸음 = -1 if getattr(사건, "delta", 0) > 0 else 1
        self.캔버스.yview_scroll(걸음, "units")
        return "break"

    def 맨위로(self) -> None:
        self.캔버스.yview_moveto(0.0)


class 본창(tk.Tk):
    """가장자리에 붙는 사이드 패널 한 장."""

    def __init__(self) -> None:
        super().__init__()
        self.title(_제목)
        self.configure(bg=theme.바탕)

        self.설정 = layout.설정불러오기()
        self.자리 = self.설정["자리"]
        self.타일크기 = self.설정["타일크기"]
        self.항상위 = bool(self.설정["항상위"])
        self.투명도 = layout.투명도다듬기(self.설정["투명도"])

        self.문서객체 = 문서(한글연결())
        self.현재명령: commands.명령 | None = None
        self._입력위젯: dict[str, tuple[commands.입력항목, Any]] = {}
        self._알림큐: queue.Queue[str] = queue.Queue()
        self._끝큐: queue.Queue[tuple[commands.명령, str]] = queue.Queue()
        self._타일들: list[타일] = []
        self._보이는명령: list[commands.명령] = []
        self._칸 = 1
        self._칩줄: list[list[int]] | None = None
        self._자리글보임 = True
        self._기본상태 = "준비"

        self._스타일()
        self._뼈대()
        self._자리적용()
        self._타일채우기()
        self.protocol("WM_DELETE_WINDOW", self._닫기)
        self.after(100, self._큐확인)
        self._연결확인()

    # ------------------------------------------------------------------ 꾸밈
    def _스타일(self) -> None:
        스타일 = ttk.Style(self)
        테마 = "clam" if "clam" in 스타일.theme_names() else 스타일.theme_use()
        스타일.theme_use(테마)
        self.option_add("*Font", (theme.글꼴, 10))

        스타일.configure("TFrame", background=theme.바탕)
        스타일.configure("TLabel", background=theme.바탕, foreground=theme.진한글)
        # 입력칸은 테두리로 가두지 않고 **옅은 파랑으로 채운다**(시안 방식).
        스타일.configure(
            "TEntry",
            fieldbackground=theme.입력칸,
            foreground=theme.진한글,
            bordercolor=theme.입력칸,
            lightcolor=theme.입력칸,
            darkcolor=theme.입력칸,
            borderwidth=0,
            padding=7,
        )
        # 고르기 칸(드롭다운)과 단추는 ttk 로는 모서리가 각지고 화살표 단추가
        # 네모나게 붙어 옛 프로그램처럼 보인다. 캔버스에 직접 그린다
        # (`widgets.고르는칸` · `widgets.채운단추`).
        # 구르는 띠 — 위아래 화살표 단추를 없애고 가늘게 만든다. 기본 clam 띠는
        # 화살표가 붙은 굵은 막대라 이 화면에서 혼자 튄다.
        스타일.layout(
            "Vertical.TScrollbar",
            [
                (
                    "Vertical.Scrollbar.trough",
                    {
                        "sticky": "ns",
                        "children": [
                            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
                        ],
                    },
                )
            ],
        )
        스타일.configure(
            "Vertical.TScrollbar",
            background=theme.섞기(theme.흐린글, theme.바탕, 0.35),
            troughcolor=theme.바탕,
            bordercolor=theme.바탕,
            lightcolor=theme.바탕,
            darkcolor=theme.바탕,
            borderwidth=0,
            width=7,
        )
        스타일.map(
            "Vertical.TScrollbar",
            background=[("active", theme.섞기(theme.흐린글, theme.바탕, 0.6))],
        )

    # ------------------------------------------------------------------ 뼈대
    def _뼈대(self) -> None:
        """머리 / 분류 칩 / [타일 격자 + 아래쪽 세부설정] / 상태줄.

        타일을 눌러도 격자를 치우지 않는다. 격자는 그대로 두고 **아래쪽 빈자리에**
        세부설정 판을 띄운다(칸 몫은 `layout.격자칸높이`). 예전에는 같은 자리에
        실행판을 겹쳐 올려(`tkraise`) 격자가 사라졌는데, 그러면 어느 기능을
        골랐는지 다시 목록으로 나가야 알 수 있었다.
        """
        self._머리만들기()
        # 상태줄을 **먼저** 아래에 붙인다. 가운데(격자+세부설정)가 요구하는 높이가
        # 창보다 커지는 순간, 나중에 붙인 것부터 잘려 상태줄이 사라진다.
        self.상태값 = tk.StringVar(value=self._기본상태)
        tk.Label(
            self,
            textvariable=self.상태값,
            bg=theme.바탕,
            fg=theme.흐린글,
            anchor="w",
            font=(theme.글꼴, 9),
        ).pack(side="bottom", fill="x", padx=10, pady=(2, 4))

        self.가운데 = tk.Frame(self, bg=theme.바탕)
        self.가운데.pack(fill="both", expand=True)
        self.가운데.grid_rowconfigure(0, weight=1)  # 타일 격자
        self.가운데.grid_rowconfigure(1, weight=0)  # 세부설정 (고를 때만 보인다)
        self.가운데.grid_columnconfigure(0, weight=1)
        self._격자만들기()
        self._실행판만들기()
        self.격자틀.grid(row=0, column=0, sticky="nsew")
        self.실행판.grid(row=1, column=0, sticky="nsew")
        self.실행판.grid_remove()  # 타일을 누를 때까지 감춘다

    def _머리만들기(self) -> None:
        # (1) 앱바 — 이름표와 붙일 자리. 시안처럼 **흰 띠**로 두고 아래에 옅은
        #     그림자를 깔아, 아래 내용이 그 밑으로 흐르는 느낌을 낸다.
        self.앱바 = tk.Frame(self, bg=theme.카드)
        self.앱바.pack(fill="x")
        속앱바 = tk.Frame(self.앱바, bg=theme.카드)
        속앱바.pack(fill="x", padx=12, pady=(9, 9))
        tk.Label(
            속앱바,
            text=_제목,
            bg=theme.카드,
            fg=theme.파랑,  # 시안의 파란 이름표
            font=(theme.글꼴, 13, "bold"),
        ).pack(side="left")
        self._자리고르기 = 토막고르기(
            속앱바,
            list(layout.자리들),
            값=self.자리,
            바뀜=self._자리바꾸기,
            바탕색=theme.카드,
            높이=26,
            안여백=10,
        )
        self._자리고르기.pack(side="right")
        self._도움말묶기(self._자리고르기, "패널을 화면 왼쪽·오른쪽 중 한 곳에 붙입니다.")
        self._앱바그늘 = tk.Canvas(
            self, height=5, bg=theme.바탕, highlightthickness=0, bd=0
        )
        self._앱바그늘.pack(fill="x")
        self._앱바그늘.bind("<Configure>", self._앱바그늘그리기)

        self.머리 = tk.Frame(self, bg=theme.바탕)
        self.머리.pack(fill="x", padx=8, pady=(5, 0))

        # (2) 검색칸
        self.검색틀 = 둥근칸(self.머리, 높이=34, 그늘=True)
        self.검색값 = tk.StringVar(value=_자리글)
        돋보기(self.검색틀.속).pack(side="left", padx=(0, 7))
        self.검색칸 = tk.Entry(
            self.검색틀.속,
            textvariable=self.검색값,
            bg=theme.카드,
            fg=theme.흐린글,
            relief="flat",
            highlightthickness=0,
            insertbackground=theme.진한글,
            font=(theme.글꼴, 10),
        )
        self.검색칸.pack(side="left", fill="both", expand=True)
        self.검색칸.bind("<KeyRelease>", lambda _사건: self._타일채우기())
        self.검색칸.bind("<FocusIn>", self._자리글치우기)
        self.검색칸.bind("<FocusOut>", self._자리글되돌리기)
        self.검색칸.bind("<Escape>", lambda _사건: self._검색지우기())
        self._지움표 = tk.Label(
            self.검색틀.속,
            text="✕",
            bg=theme.카드,
            fg=theme.흐린글,
            font=(theme.글꼴, 10),
            cursor="hand2",
        )
        self._지움표.bind("<Button-1>", lambda _사건: self._검색지우기())

        self.검색틀.pack(fill="x")

        # (3) 도구 — 타일 크기 · 항상 위 · 투명도
        self.도구틀 = tk.Frame(self.머리, bg=theme.바탕)
        self.도구틀.pack(fill="x", pady=(5, 0))
        self.칸단추 = 알약단추(
            self.도구틀, self._칸이름(), 누름=self._타일크기바꾸기, 높이=26, 안여백=10
        )
        self.칸단추.pack(side="left")
        self._도움말묶기(self.칸단추, "타일 크기를 작게·보통·크게로 바꿉니다.")

        self.위단추 = 알약단추(
            self.도구틀,
            "항상 위",
            누름=self._항상위바꾸기,
            골라짐=self.항상위,
            높이=26,
            안여백=10,
        )
        self.위단추.pack(side="left", padx=(6, 0))
        self._도움말묶기(self.위단추, "다른 창 위에 늘 띄워 둡니다. (한/글을 가리지 않게)")

        투명틀 = tk.Frame(self.도구틀, bg=theme.바탕)
        투명틀.pack(side="left", padx=(10, 0))
        tk.Label(
            투명틀, text="투명도", bg=theme.바탕, fg=theme.흐린글, font=(theme.글꼴, 9)
        ).pack(side="left")
        self.투명자 = 미끄럼자(
            투명틀,
            최소=layout.최소투명도,
            최대=100,
            값=self.투명도,
            바뀜=self._투명도적용,
            너비=88,
        )
        self.투명자.pack(side="left", padx=6)
        self.투명표시 = tk.Label(
            투명틀,
            text=f"{self.투명도}%",
            bg=theme.바탕,
            fg=theme.보통글,
            font=(theme.글꼴, 9),
            width=4,
            anchor="e",
        )
        self.투명표시.pack(side="left")
        self._도움말묶기(self.투명자, "패널을 옅게 만들어 뒤 문서가 비쳐 보이게 합니다.")

        # (4) 분류 칩 — grid 는 열 너비를 줄끼리 나눠 쓰므로 place 로 놓는다.
        self.분류틀 = tk.Frame(self, bg=theme.바탕, height=30)
        self.분류틀.pack(fill="x", padx=8, pady=(5, 1))
        self.분류 = "전체"
        self._칩들: list[알약단추] = []
        for 이름 in ("전체", *commands.분류순서):
            칩 = 알약단추(
                self.분류틀,
                이름,
                누름=lambda 값=이름: self._분류바꾸기(값),
                골라짐=(이름 == self.분류),
                높이=26,
                안여백=10,
            )
            self._칩들.append(칩)
        self.분류틀.bind("<Configure>", self._칩배치)

    def _격자만들기(self) -> None:
        self.격자틀 = 스크롤틀(self.가운데, theme.바탕)
        self.격자틀.너비알림 = self._격자너비바뀜
        self.격자안 = self.격자틀.내용

    def _실행판만들기(self) -> None:
        """세부설정 판 — 가름선 / 머리 / 설명 / 입력칸 / 실행 단추 / 결과칸.

        격자 아래에 붙는 판이라 위쪽에 가름선을 한 줄 그어 격자와 구분한다.
        칸 몫은 grid 로 나눈다. 입력칸이 짧은 기능이 대부분이라 pack 으로 두면
        가운데가 텅 비고 결과만 아래에 눌려 있었다. 결과 쪽에 더 큰 몫을 준다.
        """
        # 판 자체가 **흰 카드**다(시안). 그래서 안쪽 위젯 바탕도 모두 카드색이다.
        self.실행판 = tk.Frame(self.가운데, bg=theme.카드)
        self.실행판.grid_columnconfigure(0, weight=1)
        # 남는 자리는 입력칸에 먼저 준다. 결과는 넘쳐도 구르면 되지만, 입력칸이
        # 짧으면 어떤 항목이 있는지 보려고 스크롤해야 해서 훨씬 불편하다.
        self.실행판.grid_rowconfigure(3, weight=4, minsize=60)  # 입력칸
        self.실행판.grid_rowconfigure(5, weight=1, minsize=104)  # 결과칸

        잡이(self.실행판, 바탕색=theme.바탕).grid(row=0, column=0, sticky="ew")

        머리 = tk.Frame(self.실행판, bg=theme.카드)
        머리.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 2))
        self.기능제목 = tk.Label(
            머리,
            text="",
            bg=theme.카드,
            fg=theme.진한글,
            font=(theme.글꼴, 12, "bold"),
            anchor="w",
        )
        self.기능제목.pack(side="left", fill="x", expand=True)
        self.닫기표 = tk.Label(
            머리,
            text="✕",
            bg=theme.카드,
            fg=theme.보통글,
            font=(theme.글꼴, 12),
            cursor="hand2",
        )
        self.닫기표.pack(side="right", padx=(6, 0))
        self.닫기표.bind("<Button-1>", lambda _사건: self._세부판닫기())
        self._도움말묶기(self.닫기표, "세부설정을 접습니다.")

        self.기능설명 = tk.Label(
            self.실행판,
            text="",
            bg=theme.카드,
            fg=theme.흐린글,
            anchor="w",
            justify="left",
            wraplength=340,
            font=(theme.글꼴, 9),
        )
        self.기능설명.grid(row=2, column=0, sticky="ew", padx=13)
        self.실행판.bind("<Configure>", self._설명줄맞춤)

        self.입력스크롤 = 스크롤틀(self.실행판, theme.카드)
        self.입력스크롤.grid(row=3, column=0, sticky="nsew", padx=8, pady=(4, 2))
        self.입력틀 = self.입력스크롤.내용

        단추줄 = tk.Frame(self.실행판, bg=theme.카드)
        단추줄.grid(row=4, column=0, sticky="ew", padx=12, pady=(2, 0))
        self.실행단추 = 채운단추(
            단추줄, "실행", 누름=self._실행, 높이=38, 안여백=34, 최소너비=150, 그늘=True
        )
        self.실행단추.pack(side="right")
        self.결과지움 = 채운단추(
            단추줄,
            "결과 지우기",
            누름=lambda: self._결과쓰기(""),
            채움=theme.파랑옅게,
            글색=theme.파랑,
            누른채움=theme.섞기(theme.파랑, theme.카드, 0.22),
            높이=38,
            안여백=18,
            굵게=False,
        )
        self.결과지움.pack(side="left")

        결과틀 = tk.Frame(self.실행판, bg=theme.카드)
        결과틀.grid(row=5, column=0, sticky="nsew", padx=12, pady=(6, 8))
        # '결과' 라는 라벨을 따로 두지 않는다. 머리에 기능 이름이 있고 상자가
        # 하나뿐이라 굳이 한 줄을 더 쓸 이유가 없다.
        결과바깥 = 둥근상자(결과틀, 안색=theme.결과칸)
        결과바깥.pack(fill="both", expand=True)
        결과상자 = 결과바깥.속
        결과띠 = ttk.Scrollbar(결과상자, orient="vertical")
        결과띠.pack(side="right", fill="y")
        self.결과칸 = tk.Text(
            결과상자,
            height=3,
            wrap="word",
            bg=theme.결과칸,
            fg=theme.진한글,
            relief="flat",
            padx=10,
            pady=8,
            highlightthickness=0,
            font=(theme.글꼴, 9),
            yscrollcommand=결과띠.set,
        )
        self.결과칸.pack(side="left", fill="both", expand=True)
        결과띠.configure(command=self.결과칸.yview)
        self.결과칸.configure(state="disabled")

    def _앱바그늘그리기(self, 사건: Any) -> None:
        """앱바 아래로 번지는 옅은 그림자. (tkinter 에 투명도가 없어 줄로 긋는다)"""
        self._앱바그늘.delete("all")
        높이 = max(1, 사건.height)
        for 줄 in range(높이):
            세기 = 0.10 * (1 - 줄 / 높이)
            self._앱바그늘.create_line(
                0, 줄, 사건.width, 줄, fill=theme.그늘(theme.바탕, 세기)
            )

    def _도움말묶기(self, 위젯: tk.Misc, 말: str) -> None:
        """가리키면 아래 상태줄에 설명이 나오게 한다. (풍선 도움말 대신)"""
        위젯.bind("<Enter>", lambda _사건: self.상태값.set(말), add="+")
        위젯.bind("<Leave>", lambda _사건: self.상태값.set(self._기본상태), add="+")

    # ------------------------------------------------------------------ 자리
    def _자리적용(self) -> None:
        두께 = self.설정["두께"].get(self.자리, layout.기본설정["두께"][self.자리])
        self._자리잡기(두께)
        self.minsize(layout.최소두께, 340)
        self._항상위적용()
        self._투명도적용()

    def _자리잡기(self, 두께: int) -> None:
        자리값 = layout.창자리계산(
            self.자리, self.winfo_screenwidth(), self.winfo_screenheight(), 두께
        )
        self.geometry(자리값.지오메트리)

    def _자리바꾸기(self, 이름: str) -> None:
        if 이름 == self.자리:
            return
        self._두께기억()
        self.자리 = 이름
        self._자리고르기.고르기(이름)
        self._자리적용()
        self._칩줄 = None  # 폭이 달라졌으니 칩 줄을 다시 계산한다.
        self._기본상태 = f"패널을 {이름}쪽에 붙였습니다."
        self.상태값.set(self._기본상태)

    def _지금두께(self) -> int:
        return self.winfo_width()  # 좌·우 패널이므로 두께는 곧 너비

    def _두께기억(self) -> None:
        try:
            # 방금 geometry() 로 바꾼 크기는 아직 창에 반영되지 않았을 수 있다.
            # 그대로 읽으면 바뀌기 전 크기가 저장된다.
            self.update_idletasks()
            두께 = self._지금두께()
        except tk.TclError:  # pragma: no cover - 창이 이미 닫힌 경우
            return
        if 두께 and 두께 > 1:
            self.설정["두께"][self.자리] = 두께

    # ------------------------------------------------------------ 항상 위·투명도
    def _항상위바꾸기(self) -> None:
        self.항상위 = not self.항상위
        self.위단추.고르기(self.항상위)
        self._항상위적용()
        self._기본상태 = "항상 위" if self.항상위 else "보통 창"
        self.상태값.set(
            "이제 다른 창 위에 늘 떠 있습니다." if self.항상위 else "항상 위를 껐습니다."
        )

    def _항상위적용(self) -> None:
        try:
            self.attributes("-topmost", bool(self.항상위))
        except tk.TclError:  # pragma: no cover - 지원하지 않는 창 관리자
            pass

    def _투명도적용(self, 값: Any = None) -> None:
        if 값 is not None:
            self.투명도 = layout.투명도다듬기(값)
        self.투명표시.configure(text=f"{self.투명도}%")
        try:
            self.attributes("-alpha", self.투명도 / 100)
        except tk.TclError:  # pragma: no cover - 투명도를 지원하지 않는 환경
            pass

    def _닫기(self) -> None:
        self._두께기억()
        self.설정["자리"] = self.자리
        self.설정["항상위"] = self.항상위
        self.설정["타일크기"] = self.타일크기
        self.설정["투명도"] = self.투명도
        layout.설정저장(self.설정)
        self.destroy()

    # ------------------------------------------------------------------ 검색
    def _검색어(self) -> str:
        """자리글(회색 안내 글)은 검색어로 치지 않는다."""
        return "" if self._자리글보임 else self.검색값.get().strip()

    def _자리글치우기(self, _사건: Any = None) -> None:
        if self._자리글보임:
            self._자리글보임 = False
            self.검색값.set("")
            self.검색칸.configure(fg=theme.진한글)

    def _자리글되돌리기(self, _사건: Any = None) -> None:
        if not self.검색값.get().strip():
            self._자리글보임 = True
            self.검색값.set(_자리글)
            self.검색칸.configure(fg=theme.흐린글)
            self._지움표보이기()

    def _지움표보이기(self) -> None:
        if self._검색어():
            self._지움표.pack(side="right", padx=(6, 0))
        else:
            self._지움표.pack_forget()

    def _검색지우기(self) -> None:
        self._자리글보임 = False
        self.검색값.set("")
        self.검색칸.configure(fg=theme.진한글)
        self._타일채우기()
        self.검색칸.focus_set()

    # ------------------------------------------------------------------ 격자
    def _칩배치(self, _사건: Any = None) -> None:
        가용 = self.분류틀.winfo_width()
        if 가용 <= 1:
            return
        너비들 = [칩.winfo_reqwidth() for 칩 in self._칩들]
        줄들 = layout.줄나누기(너비들, 가용, 사이=6)
        if 줄들 == self._칩줄:
            return  # 줄이 그대로면 다시 놓지 않는다. (높이 조절 → Configure 되돌이 막기)
        self._칩줄 = 줄들
        높이 = max(칩.winfo_reqheight() for 칩 in self._칩들)
        for 줄번호, 줄 in enumerate(줄들):
            가로 = 0
            for 자리 in 줄:
                self._칩들[자리].place(
                    x=가로, y=줄번호 * (높이 + 4), width=너비들[자리], height=높이
                )
                가로 += 너비들[자리] + 6
        self.분류틀.configure(height=len(줄들) * (높이 + 4))

    def _분류바꾸기(self, 이름: str) -> None:
        """분류 칩을 누르면 그 분류의 첫 화면으로 되돌린다.

        실행판을 보던 중이었으면 목록으로 나오고, 검색말도 지우고, 맨 위로
        올린다. 칩을 눌렀는데 엉뚱한 기능의 입력칸이 그대로 떠 있으면
        지금 무엇을 보고 있는지 헷갈린다.
        """
        self.분류 = 이름
        for 칩, 값 in zip(self._칩들, ("전체", *commands.분류순서)):
            칩.고르기(값 == 이름)
        self._자리글되돌리기()
        self._세부판닫기()
        self._타일채우기()
        self.격자틀.맨위로()

    def _격자너비바뀜(self, 너비: int) -> None:
        새칸 = layout.칸수(너비 - 16, self.타일크기, 사이=8)
        if 새칸 != self._칸:
            self._칸 = 새칸
            self._타일배치()
            if self.현재명령 is not None:  # 줄 수가 달라졌으니 칸 몫을 다시 잡는다
                self._세부판맞춤()

    def _칸이름(self) -> str:
        이름들 = {76: "칸 작게", 96: "칸 보통", 120: "칸 크게"}
        return 이름들.get(self.타일크기, "칸")

    def _타일크기바꾸기(self) -> None:
        self.타일크기 = layout.다음타일크기(self.타일크기)
        self.칸단추.글바꾸기(self._칸이름())
        self._칸 = layout.칸수(self.격자틀.캔버스.winfo_width() - 16, self.타일크기, 사이=8)
        self._타일채우기()

    def _타일채우기(self) -> None:
        질의 = self._검색어()
        self._지움표보이기()
        if 질의:
            후보 = commands.검색(질의, 최대=500)  # 잘 맞는 것부터 — 차례를 흩지 않는다.
        else:
            후보 = layout.정렬순서(commands.전체명령(), commands.분류순서)
        if self.분류 != "전체":
            후보 = [하나 for 하나 in 후보 if 하나.분류 == self.분류]

        for 하나 in self._타일들:
            하나.destroy()
        self._보이는명령 = 후보
        self._타일들 = [
            타일(self.격자안, 하나, self.타일크기, self._타일누름, self._가리킴, self.격자틀.바퀴)
            for 하나 in 후보
        ]
        self._타일배치()
        self.격자틀.맨위로()
        if self.현재명령 is not None:
            # 타일을 다시 만들었으니 고른 표시와 칸 몫도 다시 잡는다.
            self._타일고르기(self.현재명령)
            self._세부판맞춤()
        self._기본상태 = f"기능 {len(후보)}개" if 후보 else "찾은 기능이 없습니다."
        self.상태값.set(self._기본상태)

    def _타일배치(self) -> None:
        칸 = max(1, self._칸)
        # 남는 자리를 타일 사이에 고르게 나눠, 한쪽으로 몰리지 않게 한다.
        너비 = self.격자틀.캔버스.winfo_width()
        남음 = max(0, 너비 - 16 - 칸 * (self.타일크기 + 8))
        곁 = min(20, 남음 // (칸 * 2))
        for 자리, 하나 in enumerate(self._타일들):
            하나.grid(row=자리 // 칸, column=자리 % 칸, padx=3 + 곁, pady=3)

    def _가리킴(self, 명령하나: commands.명령 | None) -> None:
        if 명령하나 is None:
            self.상태값.set(self._기본상태)
            return
        설명 = (명령하나.설명 or "").strip()
        self.상태값.set(f"{명령하나.제목} — {설명}" if 설명 else 명령하나.제목)

    # -------------------------------------------------------------- 세부설정 판
    def _타일누름(self, 명령하나: commands.명령) -> None:
        """타일을 누르면 격자는 그대로 두고 아래쪽에 세부설정을 띄운다."""
        self.현재명령 = 명령하나
        self.기능제목.configure(text=명령하나.제목)
        설명 = 명령하나.설명 or ""
        if 명령하나.필요:
            설명 = (설명 + "\n" if 설명 else "") + f"먼저 준비: {', '.join(명령하나.필요)}"
        self.기능설명.configure(text=설명)
        if 설명:
            self.기능설명.grid()
        else:
            self.기능설명.grid_remove()  # 빈 라벨이 한 줄을 먹지 않게
        self._입력만들기(명령하나)
        self._결과쓰기("")
        self.실행판.grid()
        self._타일고르기(명령하나)
        self._세부판맞춤()
        self.입력스크롤.맨위로()
        self._기본상태 = 명령하나.제목
        self.상태값.set(self._기본상태)

    def _타일고르기(self, 명령하나: commands.명령 | None) -> None:
        """고른 타일에만 파란 테를 두른다."""
        번호 = 명령하나.번호 if 명령하나 is not None else None
        for 하나 in self._타일들:
            하나.고르기(하나.명령.번호 == 번호)

    def _세부판맞춤(self) -> None:
        """격자와 세부설정 판이 나눠 쓸 높이를 정한다.

        세부설정 판은 **필요한 만큼**(최대 70%) 쓰고, 격자는 남은 자리를 쓴다.
        타일이 몇 개뿐이면 격자가 그만큼만 차지하므로 남는 아래 자리가 통째로
        세부설정 몫이 된다. 타일이 많으면 격자는 남은 자리 안에서 구른다.
        """
        self.update_idletasks()
        가운데높이 = self.가운데.winfo_height()
        # 입력칸 높이를 먼저 잡아야 판이 얼마나 필요한지 알 수 있다.
        self._입력칸맞춤(int(가운데높이 * layout.세부판최대비))
        self.update_idletasks()
        세부판 = layout.세부판높이(self.실행판.winfo_reqheight() + 4, 가운데높이)
        # 판이 위 한계에 걸렸으면 입력칸을 그 높이에 맞춰 다시 줄인다. 그러지 않으면
        # 판이 요구하는 높이가 창보다 커져 아래쪽이 잘린다.
        self._입력칸맞춤(세부판)
        격자요구 = self.격자안.winfo_reqheight() + 6
        self.가운데.grid_rowconfigure(
            0, weight=0, minsize=layout.격자칸높이(격자요구, 가운데높이, 세부판)
        )
        self.가운데.grid_rowconfigure(1, weight=1, minsize=세부판)

    def _세부판닫기(self) -> None:
        self.현재명령 = None
        self._타일고르기(None)
        self.실행판.grid_remove()
        self.가운데.grid_rowconfigure(0, weight=1, minsize=0)
        self.가운데.grid_rowconfigure(1, weight=0, minsize=0)
        self._기본상태 = f"기능 {len(self._보이는명령)}개"
        self.상태값.set(self._기본상태)

    def _설명줄맞춤(self, 사건: Any) -> None:
        self.기능설명.configure(wraplength=max(160, 사건.width - 28))

    def _입력만들기(self, 명령하나: commands.명령) -> None:
        for 자식 in self.입력틀.winfo_children():
            자식.destroy()
        self._입력위젯.clear()

        if not 명령하나.입력:
            tk.Label(
                self.입력틀,
                text="바로 실행할 수 있습니다.",
                bg=theme.카드,
                fg=theme.흐린글,
                anchor="w",
            ).pack(fill="x", padx=5, pady=4)
            self._입력칸맞춤()
            return

        for 항목 in 명령하나.입력:
            칸 = tk.Frame(self.입력틀, bg=theme.카드)
            칸.pack(fill="x", padx=5, pady=(4, 0))
            if 항목.종류 == "체크":
                # 켬/끔 알약은 좁으니 이름과 **한 줄에** 놓는다. 체크가 다섯 개인
                # 기능(문서 정리)에서 줄 수가 절반으로 줄어 스크롤이 없어진다.
                줄 = tk.Frame(칸, bg=theme.카드)
                줄.pack(fill="x")
                tk.Label(
                    줄,
                    text=항목.표시,
                    bg=theme.카드,
                    fg=theme.진한글,
                    anchor="w",
                    font=(theme.글꼴, 9, "bold"),
                ).pack(side="left", fill="x", expand=True)
                위젯 = 켬끔(
                    줄, 켜짐=bool(항목.기본값), 높이=25, 안여백=12, 바탕색=theme.카드
                )
                위젯.pack(side="right", padx=(6, 0))
            else:
                tk.Label(
                    칸,
                    text=항목.표시,
                    bg=theme.카드,
                    fg=theme.진한글,
                    anchor="w",
                    font=(theme.글꼴, 9, "bold"),
                ).pack(fill="x", pady=(0, 3))
                위젯 = self._위젯하나(칸, 항목)
            self._입력위젯[항목.이름] = (항목, 위젯)
            if 항목.설명:
                tk.Label(
                    칸,
                    text=항목.설명,
                    bg=theme.카드,
                    fg=theme.흐린글,
                    anchor="w",
                    justify="left",
                    wraplength=320,
                    font=(theme.글꼴, 8),
                ).pack(fill="x", pady=(3, 0))
        self._입력칸맞춤()

    def _입력칸맞춤(self, 판높이: int = 0) -> None:
        """입력 개수에 맞춰 입력칸 높이를 잡는다. (남는 몫은 결과칸으로)"""
        self.update_idletasks()  # 방금 만든 위젯의 요청 크기를 읽으려면 먼저 재야 한다
        if 판높이 <= 1:
            판높이 = self.실행판.winfo_height()
        if 판높이 <= 1:  # 아직 한 번도 그려지지 않은 판
            판높이 = int(self.winfo_height() * layout.세부판최대비)
        요구 = self.입력틀.winfo_reqheight() + 10
        self.실행판.grid_rowconfigure(
            3, weight=4, minsize=layout.입력칸높이(요구, 판높이)
        )

    def _채운입력(self, 부모: tk.Misc, 값: tk.StringVar, 높이: int = 34) -> 둥근칸:
        """옅은 파랑으로 채운 둥근 입력칸(시안 방식).

        ttk 입력칸은 모서리를 깎을 수 없어, 둥근 캔버스 안에 맨 `tk.Entry` 를
        넣는다. 테두리를 없애고 색으로만 칸을 나타낸다.
        """
        상자 = 둥근칸(부모, 높이=높이, 바탕색=theme.카드, 안색=theme.입력칸, 옆여백=11)
        tk.Entry(
            상자.속,
            textvariable=값,
            bg=theme.입력칸,
            fg=theme.진한글,
            relief="flat",
            highlightthickness=0,
            insertbackground=theme.진한글,
            font=(theme.글꼴, 10),
        ).pack(fill="both", expand=True)
        return 상자

    def _위젯하나(self, 부모: tk.Frame, 항목: commands.입력항목) -> Any:
        """이름 아래에 놓는 입력칸. (체크는 `_입력만들기` 가 한 줄로 직접 만든다)"""
        if 항목.종류 == "선택":
            칸 = 고르는칸(부모, list(항목.선택지), 값=str(항목.기본값))
            칸.pack(fill="x")
            return 칸
        if 항목.종류 == "여러줄":
            상자 = 둥근상자(부모)
            상자.pack(fill="both", expand=True)
            글칸 = tk.Text(
                상자.속,
                height=8,
                wrap="word",
                bg=theme.입력칸,
                fg=theme.진한글,
                relief="flat",
                padx=9,
                pady=7,
                highlightthickness=0,
                insertbackground=theme.진한글,
                font=(theme.글꼴, 10),
            )
            글칸.pack(fill="both", expand=True)
            if 항목.기본값:
                글칸.insert("1.0", str(항목.기본값))
            return 글칸
        if 항목.종류 in ("파일", "폴더", "저장파일"):
            값 = tk.StringVar(value=str(항목.기본값))
            줄 = tk.Frame(부모, bg=theme.카드)
            줄.pack(fill="x")
            self._채운입력(줄, 값).pack(side="left", fill="x", expand=True)
            채운단추(
                줄,
                "찾기",
                누름=lambda: self._경로고르기(항목.종류, 값),
                채움=theme.파랑옅게,
                글색=theme.파랑,
                누른채움=theme.섞기(theme.파랑, theme.카드, 0.22),
                높이=34,
                안여백=14,
                굵게=False,
            ).pack(side="left", padx=(6, 0))
            return 값
        값 = tk.StringVar(value=str(항목.기본값))
        self._채운입력(부모, 값).pack(fill="x")
        return 값

    def _경로고르기(self, 종류: str, 값: tk.StringVar) -> None:
        if 종류 == "폴더":
            고른 = filedialog.askdirectory()
        elif 종류 == "저장파일":
            고른 = filedialog.asksaveasfilename(defaultextension=".pdf")
        else:
            고른 = filedialog.askopenfilename(
                filetypes=[
                    ("자료·문서 파일", "*.csv;*.xlsx;*.tsv;*.hwp;*.hwpx"),
                    ("모든 파일", "*.*"),
                ]
            )
        if 고른:
            값.set(고른)

    def _입력값모으기(self) -> dict[str, Any]:
        모음: dict[str, Any] = {}
        for 이름, (항목, 위젯) in self._입력위젯.items():
            if 항목.종류 == "여러줄":
                모음[이름] = 위젯.get("1.0", "end").rstrip("\n")
            else:
                모음[이름] = 위젯.get()
        return 모음

    # ------------------------------------------------------------------ 실행
    def _실행(self) -> None:
        if self.현재명령 is None:
            self._결과쓰기("먼저 기능 타일을 고르세요.")
            return
        명령하나 = self.현재명령
        값들 = self._입력값모으기()

        준비오류 = self._상태확인(명령하나)
        if 준비오류:
            self._결과쓰기(준비오류)
            return

        self.실행단추.잠그기(True)
        self.상태값.set(f"{명령하나.제목} 실행 중…")

        def 일하기() -> None:
            맥락값 = commands.맥락(문서객체=self.문서객체, 값=값들, 알림=self._알림큐.put)
            try:
                결과 = 명령하나.실행(맥락값)
                말 = 결과 if isinstance(결과, str) else f"{명령하나.제목} 완료"
            except Exception as 오류:  # noqa: BLE001
                # 한/글이 돌려준 COM 오류 번호까지 한국말로 풀어 준다.
                말 = 오류풀이(오류)
            # tkinter 는 다른 스레드에서 건드리면 안 된다. 결과도 알림과 같이
            # 큐에 넣고, 주 스레드(`_큐확인`)가 꺼내어 화면에 쓴다.
            self._끝큐.put((명령하나, 말))

        threading.Thread(target=일하기, daemon=True).start()

    def _실행끝(self, 명령하나: commands.명령, 말: str) -> None:
        self.실행단추.잠그기(False)
        self._기본상태 = f"{명령하나.제목} 끝"
        self.상태값.set(self._기본상태)
        self._결과쓰기(말)
        # '보고서 유형으로 시작' 처럼 결과가 마크업이면 렌더 명령칸에 바로 채워 준다.
        if 명령하나.번호 == "보고서.유형":
            self._마크업채우기(말)

    def _마크업채우기(self, 마크업: str) -> None:
        렌더 = commands.찾기("보고서.렌더")
        self._타일누름(렌더)
        항목, 위젯 = self._입력위젯.get("마크업", (None, None))
        if 위젯 is not None and 항목 is not None and 항목.종류 == "여러줄":
            위젯.delete("1.0", "end")
            위젯.insert("1.0", 마크업)
            self.상태값.set("골격을 불러왔습니다. 내용을 채운 뒤 '실행' 을 누르세요.")

    def _상태확인(self, 명령하나: commands.명령) -> str | None:
        """'선택'/'표' 가 필요한 명령을 실행하기 전에 미리 알려 준다."""
        if not 명령하나.필요:
            return None
        가능, 이유 = 사용가능()
        if not 가능:
            return f"[안내] {이유}"
        try:
            if "선택" in 명령하나.필요 and not self.문서객체.선택있나():
                return "[안내] 한/글에서 대상 부분을 마우스로 끌어 선택한 뒤 다시 누르세요."
            if "표" in 명령하나.필요 and not self.문서객체.표안:
                return "[안내] 표 안에 커서를 두거나 셀을 선택한 뒤 다시 누르세요."
        except 한글오류 as 오류:
            return f"[안내] {오류.메시지}"
        return None

    # ------------------------------------------------------------------ 잡동사니
    def _결과쓰기(self, 말: str) -> None:
        self.결과칸.configure(state="normal")
        self.결과칸.delete("1.0", "end")
        self.결과칸.insert("1.0", 말)
        self.결과칸.configure(state="disabled")

    def _큐확인(self) -> None:
        """작업 스레드가 보낸 진행 상황·결과를 주 스레드에서 화면에 옮긴다."""
        try:
            while True:
                self.상태값.set(self._알림큐.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                명령하나, 말 = self._끝큐.get_nowait()
                self._실행끝(명령하나, 말)
        except queue.Empty:
            pass
        self.after(80, self._큐확인)

    def _연결확인(self) -> None:
        가능, 이유 = 사용가능()
        if not 가능:
            self._기본상태 = "한/글에 연결하지 않음"
            self.상태값.set(self._기본상태)
            return
        try:
            버전 = self.문서객체.연결.버전
            self._기본상태 = f"한/글 연결됨 (버전 {버전})"
        except 한글오류 as 오류:
            self._기본상태 = f"한/글 연결 실패 — {오류.메시지} ('진단' 으로 검색)"
        self.상태값.set(self._기본상태)


def 실행하기() -> None:
    """UI 를 띄운다."""
    창 = 본창()
    창.mainloop()
