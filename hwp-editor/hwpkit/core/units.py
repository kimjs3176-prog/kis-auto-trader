"""단위·색 변환.

한/글은 내부적으로 HWPUNIT(1/7200 인치)을 쓴다. 원본은 매번 COM 객체의
`MiliToHwpUnit` 을 불러 썼는데, 그러면 COM 없이는 계산을 검증할 수 없다.
여기서는 순수 계산으로 두고, COM 값이 필요할 때만 문서 계층에서 쓴다.
"""

from __future__ import annotations

__all__ = [
    "MM당",
    "PT당",
    "mm",
    "pt",
    "pt_mm",
    "hwp단위_mm",
    "rgb",
    "rgb풀기",
    "A4",
    "B4",
    "용지",
]

#: 1mm = 7200 / 25.4 HWPUNIT
MM당 = 7200 / 25.4
#: 1pt = 100 (글자 크기 단위)
PT당 = 100


def mm(값: float) -> int:
    """밀리미터를 HWPUNIT 으로."""
    return int(round(값 * MM당))


def pt(값: float) -> int:
    """포인트를 글자 크기 단위(1/100pt)로."""
    return int(round(값 * PT당))


def pt_mm(값: float) -> float:
    """포인트를 밀리미터로 (1pt = 1/72 인치).

    한/글 문단 여백 입력은 mm 인데, 보고서 편집 기준은 '문단위 10pt' 처럼
    포인트로 쓰여 있어 옮겨 적을 때 이 변환이 필요하다.
    """
    return round(값 * 25.4 / 72, 2)


def hwp단위_mm(값: int) -> float:
    """HWPUNIT 을 밀리미터로 (소수 첫째 자리)."""
    return round(값 / MM당, 1)


def rgb(빨강: int, 초록: int, 파랑: int) -> int:
    """한/글이 쓰는 COLORREF(0x00BBGGRR) 정수로 바꾼다."""
    for 값 in (빨강, 초록, 파랑):
        if not 0 <= 값 <= 255:
            raise ValueError(f"색 값은 0~255 여야 합니다: {값}")
    return 빨강 | (초록 << 8) | (파랑 << 16)


def rgb풀기(값: int) -> tuple[int, int, int]:
    """COLORREF 정수를 (R, G, B) 로."""
    return (값 & 0xFF, (값 >> 8) & 0xFF, (값 >> 16) & 0xFF)


def 색코드(코드: str) -> tuple[int, int, int]:
    """'#3057B9' / '3057B9' 를 (R, G, B) 로."""
    글자 = (코드 or "").lstrip("#").strip()
    if len(글자) != 6:
        raise ValueError(f"색 코드는 6자리여야 합니다: {코드}")
    return (int(글자[0:2], 16), int(글자[2:4], 16), int(글자[4:6], 16))


#: 용지 크기(mm)
A4 = (210.0, 297.0)
B4 = (257.0, 364.0)

용지: dict[str, tuple[float, float]] = {
    "A4": A4,
    "A4가로": (A4[1], A4[0]),
    "B4": B4,
    "B4가로": (B4[1], B4[0]),
}


def 본문너비(용지이름: str, 왼쪽여백: float, 오른쪽여백: float) -> float:
    """용지와 좌우 여백에서 실제 본문 너비(mm)를 구한다.

    표 너비를 정할 때 쓴다. 원본은 `205 - 문단여백측정()` 같은 상수를 함수마다
    다르게 박아 두어 여백을 바꾸면 표가 삐뚤어졌다.
    """
    if 용지이름 not in 용지:
        raise ValueError(f"모르는 용지: {용지이름}")
    너비 = 용지[용지이름][0]
    남은 = 너비 - 왼쪽여백 - 오른쪽여백
    return round(max(남은, 10.0), 1)
