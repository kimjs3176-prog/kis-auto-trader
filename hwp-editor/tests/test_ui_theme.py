"""배색 시험 — 토스풍 색이 규칙대로 잡혀 있는지.

색은 눈으로 봐야 아는 것이지만, 적어도 (1) 색 코드가 성한 값인지, (2) 색 섞기가
맞게 되는지, (3) 글자와 바탕이 너무 비슷해 안 보이지는 않는지는 기계가 볼 수 있다.
"""

from __future__ import annotations

from hwpkit.ui import theme

색이름들 = (
    "바탕",
    "카드",
    "카드가리킴",
    "테두리",
    "파랑",
    "파랑진하게",
    "파랑옅게",
    "진한글",
    "보통글",
    "흐린글",
)


def _밝기(색값: str) -> float:
    """사람 눈이 느끼는 밝기(0~1). 대비를 어림잡는 데 쓴다."""
    빨강, 초록, 파랑 = (int(색값[자리 : 자리 + 2], 16) / 255 for 자리 in (1, 3, 5))
    return 0.2126 * 빨강 + 0.7152 * 초록 + 0.0722 * 파랑


def test_모든_색이_여섯자리_코드다():
    for 이름 in 색이름들:
        색값 = getattr(theme, 이름)
        assert 색값.startswith("#") and len(색값) == 7, (이름, 색값)
        int(색값[1:], 16)  # 열여섯 진법으로 읽히지 않으면 여기서 터진다


def test_글자와_바탕은_충분히_다르다():
    """카드 위 글자가 묻히지 않을 만큼 밝기 차이가 나는지."""
    카드밝기 = _밝기(theme.카드)
    assert 카드밝기 - _밝기(theme.진한글) > 0.7
    assert 카드밝기 - _밝기(theme.보통글) > 0.5
    assert 카드밝기 - _밝기(theme.흐린글) > 0.3


def test_바탕보다_카드가_밝다():
    """옅은 회색 바탕에 흰 카드를 얹는 것이 이 배색의 뼈대다."""
    assert _밝기(theme.카드) > _밝기(theme.바탕)


def test_누른_파랑이_더_진하다():
    assert _밝기(theme.파랑진하게) < _밝기(theme.파랑)
    assert _밝기(theme.파랑옅게) > _밝기(theme.파랑)


def test_색섞기():
    assert theme.섞기("#000000", "#FFFFFF", 0.0) == "#FFFFFF"
    assert theme.섞기("#000000", "#FFFFFF", 1.0) == "#000000"
    assert theme.섞기("#000000", "#FFFFFF", 0.5) == "#808080"
    # 비율이 벗어나도 가둔다
    assert theme.섞기("#000000", "#FFFFFF", -3) == "#FFFFFF"
    assert theme.섞기("#000000", "#FFFFFF", 9) == "#000000"


def test_섞기는_이상한_색을_거절한다():
    try:
        theme.섞기("파랑", "#FFFFFF", 0.5)
    except ValueError:
        return
    raise AssertionError("색 코드가 아닌 값을 받아들였습니다.")


def test_배지색은_강조색을_옅게_푼_색():
    강조 = theme.파랑
    배지 = theme.배지색(강조)
    assert _밝기(배지) > _밝기(강조)  # 훨씬 옅고
    assert _밝기(배지) < _밝기(theme.카드)  # 흰 카드보다는 진하다
