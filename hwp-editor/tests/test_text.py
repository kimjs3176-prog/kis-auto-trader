"""순수 로직 테스트 — 한/글(COM) 없이 그대로 돌아간다.

원본 프로그램에는 테스트가 없었고, 텍스트 처리 로직이 COM 호출과 뒤엉켜 있어
검증할 방법도 없었다. 계층을 나눈 덕에 이 부분은 리눅스/맥에서도 검증된다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from hwpkit.text import calc, dates, markup, numbers, refine, transform
from hwpkit.text.transform import 찾아바꾸기규칙


# ------------------------------------------------------------------ 숫자
@pytest.mark.parametrize(
    "값,기대",
    [
        (0, "영"),
        (1, "일"),
        (10, "십"),
        (12, "십이"),
        (100, "백"),
        (1000, "천"),
        (10000, "일만"),
        (200000, "이십만"),
        (1234567, "백이십삼만사천오백육십칠"),
        (100000000, "일억"),
    ],
)
def test_한글금액(값, 기대):
    assert numbers.한글금액(값) == 기대


def test_한글금액_원본버그_확인():
    """원본 `한글화` 는 4자리 그룹 처리가 어긋나 '이십만' 을 만들지 못했다."""
    assert numbers.한글금액(200000) == "이십만"
    assert numbers.한글금액(20000000) == "이천만"


def test_금액문구():
    assert numbers.금액문구("1,200원") == "금 1,200원(금일천이백원)"


def test_콤마():
    assert numbers.콤마넣기("1234567") == "1,234,567"
    assert numbers.콤마넣기("1234.56") == "1,234.56"
    assert numbers.콤마빼기("1,234,567") == "1234567"


def test_콤마_숫자아니면_그대로():
    assert numbers.콤마넣기("해당없음") == "해당없음"


def test_증감문구_증가():
    assert numbers.증감문구("1,000명 → 1,250명") == "1,000명 → 1,250명으로 25% 증가(250명↑)"


def test_증감문구_감소_및_퍼센트():
    assert numbers.증감문구("20% > 15%") == "20% → 15%로 25% 감소(5%p↓)"


def test_증감문구_변화없음():
    assert numbers.증감문구("100건 → 100건") == "100건 → 100건으로 변화없음"


def test_증감문구_읽을수없음():
    assert numbers.증감문구("그냥 문장") is None


def test_조사():
    assert numbers.조사_로으로("명") == "으로"
    assert numbers.조사_로으로("원") == "으로"
    assert numbers.조사_로으로("개") == "로"  # 받침 없음
    assert numbers.조사_로으로("천원") == "으로"


def test_비율분배_합계보존():
    결과 = numbers.비율분배("1,000,000", [("국비", 70), ("지방비", 30)])
    assert 결과 == "1,000,000(국비 700,000, 지방비 300,000)"


def test_비율분배_반올림오차를_마지막이_흡수():
    결과 = numbers.비율분배("100", [("가", 1), ("나", 1), ("다", 1)])
    금액들 = [int(조각.split()[1].replace(",", "")) for 조각 in 결과.split("(")[1].rstrip(")").split(", ")]
    assert sum(금액들) == 100


# ------------------------------------------------------------------ 날짜
@pytest.mark.parametrize(
    "원문",
    ["2025-03-09", "2025.03.09.", "2025. 3. 9.", "20250309", "2025년 3월 9일", "'25.3.9", "25/3/9"],
)
def test_날짜읽기_여러표기(원문):
    assert dates.날짜읽기(원문) == date(2025, 3, 9)


def test_날짜읽기_요일표기_제거():
    assert dates.날짜읽기("2025. 3. 9.(일)") == date(2025, 3, 9)


def test_날짜읽기_연도생략():
    assert dates.날짜읽기("3.9", 기준=date(2026, 1, 1)) == date(2026, 3, 9)


def test_날짜읽기_실패():
    assert dates.날짜읽기("다음 주") is None
    assert dates.날짜읽기("2025-13-45") is None


def test_날짜서식_전체():
    값 = date(2025, 3, 9)  # 일요일
    assert dates.날짜서식(값, "공문") == "2025. 3. 9.(일)"
    assert dates.날짜서식(값, "점") == "2025.03.09."
    assert dates.날짜서식(값, "한글") == "2025년 3월 9일 일요일"
    assert dates.날짜서식(값, "숫자") == "20250309"


def test_기간문구_같은해는_연도생략():
    assert dates.기간문구("2025-03-09", "2025-03-14") == "2025. 3. 9.(일) ~ 3. 14.(금)"


def test_기간문구_해가다르면_전체표기():
    결과 = dates.기간문구("2025-12-30", "2026-01-05")
    assert 결과 == "2025. 12. 30.(화) ~ 2026. 1. 5.(월)"


def test_기간문구_순서바뀌어도_정렬():
    assert dates.기간문구("2025-03-14", "2025-03-09").startswith("2025. 3. 9.")


def test_근무일더하기_주말건너뜀():
    # 2025-03-07 은 금요일 → 근무일 1일 뒤는 월요일(3/10)
    assert dates.근무일더하기("2025-03-07", 1) == date(2025, 3, 10)


def test_일수차이_양끝포함():
    assert dates.일수차이("2025-03-09", "2025-03-14") == 5
    assert dates.일수차이("2025-03-09", "2025-03-14", 양끝포함=True) == 6


def test_디데이():
    assert dates.디데이("2025-03-09", 오늘=date(2025, 3, 1)) == "D-8"
    assert dates.디데이("2025-03-09", 오늘=date(2025, 3, 9)) == "D-DAY"
    assert dates.디데이("2025-03-09", 오늘=date(2025, 3, 10)) == "D+1"


def test_주민번호_생년월일():
    assert dates.주민번호_생년월일("900101-1234567") == date(1990, 1, 1)
    assert dates.주민번호_생년월일("050101-3234567") == date(2005, 1, 1)


def test_주민번호_6자리는_미래가되지않게():
    결과 = dates.주민번호_생년월일("991231", 오늘=date(2025, 1, 1))
    assert 결과 == date(1999, 12, 31)


def test_만나이_개월수():
    assert dates.만나이("2000-06-01", 오늘=date(2025, 5, 31)) == 24
    assert dates.만나이("2000-06-01", 오늘=date(2025, 6, 1)) == 25
    assert dates.개월수("2025-01-15", 오늘=date(2025, 3, 14)) == 1


# ------------------------------------------------------------------ 계산기
@pytest.mark.parametrize(
    "수식,기대",
    [
        ("1+2*3", 7),
        ("(1+2)*3", 9),
        ("10/4", Decimal("2.5")),
        ("1,200 + 300", 1500),
        ("-5+10", 5),
        ("2*(3+4)-5", 9),
        ("1,000원 * 3", 3000),
        ("10 × 3", 30),
    ],
)
def test_수식계산(수식, 기대):
    assert calc.수식계산(수식) == 기대


@pytest.mark.parametrize("수식", ["1+", "(1+2", "1++*2", "abc", "", "1/0"])
def test_수식계산_잘못된입력은_예외(수식):
    with pytest.raises(calc.계산오류):
        calc.수식계산(수식)


def test_수식계산은_eval을_쓰지않는다():
    """코드 실행 위험이 없어야 한다."""
    with pytest.raises(calc.계산오류):
        calc.수식계산("__import__('os').system('echo x')")


def test_블록수식문구():
    assert calc.블록수식문구("1,200 * 3") == "1,200 * 3 = 3,600"


# ------------------------------------------------------------------ 변환
def test_앞뒤붙임():
    원문 = "가\r나\r다"
    assert transform.앞뒤붙임(원문, "○ ", " 등") == "○ 가 등\r\n○ 나 등\r\n○ 다 등"


def test_앞뒤붙임_빈줄은_건너뜀():
    assert transform.앞뒤붙임("가\r\r나", "- ") == "- 가\r\n\r\n- 나"


def test_맨앞뒤제거_어절제거():
    assert transform.맨앞제거("１２３\r４５６", 1) == "２３\r\n５６"
    assert transform.맨뒤제거("abc\rdef", 1) == "ab\r\nde"
    assert transform.어절제거("가 나 다", "앞", 1) == "나 다"
    assert transform.어절제거("가 나 다", "뒤", 1) == "가 나"


def test_정렬_숫자순():
    원문 = "10건\r2건\r33건"
    assert transform.정렬(원문, "숫자순") == "2건\r\n10건\r\n33건"


def test_정렬_짧은차순():
    assert transform.정렬("가나다\r가\r가나", "짧은차순") == "가\r\n가나\r\n가나다"


def test_중복제거():
    assert transform.중복제거("가\r나\r가\r다") == "가\r\n나\r\n다"


def test_번호매기기():
    assert transform.번호매기기("가\r나", "{번호}. ") == "1. 가\r\n2. 나"


def test_글머리교체_기존기호제거():
    assert transform.글머리교체("1. 가\r○ 나\r- 다", "□ ") == "□ 가\r\n□ 나\r\n□ 다"


def test_공백_엔터정리():
    assert transform.공백정리("  가   나  ") == "가 나"
    assert transform.엔터정리("가\r\r\r나") == "가\r\n나"
    assert transform.엔터정리("가\r\r\r나", 빈줄유지=1) == "가\r\n\r\n나"


def test_찾아바꾸기규칙_정규식():
    규칙 = 찾아바꾸기규칙(찾기=r"\d+", 바꾸기="숫자", 정규식=True)
    assert 규칙.적용("2025년 3월") == "숫자년 숫자월"


def test_찾아바꾸기규칙_대소문자():
    규칙 = 찾아바꾸기규칙(찾기="abc", 바꾸기="X")
    assert 규칙.적용("ABC abc") == "X X"
    규칙2 = 찾아바꾸기규칙(찾기="abc", 바꾸기="X", 대소문자구분=True)
    assert 규칙2.적용("ABC abc") == "ABC X"


def test_찾아바꾸기규칙_백슬래시_안전():
    규칙 = 찾아바꾸기규칙(찾기="가", 바꾸기="\\1")
    assert 규칙.적용("가") == "\\1"


def test_규칙적용_순서대로():
    규칙들 = [찾아바꾸기규칙("가", "나"), 찾아바꾸기규칙("나", "다")]
    assert transform.규칙적용("가", 규칙들) == "다"


def test_문장표화_자동구분():
    결과 = transform.문장표화("구분\t2025\t2026\n예산\t100\t200", "자동")
    assert 결과 == [["구분", "2025", "2026"], ["예산", "100", "200"]]


def test_문장표화_구분자없으면_한열():
    assert transform.문장표화("가\n나", "자동") == [["가"], ["나"]]


def test_줄별변환():
    assert transform.줄별변환("1000\r2000", "콤마넣기") == "1,000\r\n2,000"


def test_한줄변환_표에_핵심기능이_모두있다():
    필수 = {"콤마넣기", "금액문구", "한글금액", "날짜공문", "만나이", "개월수", "증감문구"}
    assert 필수 <= set(transform.한줄변환)


# ------------------------------------------------------------------ 순화
def test_순화검사_찾아냄():
    지적들 = refine.검사("금번 사업은 익일까지 만전을 기하여 주시기 바랍니다.")
    대상들 = {지.항목.대상 for 지 in 지적들}
    assert "금번" in 대상들
    assert "익일" in 대상들


def test_순화_자동적용():
    바뀐, 지적들 = refine.자동순화("금번 계획은 익일 시행합니다.")
    assert "이번" in 바뀐 and "다음 날" in 바뀐
    assert len(지적들) == 2


def test_순화_긴표현_우선():
    """'협조하여 주시기 바랍니다' 가 '에 대하여' 같은 짧은 항목보다 먼저 잡혀야 한다."""
    지적들 = refine.검사("적극 협조하여 주시기 바랍니다.")
    assert 지적들[0].항목.대상 == "적극 협조하여 주시기 바랍니다"


def test_순화_없으면_빈목록():
    assert refine.검사("쉬운 말로 쓴 문장입니다.") == []


def test_순화사전_구조():
    사전 = refine.사전읽기()
    assert len(사전) > 50
    assert all(항.권장 for 항 in 사전)


# ------------------------------------------------------------------ 마크업
def test_마크업_기본파싱():
    요소들 = markup.파싱("제목: 계획\n소제목: 배경\n원: 내용")
    assert [항.종류 for 항 in 요소들] == ["제목", "소제목", "원"]
    assert 요소들[0].내용 == "계획"


def test_마크업_표는_하나로_합쳐진다():
    요소들 = markup.파싱("표: 구분 | 값\n표: 예산 | 100\n원: 뒤 내용")
    표 = 요소들[0]
    assert isinstance(표, markup.표요소)
    assert 표.행수 == 2 and 표.열수 == 2
    assert 요소들[1].종류 == "원"


def test_마크업_별칭과_기호():
    요소들 = markup.파싱("대제목: 가\n## 나\n□ 다\n- 라\n※ 마")
    assert [항.종류 for 항 in 요소들] == ["제목", "소제목", "네모", "바", "별"]


def test_마크업_자동번호():
    요소들 = markup.파싱("소제목: 가\n중제목: 1\n중제목: 2\n소제목: 나")
    번호들 = [(항.종류, 항.번호) for 항 in 요소들]
    assert 번호들 == [("소제목", 1), ("중제목", 1), ("중제목", 2), ("소제목", 2)]


def test_마크업_앞뒤빈줄_정리():
    요소들 = markup.파싱("\n\n제목: 가\n\n\n원: 나\n\n")
    assert [항.종류 for 항 in 요소들] == ["제목", "빈줄", "원"]


def test_마크업_모르는줄은_본문():
    요소들 = markup.파싱("그냥 문장입니다")
    assert 요소들[0].종류 == "본문"


def test_예시마크업은_파싱된다():
    요소들 = markup.파싱(markup.예시마크업())
    assert any(isinstance(항, markup.표요소) for 항 in 요소들)
    assert len(요소들) > 8
