"""예외 정의. 오류 메시지는 사용자에게 그대로 보여도 되는 한국말로 쓴다."""

from __future__ import annotations

__all__ = ["한글오류", "연결오류", "환경오류", "상태오류", "입력오류"]


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
