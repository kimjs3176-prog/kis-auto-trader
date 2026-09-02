"""문서 서식 기준 시험 — 회사 보고서 양식에 맞추는 부분.

기준 값은 회사 양식 파일(「보고서 작성 기본 편집요건」)에서 읽어 온 것이다.
그 파일이 정한 숫자(여백 12.7/20mm, 줄간격 160%, 신명조 15pt, 문단위 10/8/5pt)를
프리셋이 그대로 담고 있는지, 그리고 문단마다 수준을 제대로 알아내는지 본다.
"""

from __future__ import annotations

import pytest

from fake_hwp import 문서만들기
from hwpkit.core import units
from hwpkit.core.errors import 입력오류
from hwpkit.features import cleanup, doc_format, outline


# ------------------------------------------------------------------ 기준 읽기
def test_기준이_적어도_두_가지():
    이름들 = doc_format.기준이름들()
    assert "보고서 15pt" in 이름들
    assert "보고서 14pt" in 이름들


def test_양식이_정한_편집여백을_그대로_담는다():
    """양식 첫 줄: '위·아래 12.7mm, 좌·우 20mm, 머리말·꼬리말 12.7mm'."""
    기준 = doc_format.기준찾기("보고서 15pt")
    칸 = 기준.여백값
    assert (칸.위, 칸.아래) == (12.7, 12.7)
    assert (칸.왼쪽, 칸.오른쪽) == (20.0, 20.0)
    assert (칸.머리, 칸.꼬리) == (12.7, 12.7)
    assert 기준.용지 == "A4"


def test_본문은_신명조_줄간격160():
    기준 = doc_format.기준찾기("보고서 15pt")
    assert 기준.본문.폰트 == "한양신명조"
    assert 기준.본문.크기 == 15.0
    assert 기준.본문.줄간격 == 160
    assert 기준.본문.정렬 == "양쪽"
    assert (기준.장평, 기준.자간) == (100, 0)


def test_본문은_굵기를_건드리지_않는다():
    """양식은 '중요한 부분은 진하게' 라고 했다. 정리가 그 강조를 지우면 안 된다."""
    assert doc_format.기준찾기("보고서 15pt").본문.진하게 is None


def test_제목은_헤드라인M_22pt_가운데():
    기준 = doc_format.기준찾기("보고서 15pt")
    assert (기준.제목.폰트, 기준.제목.크기) == ("HY헤드라인M", 22.0)
    assert 기준.제목.정렬 == "가운데"


@pytest.mark.parametrize(
    ("수준", "폰트", "크기", "진하게", "문단위pt"),
    [
        (1, "한양신명조", 15.0, True, 10),
        (2, "한양신명조", 15.0, False, 8),
        (3, "한양신명조", 15.0, False, 5),
        (4, "한양중고딕", 13.0, False, 2),
    ],
)
def test_수준별_서식이_양식과_같다(수준, 폰트, 크기, 진하게, 문단위pt):
    서식 = doc_format.기준찾기("보고서 15pt").수준서식찾기(수준)
    assert 서식 is not None
    assert (서식.폰트, 서식.크기) == (폰트, 크기)
    assert bool(서식.진하게) is 진하게
    assert 서식.문단위pt == 문단위pt


def test_14pt_기준은_본문만_작다():
    열다섯 = doc_format.기준찾기("보고서 15pt")
    열넷 = doc_format.기준찾기("보고서 14pt")
    assert 열넷.본문.크기 == 14.0
    assert 열넷.수준서식찾기(1).크기 == 14.0
    assert 열넷.수준서식찾기(4).크기 == 13.0  # 4수준 중고딕은 두 양식이 같다
    assert 열넷.여백값 == 열다섯.여백값


def test_없는_기준은_쓸_수_있는_목록을_알려_준다():
    with pytest.raises(입력오류) as 잡힘:
        doc_format.기준찾기("없는양식")
    assert "보고서 15pt" in str(잡힘.value)


def test_기준요약은_사람이_읽을_수_있다():
    요약 = doc_format.기준찾기("보고서 15pt").요약
    assert "A4" in 요약 and "12.7" in 요약 and "한양신명조" in 요약 and "160%" in 요약


def test_문단위는_포인트를_밀리미터로_바꾼다():
    assert units.pt_mm(10) == 3.53  # 10pt = 10/72 inch
    assert units.pt_mm(0) == 0.0
    서식 = doc_format.기준찾기("보고서 15pt").수준서식찾기(2)
    assert 서식.위여백 == pytest.approx(2.82, abs=0.01)  # 문단위 8pt


