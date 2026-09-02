"""명령 레지스트리·CLI·양식·일괄처리 테스트.

명령 표가 곧 화면 구성이므로, 표 자체가 성립하는지(중복·잘못된 선택지 등)를
자동으로 검증한다. 원본은 창마다 손으로 짠 코드여서 이런 검증이 불가능했다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fake_hwp import 문서만들기
from hwpkit import commands
from hwpkit.core.errors import 입력오류
from hwpkit.features import batch, forms, mailmerge
from hwpkit.text.transform import 찾아바꾸기규칙


# ------------------------------------------------------------------ 레지스트리
def test_명령이_충분히_등록됨():
    assert len(commands.전체명령()) >= 40


def test_모든분류에_명령이_있다():
    묶음 = commands.분류별명령()
    for 이름 in commands.분류순서:
        assert 묶음[이름], f"{이름} 분류가 비었습니다"


def test_명령번호_중복없음():
    번호들 = [하나.번호 for 하나 in commands.전체명령()]
    assert len(번호들) == len(set(번호들))


def test_선택입력의_기본값은_선택지에_있다():
    for 하나 in commands.전체명령():
        for 항목 in 하나.입력:
            if 항목.종류 == "선택":
                assert 항목.선택지, f"{하나.번호}/{항목.이름} 선택지가 비었습니다"
                assert 항목.기본값 in 항목.선택지, f"{하나.번호}/{항목.이름} 기본값이 선택지에 없습니다"


def test_입력종류는_UI가_아는것만():
    아는종류 = {"문자", "여러줄", "숫자", "소수", "선택", "체크", "파일", "폴더", "저장파일"}
    for 하나 in commands.전체명령():
        for 항목 in 하나.입력:
            assert 항목.종류 in 아는종류, f"{하나.번호}/{항목.이름}: {항목.종류}"


def test_필요조건은_정해진값만():
    for 하나 in commands.전체명령():
        assert set(하나.필요) <= {"선택", "표"}


def test_검색():
    assert any(하나.번호 == "표.대량계산" for 하나 in commands.검색("대량"))
    assert any("PDF" in 하나.제목 for 하나 in commands.검색("pdf"))
    assert commands.검색("존재하지않는낱말") == []


def test_검색은_여러낱말을_모두포함():
    결과 = commands.검색("셀 바꾸기")
    assert 결과 and all("셀" in 하나.제목 or "셀" in " ".join(하나.검색어) for 하나 in 결과)


def test_찾기_없는번호():
    with pytest.raises(입력오류):
        commands.찾기("없는.명령")


def test_기관별기능이_남아있지않다():
    """기관 한정 기능은 모두 제거했다. (요청 사항)"""
    금지 = ("경남", "남해", "서울시", "인천", "용인", "행안부", "산인공", "제주교", "광주", "합천")
    본문 = " ".join(
        f"{하나.번호} {하나.제목} {하나.설명} {' '.join(하나.검색어)}"
        for 하나 in commands.전체명령()
    )
    for 낱말 in 금지:
        assert 낱말 not in 본문, f"기관 한정 기능이 남아 있습니다: {낱말}"


# ------------------------------------------------------------------ 실행
def test_맥락_값읽기():
    문서객체, _한글 = 문서만들기()
    맥락값 = commands.맥락(문서객체=문서객체, 값={"수": "12", "켬": "1", "소수": "1.5"})
    assert 맥락값.정수("수") == 12
    assert 맥락값.참("켬") is True
    assert 맥락값.소수("소수") == 1.5
    assert 맥락값.글("없음", "기본") == "기본"


def test_맥락_숫자아니면_입력오류():
    문서객체, _한글 = 문서만들기()
    맥락값 = commands.맥락(문서객체=문서객체, 값={"수": "열둘"})
    with pytest.raises(입력오류):
        맥락값.정수("수")


def test_명령실행_블록변환():
    문서객체, 한글 = 문서만들기(선택텍스트="1000")
    하나 = commands.찾기("블록.변환")
    말 = 하나.실행(commands.맥락(문서객체=문서객체, 값={"변환": "콤마넣기"}))
    assert "콤마넣기" in 말
    assert [값.get("Text") for 이름, 값 in 한글.기록 if 이름 == "InsertText"] == ["1,000"]


def test_명령실행_날짜변환():
    문서객체, 한글 = 문서만들기()
    하나 = commands.찾기("도구.날짜변환")
    말 = 하나.실행(
        commands.맥락(문서객체=문서객체, 값={"날짜": "2025-3-9", "서식": "공문", "넣기": True})
    )
    assert 말 == "2025. 3. 9.(일)"
    assert ("InsertText", {"Text": "2025. 3. 9.(일)"}) in 한글.기록


def test_명령실행_보고서유형은_마크업을_돌려준다():
    문서객체, _한글 = 문서만들기()
    하나 = commands.찾기("보고서.유형")
    말 = 하나.실행(commands.맥락(문서객체=문서객체, 값={"유형": "정책보고"}))
    assert 말.startswith("제목:")
    assert "소제목:" in 말


def test_명령실행_증감문구():
    문서객체, _한글 = 문서만들기()
    하나 = commands.찾기("도구.증감")
    말 = 하나.실행(
        commands.맥락(문서객체=문서객체, 값={"내용": "100건 → 150건", "넣기": False})
    )
    assert "50% 증가" in 말


def test_명령실행_잘못된입력은_안내오류():
    문서객체, _한글 = 문서만들기()
    하나 = commands.찾기("도구.증감")
    with pytest.raises(입력오류):
        하나.실행(commands.맥락(문서객체=문서객체, 값={"내용": "숫자없음"}))


# ------------------------------------------------------------------ CLI
def test_CLI_목록(capsys):
    from hwpkit.cli import 주실행

    assert 주실행(["목록"]) == 0
    출력 = capsys.readouterr().out
    assert "[블록 편집]" in 출력 and "모두" in 출력


def test_CLI_목록_분류(capsys):
    from hwpkit.cli import 주실행

    assert 주실행(["목록", "--분류", "표"]) == 0
    출력 = capsys.readouterr().out
    assert "표.만들기" in 출력 and "블록.변환" not in 출력


def test_CLI_도움(capsys):
    from hwpkit.cli import 주실행

    assert 주실행(["도움", "표.대량계산"]) == 0
    출력 = capsys.readouterr().out
    assert "수식" in 출력 and "python -m hwpkit 실행" in 출력


def test_CLI_값파싱():
    from hwpkit.cli import _값파싱

    assert _값파싱(["가=1", "나=2=3"]) == {"가": "1", "나": "2=3"}
    with pytest.raises(SystemExit):
        _값파싱(["가"])


# ------------------------------------------------------------------ 양식
def test_양식목록_폴더지정(tmp_path, monkeypatch):
    (tmp_path / "출장신청서.hwp").write_bytes(b"x")
    (tmp_path / "~임시.hwp").write_bytes(b"x")
    (tmp_path / "메모.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("HWPKIT_FORMS", str(tmp_path))

    목록 = forms.양식목록()
    이름들 = [하나.이름 for 하나 in 목록]
    assert "출장신청서" in 이름들
    assert "~임시" not in 이름들 and "메모" not in 이름들


def test_양식찾기_없으면_안내에_폴더가_들어간다(monkeypatch, tmp_path):
    monkeypatch.setenv("HWPKIT_FORMS", str(tmp_path))
    with pytest.raises(입력오류) as 정보:
        forms.양식찾기("없는양식")
    assert "양식 폴더" in 정보.value.도움말


def test_자리표시자_본문에서_찾기():
    문서객체, 한글 = 문서만들기()
    한글.본문 = "수신 {{기관명}} 귀하\n제목 {{제목}}\n{{기관명}} 재등장"
    assert forms.자리표시자목록(문서객체) == ["기관명", "제목"]


def test_양식채우기_필드가있으면_필드로():
    문서객체, 한글 = 문서만들기()
    한글.필드이름 = ["성명", "부서"]
    채움 = forms.양식채우기(문서객체, {"성명": "홍길동", "부서": "총무과"})
    assert 채움 == 2
    assert 한글.필드값 == {"성명": "홍길동", "부서": "총무과"}


def test_양식채우기_필드가없으면_찾아바꾸기로():
    문서객체, 한글 = 문서만들기()
    한글.본문 = "{{성명}} 님"
    forms.양식채우기(문서객체, {"성명": "홍길동"})
    바꾸기들 = [값 for 이름, 값 in 한글.기록 if 이름 == "AllReplace"]
    assert 바꾸기들 and 바꾸기들[0]["FindString"] == "{{성명}}"
    assert 바꾸기들[0]["ReplaceString"] == "홍길동"


# ------------------------------------------------------------------ 메일머지
def test_자료읽기_CSV(tmp_path):
    파일 = tmp_path / "명단.csv"
    파일.write_text("성명,부서\n홍길동,총무과\n김농부,기술과\n", encoding="utf-8-sig")
    줄들 = mailmerge.자료읽기(파일)
    assert 줄들 == [
        {"성명": "홍길동", "부서": "총무과"},
        {"성명": "김농부", "부서": "기술과"},
    ]


def test_자료읽기_CP949도_읽는다(tmp_path):
    파일 = tmp_path / "명단.csv"
    파일.write_bytes("성명,부서\n홍길동,총무과\n".encode("cp949"))
    줄들 = mailmerge.자료읽기(파일)
    assert 줄들[0]["성명"] == "홍길동"


def test_자료읽기_모르는형식(tmp_path):
    파일 = tmp_path / "자료.json"
    파일.write_text("{}", encoding="utf-8")
    with pytest.raises(입력오류):
        mailmerge.자료읽기(파일)


def test_파일이름만들기():
    자료 = {"성명": "홍길동", "부서": "총무과"}
    assert mailmerge.파일이름만들기("{성명}_{부서}", 자료, 1) == "홍길동_총무과"
    assert mailmerge.파일이름만들기("{순번}", 자료, 7) == "007"


def test_파일이름만들기_금지문자제거():
    자료 = {"제목": "가/나:다*라"}
    assert mailmerge.파일이름만들기("{제목}", 자료, 1) == "가_나_다_라"


def test_메일머지_한바퀴(tmp_path, monkeypatch):
    양식폴더 = tmp_path / "양식"
    양식폴더.mkdir()
    (양식폴더 / "공문.hwp").write_bytes(b"x")
    monkeypatch.setenv("HWPKIT_FORMS", str(양식폴더))

    자료 = tmp_path / "명단.csv"
    자료.write_text("성명,부서\n홍길동,총무과\n김농부,기술과\n", encoding="utf-8")

    문서객체, 한글 = 문서만들기()
    한글.필드이름 = ["성명", "부서"]
    결과 = mailmerge.메일머지(
        문서객체,
        양식이름="공문",
        자료=자료,
        저장폴더=tmp_path / "결과",
        파일이름서식="{성명}",
        형식="HWP+PDF",
    )
    assert len(결과.성공) == 2 and not 결과.실패
    저장이름 = [Path(경로).name for 경로, _형식 in 한글.저장기록]
    assert "홍길동.hwp" in 저장이름 and "홍길동.pdf" in 저장이름


def test_메일머지_자료가없으면_안내(tmp_path, monkeypatch):
    monkeypatch.setenv("HWPKIT_FORMS", str(tmp_path))
    (tmp_path / "공문.hwp").write_bytes(b"x")
    빈자료 = tmp_path / "빈.csv"
    빈자료.write_text("성명,부서\n", encoding="utf-8")
    문서객체, _한글 = 문서만들기()
    with pytest.raises(입력오류):
        mailmerge.메일머지(문서객체, "공문", 빈자료, tmp_path / "결과")


# ------------------------------------------------------------------ 일괄처리
def test_파일찾기_확장자와_임시파일(tmp_path):
    (tmp_path / "가.hwp").write_bytes(b"x")
    (tmp_path / "나.hwpx").write_bytes(b"x")
    (tmp_path / "~다.hwp").write_bytes(b"x")
    (tmp_path / "라.docx").write_bytes(b"x")
    안쪽 = tmp_path / "안쪽"
    안쪽.mkdir()
    (안쪽 / "마.hwp").write_bytes(b"x")

    이름들 = [파일.name for 파일 in batch.파일찾기(tmp_path)]
    assert set(이름들) == {"가.hwp", "나.hwpx", "마.hwp"}

    얕게 = [파일.name for 파일 in batch.파일찾기(tmp_path, 하위폴더포함=False)]
    assert "마.hwp" not in 얕게


def test_파일찾기_폴더없음():
    with pytest.raises(입력오류):
        batch.파일찾기("/없는/폴더/입니다")


def test_일괄작업_할일없으면_안내(tmp_path):
    (tmp_path / "가.hwp").write_bytes(b"x")
    문서객체, _한글 = 문서만들기()
    with pytest.raises(입력오류):
        batch.일괄실행(문서객체, tmp_path, batch.일괄작업())


def test_일괄_미리보기는_저장하지않는다(tmp_path):
    (tmp_path / "가.hwp").write_bytes(b"x")
    문서객체, 한글 = 문서만들기()
    한글.본문 = "2025년 계획"
    작업 = batch.일괄작업(바꾸기규칙=[찾아바꾸기규칙(찾기="2025", 바꾸기="2026")])
    결과 = batch.일괄실행(문서객체, tmp_path, 작업, 미리보기=True)
    assert 결과.성공수 == 1
    assert 한글.저장기록 == []
    assert "미리보기" in 결과.파일들[0].메모


def test_일괄_PDF변환(tmp_path):
    (tmp_path / "가.hwp").write_bytes(b"x")
    (tmp_path / "나.hwp").write_bytes(b"x")
    문서객체, 한글 = 문서만들기()
    작업 = batch.일괄작업(PDF변환=True, 저장=False, 출력폴더=str(tmp_path / "출력"))
    결과 = batch.일괄실행(문서객체, tmp_path, 작업)
    assert 결과.성공수 == 2
    형식들 = {형식 for _경로, 형식 in 한글.저장기록}
    assert 형식들 == {"PDF"}


def test_일괄_보고서문구(tmp_path):
    (tmp_path / "가.hwp").write_bytes(b"x")
    문서객체, _한글 = 문서만들기()
    작업 = batch.일괄작업(PDF변환=True, 저장=False)
    보고 = batch.일괄실행(문서객체, tmp_path, 작업).보고서()
    assert "가.hwp" in 보고 and "1개 처리" in 보고


# ------------------------------------------------------------------ 연결 계층
def test_늦은바인딩을_쓴다():
    """exe 로 묶으면 gencache(EnsureDispatch)는 캐시를 쓸 수 없어 실패한다.

    실제로 첫 exe 빌드가 이 문제로 '한/글을 실행할 수 없습니다' 를 냈다.
    늦은 바인딩(Dispatch)으로 되돌아가지 않도록 지켜 준다.
    """
    import ast

    본문 = (Path(__file__).resolve().parent.parent / "hwpkit/core/connection.py").read_text(
        encoding="utf-8"
    )
    나무 = ast.parse(본문)
    # 설명(문서화 문자열)에는 EnsureDispatch 가 나올 수 있으므로 실제 코드만 본다.
    이름들 = {
        노드.attr if isinstance(노드, ast.Attribute) else 노드.id
        for 노드 in ast.walk(나무)
        if isinstance(노드, (ast.Attribute, ast.Name))
    }
    가져온것 = {
        별칭.name
        for 노드 in ast.walk(나무)
        if isinstance(노드, ast.ImportFrom)
        for 별칭 in 노드.names
    }
    assert "EnsureDispatch" not in 이름들 | 가져온것, "gencache.EnsureDispatch 는 exe 에서 실패한다"
    assert "Dispatch" in 가져온것


def test_스레드마다_COM초기화한다():
    """화면은 기능을 작업 스레드에서 돌리므로 스레드별 CoInitialize 가 필요하다."""
    본문 = (Path(__file__).resolve().parent.parent / "hwpkit/core/connection.py").read_text(
        encoding="utf-8"
    )
    assert "threading.local()" in 본문
    assert "CoInitialize" in 본문


def test_프로그램ID_후보():
    from hwpkit.core.connection import 프로그램ID들

    assert "HWPFrame.HwpObject" in 프로그램ID들
    assert len(프로그램ID들) >= 2, "버전에 따라 .1 이 붙은 ProgID 만 등록된 경우가 있다"


def test_사용가능_리눅스에서는_거짓():
    from hwpkit.core.connection import 사용가능

    가능, 이유 = 사용가능()
    assert 가능 is False and "윈도우" in 이유


def test_진단은_환경부터_보고한다():
    from hwpkit.core.connection import 진단

    말 = 진단()
    assert "[실행 환경]" in 말
    assert "비트" in 말 and "실행 형태" in 말
    assert "[중단]" in 말  # 리눅스에서는 여기서 멈춘다


def test_진단명령_등록됨():
    하나 = commands.찾기("도구.연결진단")
    문서객체, _한글 = 문서만들기()
    말 = 하나.실행(commands.맥락(문서객체=문서객체))
    assert "[실행 환경]" in 말


def test_CLI_영문별칭(capsys):
    """한글 인자가 깨지는 콘솔(예: 일부 cmd 설정)에서도 쓸 수 있어야 한다."""
    from hwpkit.cli import 주실행

    assert 주실행(["list", "--분류", "도구"]) == 0
    출력 = capsys.readouterr().out
    assert "도구.연결진단" in 출력

    assert 주실행(["help", "표.합계행"]) == 0
    assert "합계" in capsys.readouterr().out


def test_CLI_출력글자표를_UTF8로_맞춘다(monkeypatch):
    """영문 윈도우(cp1252) 콘솔에서 한글을 찍다 죽지 않아야 한다."""
    import io
    import sys

    from hwpkit.cli import _출력글자표맞추기

    바뀐: list[tuple] = []

    class 가짜흐름(io.StringIO):
        def reconfigure(self, **인자):
            바뀐.append(인자)

    monkeypatch.setattr(sys, "stdout", 가짜흐름())
    monkeypatch.setattr(sys, "stderr", 가짜흐름())
    _출력글자표맞추기()
    assert 바뀐 == [
        {"encoding": "utf-8", "errors": "replace"},
        {"encoding": "utf-8", "errors": "replace"},
    ]
