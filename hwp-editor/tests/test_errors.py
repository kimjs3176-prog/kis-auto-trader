"""오류 풀이 시험 — COM 오류를 사람 말로 바꾸는 부분.

한/글이 돌려주는 오류는 `(-2147352562, '매개 변수의 개수가 잘못되었습니다.',
None, None)` 처럼 생겨서, 그대로 보여 주면 무엇을 해야 할지 알 수 없다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from hwpkit.core.errors import 상태오류, 오류풀이

뿌리 = Path(__file__).resolve().parent.parent


class com_error(Exception):  # noqa: N801 - pywin32 의 이름을 그대로 흉내 낸다
    """pywin32 의 `pywintypes.com_error` 대역."""


def test_우리가_낸_안내는_그대로_보여_준다():
    말 = 오류풀이(상태오류("표 안에 커서를 두세요.", "표를 먼저 만드세요."))
    assert 말.startswith("[안내]")
    assert "표 안에 커서를 두세요." in 말 and "표를 먼저 만드세요." in 말


def test_인수개수_오류를_풀어_준다():
    오류 = com_error(-2147352562, "매개 변수의 개수가 잘못되었습니다.", None, None)
    말 = 오류풀이(오류)
    assert "인수 개수" in 말
    assert "매개 변수의 개수가 잘못되었습니다." in 말  # 한/글이 한 말도 남긴다
    assert "0x8002000E" in 말


def test_한글을_못_찾은_오류():
    말 = 오류풀이(com_error(-2147221021, "사용할 수 없음", None, None))
    assert "실행 중인 한/글" in 말
    assert "먼저 켜" in 말


def test_권한_오류():
    말 = 오류풀이(com_error(-2147024891, "액세스가 거부되었습니다.", None, None))
    assert "권한" in 말 and "관리자" in 말


def test_모르는_COM오류도_번호를_보여_준다():
    말 = 오류풀이(com_error(-2147467259, "알 수 없는 오류", None, None))
    assert "[오류]" in 말 and "0x80004005" in 말


def test_속에_든_설명이_겹치면_한_번만():
    오류 = com_error(-2147352567, "같은 말", ("같은 말", "한글", None, 0, None), None)
    말 = 오류풀이(오류)
    assert 말.count("같은 말") == 1


def test_COM이_아닌_예외는_종류와_함께():
    말 = 오류풀이(ValueError("숫자가 아닙니다"))
    assert 말 == "[오류] ValueError: 숫자가 아닙니다"


# --------------------------------------------------------- 늦은 바인딩 안전장치
#: 한/글 API 이름 → 반드시 넘겨야 하는 인수 개수.
#: 늦은 바인딩(`Dispatch`)에서는 생략 가능 인수를 파이썬이 채워 주지 않아,
#: 하나라도 빠뜨리면 "매개 변수의 개수가 잘못되었습니다"(0x8002000E) 가 난다.
인수개수 = {
    "MovePos": 3,  # moveID, Para, pos
    "InitScan": 6,  # option, Range, spara, spos, epara, epos
    "InsertPicture": 8,  # Path, Embedded, sizeoption, reverse, watermark, effect, w, h
    "GetTextFile": 2,  # Format, option
    "GetFieldList": 2,  # Number, Option
    "SaveAs": 3,  # Path, Format, arg
    "Open": 3,  # Path, Format, arg
    "Add": 1,  # XHwpDocuments.Add(isTab)
}


def test_한글API를_인수를_다_채워_부른다():
    """`한글.MovePos(코드)` 처럼 뒤쪽 인수를 빠뜨린 곳이 없는지 본다."""
    부족한것: list[str] = []
    for 파일 in sorted((뿌리 / "hwpkit").rglob("*.py")):
        나무 = ast.parse(파일.read_text(encoding="utf-8"))
        for 마디 in ast.walk(나무):
            if not isinstance(마디, ast.Call) or not isinstance(마디.func, ast.Attribute):
                continue
            이름 = 마디.func.attr
            바람 = 인수개수.get(이름)
            if 바람 is None:
                continue
            # `한글.MovePos(...)` 처럼 한/글 객체에 대고 부르는 것만 본다.
            받는쪽 = ast.unparse(마디.func.value)
            if "한글" not in 받는쪽:
                continue
            if len(마디.args) != 바람:
                부족한것.append(
                    f"{파일.name}:{마디.lineno} {이름} 인수 {len(마디.args)}개"
                    f" (한/글은 {바람}개를 받습니다)"
                )
    assert not 부족한것, "\n".join(부족한것)


def test_대역도_인수를_그대로_받는다():
    """시험용 가짜 한/글이 느슨하면 위 실수가 윈도우에 가서야 드러난다."""
    본문 = (뿌리 / "tests" / "fake_hwp.py").read_text(encoding="utf-8")
    나무 = ast.parse(본문)
    정의 = {
        마디.name: 마디
        for 마디 in ast.walk(나무)
        if isinstance(마디, ast.FunctionDef)
    }
    for 이름, 바람 in 인수개수.items():
        마디 = 정의.get(이름)
        if 마디 is None:
            continue
        받는수 = len(마디.args.args) - 1  # self 는 뺀다
        assert 받는수 == 바람, f"대역 {이름} 이 {받는수}개만 받습니다 (한/글은 {바람}개)"
        assert not 마디.args.vararg, f"대역 {이름} 이 *인자 로 뭉뚱그려 받습니다"
        assert not 마디.args.defaults, f"대역 {이름} 에 기본값이 있어 빠뜨려도 통과합니다"


def test_화면과_CLI는_오류풀이를_쓴다():
    """오류가 원문 그대로 나오지 않도록."""
    for 상대 in ("hwpkit/ui/app.py", "hwpkit/cli.py"):
        본문 = (뿌리 / 상대).read_text(encoding="utf-8")
        assert re.search(r"오류풀이\(", 본문), f"{상대} 가 오류풀이를 쓰지 않습니다"
