"""연결 상태 시험 — 한/글에 붙었지만 **명령을 받지 못하는** 상황을 다룬다.

실제로 이런 신고가 있었다.

    [오류] AttributeError: 'NoneType' object has no attribute 'Run'

한/글 시작 화면만 떠 있어 편집할 문서가 하나도 없으면 `HAction` 이 None 으로 온다.
그 상태로 `HAction.Run(...)` 을 부르면 위와 같은 영문 오류만 화면에 떠서, 사용자는
무엇을 해야 하는지 알 수 없다. 이 파일은 세 가지를 지킨다.

1. 문서가 없으면 **빈 문서를 만들어** 스스로 풀고 넘어간다.
2. 그래도 안 되면 **한국말 안내가 붙은 오류**로 바꾼다(영문 AttributeError 금지).
3. 진단 보고서가 이 상태를 짚어 준다.
"""

from __future__ import annotations

import pytest

from fake_hwp import 가짜한글, 문서만들기
from hwpkit.core import connection
from hwpkit.core.errors import 연결오류, 오류풀이


# --------------------------------------------------------------- 상태 판단
def test_문서가_없으면_명령을_받지_못한다():
    한글 = 가짜한글(문서수=0)
    assert 한글.HAction is None  # 실제 한/글이 이렇게 준다
    이유 = connection.받을수있나(한글)
    assert "HAction" in 이유


def test_문서가_있으면_받을수있다():
    assert connection.받을수있나(가짜한글()) == ""


def test_연결객체가_없으면_이유를_말한다():
    assert connection.받을수있나(None)


# ------------------------------------------------------------- 스스로 풀기
def test_빈문서보장이_문서를_만들고_통로를_연다():
    한글 = 가짜한글(문서수=0)
    assert connection.빈문서보장(한글) is True
    assert 한글.XHwpDocuments.Count == 1
    assert 한글.XHwpDocuments.탭으로 == 0  # Add(isTab) 인수를 채워 부른다
    assert connection.받을수있나(한글) == ""


def test_문서가_이미_있으면_만들지_않는다():
    한글 = 가짜한글()
    assert connection.빈문서보장(한글) is False
    assert 한글.XHwpDocuments.Count == 1


def test_준비기다리기가_빈문서로_풀어_준다():
    한글 = 가짜한글(문서수=0)
    assert connection.준비기다리기(한글, 대기=0) == ""


def test_준비기다리기는_못_풀면_이유를_돌려준다():
    class 껍데기:
        """붙기는 하지만 아무것도 주지 않는 객체."""

        HAction = None
        HParameterSet = None
        XHwpDocuments = None

    이유 = connection.준비기다리기(껍데기(), 대기=0)
    assert "HAction" in 이유


# ----------------------------------------------------------- 오류 갈아입히기
def test_통로가_없으면_안내오류가_난다():
    """AttributeError 가 아니라 무엇을 할지 알려 주는 오류여야 한다."""
    문서객체, 한글 = 문서만들기()
    한글.HAction = None  # 도중에 문서를 다 닫은 상태
    with pytest.raises(연결오류) as 담김:
        문서객체.실행("BreakPara")
    assert "새 문서" in 담김.value.도움말


def test_세트파라미터도_안내오류가_난다():
    문서객체, 한글 = 문서만들기()
    한글.HParameterSet = None
    with pytest.raises(연결오류):
        with 문서객체.세트파라미터("TableCreate", "HTableCreation"):
            pass


def test_액션을_만들지_못하면_안내오류가_난다():
    문서객체, 한글 = 문서만들기()
    한글.CreateAction = lambda _이름: None
    with pytest.raises(연결오류):
        with 문서객체.파라미터("InsertText"):
            pass


def test_안내오류는_영문_속내용을_보여주지_않는다():
    문서객체, 한글 = 문서만들기()
    한글.HAction = None
    try:
        문서객체.실행("BreakPara")
    except 연결오류 as 오류:
        말 = 오류풀이(오류)
    assert 말.startswith("[안내]")
    assert "NoneType" not in 말
    assert "한/글" in 말


def test_준비도움말은_해볼_것을_알려_준다():
    도움말 = connection.준비도움말("HAction 을 받지 못했습니다.")
    for 낱말 in ("새 문서", "권한", "연결 진단"):
        assert 낱말 in 도움말
