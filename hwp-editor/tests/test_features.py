"""기능 계층 테스트 — 가짜 한/글로 호출 흐름을 검증한다."""

from __future__ import annotations

import pytest

from fake_hwp import 문서만들기
from hwpkit.core import units
from hwpkit.core.errors import 상태오류, 입력오류
from hwpkit.features import block, find_replace, format as 서식, page, report, table_ops
from hwpkit.text.transform import 찾아바꾸기규칙


# ------------------------------------------------------------------ 단위
def test_밀리미터변환():
    assert units.mm(10) == 2835  # 10mm
    assert units.pt(15) == 1500
    assert round(units.hwp단위_mm(2835), 1) == 10.0


def test_색():
    assert units.rgb(255, 0, 0) == 0x0000FF
    assert units.rgb풀기(units.rgb(1, 2, 3)) == (1, 2, 3)
    with pytest.raises(ValueError):
        units.rgb(300, 0, 0)


def test_본문너비():
    assert units.본문너비("A4", 20, 20) == 170.0
    assert units.본문너비("A4가로", 20, 20) == 257.0


# ------------------------------------------------------------------ 문서
def test_선택없으면_안내오류():
    문서객체, _한글 = 문서만들기()
    with pytest.raises(상태오류):
        문서객체.선택텍스트()


def test_선택교체는_문단을_나눠_입력():
    문서객체, 한글 = 문서만들기(선택텍스트="가")
    문서객체.선택교체("가\r나\r다")
    입력들 = [값.get("Text") for 이름, 값 in 한글.기록 if 이름 == "InsertText"]
    assert 입력들 == ["가", "나", "다"]
    assert 한글.실행기록.count("BreakPara") == 2


def test_한번에_실패하면_되돌린다():
    문서객체, 한글 = 문서만들기(선택텍스트="가")
    with pytest.raises(RuntimeError):
        with 문서객체.한번에("시험"):
            문서객체.문장입력("하나")
            문서객체.문장입력("둘")
            raise RuntimeError("일부러 실패")
    assert 한글.실행기록.count("Undo") == 2


def test_셀블록범위_방향무관():
    """↖ 방향으로 끌어도(끝 목록이 작아도) 같은 범위가 나와야 한다."""
    셀값 = {10: "1", 11: "2", 12: "3", 13: "4"}
    주소 = {10: "B2", 11: "C2", 12: "B3", 13: "C3"}
    문서객체, _한글 = 문서만들기(셀값=셀값, 셀주소=주소)
    범위 = 문서객체.셀블록범위()
    assert (범위.시작.이름, 범위.끝.이름) == ("B2", "C3")
    assert 범위.행수 == 2 and 범위.열수 == 2 and 범위.셀수 == 4


def test_셀주소_Z열넘김():
    from hwpkit.core.document import 셀주소

    assert 셀주소.읽기("AA12") == 셀주소(열=27, 행=12)
    assert 셀주소(열=27, 행=12).이름 == "AA12"
    assert 셀주소.읽기("(B3)").이름 == "B3"


def test_필드목록_파싱():
    문서객체, 한글 = 문서만들기()
    한글.필드이름 = ["성명{{0}}", "부서{{1}}", "성명{{2}}"]
    assert 문서객체.필드목록() == ["성명", "부서"]


# ------------------------------------------------------------------ 블록
def test_블록_줄별변환():
    문서객체, 한글 = 문서만들기(선택텍스트="1000\r2000")
    block.줄별변환실행(문서객체, "콤마넣기")
    입력들 = [값.get("Text") for 이름, 값 in 한글.기록 if 이름 == "InsertText"]
    assert 입력들 == ["1,000", "2,000"]


def test_블록_모르는변환은_입력오류():
    문서객체, _한글 = 문서만들기(선택텍스트="1000")
    with pytest.raises(입력오류):
        block.줄별변환실행(문서객체, "없는변환")


def test_블록_앞뒤붙임():
    문서객체, 한글 = 문서만들기(선택텍스트="가\r나")
    block.앞뒤붙임실행(문서객체, 앞="○ ", 뒤=" 등")
    입력들 = [값.get("Text") for 이름, 값 in 한글.기록 if 이름 == "InsertText"]
    assert 입력들 == ["○ 가 등", "○ 나 등"]


def test_블록_통계():
    문서객체, _한글 = 문서만들기(선택텍스트="가 나\r다")
    값 = block.블록통계(문서객체)
    assert 값["줄수"] == 2 and 값["낱말수"] == 3


