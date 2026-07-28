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
    · 타일을 누르면 같은 자리에 실행판이 열린다. 입력칸은 `commands.입력항목`
      정의만 보고 자동으로 만든다 — 기능마다 창을 따로 만들지 않는다.

배색은 토스(Toss) 앱을 참고했다(`theme.py`). 둥근 카드·알약 단추는 tkinter 기본
위젯으로 되지 않아 캔버스에 직접 그린다(`widgets.py`). 창 자리·칸 수 같은 계산은
`layout.py` 에 따로 두어 tkinter 없이 시험한다.
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
from .widgets import 켬끔, 둥근칸, 미끄럼자, 바퀴묶기, 알약단추, 타일

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
        스타일.configure(
            "TEntry",
            fieldbackground=theme.카드,
            bordercolor=theme.테두리,
            lightcolor=theme.테두리,
            darkcolor=theme.테두리,
            borderwidth=1,
            padding=6,
        )
        스타일.configure(
            "TCombobox",
            fieldbackground=theme.카드,
            background=theme.카드,
            bordercolor=theme.테두리,
            lightcolor=theme.테두리,
            darkcolor=theme.테두리,
            arrowcolor=theme.보통글,
            borderwidth=1,
            padding=5,
        )
        스타일.map("TCombobox", fieldbackground=[("readonly", theme.카드)])
        스타일.configure(
            "TCheckbutton", background=theme.바탕, foreground=theme.보통글
        )
        # 주 단추(실행) — 토스의 파란 채움 단추
        스타일.configure(
            "주.TButton",
            background=theme.파랑,
            foreground=theme.카드,
            bordercolor=theme.파랑,
            lightcolor=theme.파랑,
            darkcolor=theme.파랑,
            focuscolor=theme.파랑,
            borderwidth=0,
            padding=(20, 9),
            font=(theme.글꼴, 10, "bold"),
        )
        스타일.map(
            "주.TButton",
            background=[("pressed", theme.파랑진하게), ("active", theme.파랑진하게), ("disabled", theme.꺼짐)],
            lightcolor=[("disabled", theme.꺼짐)],
            darkcolor=[("disabled", theme.꺼짐)],
            bordercolor=[("disabled", theme.꺼짐)],
        )
        스타일.configure(
            "곁.TButton",
            background=theme.카드,
            foreground=theme.보통글,
            bordercolor=theme.테두리,
            lightcolor=theme.테두리,
            darkcolor=theme.테두리,
            borderwidth=1,
            padding=(10, 6),
        )
        스타일.map("곁.TButton", background=[("active", theme.파랑옅게)])
        스타일.configure(
            "Vertical.TScrollbar",
            background=theme.테두리,
            troughcolor=theme.바탕,
            bordercolor=theme.바탕,
            arrowcolor=theme.흐린글,
            borderwidth=0,
        )

    # ------------------------------------------------------------------ 뼈대
    def _뼈대(self) -> None:
        self._머리만들기()
        self.가운데 = tk.Frame(self, bg=theme.바탕)
        self.가운데.pack(fill="both", expand=True)
        self.가운데.grid_rowconfigure(0, weight=1)
        self.가운데.grid_columnconfigure(0, weight=1)
        self._격자만들기()
        self._실행판만들기()
        self.격자틀.grid(row=0, column=0, sticky="nsew")
        self.실행판.grid(row=0, column=0, sticky="nsew")
        self.격자틀.tkraise()

        self.상태값 = tk.StringVar(value=self._기본상태)
        tk.Label(
            self,
            textvariable=self.상태값,
            bg=theme.바탕,
            fg=theme.흐린글,
            anchor="w",
            font=(theme.글꼴, 9),
        ).pack(fill="x", padx=14, pady=(0, 8))

    def _머리만들기(self) -> None:
        self.머리 = tk.Frame(self, bg=theme.바탕)
        self.머리.pack(fill="x", padx=12, pady=(10, 0))

        # (1) 이름 + 붙일 자리
        self.이름틀 = tk.Frame(self.머리, bg=theme.바탕)
        tk.Label(
            self.이름틀,
            text=_제목,
            bg=theme.바탕,
            fg=theme.진한글,
            font=(theme.글꼴, 12, "bold"),
        ).pack(side="left")
        자리단추틀 = tk.Frame(self.이름틀, bg=theme.바탕)
        자리단추틀.pack(side="right")
        self._자리단추: dict[str, 알약단추] = {}
        for 이름 in layout.자리들:
            단추 = 알약단추(
                자리단추틀,
                이름,
                누름=lambda 값=이름: self._자리바꾸기(값),
                골라짐=(이름 == self.자리),
                높이=26,
                안여백=9,
            )
            단추.pack(side="left", padx=(3, 0))
            self._도움말묶기(단추, f"패널을 화면 {이름}쪽에 붙입니다.")
            self._자리단추[이름] = 단추

        self.이름틀.pack(fill="x")

        # (2) 검색칸
        self.검색틀 = 둥근칸(self.머리, 높이=36)
        self.검색값 = tk.StringVar(value=_자리글)
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

        self.검색틀.pack(fill="x", pady=(8, 0))

        # (3) 도구 — 타일 크기 · 항상 위 · 투명도
        self.도구틀 = tk.Frame(self.머리, bg=theme.바탕)
        self.도구틀.pack(fill="x", pady=(8, 0))
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
        self.분류틀.pack(fill="x", padx=12, pady=(8, 2))
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
        """실행판 — 머리 / 설명 / 입력칸 / 실행 단추 / 결과칸.

        칸 몫은 grid 로 나눈다. 입력칸이 짧은 기능이 대부분이라 pack 으로 두면
        가운데가 텅 비고 결과만 아래에 눌려 있었다. 결과 쪽에 더 큰 몫을 준다.
        """
        self.실행판 = tk.Frame(self.가운데, bg=theme.바탕)
        self.실행판.grid_columnconfigure(0, weight=1)
        self.실행판.grid_rowconfigure(2, weight=2, minsize=90)  # 입력칸
        self.실행판.grid_rowconfigure(4, weight=5, minsize=170)  # 결과칸

        머리 = tk.Frame(self.실행판, bg=theme.바탕)
        머리.grid(row=0, column=0, sticky="ew", padx=12, pady=(6, 4))
        알약단추(머리, "← 목록", 누름=self._목록으로, 높이=26, 안여백=10).pack(side="left")
        self.기능제목 = tk.Label(
            머리,
            text="",
            bg=theme.바탕,
            fg=theme.진한글,
            font=(theme.글꼴, 12, "bold"),
            anchor="w",
        )
        self.기능제목.pack(side="left", padx=10, fill="x", expand=True)

        self.기능설명 = tk.Label(
            self.실행판,
            text="",
            bg=theme.바탕,
            fg=theme.보통글,
            anchor="w",
            justify="left",
            wraplength=340,
            font=(theme.글꼴, 9),
        )
        self.기능설명.grid(row=1, column=0, sticky="ew", padx=14)
        self.실행판.bind("<Configure>", self._설명줄맞춤)

        self.입력스크롤 = 스크롤틀(self.실행판, theme.바탕)
        self.입력스크롤.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        self.입력틀 = self.입력스크롤.내용

        단추줄 = tk.Frame(self.실행판, bg=theme.바탕)
        단추줄.grid(row=3, column=0, sticky="ew", padx=12)
        self.실행단추 = ttk.Button(
            단추줄, text="실행", style="주.TButton", command=self._실행
        )
        self.실행단추.pack(side="right")
        self.결과지움 = 알약단추(
            단추줄, "결과 지우기", 누름=lambda: self._결과쓰기(""), 높이=26, 안여백=10
        )
        self.결과지움.pack(side="left")

        결과틀 = tk.Frame(self.실행판, bg=theme.바탕)
        결과틀.grid(row=4, column=0, sticky="nsew", padx=12, pady=(6, 8))
        tk.Label(
            결과틀, text="결과", bg=theme.바탕, fg=theme.흐린글, font=(theme.글꼴, 9)
        ).pack(anchor="w", pady=(0, 3))
        결과상자 = tk.Frame(결과틀, bg=theme.바탕)
        결과상자.pack(fill="both", expand=True)
        결과띠 = ttk.Scrollbar(결과상자, orient="vertical")
        결과띠.pack(side="right", fill="y")
        self.결과칸 = tk.Text(
            결과상자,
            height=6,
            wrap="word",
            bg=theme.카드,
            fg=theme.진한글,
            relief="flat",
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=theme.테두리,
            highlightcolor=theme.테두리,
            font=(theme.글꼴, 9),
            yscrollcommand=결과띠.set,
        )
        self.결과칸.pack(side="left", fill="both", expand=True)
        결과띠.configure(command=self.결과칸.yview)
        self.결과칸.configure(state="disabled")

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
        for 값, 단추 in self._자리단추.items():
            단추.고르기(값 == 이름)
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
        self.현재명령 = None
        self.격자틀.tkraise()
        self._타일채우기()
        self.격자틀.맨위로()

    def _격자너비바뀜(self, 너비: int) -> None:
        새칸 = layout.칸수(너비 - 16, self.타일크기, 사이=8)
        if 새칸 != self._칸:
            self._칸 = 새칸
            self._타일배치()

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
        self._기본상태 = f"기능 {len(후보)}개" if 후보 else "찾은 기능이 없습니다."
        self.상태값.set(self._기본상태)

    def _타일배치(self) -> None:
        칸 = max(1, self._칸)
        # 남는 자리를 타일 사이에 고르게 나눠, 한쪽으로 몰리지 않게 한다.
        너비 = self.격자틀.캔버스.winfo_width()
        남음 = max(0, 너비 - 16 - 칸 * (self.타일크기 + 8))
        곁 = min(20, 남음 // (칸 * 2))
        for 자리, 하나 in enumerate(self._타일들):
            하나.grid(row=자리 // 칸, column=자리 % 칸, padx=4 + 곁, pady=5)

    def _가리킴(self, 명령하나: commands.명령 | None) -> None:
        if 명령하나 is None:
            self.상태값.set(self._기본상태)
            return
        설명 = (명령하나.설명 or "").strip()
        self.상태값.set(f"{명령하나.제목} — {설명}" if 설명 else 명령하나.제목)

    # ------------------------------------------------------------------ 실행판
    def _타일누름(self, 명령하나: commands.명령) -> None:
        self.현재명령 = 명령하나
        self.기능제목.configure(text=명령하나.제목)
        설명 = 명령하나.설명 or ""
        if 명령하나.필요:
            설명 = (설명 + "\n" if 설명 else "") + f"먼저 준비: {', '.join(명령하나.필요)}"
        self.기능설명.configure(text=설명)
        self._입력만들기(명령하나)
        self._결과쓰기("")
        self.실행판.tkraise()
        self.입력스크롤.맨위로()
        self._기본상태 = 명령하나.제목
        self.상태값.set(self._기본상태)

    def _목록으로(self) -> None:
        self.격자틀.tkraise()
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
                bg=theme.바탕,
                fg=theme.흐린글,
                anchor="w",
            ).pack(fill="x", padx=6, pady=6)
            self._입력칸맞춤()
            return

        for 항목 in 명령하나.입력:
            칸 = tk.Frame(self.입력틀, bg=theme.바탕)
            칸.pack(fill="x", padx=6, pady=(6, 0))
            tk.Label(
                칸,
                text=항목.표시,
                bg=theme.바탕,
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
                    bg=theme.바탕,
                    fg=theme.흐린글,
                    anchor="w",
                    justify="left",
                    wraplength=320,
                    font=(theme.글꼴, 8),
                ).pack(fill="x", pady=(3, 0))
        self._입력칸맞춤()

    def _입력칸맞춤(self) -> None:
        """입력 개수에 맞춰 입력칸 높이를 잡는다. (남는 몫은 결과칸으로)"""
        self.update_idletasks()  # 방금 만든 위젯의 요청 크기를 읽으려면 먼저 재야 한다
        요구 = self.입력틀.winfo_reqheight() + 12
        self.실행판.grid_rowconfigure(
            2, weight=2, minsize=layout.입력칸높이(요구, self.winfo_height())
        )

    def _위젯하나(self, 부모: tk.Frame, 항목: commands.입력항목) -> Any:
        if 항목.종류 == "선택":
            값 = tk.StringVar(value=str(항목.기본값))
            ttk.Combobox(
                부모, textvariable=값, values=list(항목.선택지), state="readonly"
            ).pack(fill="x")
            return 값
        if 항목.종류 == "체크":
            토글 = 켬끔(부모, 켜짐=bool(항목.기본값))
            토글.pack(anchor="w")
            return 토글
        if 항목.종류 == "여러줄":
            글칸 = tk.Text(
                부모,
                height=8,
                wrap="word",
                bg=theme.카드,
                fg=theme.진한글,
                relief="flat",
                padx=8,
                pady=6,
                highlightthickness=1,
                highlightbackground=theme.테두리,
                highlightcolor=theme.파랑,
                font=(theme.글꼴, 10),
            )
            글칸.pack(fill="both", expand=True)
            if 항목.기본값:
                글칸.insert("1.0", str(항목.기본값))
            return 글칸
        if 항목.종류 in ("파일", "폴더", "저장파일"):
            값 = tk.StringVar(value=str(항목.기본값))
            줄 = tk.Frame(부모, bg=theme.바탕)
            줄.pack(fill="x")
            ttk.Entry(줄, textvariable=값).pack(side="left", fill="x", expand=True)
            ttk.Button(
                줄,
                text="찾기",
                style="곁.TButton",
                width=5,
                command=lambda: self._경로고르기(항목.종류, 값),
            ).pack(side="left", padx=(6, 0))
            return 값
        값 = tk.StringVar(value=str(항목.기본값))
        ttk.Entry(부모, textvariable=값).pack(fill="x")
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

        self.실행단추.configure(state="disabled")
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
        self.실행단추.configure(state="normal")
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
