"""화면 — 화면 가장자리에 붙는 사이드 패널 + 기능 타일 격자.

원본 UI
    · 창 100개 이상(기능마다 Toplevel), 탭 19개, 버튼 PNG 이미지 17MB
    · 버튼 위치를 좌표로 직접 지정(x=150, y=300 …)
    · 한/글 창을 가려서, 문서를 보며 기능을 누르기 어려웠다

바뀐 화면
    · **사이드 패널**: 상·하·좌·우 중 하나를 골라 화면 가장자리에 붙인다.
      한/글 문서를 옆에 두고 쓰라고 만든 자리다. 고른 자리는 다음에도 기억한다.
    · **타일 격자**: 주요 기능을 작은 사각 박스로 늘어놓는다. 분류마다 색과
      글머리가 달라, 목록을 읽지 않고 눈으로 찾는다. 패널 너비에 맞춰 칸 수가
      저절로 바뀌고, 타일 크기는 '칸' 단추로 세 단계로 바꾼다.
    · 위쪽 검색칸에 낱말을 넣으면 타일이 즉시 걸러진다(명령 팔레트).
    · 타일을 누르면 같은 자리에 실행판이 열린다. 입력칸은 `commands.입력항목`
      정의만 보고 자동으로 만든다 — 기능마다 창을 따로 만들지 않는다.

창 자리·칸 수 같은 계산은 `layout.py` 에 따로 두어 시험할 수 있게 했다.
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
from ..core.errors import 한글오류
from . import layout

__all__ = ["실행하기", "본창"]

_제목 = "한글 문서 도우미"

#: 상·하 패널에서 실행판을 볼 때 최소한 이만큼은 높아야 입력칸이 눌리지 않는다.
_실행판최소두께 = 420


class 색:
    """패널 색. 한/글 옆에 붙어 있어도 눈에 거슬리지 않게 옅게 잡았다."""

    배경 = "#f4f5f7"
    타일 = "#ffffff"
    타일가리킴 = "#eef2ff"
    테두리 = "#d8dbe0"
    글 = "#1f2328"
    흐림 = "#5b6470"
    입력 = "#ffffff"


def _바퀴묶기(위젯: tk.Misc, 함수: Callable[[Any], Any]) -> None:
    """마우스 바퀴를 묶는다. 윈도우는 MouseWheel, X11 은 Button-4/5 를 쓴다."""
    위젯.bind("<MouseWheel>", 함수)
    위젯.bind("<Button-4>", 함수)
    위젯.bind("<Button-5>", 함수)


class 스크롤틀(tk.Frame):
    """세로로 구르는 상자. 안쪽 `내용` 프레임에 위젯을 넣는다."""

    def __init__(self, 부모: tk.Misc, 바탕색: str = 색.배경) -> None:
        super().__init__(부모, bg=바탕색)
        self.캔버스 = tk.Canvas(self, bg=바탕색, highlightthickness=0, bd=0)
        self.띠 = ttk.Scrollbar(self, orient="vertical", command=self.캔버스.yview)
        self.캔버스.configure(yscrollcommand=self.띠.set)
        self.캔버스.pack(side="left", fill="both", expand=True)
        self.띠.pack(side="right", fill="y")

        self.내용 = tk.Frame(self.캔버스, bg=바탕색)
        self._창 = self.캔버스.create_window((0, 0), window=self.내용, anchor="nw")
        self.내용.bind("<Configure>", self._내용바뀜)
        self.캔버스.bind("<Configure>", self._캔버스바뀜)

        self.너비알림: Callable[[int], None] | None = None
        _바퀴묶기(self.캔버스, self.바퀴)
        _바퀴묶기(self.내용, self.바퀴)

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


class 타일(tk.Frame):
    """기능 하나를 나타내는 작은 사각 박스."""

    def __init__(
        self,
        부모: tk.Misc,
        명령하나: commands.명령,
        크기: int,
        누름: Callable[[commands.명령], None],
        가리킴: Callable[[commands.명령 | None], None],
        바퀴: Callable[[Any], Any],
    ) -> None:
        글머리, 강조 = layout.분류모습얻기(명령하나.분류)
        super().__init__(
            부모,
            width=크기,
            height=크기,
            bg=색.타일,
            highlightthickness=1,
            highlightbackground=색.테두리,
            highlightcolor=색.테두리,
            cursor="hand2",
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.명령 = 명령하나
        self._강조 = 강조

        띠 = tk.Frame(self, bg=강조, height=3)
        띠.pack(fill="x", side="top")

        self._글머리 = tk.Label(
            self,
            text=글머리,
            bg=색.타일,
            fg=강조,
            font=("맑은 고딕", max(11, 크기 // 5)),
        )
        self._글머리.pack(pady=(max(3, 크기 // 14), 0))

        self._제목 = tk.Label(
            self,
            text=layout.제목자르기(명령하나.제목, 크기),
            bg=색.타일,
            fg=색.글,
            font=("맑은 고딕", 9),
            wraplength=크기 - 10,
            justify="center",
        )
        self._제목.pack(fill="x", padx=3)

        self._필요: tk.Label | None = None
        if 명령하나.필요:
            self._필요 = tk.Label(
                self,
                text="·".join(명령하나.필요) + " 필요",
                bg=색.타일,
                fg=색.흐림,
                font=("맑은 고딕", 7),
            )
            self._필요.pack(side="bottom", pady=(0, 3))

        for 대상 in (self, 띠, self._글머리, self._제목, self._필요):
            if 대상 is None:
                continue
            대상.bind("<Button-1>", lambda _사건: 누름(명령하나))
            대상.bind("<Enter>", lambda _사건: self._들어옴(가리킴))
            대상.bind("<Leave>", lambda _사건: self._나감(가리킴))
            _바퀴묶기(대상, 바퀴)

    def _들어옴(self, 가리킴: Callable[[commands.명령 | None], None]) -> None:
        self._칠하기(색.타일가리킴, self._강조)
        가리킴(self.명령)

    def _나감(self, 가리킴: Callable[[commands.명령 | None], None]) -> None:
        # 타일 안 글자로 옮겨 가도 <Leave> 가 오기 때문에, 정말 밖으로 나갔는지
        # 마우스 자리로 확인한다. (확인하지 않으면 타일이 깜빡인다)
        if self._안에있나():
            return
        self._칠하기(색.타일, 색.테두리)
        가리킴(None)

    def _안에있나(self) -> bool:
        try:
            가로, 세로 = self.winfo_pointerxy()
            왼쪽, 위 = self.winfo_rootx(), self.winfo_rooty()
        except tk.TclError:  # pragma: no cover - 이미 지워진 타일
            return False
        return (
            왼쪽 <= 가로 < 왼쪽 + self.winfo_width()
            and 위 <= 세로 < 위 + self.winfo_height()
        )

    def _칠하기(self, 바탕: str, 테두리: str) -> None:
        self.configure(bg=바탕, highlightbackground=테두리, highlightcolor=테두리)
        for 자식 in (self._글머리, self._제목, self._필요):
            if 자식 is not None:
                자식.configure(bg=바탕)


class 본창(tk.Tk):
    """가장자리에 붙는 사이드 패널 한 장."""

    def __init__(self) -> None:
        super().__init__()
        self.title(_제목)
        self.configure(bg=색.배경)

        self.설정 = layout.설정불러오기()
        self.자리 = self.설정["자리"]
        self.타일크기 = self.설정["타일크기"]

        self.문서객체 = 문서(한글연결())
        self.현재명령: commands.명령 | None = None
        self._입력위젯: dict[str, tuple[commands.입력항목, Any]] = {}
        self._알림큐: queue.Queue[str] = queue.Queue()
        self._끝큐: queue.Queue[tuple[commands.명령, str]] = queue.Queue()
        self._타일들: list[타일] = []
        self._보이는명령: list[commands.명령] = []
        self._칸 = 1
        self._칩줄 = None
        self._펼친두께: int | None = None
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
        self.option_add("*Font", ("맑은 고딕", 10))
        스타일.configure("TFrame", background=색.배경)
        스타일.configure("TLabel", background=색.배경, foreground=색.글)
        스타일.configure("설명.TLabel", foreground=색.흐림)
        스타일.configure("제목.TLabel", font=("맑은 고딕", 11, "bold"))
        스타일.configure("실행.TButton", font=("맑은 고딕", 10, "bold"))
        스타일.configure("Toolbutton", padding=(6, 2))

    # ------------------------------------------------------------------ 뼈대
    def _뼈대(self) -> None:
        self._머리만들기()
        self.가운데 = tk.Frame(self, bg=색.배경)
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
            bg=색.배경,
            fg=색.흐림,
            anchor="w",
            font=("맑은 고딕", 9),
        ).pack(fill="x", padx=8, pady=(0, 5))

    def _머리만들기(self) -> None:
        첫줄 = ttk.Frame(self, padding=(8, 6, 8, 0))
        첫줄.pack(fill="x")
        ttk.Label(첫줄, text=_제목, style="제목.TLabel").pack(side="left")

        자리틀 = ttk.Frame(첫줄)
        자리틀.pack(side="right")
        self.자리값 = tk.StringVar(value=self.자리)
        for 이름 in layout.자리들:
            단추 = ttk.Radiobutton(
                자리틀,
                text=이름,
                value=이름,
                variable=self.자리값,
                style="Toolbutton",
                width=2,
                command=self._자리바꾸기,
            )
            단추.pack(side="left", padx=1)
            self._도움말묶기(단추, f"패널을 화면 {이름}쪽에 붙입니다.")

        둘째줄 = ttk.Frame(self, padding=(8, 4, 8, 2))
        둘째줄.pack(fill="x")
        self.검색값 = tk.StringVar()
        검색칸 = ttk.Entry(둘째줄, textvariable=self.검색값)
        검색칸.pack(side="left", fill="x", expand=True)
        검색칸.bind("<KeyRelease>", lambda _사건: self._타일채우기())
        검색칸.bind("<Escape>", lambda _사건: self._검색지우기())
        검색칸.focus_set()
        self._도움말묶기(검색칸, "낱말을 넣으면 기능 타일이 걸러집니다. (예: 표, 콤마, PDF)")

        지움 = ttk.Button(둘째줄, text="✕", width=3, command=self._검색지우기)
        지움.pack(side="left", padx=(4, 0))
        self._도움말묶기(지움, "검색말을 지웁니다.")

        칸단추 = ttk.Button(둘째줄, text="칸", width=3, command=self._타일크기바꾸기)
        칸단추.pack(side="left", padx=(4, 0))
        self._도움말묶기(칸단추, "타일 크기를 작게·보통·크게로 바꿉니다.")

        self.항상위값 = tk.BooleanVar(value=bool(self.설정["항상위"]))
        위단추 = ttk.Checkbutton(
            둘째줄,
            text="위",
            variable=self.항상위값,
            style="Toolbutton",
            width=2,
            command=self._항상위적용,
        )
        위단추.pack(side="left", padx=(4, 0))
        self._도움말묶기(위단추, "다른 창 위에 늘 띄워 둡니다.")

        # 칩은 grid 가 아니라 place 로 놓는다. grid 는 열 너비를 줄끼리 나눠 쓰기
        # 때문에, 아랫줄의 긴 칩('양식·메일머지')이 윗줄까지 넓혀 칩이 잘렸다.
        self.분류틀 = tk.Frame(self, bg=색.배경, height=28)
        self.분류틀.pack(fill="x", padx=6, pady=(0, 2))
        self.분류값 = tk.StringVar(value="전체")
        self._칩들: list[ttk.Radiobutton] = []
        for 이름 in ("전체", *commands.분류순서):
            칩 = ttk.Radiobutton(
                self.분류틀,
                text=이름,
                value=이름,
                variable=self.분류값,
                style="Toolbutton",
                command=self._타일채우기,
            )
            self._칩들.append(칩)
        self.분류틀.bind("<Configure>", self._칩배치)

    def _격자만들기(self) -> None:
        self.격자틀 = 스크롤틀(self.가운데, 색.배경)
        self.격자틀.너비알림 = self._격자너비바뀜
        self.격자안 = self.격자틀.내용

    def _실행판만들기(self) -> None:
        self.실행판 = tk.Frame(self.가운데, bg=색.배경)

        머리 = tk.Frame(self.실행판, bg=색.배경)
        머리.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Button(머리, text="← 목록", width=7, command=self._목록으로).pack(side="left")
        self.기능제목 = tk.Label(
            머리,
            text="",
            bg=색.배경,
            fg=색.글,
            font=("맑은 고딕", 11, "bold"),
            anchor="w",
        )
        self.기능제목.pack(side="left", padx=8, fill="x", expand=True)

        self.기능설명 = tk.Label(
            self.실행판,
            text="",
            bg=색.배경,
            fg=색.흐림,
            anchor="w",
            justify="left",
            wraplength=340,
            font=("맑은 고딕", 9),
        )
        self.기능설명.pack(fill="x", padx=10)
        self.실행판.bind("<Configure>", self._설명줄맞춤)

        # 실행 단추와 결과칸을 먼저 아래에 붙인다. 패널이 낮은 상·하 자리에서도
        # 이 둘은 잘리지 않고, 남는 자리만 입력칸이 차지하도록.
        self.결과칸 = tk.Text(
            self.실행판,
            height=4,
            wrap="word",
            bg=색.입력,
            fg=색.글,
            relief="flat",
            highlightthickness=1,
            highlightbackground=색.테두리,
        )
        self.결과칸.pack(side="bottom", fill="x", padx=8, pady=(4, 6))
        self.결과칸.configure(state="disabled")

        self.단추줄 = tk.Frame(self.실행판, bg=색.배경)
        self.실행단추 = ttk.Button(
            self.단추줄, text="실행", style="실행.TButton", command=self._실행
        )
        self.실행단추.pack(side="right")

        self.입력스크롤 = 스크롤틀(self.실행판, 색.배경)
        self.입력틀 = self.입력스크롤.내용
        self._실행판모양맞춤()

    def _실행판모양맞춤(self) -> None:
        """붙인 자리에 따라 실행판 안을 다시 짠다.

        길쭉한 좌·우 패널은 위에서 아래로(입력 → 실행 → 결과), 넓적한 상·하
        패널은 높이가 모자라므로 결과를 오른쪽으로 보내 가로를 쓴다.
        """
        for 하나 in (self.결과칸, self.단추줄, self.입력스크롤):
            하나.pack_forget()
        if self.자리 in layout.가로자리:
            self.결과칸.configure(width=46, height=6)
            self.결과칸.pack(side="right", fill="y", padx=(4, 8), pady=(0, 6))
            self.단추줄.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
            self.입력스크롤.pack(side="left", fill="both", expand=True, padx=6, pady=4)
        else:
            self.결과칸.configure(width=1, height=4)
            self.결과칸.pack(side="bottom", fill="x", padx=8, pady=(4, 6))
            self.단추줄.pack(side="bottom", fill="x", padx=8)
            self.입력스크롤.pack(fill="both", expand=True, padx=6, pady=4)

    def _도움말묶기(self, 위젯: tk.Misc, 말: str) -> None:
        """가리키면 아래 상태줄에 설명이 나오게 한다. (풍선 도움말 대신)"""
        위젯.bind("<Enter>", lambda _사건: self.상태값.set(말))
        위젯.bind("<Leave>", lambda _사건: self.상태값.set(self._기본상태))

    # ------------------------------------------------------------------ 자리
    def _자리적용(self) -> None:
        두께 = self.설정["두께"].get(self.자리, layout.기본설정["두께"][self.자리])
        self._펼친두께 = None
        self._자리잡기(두께)
        self._실행판모양맞춤()
        if self.자리 in layout.세로자리:
            self.minsize(layout.최소두께, 320)
        else:
            self.minsize(480, layout.최소두께)
        self._항상위적용()

    def _자리잡기(self, 두께: int) -> None:
        자리값 = layout.창자리계산(
            self.자리, self.winfo_screenwidth(), self.winfo_screenheight(), 두께
        )
        self.geometry(자리값.지오메트리)

    def _자리바꾸기(self) -> None:
        self._두께기억()
        self.자리 = self.자리값.get()
        self._자리적용()
        self._칩줄 = None  # 폭이 달라졌으니 칩 줄을 다시 계산한다.
        self.상태값.set(f"패널을 {self.자리}쪽에 붙였습니다.")

    def _지금두께(self) -> int:
        return self.winfo_width() if self.자리 in layout.세로자리 else self.winfo_height()

    def _두께기억(self) -> None:
        try:
            두께 = self._펼친두께 if self._펼친두께 is not None else self._지금두께()
        except tk.TclError:  # pragma: no cover - 창이 이미 닫힌 경우
            return
        if 두께 and 두께 > 1:
            self.설정["두께"][self.자리] = 두께

    def _판열때펼치기(self) -> None:
        """상·하 패널이 너무 낮으면 실행판을 보는 동안만 잠깐 넓힌다."""
        if self.자리 not in layout.가로자리 or self._펼친두께 is not None:
            return
        지금 = self._지금두께()
        if 지금 >= _실행판최소두께:
            return
        self._펼친두께 = 지금  # 목록으로 돌아갈 때 되돌릴 값
        self._자리잡기(_실행판최소두께)

    def _판닫을때되돌리기(self) -> None:
        if self._펼친두께 is None:
            return
        되돌릴것, self._펼친두께 = self._펼친두께, None
        self._자리잡기(되돌릴것)

    def _항상위적용(self) -> None:
        try:
            self.attributes("-topmost", bool(self.항상위값.get()))
        except tk.TclError:  # pragma: no cover - 지원하지 않는 창 관리자
            pass

    def _닫기(self) -> None:
        self._두께기억()
        self.설정["자리"] = self.자리
        self.설정["항상위"] = bool(self.항상위값.get())
        self.설정["타일크기"] = self.타일크기
        layout.설정저장(self.설정)
        self.destroy()

    # ------------------------------------------------------------------ 격자
    def _칩배치(self, _사건: Any = None) -> None:
        가용 = self.분류틀.winfo_width()
        if 가용 <= 1:
            return
        너비들 = [칩.winfo_reqwidth() for 칩 in self._칩들]
        줄들 = layout.줄나누기(너비들, 가용, 사이=4)
        if 줄들 == self._칩줄:
            return  # 줄이 그대로면 다시 놓지 않는다. (높이 조절 → Configure 되돌이 막기)
        self._칩줄 = 줄들
        높이 = max(칩.winfo_reqheight() for 칩 in self._칩들)
        for 줄번호, 줄 in enumerate(줄들):
            가로 = 0
            for 자리 in 줄:
                self._칩들[자리].place(
                    x=가로, y=줄번호 * (높이 + 2), width=너비들[자리], height=높이
                )
                가로 += 너비들[자리] + 4
        self.분류틀.configure(height=len(줄들) * (높이 + 2))

    def _격자너비바뀜(self, 너비: int) -> None:
        새칸 = layout.칸수(너비 - 8, self.타일크기, 사이=8)
        if 새칸 != self._칸:
            self._칸 = 새칸
            self._타일배치()

    def _검색지우기(self) -> None:
        self.검색값.set("")
        self._타일채우기()

    def _타일크기바꾸기(self) -> None:
        self.타일크기 = layout.다음타일크기(self.타일크기)
        self._칸 = layout.칸수(self.격자틀.캔버스.winfo_width() - 8, self.타일크기, 사이=8)
        self._타일채우기()
        self.상태값.set(f"타일 크기 {self.타일크기}")

    def _타일채우기(self) -> None:
        질의 = self.검색값.get().strip()
        분류 = self.분류값.get()
        if 질의:
            후보 = commands.검색(질의, 최대=500)  # 잘 맞는 것부터 — 차례를 흩지 않는다.
        else:
            후보 = layout.정렬순서(commands.전체명령(), commands.분류순서)
        if 분류 != "전체":
            후보 = [하나 for 하나 in 후보 if 하나.분류 == 분류]

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
        남음 = max(0, 너비 - 칸 * (self.타일크기 + 8))
        곁 = min(20, 남음 // (칸 * 2))
        for 자리, 하나 in enumerate(self._타일들):
            하나.grid(row=자리 // 칸, column=자리 % 칸, padx=4 + 곁, pady=4)

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
        self._판열때펼치기()
        self.실행판.tkraise()
        self.입력스크롤.맨위로()
        self._기본상태 = 명령하나.제목
        self.상태값.set(self._기본상태)

    def _목록으로(self) -> None:
        self._판닫을때되돌리기()
        self.격자틀.tkraise()
        self._기본상태 = f"기능 {len(self._보이는명령)}개"
        self.상태값.set(self._기본상태)

    def _설명줄맞춤(self, 사건: Any) -> None:
        self.기능설명.configure(wraplength=max(160, 사건.width - 24))

    def _입력만들기(self, 명령하나: commands.명령) -> None:
        for 자식 in self.입력틀.winfo_children():
            자식.destroy()
        self._입력위젯.clear()

        if not 명령하나.입력:
            tk.Label(
                self.입력틀,
                text="바로 실행할 수 있습니다.",
                bg=색.배경,
                fg=색.흐림,
                anchor="w",
            ).pack(fill="x", padx=4, pady=4)
            return

        for 항목 in 명령하나.입력:
            칸 = tk.Frame(self.입력틀, bg=색.배경)
            칸.pack(fill="x", padx=4, pady=(4, 0))
            tk.Label(
                칸,
                text=항목.표시,
                bg=색.배경,
                fg=색.글,
                anchor="w",
                font=("맑은 고딕", 9, "bold"),
            ).pack(fill="x")
            위젯 = self._위젯하나(칸, 항목)
            self._입력위젯[항목.이름] = (항목, 위젯)
            if 항목.설명:
                tk.Label(
                    칸,
                    text=항목.설명,
                    bg=색.배경,
                    fg=색.흐림,
                    anchor="w",
                    justify="left",
                    wraplength=320,
                    font=("맑은 고딕", 8),
                ).pack(fill="x")

    def _위젯하나(self, 부모: tk.Frame, 항목: commands.입력항목) -> Any:
        if 항목.종류 == "선택":
            값 = tk.StringVar(value=str(항목.기본값))
            ttk.Combobox(
                부모, textvariable=값, values=list(항목.선택지), state="readonly"
            ).pack(fill="x")
            return 값
        if 항목.종류 == "체크":
            값 = tk.BooleanVar(value=bool(항목.기본값))
            ttk.Checkbutton(부모, variable=값, text="사용").pack(anchor="w")
            return 값
        if 항목.종류 == "여러줄":
            글칸 = tk.Text(
                부모,
                height=8,
                wrap="word",
                bg=색.입력,
                relief="flat",
                highlightthickness=1,
                highlightbackground=색.테두리,
            )
            글칸.pack(fill="both", expand=True)
            if 항목.기본값:
                글칸.insert("1.0", str(항목.기본값))
            return 글칸
        if 항목.종류 in ("파일", "폴더", "저장파일"):
            값 = tk.StringVar(value=str(항목.기본값))
            줄 = tk.Frame(부모, bg=색.배경)
            줄.pack(fill="x")
            ttk.Entry(줄, textvariable=값).pack(side="left", fill="x", expand=True)
            ttk.Button(
                줄, text="찾기", width=5, command=lambda: self._경로고르기(항목.종류, 값)
            ).pack(side="left", padx=(4, 0))
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
            except 한글오류 as 오류:
                말 = f"[안내] {오류.메시지}\n{오류.도움말}".strip()
            except Exception as 오류:  # noqa: BLE001
                말 = f"[오류] {오류}"
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
