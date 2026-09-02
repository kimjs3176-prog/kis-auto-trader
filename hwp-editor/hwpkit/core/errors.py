"""예외 정의. 오류 메시지는 사용자에게 그대로 보여도 되는 한국말로 쓴다."""

from __future__ import annotations

__all__ = ["한글오류", "연결오류", "환경오류", "상태오류", "입력오류", "오류풀이"]

#: 한/글(COM)이 돌려주는 오류 번호 → 사람이 읽을 말.
#: 화면에 `(-2147352562, '매개 변수의 개수가 잘못되었습니다.', None, None)` 같은
#: 원문이 그대로 뜨면 무엇을 해야 할지 알 수 없어서 여기서 풀어 준다.
_COM풀이 = {
    -2147352562: (  # 0x8002000E DISP_E_BADPARAMCOUNT
        "한/글이 이 기능을 다른 인수 개수로 받습니다.",
        "쓰시는 한/글 판과 맞지 않아 생기는 문제입니다. 어떤 기능에서 났는지 알려 주시면 고칩니다.",
    ),
    -2147352570: (  # 0x80020006 DISP_E_UNKNOWNNAME
        "이 한/글 판에는 없는 기능입니다.",
        "한/글을 최신 판으로 올리면 되는 경우가 많습니다.",
    ),
    -2147352567: (  # 0x80020009 DISP_E_EXCEPTION
        "한/글이 작업을 거절했습니다.",
        "문서가 편집 잠금 상태이거나, 지금 상태에서 할 수 없는 작업일 수 있습니다.",
    ),
    -2147221021: (  # 0x800401E3 MK_E_UNAVAILABLE
        "실행 중인 한/글을 찾지 못했습니다.",
        "한/글을 먼저 켜 두고 다시 눌러 보세요.",
    ),
    -2147024891: (  # 0x80070005 E_ACCESSDENIED
        "권한이 없어 한/글을 조종하지 못했습니다.",
        "한/글과 이 프로그램을 같은 권한으로 실행해야 합니다(둘 다 일반 또는 둘 다 관리자).",
    ),
    -2147418113: (  # 0x8000FFFF E_UNEXPECTED
        "한/글에서 뜻밖의 오류가 났습니다.",
        "한/글을 껐다 켠 뒤 다시 해 보세요.",
    ),
}


def 오류풀이(오류: BaseException) -> str:
    """예외 하나를 화면에 보여 줄 한국말로 바꾼다.

    한/글 COM 오류면 번호를 풀어 주고, 그 밖의 예외는 종류와 함께 보여 준다.
    """
    if isinstance(오류, 한글오류):
        return f"[안내] {오류.메시지}\n{오류.도움말}".strip()

    번호 = _COM번호(오류)
    if 번호 is not None:
        원문 = _COM원문(오류)
        말, 도움말 = _COM풀이.get(
            번호, ("한/글이 오류를 돌려줬습니다.", "한/글을 껐다 켠 뒤 다시 해 보세요.")
        )
        줄들 = [f"[오류] {말}", 도움말]
        if 원문:
            줄들.append(f"한/글이 말한 것: {원문}")
        줄들.append(f"오류 번호: {번호} (0x{번호 & 0xFFFFFFFF:08X})")
        return "\n".join(하나 for 하나 in 줄들 if 하나)
    return f"[오류] {type(오류).__name__}: {오류}"


def _COM번호(오류: BaseException) -> int | None:
    """pywin32 의 com_error 에서 오류 번호(HRESULT)를 꺼낸다."""
    if type(오류).__name__ != "com_error":
        return None
    인수 = getattr(오류, "args", ())
    if 인수 and isinstance(인수[0], int):
        return 인수[0]
    return None


def _COM원문(오류: BaseException) -> str:
    """com_error 안에 들어 있는 한/글 쪽 설명을 꺼낸다."""
    인수 = getattr(오류, "args", ())
    조각: list[str] = []
    for 하나 in 인수[1:]:
        if isinstance(하나, str) and 하나.strip():
            조각.append(하나.strip())
        elif isinstance(하나, tuple):  # excepinfo
            조각.extend(
                낱개.strip() for 낱개 in 하나 if isinstance(낱개, str) and 낱개.strip()
            )
    # 같은 말이 두 번 들어 있는 일이 잦다.
    본것: list[str] = []
    for 하나 in 조각:
        if 하나 not in 본것:
            본것.append(하나)
    return " / ".join(본것)


class 한글오류(Exception):
    """이 프로그램이 발생시키는 모든 오류의 부모."""

    def __init__(self, 메시지: str, 도움말: str = "") -> None:
        super().__init__(메시지)
        self.메시지 = 메시지
        self.도움말 = 도움말

    def __str__(self) -> str:  # pragma: no cover - 표시용
        return f"{self.메시지}\n{self.도움말}".strip()


class 환경오류(한글오류):
    """윈도우가 아니거나 pywin32 가 없는 등 실행 환경 문제."""


class 연결오류(한글오류):
    """한/글 프로그램에 붙지 못했을 때."""


class 상태오류(한글오류):
    """기능을 쓸 수 있는 상태가 아닐 때. (예: 표 안이 아님, 선택 영역 없음)"""


class 입력오류(한글오류):
    """사용자가 넣은 값이 잘못됐을 때."""
