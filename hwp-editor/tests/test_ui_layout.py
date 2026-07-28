"""사이드 패널 배치 계산 시험.

화면(tkinter) 자체는 윈도우에서만 띄울 수 있으므로, 여기서는
    · 가장자리에 붙였을 때 창 자리가 맞는지
    · 폭에 따라 타일 칸 수·분류 칩 줄이 제대로 접히는지
    · 화면 설정(붙인 자리·타일 크기)이 안전하게 오가는지
를 검사한다. 마지막 두 시험은 `app.py` 가 없는 계산 함수를 부르거나 문법이
깨진 채로 올라가지 않게 막는 안전장치다.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from hwpkit import commands
from hwpkit.ui import layout, theme

화면너비, 화면높이 = 1920, 1080


# ------------------------------------------------------------------ 창 자리
def test_왼쪽에_붙이면_화면_왼쪽_끝에_길쭉하게_선다():
    자리 = layout.창자리계산("좌", 화면너비, 화면높이, 두께=380, 여백=48)
    assert (자리.너비, 자리.왼쪽, 자리.위) == (380, 0, 0)
    assert 자리.높이 == 화면높이 - 48
    assert 자리.지오메트리 == f"380x{화면높이 - 48}+0+0"


def test_오른쪽에_붙이면_오른쪽_끝에_딱_맞는다():
    자리 = layout.창자리계산("우", 화면너비, 화면높이, 두께=380, 여백=48)
    assert 자리.왼쪽 + 자리.너비 == 화면너비


def test_붙일_자리는_좌우_둘뿐이다():
    """위·아래로 눕히면 타일이 두 줄밖에 안 들어가 없앴다."""
    assert layout.자리들 == ("좌", "우")
    for 이름 in layout.자리들:
        자리 = layout.창자리계산(이름, 화면너비, 화면높이, 두께=320)
        assert 자리.너비 > 0 and 자리.높이 > 0
        assert 자리.높이 > 자리.너비, "좌·우 패널은 길쭉해야 한다"


def test_모르는_자리는_거절한다():
    for 이름 in ("가운데", "상", "하"):
        try:
            layout.창자리계산(이름, 화면너비, 화면높이, 두께=320)
        except ValueError:
            continue
        raise AssertionError(f"모르는 자리를 받아들였습니다: {이름}")


def test_예전에_상하로_저장해_둔_설정은_오른쪽으로_돌린다(tmp_path: Path):
    """자리를 줄이기 전에 쓰던 설정 파일이 있어도 멀쩡히 켜져야 한다."""
    파일 = tmp_path / "ui.json"
    파일.write_text(
        json.dumps({"자리": "하", "두께": {"하": 300}}, ensure_ascii=False),
        encoding="utf-8",
    )
    읽은것 = layout.설정불러오기(파일)
    assert 읽은것["자리"] == layout.기본설정["자리"]
    assert set(읽은것["두께"]) == set(layout.기본설정["두께"])


def test_두께는_너무_얇거나_두꺼워지지_않는다():
    assert layout.두께다듬기("우", 10, 화면너비, 화면높이) == layout.최소두께
    assert layout.두께다듬기("우", 5000, 화면너비, 화면높이) <= int(화면너비 * layout.최대두께비)
    assert layout.두께다듬기("좌", 5000, 화면너비, 화면높이) <= int(화면너비 * layout.최대두께비)
    assert layout.두께다듬기("우", "엉터리", 화면너비, 화면높이) == layout.최소두께


def test_작은_화면에서도_최소_두께는_지킨다():
    두께 = layout.두께다듬기("우", 400, 300, 200)
    assert 두께 == layout.최소두께


# ------------------------------------------------------------------ 격자
def test_칸수는_폭에_따라_늘어난다():
    assert layout.칸수(가용너비=100, 타일크기=96, 사이=8) == 1
    assert layout.칸수(가용너비=200, 타일크기=96, 사이=8) == 2
    assert layout.칸수(가용너비=1000, 타일크기=96, 사이=8) == 9


def test_칸수는_아무리_좁아도_한_칸():
    assert layout.칸수(가용너비=10, 타일크기=96) == 1
    assert layout.칸수(가용너비=0, 타일크기=0) == 1


def test_타일이_커지면_칸수는_줄어든다():
    좁게 = layout.칸수(400, 120, 사이=8)
    넓게 = layout.칸수(400, 76, 사이=8)
    assert 좁게 < 넓게


def test_칩은_폭에_맞춰_줄이_접힌다():
    너비들 = [50, 50, 50, 50]
    assert layout.줄나누기(너비들, 가용너비=1000, 사이=4) == [[0, 1, 2, 3]]
    assert layout.줄나누기(너비들, 가용너비=110, 사이=4) == [[0, 1], [2, 3]]


def test_칩_하나가_폭보다_넓어도_한_줄에_남는다():
    assert layout.줄나누기([500], 가용너비=100) == [[0]]


def test_빈_칩목록은_빈_줄():
    assert layout.줄나누기([], 가용너비=300) == []


def test_긴_제목은_타일_크기에_맞춰_잘린다():
    긴제목 = "표 전체를 골라 셀 배경색과 테두리를 한꺼번에 바꾸기"
    작게 = layout.제목자르기(긴제목, 76)
    크게 = layout.제목자르기(긴제목, 120)
    assert 작게.endswith("…") and len(작게) < len(긴제목)
    assert len(작게) < len(크게)
    assert layout.제목자르기("표 만들기", 96) == "표 만들기"


def test_괄호로_덧붙인_설명은_통째로_덜어낸다():
    assert layout.제목자르기("블록 값 변환(콤마·금액·날짜·나이)", 96) == "블록 값 변환"
    assert layout.제목자르기("단위 환산(원↔천원↔백만원)", 96) == "단위 환산"
    # 괄호 앞도 여전히 길면 그냥 말줄임표로 자른다.
    잘린것 = layout.제목자르기("아주아주 길고 긴 기능 이름입니다(덧붙임)", 96)
    assert 잘린것.endswith("…")


def test_타일_제목은_두_줄_안에_들어간다():
    """한 줄 일곱 자 기준 — 세 줄이 되면 '선택 필요' 딱지를 가린다."""
    한줄 = 7
    for 크기 in layout.타일크기들:
        칸당 = max(3, int(한줄 * 크기 / 96))
        for 하나 in commands.전체명령():
            줄인것 = layout.제목자르기(하나.제목, 크기)
            assert len(줄인것) <= 칸당 * 2 + 1, (하나.제목, 크기, 줄인것)


def test_모든_분류에_글머리와_색이_있다():
    본색 = set()
    for 이름 in commands.분류순서:
        글머리, 색값 = theme.분류모습(이름)
        assert 글머리 and 색값.startswith("#") and len(색값) == 7
        본색.add(색값)
    assert len(본색) == len(commands.분류순서), "분류끼리 색이 겹칩니다."
    assert theme.분류모습("없는분류")[0] == "■"


def test_타일크기는_돌아가며_바뀐다():
    크기 = layout.타일크기들[0]
    본것 = []
    for _번 in range(len(layout.타일크기들)):
        본것.append(크기)
        크기 = layout.다음타일크기(크기)
    assert 본것 == list(layout.타일크기들)
    assert 크기 == layout.타일크기들[0]  # 한 바퀴 돌아 처음으로
    assert layout.다음타일크기(999) == layout.타일크기들[0]


def test_타일은_분류_차례로_늘어놓는다():
    늘어놓음 = layout.정렬순서(commands.전체명령(), commands.분류순서)
    차례 = [commands.분류순서.index(하나.분류) for 하나 in 늘어놓음]
    assert 차례 == sorted(차례)
    assert len(늘어놓음) == len(commands.전체명령())


# ------------------------------------------------------------------ 실행판 입력칸
def test_입력이_하나면_입력칸은_최소만_쓴다():
    """입력 하나짜리 기능이 대부분이다. 결과칸이 눌리면 안 된다."""
    assert layout.입력칸높이(40, 800) == layout.입력칸최소


def test_입력이_많으면_입력칸을_늘린다():
    """'문서 서식 한 번에 정리' 는 입력이 여섯 개라 최소 높이로는 두 줄만 보인다."""
    assert layout.입력칸높이(300, 800) == 300


def test_입력칸이_결과칸_몫을_다_먹지_않는다():
    높이 = layout.입력칸높이(5000, 800)
    assert 높이 == int(800 * layout.입력칸최대비)
    assert 800 - 높이 >= 300, "결과칸에 남는 자리가 너무 적습니다"


def test_창_높이를_모를_때도_최소는_준다():
    assert layout.입력칸높이(0, 0) == layout.입력칸최소


# ------------------------------------------------------- 아래쪽 세부설정 판
def test_세부판은_필요한_만큼만_쓴다():
    """타일을 눌러도 격자를 치우지 않으므로, 판이 화면을 다 먹으면 안 된다."""
    assert layout.세부판높이(300, 800) == 300


def test_세부판은_아무리_짧아도_최소는_받는다():
    assert layout.세부판높이(50, 800) == layout.세부판최소


def test_세부판은_격자_몫을_남긴다():
    높이 = layout.세부판높이(5000, 800)
    assert 높이 == int(800 * layout.세부판최대비)
    assert 800 - 높이 >= 200, "격자에 남는 자리가 너무 적습니다"


def test_타일이_적으면_격자는_필요한_만큼만_쓴다():
    """남는 아래 자리가 통째로 세부설정 몫이 되어 가운데가 텅 비지 않는다."""
    assert layout.격자칸높이(240, 800, 400) == 240


def test_타일이_많으면_격자는_남은_자리까지만():
    assert layout.격자칸높이(5000, 800, 400) == 400


def test_세부판이_화면보다_크면_격자는_사라진다():
    assert layout.격자칸높이(300, 300, 400) == 0


def test_창_크기를_모를_때는_요구를_그대로():
    assert layout.격자칸높이(240, 0, 400) == 240
    assert layout.세부판높이(300, 0) == 300


# ------------------------------------------------------------------ 둥근 모서리·딱지·투명도
def test_둥근네모는_모서리마다_점_세_개를_둔다():
    점들 = layout.둥근네모점들(0, 0, 100, 60, 10)
    assert len(점들) == 24  # (x, y) 열두 쌍
    assert 점들[:4] == [10, 0, 90, 0]  # 위쪽 변은 반경만큼 들어가서 시작한다


def test_반경은_네모_절반을_넘지_않는다():
    """작은 타일에 큰 반경을 주면 모양이 뒤집히므로 가둔다."""
    점들 = layout.둥근네모점들(0, 0, 20, 10, 999)
    assert min(점들) >= 0
    assert 점들[0] == 5  # 반경이 높이 절반(5)으로 깎였다


def test_큰_타일은_글자_딱지_작은_타일은_점():
    assert layout.딱지방식(96) == "글자"
    assert layout.딱지방식(120) == "글자"
    assert layout.딱지방식(76) == "점"


def test_투명도는_사십에서_백_사이로_가둔다():
    assert layout.투명도다듬기(100) == 100
    assert layout.투명도다듬기(0) == layout.최소투명도
    assert layout.투명도다듬기(1000) == 100
    assert layout.투명도다듬기("85") == 85
    assert layout.투명도다듬기("72.6") == 73  # 슬라이더는 소수로 온다
    assert layout.투명도다듬기(None) == layout.기본설정["투명도"]


# ------------------------------------------------------------------ 설정 저장
def test_설정을_저장하고_다시_읽는다(tmp_path: Path):
    파일 = tmp_path / "ui.json"
    설정 = {"자리": "좌", "두께": {"좌": 340}, "항상위": True, "타일크기": 120, "투명도": 80}
    assert layout.설정저장(설정, 파일) is True
    읽은것 = layout.설정불러오기(파일)
    assert 읽은것["자리"] == "좌"
    assert 읽은것["두께"]["좌"] == 340
    assert 읽은것["항상위"] is True
    assert 읽은것["타일크기"] == 120
    assert 읽은것["투명도"] == 80


def test_설정_파일이_없으면_기본값(tmp_path: Path):
    읽은것 = layout.설정불러오기(tmp_path / "없는파일.json")
    assert 읽은것["자리"] == layout.기본설정["자리"]
    assert 읽은것["타일크기"] == layout.기본설정["타일크기"]


def test_깨진_설정_파일도_프로그램을_멈추지_않는다(tmp_path: Path):
    파일 = tmp_path / "ui.json"
    파일.write_text("{망가진 json", encoding="utf-8")
    assert layout.설정불러오기(파일)["자리"] == layout.기본설정["자리"]


def test_엉뚱한_값은_걸러낸다(tmp_path: Path):
    파일 = tmp_path / "ui.json"
    파일.write_text(
        json.dumps(
            {"자리": "가운데", "두께": {"우": "많이", "없는자리": 10}, "타일크기": 7, "투명도": "훤함"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    읽은것 = layout.설정불러오기(파일)
    assert 읽은것["자리"] == layout.기본설정["자리"]
    assert 읽은것["두께"]["우"] == layout.기본설정["두께"]["우"]
    assert "없는자리" not in 읽은것["두께"]
    assert 읽은것["타일크기"] == layout.기본설정["타일크기"]
    assert 읽은것["투명도"] == layout.기본설정["투명도"]


def test_저장_폴더가_없으면_만든다(tmp_path: Path):
    파일 = tmp_path / "새폴더" / "ui.json"
    assert layout.설정저장(layout.기본설정, 파일) is True
    assert 파일.exists()


# ------------------------------------------------------------------ app.py 안전장치
def _앱나무() -> ast.Module:
    앱파일 = Path(__file__).resolve().parent.parent / "hwpkit" / "ui" / "app.py"
    return ast.parse(앱파일.read_text(encoding="utf-8"))


def test_화면_코드는_문법이_올바르다():
    """tkinter 가 없는 곳에서도 오타를 잡는다."""
    assert _앱나무() is not None


def _쓰인이름(나무: ast.Module, 묶음이름: str) -> set[str]:
    return {
        마디.attr
        for 마디 in ast.walk(나무)
        if isinstance(마디, ast.Attribute)
        and isinstance(마디.value, ast.Name)
        and 마디.value.id == 묶음이름
    }


def test_화면이_부르는_배치함수는_모두_있다():
    """`layout.없는이름()` 같은 오타를 잡는다."""
    이름들 = _쓰인이름(_앱나무(), "layout")
    assert 이름들, "화면이 배치 계산을 쓰지 않습니다."
    없는것 = sorted(이름 for 이름 in 이름들 if not hasattr(layout, 이름))
    assert not 없는것, f"layout 에 없는 이름을 씁니다: {없는것}"


def test_화면이_쓰는_색_이름은_모두_있다():
    이름들 = _쓰인이름(_앱나무(), "theme")
    assert 이름들, "화면이 배색을 쓰지 않습니다."
    없는것 = sorted(이름 for 이름 in 이름들 if not hasattr(theme, 이름))
    assert not 없는것, f"theme 에 없는 이름을 씁니다: {없는것}"


def test_직접_그린_위젯도_없는_계산을_부르지_않는다():
    위젯파일 = Path(__file__).resolve().parent.parent / "hwpkit" / "ui" / "widgets.py"
    나무 = ast.parse(위젯파일.read_text(encoding="utf-8"))
    for 묶음, 뭉치 in (("layout", layout), ("theme", theme)):
        없는것 = sorted(이름 for 이름 in _쓰인이름(나무, 묶음) if not hasattr(뭉치, 이름))
        assert not 없는것, f"{묶음} 에 없는 이름을 씁니다: {없는것}"