# ------------------------------------------------------------------ 수준 판정
@pytest.mark.parametrize(
    ("줄", "수준"),
    [
        ("□ 추진배경", 1),
        (" □ 추진배경", 1),
        ("■ 추진배경", 1),
        ("  ㅇ 내용입니다", 2),  # 양식이 정한 한글 ㅇ
        ("  ○ 내용입니다", 2),
        ("   - 세부 내용", 3),
        ("    * 참고 사항", 4),
        ("1. 추진배경", 0),  # 번호 소제목
        ("12. 추진배경", 0),
    ],
)
def test_글머리로_수준을_알아낸다(줄, 수준):
    assert doc_format.수준찾기(줄) == 수준


@pytest.mark.parametrize(
    "줄",
    [
        "",
        "그냥 문장입니다.",
        "-------------------",  # 구분선은 글머리가 아니다
        "*강조*",  # 기호 뒤에 공백이 없다
        "□",  # 기호만 있고 내용이 없다
        "□ ",
        "2023. 9. 7.(목) 작성",  # 날짜는 소제목이 아니다
    ],
)
def test_글머리가_아닌_줄은_수준이_없다(줄):
    assert doc_format.수준찾기(줄) is None


def test_목차도_한글_ㅇ_을_2수준으로_본다():
    """양식대로 `ㅇ` 를 쓴 문서에서 목차가 비어 나오면 안 된다."""
    제목들 = outline.제목추출("□ 추진배경\r ㅇ 첫째 항목\r ㅇ 둘째 항목", 최대수준=2)
    assert [하나.수준 for 하나 in 제목들] == [1, 2, 2]


# ------------------------------------------------------------------ 글머리 통일
def test_글머리통일규칙은_기호_뒤_공백까지_짝짓는다():
    규칙 = dict(doc_format.글머리통일규칙(doc_format.기준찾기("보고서 15pt")))
    assert 규칙["○ "] == "ㅇ "
    assert 규칙["● "] == "ㅇ "
    assert 규칙["■ "] == "□ "
    for 찾기 in 규칙:
        assert 찾기.endswith(" "), "공백 없이 바꾸면 '○○○팀' 같은 낱말도 바뀐다"


def test_글머리통일은_문서전체바꾸기를_쓴다():
    문서객체, 한글 = 문서만들기(선택텍스트="○ 내용")
    바꾼수 = doc_format.글머리통일(문서객체, doc_format.기준찾기("보고서 15pt"))
    짝 = [
        (값.get("FindString"), 값.get("ReplaceString"))
        for 이름, 값 in 한글.기록
        if 이름 == "AllReplace"
    ]
    assert 바꾼수 == len(짝) == 4
    assert ("○ ", "ㅇ ") in 짝
    assert all(값.get("FindRegExp") == 0 for 이름, 값 in 한글.기록 if 이름 == "AllReplace")


# ------------------------------------------------------------------ 한/글 적용
def test_용지기준은_문서전체에_적용한다():
    문서객체, 한글 = 문서만들기()
    doc_format.용지기준적용(문서객체, doc_format.기준찾기("보고서 15pt"))
    이름, 세트 = 한글.세트기록[-1]
    assert 이름 == "PageSetup"
    assert 세트.HSet.Item("ApplyTo") == 2  # 2 = 문서 전체
    쪽 = 세트.PageDef
    assert 쪽.값읽기("TopMargin") == units.mm(12.7)
    assert 쪽.값읽기("LeftMargin") == units.mm(20.0)
    assert 쪽.값읽기("PaperWidth") == units.mm(210.0)


def test_문단순회는_문단마다_한_번씩_준다():
    문서객체, _한글 = 문서만들기(선택텍스트="첫 줄\r둘째 줄\r셋째 줄")
    assert list(doc_format.문단순회(문서객체)) == ["첫 줄", "둘째 줄", "셋째 줄"]


def test_문단순회는_한계를_넘지_않는다():
    문서객체, _한글 = 문서만들기(선택텍스트="\r".join(f"{번호}번 줄" for 번호 in range(50)))
    assert len(list(doc_format.문단순회(문서객체, 최대문단=5))) == 5