def test_블록_계산():
    문서객체, 한글 = 문서만들기(선택텍스트="1,200 * 3")
    결과 = block.계산실행(문서객체)
    assert 결과 == "1,200 * 3 = 3,600"


def test_블록_비율분배_금액없으면_안내():
    문서객체, _한글 = 문서만들기(선택텍스트="금액 없음")
    with pytest.raises(상태오류):
        block.비율분배실행(문서객체, [("국비", 70), ("지방비", 30)])


# ------------------------------------------------------------------ 서식
def test_글자모양_언어별폰트를_모두설정():
    문서객체, 한글 = 문서만들기()
    서식.글자모양(문서객체, 폰트="맑은 고딕", 크기=15, 진하게=True)
    이름, 값 = [항 for 항 in 한글.기록 if 항[0] == "CharShape"][0]
    assert 값["FaceNameHangul"] == "맑은 고딕"
    assert 값["FaceNameLatin"] == "맑은 고딕"
    assert 값["Height"] == 1500
    assert 값["Bold"] == 1


def test_글자모양_주지않은값은_건드리지않음():
    문서객체, 한글 = 문서만들기()
    서식.글자모양(문서객체, 크기=12)
    _이름, 값 = [항 for 항 in 한글.기록 if 항[0] == "CharShape"][0]
    assert "FaceNameHangul" not in 값 and "Bold" not in 값


def test_스타일적용():
    문서객체, 한글 = 문서만들기()
    서식.스타일적용(문서객체, "소제목")
    _이름, 값 = [항 for 항 in 한글.기록 if 항[0] == "CharShape"][0]
    assert 값["Bold"] == 1
    assert "ParagraphShapeAlignLeft" in 한글.실행기록


def test_없는스타일():
    문서객체, _한글 = 문서만들기()
    with pytest.raises(입력오류):
        서식.스타일적용(문서객체, "없는스타일")


def test_문단모양_정렬만():
    문서객체, 한글 = 문서만들기()
    서식.문단모양(문서객체, 정렬="가운데")
    assert "ParagraphShapeAlignCenter" in 한글.실행기록
    assert not [항 for 항 in 한글.기록 if 항[0] == "ParagraphShape"]


# ------------------------------------------------------------------ 표
def test_표만들기_너비계산():
    문서객체, 한글 = 문서만들기()
    table_ops.표만들기(문서객체, 열수=3, 행수=2, 전체너비=150)
    이름, 세트 = 한글.세트기록[-1]
    assert 이름 == "TableCreate"
    assert 세트.값읽기("Rows") == 2
    assert 세트.값읽기("Cols") == 3


def test_표만들기_잘못된크기():
    문서객체, _한글 = 문서만들기()
    with pytest.raises(입력오류):
        table_ops.표만들기(문서객체, 열수=0, 행수=3)


def test_표기능은_표밖에서_안내오류():
    문서객체, _한글 = 문서만들기(선택텍스트="가")
    with pytest.raises(상태오류):
        table_ops.셀너비자동(문서객체)


def test_셀변환_여러셀():
    셀값 = {5: "1000", 6: "2000", 7: ""}
    주소 = {5: "A1", 6: "B1", 7: "C1"}
    문서객체, 한글 = 문서만들기(셀값=셀값, 셀주소=주소)
    바뀐 = table_ops.셀변환(문서객체, "콤마넣기")
    assert 바뀐 == 2
    assert 한글.셀값[5] == "1,000" and 한글.셀값[6] == "2,000"


def test_대량계산():
    셀값 = {1: "1000", 2: "2000"}
    주소 = {1: "A1", 2: "A2"}
    문서객체, 한글 = 문서만들기(셀값=셀값, 셀주소=주소)
    바뀐 = table_ops.대량계산(문서객체, "값 * 1.1")
    assert 바뀐 == 2
    assert 한글.셀값[1] == "1,100" and 한글.셀값[2] == "2,200"


def test_대량계산_수식에_값없으면_안내():
    문서객체, _한글 = 문서만들기(셀값={1: "10"}, 셀주소={1: "A1"})
    with pytest.raises(입력오류):
        table_ops.대량계산(문서객체, "1 + 2")


