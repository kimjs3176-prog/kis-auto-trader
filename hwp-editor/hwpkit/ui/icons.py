"""분류 아이콘 — 선으로 그린 그림.

전에는 분류 아이콘을 `¶ § ▦ ◎` 같은 **글자 기호**로 찍었다. 한글 글꼴에 있는
기호라 깨지지는 않지만, 획 굵기가 글꼴에 따라 제멋대로고 모양이 오래돼 보인다.
그래서 요즘 앱처럼 **같은 굵기의 선 아이콘**을 캔버스에 직접 그린다.

그림 파일을 쓰지 않는 이유는 원본과 같다 — 원본은 버튼 이미지 PNG 만 17MB 였다.
여기서는 좌표 계산 몇 줄로 끝나고, 크기·색을 그때그때 정할 수 있다.

모든 아이콘은 `가운데(x, y)` 를 중심으로 한 변이 `크기` 인 네모 안에 그린다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # pragma: no cover - 이름표에만 쓴다
    import tkinter as tk

# tkinter 를 실제로 들여오지 않는다. 캔버스는 넘겨받아 메서드만 부르므로,
# 이 묶음은 tkinter 없는 곳(리눅스 시험판)에서도 그대로 들여올 수 있다.

__all__ = ["분류아이콘", "그리기", "색칠", "아이콘이름들"]

#: 분류 → 아이콘 이름
_분류아이콘 = {
    "블록 편집": "글줄",
    "표": "격자",
    "서식": "글자",
    "문서": "문서",
    "보고서 만들기": "그래프",
    "양식·메일머지": "편지",
    "일괄 처리": "여러장",
    "도구": "톱니",
}


def 분류아이콘(분류: str) -> str:
    """분류에 맞는 아이콘 이름. 모르는 분류는 점 세 개로 그린다."""
    return _분류아이콘.get(분류, "점셋")


def 아이콘이름들() -> tuple[str, ...]:
    return tuple(_그리는법)


# ------------------------------------------------------------------ 그리는 법
def _글줄(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """글줄 세 개와 커서 — 블록 편집."""
    줄들 = []
    for 번, 몫 in enumerate((1.0, 0.62, 0.85)):
        y = 위 + 폭 * (0.22 + 번 * 0.28)
        줄들.append(캔.create_line(왼, y, 왼 + 폭 * 몫, y, **옵션))
    줄들.append(
        캔.create_line(왼 + 폭 * 0.72, 위 + 폭 * 0.36, 왼 + 폭 * 0.72, 위 + 폭 * 0.64, **옵션)
    )
    return 줄들


def _격자(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """네 칸 격자 — 표."""
    오, 아래 = 왼 + 폭, 위 + 폭
    가운데가로, 가운데세로 = 왼 + 폭 / 2, 위 + 폭 / 2
    return [
        캔.create_line(왼, 위, 오, 위, 오, 아래, 왼, 아래, 왼, 위, **옵션),
        캔.create_line(가운데가로, 위, 가운데가로, 아래, **옵션),
        캔.create_line(왼, 가운데세로, 오, 가운데세로, **옵션),
    ]


def _글자(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """글자 'A' 와 밑줄 — 서식."""
    가운데 = 왼 + 폭 / 2
    아래 = 위 + 폭 * 0.74
    오 = 왼 + 폭 * 0.9
    return [
        캔.create_line(왼 + 폭 * 0.1, 아래, 가운데, 위, 오, 아래, **옵션),
        캔.create_line(왼 + 폭 * 0.28, 위 + 폭 * 0.5, 왼 + 폭 * 0.72, 위 + 폭 * 0.5, **옵션),
        캔.create_line(왼, 위 + 폭, 오, 위 + 폭, **옵션),
    ]


def _문서(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """모서리 접힌 종이 — 문서."""
    오, 아래 = 왼 + 폭 * 0.86, 위 + 폭
    접기 = 폭 * 0.3
    return [
        캔.create_line(
            왼, 위, 오 - 접기, 위, 오, 위 + 접기, 오, 아래, 왼, 아래, 왼, 위, **옵션
        ),
        캔.create_line(오 - 접기, 위, 오 - 접기, 위 + 접기, 오, 위 + 접기, **옵션),
        캔.create_line(왼 + 폭 * 0.16, 위 + 폭 * 0.62, 오 - 폭 * 0.16, 위 + 폭 * 0.62, **옵션),
        캔.create_line(왼 + 폭 * 0.16, 위 + 폭 * 0.8, 오 - 폭 * 0.3, 위 + 폭 * 0.8, **옵션),
    ]


def _그래프(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """막대 세 개와 밑줄 — 보고서 만들기."""
    아래 = 위 + 폭
    막대들 = []
    for 번, 몫 in enumerate((0.42, 0.78, 0.58)):
        x = 왼 + 폭 * (0.18 + 번 * 0.32)
        막대들.append(캔.create_line(x, 아래 - 폭 * 몫, x, 아래 - 폭 * 0.06, **옵션))
    막대들.append(캔.create_line(왼, 아래, 왼 + 폭, 아래, **옵션))
    return 막대들


def _편지(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """봉투 — 양식·메일머지."""
    오 = 왼 + 폭
    윗변 = 위 + 폭 * 0.16
    아래 = 위 + 폭 * 0.84
    return [
        캔.create_line(왼, 윗변, 오, 윗변, 오, 아래, 왼, 아래, 왼, 윗변, **옵션),
        캔.create_line(왼, 윗변, 왼 + 폭 / 2, 위 + 폭 * 0.55, 오, 윗변, **옵션),
    ]


def _여러장(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """겹친 종이 두 장 — 일괄 처리."""
    치우침 = 폭 * 0.22
    앞왼, 앞위 = 왼, 위 + 치우침
    앞오, 앞아래 = 왼 + 폭 - 치우침, 위 + 폭
    return [
        캔.create_line(
            앞왼 + 치우침, 위, 왼 + 폭, 위, 왼 + 폭, 앞아래 - 치우침, **옵션
        ),
        캔.create_line(앞왼, 앞위, 앞오, 앞위, 앞오, 앞아래, 앞왼, 앞아래, 앞왼, 앞위, **옵션),
    ]


def _톱니(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """톱니바퀴 — 도구. (원 하나 + 살 네 개)"""
    가운데가로, 가운데세로 = 왼 + 폭 / 2, 위 + 폭 / 2
    반 = 폭 * 0.3
    그린것 = [
        캔.create_oval(
            가운데가로 - 반,
            가운데세로 - 반,
            가운데가로 + 반,
            가운데세로 + 반,
            outline=옵션.get("fill", "#000000"),
            width=옵션.get("width", 1),
        )
    ]
    for 가로몫, 세로몫 in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        그린것.append(
            캔.create_line(
                가운데가로 + 가로몫 * 반,
                가운데세로 + 세로몫 * 반,
                가운데가로 + 가로몫 * 폭 * 0.5,
                가운데세로 + 세로몫 * 폭 * 0.5,
                **옵션,
            )
        )
    return 그린것


def _점셋(캔: tk.Canvas, 왼: float, 위: float, 폭: float, 옵션: dict) -> list[int]:
    """모르는 분류 — 점 세 개."""
    세로 = 위 + 폭 / 2
    점 = max(1.0, 폭 * 0.08)
    그린것 = []
    for 몫 in (0.2, 0.5, 0.8):
        가로 = 왼 + 폭 * 몫
        그린것.append(
            캔.create_oval(
                가로 - 점,
                세로 - 점,
                가로 + 점,
                세로 + 점,
                fill=옵션.get("fill", "#000000"),
                outline="",
            )
        )
    return 그린것


_그리는법: dict[str, Callable[..., list[int]]] = {
    "글줄": _글줄,
    "격자": _격자,
    "글자": _글자,
    "문서": _문서,
    "그래프": _그래프,
    "편지": _편지,
    "여러장": _여러장,
    "톱니": _톱니,
    "점셋": _점셋,
}


def 그리기(
    캔버스: tk.Canvas,
    이름: str,
    가운데가로: float,
    가운데세로: float,
    크기: float,
    색: str,
    굵기: float | None = None,
) -> list[int]:
    """아이콘을 그리고 그린 것들의 번호를 돌려준다. (`색칠` 로 색을 바꿀 수 있다)"""
    그릴것 = _그리는법.get(이름, _점셋)
    굵기값 = 굵기 if 굵기 is not None else max(1.4, 크기 * 0.1)
    옵션: dict[str, Any] = {"fill": 색, "width": 굵기값, "capstyle": "round"}
    return 그릴것(캔버스, 가운데가로 - 크기 / 2, 가운데세로 - 크기 / 2, 크기, 옵션)


def 색칠(캔버스: tk.Canvas, 번호들: list[int], 색: str) -> None:
    """그려 둔 아이콘 색을 바꾼다. (고른 타일은 흰 아이콘이 된다)

    선은 `fill`, 테두리만 있는 동그라미는 `outline` 으로 색을 잡아야 해서
    캔버스에 물어보고 갈라 쓴다.
    """
    for 번호 in 번호들:
        종류 = 캔버스.type(번호)
        if 종류 == "oval" and not 캔버스.itemcget(번호, "fill"):
            캔버스.itemconfigure(번호, outline=색)
        else:
            캔버스.itemconfigure(번호, fill=색)
