"""날짜 파싱·서식·계산 (순수 함수).

원본의 `날짜변환`(12종 서식), `날짜계산기창`, `각종날짜입력창`, `날짜검색`,
`남해나이함수`/`남해개월함수`를 하나로 합쳤다.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

__all__ = [
    "요일",
    "서식목록",
    "날짜읽기",
    "날짜서식",
    "날짜변환",
    "기간문구",
    "날짜더하기",
    "근무일더하기",
    "일수차이",
    "디데이",
    "주민번호_생년월일",
    "만나이",
    "개월수",
]

요일 = ("월", "화", "수", "목", "금", "토", "일")

#: 서식 이름 -> 설명. UI 선택 목록으로 그대로 쓴다.
서식목록: dict[str, str] = {
    "점": "2025.03.09.",
    "점띄": "2025. 3. 9.",
    "바": "2025-03-09",
    "슬래시": "2025/03/09",
    "한글": "2025년 3월 9일 일요일",
    "한글짧게": "2025년 3월 9일",
    "점요일": "2025.03.09.(일)",
    "점띄요일": "2025. 3. 9.(일)",
    "바요일": "2025-03-09(일)",
    "공문": "2025. 3. 9.(일)",
    "숫자": "20250309",
    "월일": "3. 9.(일)",
}

_한글자모 = re.compile(r"[가-힣]")


def 날짜읽기(원문: str, 기준: date | None = None) -> date | None:
    """사람이 쓴 온갖 날짜 표기를 date 로 바꾼다.

    허용 예: '2025-3-9', '2025.03.09.', '25.3.9', "'25.3.9", '20250309',
    '2025년 3월 9일', '3.9', '3월 9일', '2025. 3. 9.(일)'
    """
    if not 원문:
        return None
    기준 = 기준 or date.today()

    값 = 원문.strip()
    값 = re.sub(r"\([^)]*\)", "", 값)  # (일), (월요일) 등 제거
    값 = 값.replace(" ", "")
    for 따옴표 in ("'", "`", "ʹ", "’", "‘"):
        값 = 값.replace(따옴표, "20")
    값 = 값.replace("년", "-").replace("월", "-").replace("일", "")
    값 = _한글자모.sub("", 값)
    값 = 값.strip(".-/")
    값 = re.sub(r"[./]", "-", 값)
    값 = re.sub(r"-+", "-", 값)

    if re.fullmatch(r"\d{8}", 값):
        값 = f"{값[:4]}-{값[4:6]}-{값[6:]}"
    elif re.fullmatch(r"\d{6}", 값):  # 250309 형태
        값 = f"20{값[:2]}-{값[2:4]}-{값[4:]}"

    조각 = [a for a in 값.split("-") if a]
    if len(조각) == 2:  # 연도 생략 -> 기준 연도
        조각 = [str(기준.year), *조각]
    if len(조각) != 3:
        return None
    if len(조각[0]) == 2:  # 25-3-9
        조각[0] = f"20{조각[0]}"

    try:
        return date(int(조각[0]), int(조각[1]), int(조각[2]))
    except ValueError:
        return None


def 날짜서식(값: date, 종류: str = "공문") -> str:
    """date 를 지정한 서식 문자열로 만든다."""
    요일자 = 요일[값.weekday()]
    표 = {
        "점": f"{값.year}.{값.month:02d}.{값.day:02d}.",
        "점띄": f"{값.year}. {값.month}. {값.day}.",
        "바": f"{값.year}-{값.month:02d}-{값.day:02d}",
        "슬래시": f"{값.year}/{값.month:02d}/{값.day:02d}",
        "한글": f"{값.year}년 {값.month}월 {값.day}일 {요일자}요일",
        "한글짧게": f"{값.year}년 {값.month}월 {값.day}일",
        "점요일": f"{값.year}.{값.month:02d}.{값.day:02d}.({요일자})",
        "점띄요일": f"{값.year}. {값.month}. {값.day}.({요일자})",
        "바요일": f"{값.year}-{값.month:02d}-{값.day:02d}({요일자})",
        "공문": f"{값.year}. {값.month}. {값.day}.({요일자})",
        "숫자": f"{값.year}{값.month:02d}{값.day:02d}",
        "월일": f"{값.month}. {값.day}.({요일자})",
    }
    if 종류 not in 표:
        raise KeyError(f"모르는 날짜 서식: {종류}")
    return 표[종류]


def 날짜변환(원문: str, 종류: str = "공문", 기준: date | None = None) -> str | None:
    """문자열 날짜를 다른 서식으로 바로 변환한다."""
    값 = 날짜읽기(원문, 기준)
    return None if 값 is None else 날짜서식(값, 종류)


def 기간문구(시작: str, 종료: str, 종류: str = "공문") -> str | None:
    """'2025. 3. 9.(일) ~ 3. 14.(금)' 형태의 기간 문구를 만든다.

    같은 해라면 종료일의 연도를 생략해 공문 관행에 맞춘다.
    """
    시 = 날짜읽기(시작)
    종 = 날짜읽기(종료)
    if 시 is None or 종 is None:
        return None
    if 시 > 종:
        시, 종 = 종, 시
    뒤 = 날짜서식(종, "월일" if 시.year == 종.year else 종류)
    return f"{날짜서식(시, 종류)} ~ {뒤}"


def 날짜더하기(기준: str | date, 일수: int) -> date | None:
    """기준일에 일수를 더한다(음수는 이전 날짜)."""
    값 = 기준 if isinstance(기준, date) else 날짜읽기(기준)
    return None if 값 is None else 값 + timedelta(days=일수)


def 근무일더하기(기준: str | date, 근무일: int, 휴일: set[date] | None = None) -> date | None:
    """토·일과 지정한 휴일을 건너뛰고 근무일 기준으로 날짜를 계산한다."""
    값 = 기준 if isinstance(기준, date) else 날짜읽기(기준)
    if 값 is None:
        return None
    휴일 = 휴일 or set()
    걸음 = 1 if 근무일 >= 0 else -1
    남은 = abs(근무일)
    while 남은:
        값 += timedelta(days=걸음)
        if 값.weekday() < 5 and 값 not in 휴일:
            남은 -= 1
    return 값


def 일수차이(시작: str | date, 종료: str | date, 양끝포함: bool = False) -> int | None:
    """두 날짜 사이의 일수. 양끝포함=True 면 공문식 '기간 일수'."""
    시 = 시작 if isinstance(시작, date) else 날짜읽기(시작)
    종 = 종료 if isinstance(종료, date) else 날짜읽기(종료)
    if 시 is None or 종 is None:
        return None
    차이 = (종 - 시).days
    return 차이 + (1 if 양끝포함 and 차이 >= 0 else 0)


def 디데이(목표: str | date, 오늘: date | None = None) -> str | None:
    """'D-12' / 'D-DAY' / 'D+3' 문구를 만든다."""
    값 = 목표 if isinstance(목표, date) else 날짜읽기(목표)
    if 값 is None:
        return None
    차이 = (값 - (오늘 or date.today())).days
    if 차이 == 0:
        return "D-DAY"
    return f"D-{차이}" if 차이 > 0 else f"D+{abs(차이)}"


def 주민번호_생년월일(원문: str, 오늘: date | None = None) -> date | None:
    """주민등록번호(앞 6자리 또는 13자리)에서 생년월일을 뽑는다.

    13자리면 뒤 첫 자리로 세기를 판정하고, 6자리만 있으면 미래가 되지 않도록
    2000년대/1900년대를 고른다.
    """
    자리 = re.sub(r"[^0-9]", "", 원문 or "")
    if len(자리) not in (6, 13):
        return None
    오늘 = 오늘 or date.today()
    연, 월, 일 = int(자리[0:2]), int(자리[2:4]), int(자리[4:6])

    if len(자리) == 13:
        구분 = 자리[6]
        세기 = {"1": 1900, "2": 1900, "5": 1900, "6": 1900,
                "3": 2000, "4": 2000, "7": 2000, "8": 2000,
                "9": 1800, "0": 1800}.get(구분)
        if 세기 is None:
            return None
        연도 = 세기 + 연
    else:
        연도 = 2000 + 연
        if 연도 > 오늘.year:
            연도 -= 100
    try:
        return date(연도, 월, 일)
    except ValueError:
        return None


def 만나이(생일: str | date, 오늘: date | None = None) -> int | None:
    """만 나이를 계산한다."""
    값 = 생일 if isinstance(생일, date) else (주민번호_생년월일(생일) or 날짜읽기(생일))
    if 값 is None:
        return None
    오늘 = 오늘 or date.today()
    나이 = 오늘.year - 값.year - ((오늘.month, 오늘.day) < (값.month, 값.day))
    return 나이 if 나이 >= 0 else None


def 개월수(생일: str | date, 오늘: date | None = None) -> int | None:
    """개월 수를 계산한다(영유아 사업에서 사용)."""
    값 = 생일 if isinstance(생일, date) else (주민번호_생년월일(생일) or 날짜읽기(생일))
    if 값 is None:
        return None
    오늘 = 오늘 or date.today()
    개월 = (오늘.year - 값.year) * 12 + (오늘.month - 값.month)
    if 오늘.day < 값.day:
        개월 -= 1
    return 개월 if 개월 >= 0 else None


def 오늘(종류: str = "공문") -> str:
    """오늘 날짜 문자열."""
    return 날짜서식(datetime.now().date(), 종류)
