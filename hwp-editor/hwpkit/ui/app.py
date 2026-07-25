"""화면 — 명령 팔레트 하나로 모든 기능에 닿는 단일 창.

원본 UI
    · 창 100개 이상(기능마다 Toplevel), 탭 19개, 버튼 PNG 이미지 17MB
    · 버튼 위치를 좌표로 직접 지정(x=150, y=300 …)
    · 기능을 찾으려면 어느 탭에 있는지 외워야 했다

바뀐 화면
    · 위쪽 검색칸에 낱말을 넣으면 모든 기능이 즉시 걸러진다(명령 팔레트)
    · 왼쪽은 주요 기능 분류 8개뿐 (기관별 탭 전부 제거)
    · 입력이 필요한 기능은 오른쪽에 입력칸이 자동으로 생긴다
      (`commands.입력항목` 정의만 보고 만든다 — 창을 따로 만들지 않는다)
    · 결과·오류는 아래 상태칸에 한국말로 표시한다
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any

from .. import commands
from ..core.connection import 사용가능, 한글연결
from ..core.document import 문서
from ..core.errors import 한글오류

__all__ = ["실행하기", "본창"]

_제목 = "한글 문서 도우미 (HwpKit)"


class 본창(tk.Tk):
    """단일 창 UI."""

    def __init__(self) -> None:
        super().__init__()
        self.title(_제목)
        self.geometry("980x640")
        self.minsize(820, 560)

        self.문서객체 = 문서(한글연결())
        self.현재명령: commands.명령 | None = None
        self._입력위젯: dict[str, tuple[commands.입력항목, Any]] = {}
        self._알림큐: queue.Queue[str] = queue.Queue()

        self._스타일()
        self._뼈대()
        self._목록채우기()
        self.after(100, self._큐확인)
        self._연결확인()

    # ------------------------------------------------------------------ 화면
    def _스타일(self) -> None:
        스타일 = ttk.Style(self)
        테마 = "clam" if "clam" in 스타일.theme_names() else 스타일.theme_use()
        스타일.theme_use(테마)
        기본폰트 = ("맑은 고딕", 10)
        self.option_add("*Font", 기본폰트)
        스타일.configure("제목.TLabel", font=("맑은 고딕", 12, "bold"))
        스타일.configure("설명.TLabel", foreground="#555555")
        스타일.configure("실행.TButton", font=("맑은 고딕", 11, "bold"))

    def _뼈대(self) -> None:
        위 = ttk.Frame(self, padding=(10, 10, 10, 4))
        위.pack(fill="x")
        ttk.Label(위, text="기능 검색", style="제목.TLabel").pack(side="left")
        self.검색값 = tk.StringVar()
        검색칸 = ttk.Entry(위, textvariable=self.검색값)
        검색칸.pack(side="left", fill="x", expand=True, padx=8)
        검색칸.bind("<KeyRelease>", lambda _사건: self._목록채우기())
        검색칸.focus_set()
        ttk.Button(위, text="지우기", command=self._검색지우기).pack(side="left")

        가운데 = ttk.Frame(self, padding=(10, 4))
        가운데.pack(fill="both", expand=True)

        왼쪽 = ttk.Frame(가운데)
        왼쪽.pack(side="left", fill="y")
        ttk.Label(왼쪽, text="분류").pack(anchor="w")
        self.분류목록 = tk.Listbox(왼쪽, width=16, height=22, exportselection=False)
        self.분류목록.pack(fill="y", expand=True, pady=(2, 0))
        self.분류목록.insert("end", "전체")
        for 이름 in commands.분류순서:
            self.분류목록.insert("end", 이름)
        self.분류목록.selection_set(0)
        self.분류목록.bind("<<ListboxSelect>>", lambda _사건: self._목록채우기())

        중간 = ttk.Frame(가운데)
        중간.pack(side="left", fill="both", expand=True, padx=8)
        ttk.Label(중간, text="기능").pack(anchor="w")
        self.명령목록 = tk.Listbox(중간, height=22, exportselection=False)
        self.명령목록.pack(fill="both", expand=True, pady=(2, 0))
        self.명령목록.bind("<<ListboxSelect>>", lambda _사건: self._명령선택())
        self.명령목록.bind("<Double-Button-1>", lambda _사건: self._실행())

        오른쪽 = ttk.Frame(가운데, width=360)
        오른쪽.pack(side="left", fill="both", expand=True)
        self.기능제목 = ttk.Label(오른쪽, text="기능을 고르세요", style="제목.TLabel")
        self.기능제목.pack(anchor="w")
        self.기능설명 = ttk.Label(오른쪽, text="", style="설명.TLabel", wraplength=340, justify="left")
        self.기능설명.pack(anchor="w", pady=(2, 6))
        self.입력틀 = ttk.Frame(오른쪽)
        self.입력틀.pack(fill="both", expand=True)
        self.실행단추 = ttk.Button(오른쪽, text="실행", style="실행.TButton", command=self._실행)
        self.실행단추.pack(anchor="e", pady=6)

        아래 = ttk.Frame(self, padding=(10, 0, 10, 10))
        아래.pack(fill="both")
        ttk.Label(아래, text="결과").pack(anchor="w")
        self.결과칸 = tk.Text(아래, height=7, wrap="word")
        self.결과칸.pack(fill="both", expand=True)
        self.결과칸.configure(state="disabled")

        self.상태값 = tk.StringVar(value="준비")
        ttk.Label(self, textvariable=self.상태값, style="설명.TLabel", anchor="w").pack(
            fill="x", padx=10, pady=(0, 6)
        )

    # -------------------------------------------------------------- 목록
    def _검색지우기(self) -> None:
        self.검색값.set("")
        self._목록채우기()

    def _고른분류(self) -> str:
        고름 = self.분류목록.curselection()
        if not 고름:
            return "전체"
        return self.분류목록.get(고름[0])

    def _목록채우기(self) -> None:
        질의 = self.검색값.get().strip()
        분류 = self._고른분류()
        후보 = commands.검색(질의) if 질의 else commands.전체명령()
        if 분류 != "전체":
            후보 = [하나 for 하나 in 후보 if 하나.분류 == 분류]

        self._보이는명령 = 후보
        self.명령목록.delete(0, "end")
        for 하나 in 후보:
            표시 = f"{하나.제목}"
            if 하나.필요:
                표시 += f"   [{'·'.join(하나.필요)} 필요]"
            self.명령목록.insert("end", 표시)
        self.상태값.set(f"기능 {len(후보)}개")

    def _명령선택(self) -> None:
        고름 = self.명령목록.curselection()
        if not 고름:
            return
        self.현재명령 = self._보이는명령[고름[0]]
        self.기능제목.configure(text=self.현재명령.제목)
        설명 = self.현재명령.설명 or ""
        if self.현재명령.필요:
            설명 = (설명 + "\n" if 설명 else "") + f"먼저 준비: {', '.join(self.현재명령.필요)}"
        self.기능설명.configure(text=설명)
        self._입력만들기(self.현재명령)

    # -------------------------------------------------------------- 입력칸
    def _입력만들기(self, 명령하나: commands.명령) -> None:
        for 자식 in self.입력틀.winfo_children():
            자식.destroy()
        self._입력위젯.clear()

        if not 명령하나.입력:
            ttk.Label(self.입력틀, text="바로 실행할 수 있습니다.", style="설명.TLabel").pack(
                anchor="w"
            )
            return

        for 항목 in 명령하나.입력:
            줄 = ttk.Frame(self.입력틀)
            줄.pack(fill="x", pady=2)
            ttk.Label(줄, text=항목.표시, width=18, anchor="w").pack(side="left")
            위젯 = self._위젯하나(줄, 항목)
            self._입력위젯[항목.이름] = (항목, 위젯)
            if 항목.설명:
                ttk.Label(
                    self.입력틀, text=f"  {항목.설명}", style="설명.TLabel"
                ).pack(anchor="w")

    def _위젯하나(self, 부모: ttk.Frame, 항목: commands.입력항목) -> Any:
        if 항목.종류 == "선택":
            값 = tk.StringVar(value=str(항목.기본값))
            상자 = ttk.Combobox(부모, textvariable=값, values=list(항목.선택지), state="readonly")
            상자.pack(side="left", fill="x", expand=True)
            return 값
        if 항목.종류 == "체크":
            값 = tk.BooleanVar(value=bool(항목.기본값))
            ttk.Checkbutton(부모, variable=값).pack(side="left")
            return 값
        if 항목.종류 == "여러줄":
            글칸 = tk.Text(부모, height=10, wrap="word")
            글칸.pack(side="left", fill="both", expand=True)
            if 항목.기본값:
                글칸.insert("1.0", str(항목.기본값))
            return 글칸
        if 항목.종류 in ("파일", "폴더", "저장파일"):
            값 = tk.StringVar(value=str(항목.기본값))
            ttk.Entry(부모, textvariable=값).pack(side="left", fill="x", expand=True)
            ttk.Button(
                부모, text="찾기", width=5, command=lambda: self._경로고르기(항목.종류, 값)
            ).pack(side="left", padx=(4, 0))
            return 값
        값 = tk.StringVar(value=str(항목.기본값))
        ttk.Entry(부모, textvariable=값).pack(side="left", fill="x", expand=True)
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

    # -------------------------------------------------------------- 실행
    def _실행(self) -> None:
        if self.현재명령 is None:
            self._결과쓰기("먼저 왼쪽에서 기능을 고르세요.")
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
            맥락값 = commands.맥락(
                문서객체=self.문서객체, 값=값들, 알림=self._알림큐.put
            )
            try:
                결과 = 명령하나.실행(맥락값)
                말 = 결과 if isinstance(결과, str) else f"{명령하나.제목} 완료"
            except 한글오류 as 오류:
                말 = f"[안내] {오류.메시지}\n{오류.도움말}".strip()
            except Exception as 오류:  # noqa: BLE001
                말 = f"[오류] {오류}"
            self.after(0, lambda: self._실행끝(명령하나, 말))

        threading.Thread(target=일하기, daemon=True).start()

    def _실행끝(self, 명령하나: commands.명령, 말: str) -> None:
        self.실행단추.configure(state="normal")
        self.상태값.set(f"{명령하나.제목} 끝")
        self._결과쓰기(말)
        # '보고서 유형으로 시작' 처럼 결과가 마크업이면 렌더 명령칸에 바로 채워 준다.
        if 명령하나.번호 == "보고서.유형":
            self._마크업채우기(말)

    def _마크업채우기(self, 마크업: str) -> None:
        렌더 = commands.찾기("보고서.렌더")
        self.현재명령 = 렌더
        self.기능제목.configure(text=렌더.제목)
        self.기능설명.configure(text=렌더.설명 or "")
        self._입력만들기(렌더)
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

    # -------------------------------------------------------------- 잡동사니
    def _결과쓰기(self, 말: str) -> None:
        self.결과칸.configure(state="normal")
        self.결과칸.delete("1.0", "end")
        self.결과칸.insert("1.0", 말)
        self.결과칸.configure(state="disabled")

    def _큐확인(self) -> None:
        """작업 스레드가 보낸 진행 상황을 상태칸에 보여준다."""
        try:
            while True:
                self.상태값.set(self._알림큐.get_nowait())
        except queue.Empty:
            pass
        self.after(150, self._큐확인)

    def _연결확인(self) -> None:
        가능, 이유 = 사용가능()
        if not 가능:
            self._결과쓰기(
                f"[안내] {이유}\n\n"
                "기능 목록과 도움말은 그대로 볼 수 있지만, 실제 문서 편집은 "
                "윈도우 + 한/글 환경에서만 됩니다."
            )
            self.상태값.set("한/글에 연결하지 않음")
            return
        try:
            버전 = self.문서객체.연결.버전
            self.상태값.set(f"한/글 연결됨 (버전 {버전})")
            self._결과쓰기(
                "한/글에 연결했습니다.\n"
                "위 검색칸에 '콤마', '표', '보고서', 'PDF' 처럼 낱말을 넣어 기능을 찾으세요."
            )
        except 한글오류 as 오류:
            self.상태값.set("한/글 연결 실패")
            self._결과쓰기(
                f"[안내] {오류.메시지}\n{오류.도움말}\n\n"
                "위 검색칸에 '진단' 을 넣고 '한/글 연결 진단' 을 실행하면 "
                "원인을 자세히 볼 수 있습니다."
            )


def 실행하기() -> None:
    """UI 를 띄운다."""
    창 = 본창()
    창.mainloop()