def test_합계수식_범위():
    셀값 = {1: "1", 2: "2", 3: "3"}
    주소 = {1: "B2", 2: "B3", 3: "B4"}
    문서객체, 한글 = 문서만들기(셀값=셀값, 셀주소=주소)
    table_ops.합계넣기(문서객체, "합계")
    _이름, 값 = [항 for 항 in 한글.기록 if 항[0] == "TableFormula"][0]
    assert 값["Command"].startswith("=SUM(B2:B4)")


def test_셀앞뒤붙임():
    셀값 = {1: "100", 2: "200"}
    주소 = {1: "A1", 2: "A2"}
    문서객체, 한글 = 문서만들기(셀값=셀값, 셀주소=주소)
    바뀐 = table_ops.셀앞뒤붙임(문서객체, 뒤="원")
    assert 바뀐 == 2 and 한글.셀값[1] == "100원"


# ------------------------------------------------------------------ 찾아바꾸기
def test_문서전체바꾸기_파라미터():
    문서객체, 한글 = 문서만들기()
    규칙 = 찾아바꾸기규칙(찾기="가", 바꾸기="나", 정규식=True)
    결과 = find_replace.문서전체바꾸기(문서객체, [규칙])
    _이름, 값 = [항 for 항 in 한글.기록 if 항[0] == "AllReplace"][0]
    assert 값["FindString"] == "가" and 값["ReplaceString"] == "나"
    assert 값["FindRegExp"] == 1 and 값["ReplaceMode"] == 1
    assert "1건" in 결과.문구


def test_찾기규칙없으면_입력오류():
    문서객체, _한글 = 문서만들기()
    with pytest.raises(입력오류):
        find_replace.문서전체바꾸기(문서객체, [찾아바꾸기규칙(찾기="")])


def test_셀바꾸기():
    셀값 = {1: "2025년 계획", 2: "2025년 실적"}
    주소 = {1: "A1", 2: "A2"}
    문서객체, 한글 = 문서만들기(셀값=셀값, 셀주소=주소)
    결과 = find_replace.셀바꾸기(문서객체, [찾아바꾸기규칙(찾기="2025", 바꾸기="2026")])
    assert 결과.바뀐건 == 2
    assert 한글.셀값[1] == "2026년 계획"


# ------------------------------------------------------------------ 쪽·보고서
def test_용지설정():
    문서객체, 한글 = 문서만들기()
    page.용지설정(문서객체, 용지="A4", 여백값="공문기본")
    이름, 세트 = 한글.세트기록[-1]
    assert 이름 == "PageSetup"


def test_모르는용지():
    문서객체, _한글 = 문서만들기()
    with pytest.raises(입력오류):
        page.용지설정(문서객체, 용지="A9")


def test_쪽번호_위치():
    문서객체, 한글 = 문서만들기()
    page.쪽번호넣기(문서객체, "오른쪽아래")
    _이름, 값 = [항 for 항 in 한글.기록 if 항[0] == "PageNumPos"][0]
    assert 값["DrawPos"] == 6


def test_보고서템플릿_모두_렌더가능한마크업():
    from hwpkit.text import markup

    for 이름 in report.템플릿목록():
        마크업 = report.템플릿마크업(이름)
        요소들 = markup.파싱(마크업)
        assert 요소들, f"{이름} 템플릿이 비었습니다"
        assert 요소들[0].종류 == "제목", f"{이름} 은 제목으로 시작해야 합니다"


def test_보고서_렌더가_표와_문단을_그린다():
    문서객체, 한글 = 문서만들기()
    마크업 = "제목: 계획\n소제목: 배경\n원: 내용\n표: 구분 | 값\n표: 예산 | 100"
    결과 = report.렌더(문서객체, 마크업, 새문서=True)
    assert 결과.표수 == 1
    # 표: 두 줄은 하나의 표 요소로 합쳐지므로 제목·소제목·원·표 = 4개
    assert 결과.요소수 == 4
    입력들 = [값.get("Text") for 이름, 값 in 한글.기록 if 이름 == "InsertText"]
    assert "계획" in 입력들
    assert "□ 1. 배경" in 입력들
    assert "예산" in 입력들


def test_보고서_빈마크업은_입력오류():
    문서객체, _한글 = 문서만들기()
    with pytest.raises(입력오류):
        report.렌더(문서객체, "   ")


def test_미리보기_문구():
    말 = report.마크업미리보기("제목: 가\n표: 1 | 2")
    assert "[제목] 가" in 말 and "[표] 1행 × 2열" in 말