def test_문단마다_수준_서식을_입힌다():
    본문 = "보고서 제목\r□ 추진배경\r ㅇ 첫째\r  - 자세히\r   * 참고\r그냥 문장"
    문서객체, 한글 = 문서만들기(선택텍스트=본문)
    손댐 = doc_format.문단기준적용(문서객체, doc_format.기준찾기("보고서 15pt"))
    assert 손댐 == 6

    글자 = [값 for 이름, 값 in 한글.기록 if 이름 == "CharShape"]
    문단 = [값 for 이름, 값 in 한글.기록 if 이름 == "ParagraphShape"]
    assert len(글자) == len(문단) == 6

    # 제목 줄은 손대지 않는 것이 기본값이라 본문 서식이 들어간다.
    assert 글자[0]["FaceNameHangul"] == "한양신명조"
    assert 글자[0]["Height"] == units.pt(15)
    assert "Bold" not in 글자[0]  # 본문은 굵기를 건드리지 않는다

    assert 글자[1]["Bold"] == 1  # □ 1수준은 진하게
    assert 문단[1]["TopMargin"] == units.mm(units.pt_mm(10))

    assert 글자[2]["Bold"] == 0  # ㅇ 2수준은 굵지 않게
    assert 문단[2]["TopMargin"] == units.mm(units.pt_mm(8))

    assert 글자[4]["FaceNameHangul"] == "한양중고딕"  # * 4수준
    assert 글자[4]["Height"] == units.pt(13)

    assert all(값["LineSpacing"] == 160 for 값 in 문단)


def test_제목포함이면_첫_문단에_제목_서식():
    문서객체, 한글 = 문서만들기(선택텍스트="보고서 제목\r□ 추진배경")
    doc_format.문단기준적용(문서객체, doc_format.기준찾기("보고서 15pt"), 제목포함=True)
    글자 = [값 for 이름, 값 in 한글.기록 if 이름 == "CharShape"]
    assert 글자[0]["FaceNameHangul"] == "HY헤드라인M"
    assert 글자[0]["Height"] == units.pt(22)
    assert "ParagraphShapeAlignCenter" in 한글.실행기록


def test_빈_문단은_건너뛴다():
    문서객체, _한글 = 문서만들기(선택텍스트="□ 가\r\r\rㅇ 나")
    assert doc_format.문단기준적용(문서객체, doc_format.기준찾기("보고서 15pt")) == 2


def test_기준적용_요약에_한_일이_남는다():
    문서객체, _한글 = 문서만들기(선택텍스트="□ 가\rㅇ 나")
    요약 = doc_format.기준적용(문서객체, "보고서 15pt")
    assert 요약.기준이름 == "보고서 15pt"
    assert 요약.손댄문단 == 2
    assert "문단 2개" in 요약.문구
    assert any("편집용지" in 하나 for 하나 in 요약.한일)
    assert "글머리 기호" in 요약.한일


def test_기준적용은_끌_수_있다():
    문서객체, 한글 = 문서만들기(선택텍스트="□ 가")
    요약 = doc_format.기준적용(문서객체, "보고서 15pt", 용지=False, 문단=False, 글머리=False)
    assert 요약.한일 == []
    assert "바꿀 것이 없었습니다" in 요약.문구
    assert not [이름 for 이름, _값 in 한글.세트기록 if 이름 == "PageSetup"]


# ------------------------------------------------------------------ 정리와 이어짐
def test_문서정리가_기준을_받아_입힌다():
    문서객체, 한글 = 문서만들기(선택텍스트="□ 가\rㅇ 나")
    요약 = cleanup.서식정리(
        문서객체, 표초기화=False, 공백=False, 빈줄=False, 기준="보고서 15pt"
    )
    assert "문단 서식" in 요약.항목  # 먼저 지우고
    assert any("편집용지" in 하나 for 하나 in 요약.항목)  # 그 다음 양식을 입힌다
    assert 요약.항목.index("문단 서식") < 요약.항목.index("글머리 기호")
    assert [이름 for 이름, _값 in 한글.세트기록 if 이름 == "PageSetup"]


def test_기준을_주지_않으면_예전처럼_지우기만():
    문서객체, 한글 = 문서만들기(선택텍스트="□ 가")
    요약 = cleanup.서식정리(문서객체, 표초기화=False, 공백=False, 빈줄=False)
    assert 요약.항목 == ["문단 서식"]
    assert not [이름 for 이름, _값 in 한글.세트기록 if 이름 == "PageSetup"]
