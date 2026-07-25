"""빌드 관련 파일 점검.

윈도우 실행 파일은 이 저장소를 만든 환경(리눅스)에서 만들 수 없다. 그래서 빌드에
쓰이는 파일들이 **문법·구조상 올바른지, 서로 어긋나지 않는지** 를 여기서 검사한다.
윈도우에서 빌드하다 오타 때문에 실패하는 일을 막기 위한 안전장치다.
"""

from __future__ import annotations

import ast
import struct
from pathlib import Path

뿌리 = Path(__file__).resolve().parent.parent


def _읽기(이름: str) -> str:
    """문서·spec 은 UTF-8, 배치 파일은 CP949 로 읽는다."""
    if 이름.endswith(".bat"):
        return (뿌리 / 이름).read_bytes().decode("cp949")
    return (뿌리 / 이름).read_text(encoding="utf-8")


# ------------------------------------------------------------ version_info.txt
def _버전정보나무() -> ast.Call:
    나무 = ast.parse(_읽기("version_info.txt"), mode="eval")
    assert isinstance(나무.body, ast.Call)
    return 나무.body


def test_버전정보_문법과_최상위이름():
    부름 = _버전정보나무()
    assert 부름.func.id == "VSVersionInfo"
    이름들 = {키워드.arg for 키워드 in 부름.keywords}
    assert {"ffi", "kids"} <= 이름들


def _문자항목() -> dict[str, str]:
    부름 = _버전정보나무()
    표: dict[str, str] = {}
    for 노드 in ast.walk(부름):
        if isinstance(노드, ast.Call) and getattr(노드.func, "id", "") == "StringStruct":
            이름, 값 = 노드.args
            표[이름.value] = 값.value
    return 표


def test_버전정보에_필요한항목이_모두있다():
    """이 항목이 비어 있으면 윈도우 속성창이 텅 비고 백신 의심도 커진다."""
    표 = _문자항목()
    필수 = {
        "CompanyName",
        "FileDescription",
        "FileVersion",
        "InternalName",
        "LegalCopyright",
        "OriginalFilename",
        "ProductName",
        "ProductVersion",
    }
    assert 필수 <= set(표)
    assert all(값.strip() for 값 in 표.values())


def test_버전번호_형식이_맞다():
    표 = _문자항목()
    for 이름 in ("FileVersion", "ProductVersion"):
        조각 = 표[이름].split(".")
        assert len(조각) == 4 and all(하나.isdigit() for 하나 in 조각), 이름


def test_실행파일이름이_spec과_같다():
    """version_info 의 OriginalFilename 과 spec 의 name 이 어긋나면 안 된다."""
    이름 = _문자항목()["OriginalFilename"]
    assert 이름.endswith(".exe")
    spec이름 = _spec값("이름")
    assert 이름 == f"{spec이름}.exe"


def test_언어코드와_번역항목이_짝이맞다():
    """StringTable 의 041204B0 과 Translation 의 (0x0412, 1200) 이 같아야 한다."""
    원문 = _읽기("version_info.txt")
    assert '"041204B0"' in 원문
    assert "[0x0412, 1200]" in 원문


# ---------------------------------------------------------------- hwpkit.spec
def _spec값(변수이름: str) -> str:
    나무 = ast.parse(_읽기("hwpkit.spec"))
    for 노드 in 나무.body:
        if isinstance(노드, ast.Assign):
            for 대상 in 노드.targets:
                if getattr(대상, "id", "") == 변수이름 and isinstance(노드.value, ast.Constant):
                    return 노드.value.value
    raise AssertionError(f"spec 에서 {변수이름} 을 찾지 못했습니다")


def test_spec_문법():
    ast.parse(_읽기("hwpkit.spec"))


def test_spec에_보안경고_줄이는_설정이_들어있다():
    원문 = _읽기("hwpkit.spec")
    assert "upx=False" in 원문, "UPX 압축은 백신 오탐의 가장 큰 원인이다"
    assert "uac_admin=False" in 원문, "관리자 권한을 요구하면 실행 때마다 권한 창이 뜬다"
    assert 'icon="assets/hwpkit.ico"' in 원문
    assert 'version="version_info.txt"' in 원문
    assert "console=False" in 원문


def test_spec이_가리키는_파일들이_실제로_있다():
    원문 = _읽기("hwpkit.spec")
    for 이름 in ("run.py", "assets/hwpkit.ico", "version_info.txt", "hwpkit/presets"):
        assert 이름 in 원문
        assert (뿌리 / 이름).exists(), f"spec 이 없는 파일을 가리킵니다: {이름}"


def test_spec_숨은가져오기에_COM모듈이_있다():
    원문 = _읽기("hwpkit.spec")
    for 이름 in ("win32com.client", "pythoncom", "pywintypes", "tkinter"):
        assert f'"{이름}"' in 원문


# ---------------------------------------------------------------- 아이콘 파일
def test_아이콘_형식과_크기():
    자료 = (뿌리 / "assets/hwpkit.ico").read_bytes()
    예약, 종류, 개수 = struct.unpack("<HHH", 자료[:6])
    assert (예약, 종류) == (0, 1), "ICO 머리표가 아닙니다"
    assert 개수 >= 4, "여러 크기를 담아야 작업표시줄·바탕화면에서 또렷하다"

    크기들 = set()
    for 번호 in range(개수):
        시작 = 6 + 16 * 번호
        너비, 높이, _색, _예약, _면, _비트, 길이, 위치 = struct.unpack(
            "<BBBBHHII", 자료[시작 : 시작 + 16]
        )
        크기들.add(너비 or 256)
        assert 위치 + 길이 <= len(자료), "그림 위치가 파일 밖을 가리킵니다"
        assert 자료[위치 : 위치 + 8] == b"\x89PNG\r\n\x1a\n"
    assert {16, 32, 48, 256} <= 크기들


# ------------------------------------------------------------- 빌드 스크립트
def test_빌드스크립트_존재와_내용():
    본문 = _읽기("build_win.bat")
    assert "pyinstaller" in 본문
    assert "hwpkit.spec" in 본문
    assert "pytest" in 본문, "빌드 전에 시험을 돌려야 한다"


def test_서명스크립트_핵심옵션():
    본문 = _읽기("sign_win.bat")
    # SHA256 서명 + 시간 도장(RFC3161) 이 없으면 서명해도 경고가 남는다.
    assert "/fd" in 본문 and "sha256" in 본문.lower()
    assert "/tr" in 본문 and "/td" in 본문
    assert "verify" in 본문


def test_배치파일은_CP949_CRLF다():
    """UTF-8 로 저장하면 한국어 윈도우 cmd 에서 한글이 깨지고 조건문이 어긋난다."""
    for 이름 in ("build_win.bat", "sign_win.bat"):
        자료 = (뿌리 / 이름).read_bytes()
        자료.decode("cp949")  # 못 읽으면 예외
        assert b"\r\n" in 자료, f"{이름} 은 CRLF 줄바꿈이어야 합니다"
        try:
            자료.decode("utf-8")
        except UnicodeDecodeError:
            pass  # 한글이 CP949 로 들어 있다는 뜻 — 정상
        else:
            raise AssertionError(f"{이름} 이 UTF-8 로 저장돼 있습니다")


def test_배치파일_식별자는_ASCII다():
    """변수 이름·라벨에 한글을 쓰면 일부 윈도우 환경에서 배치가 오작동한다."""
    import re

    for 이름 in ("build_win.bat", "sign_win.bat"):
        본문 = _읽기(이름)
        for 줄 in 본문.splitlines():
            벗김 = 줄.strip()
            if 벗김.startswith("set ") and "=" in 벗김:
                변수 = 벗김[4:].split("=", 1)[0].strip().strip('"')
                assert 변수.isascii(), f"{이름}: 변수 이름에 한글 — {변수}"
            if 벗김.startswith(":") or 벗김.startswith("goto "):
                라벨 = re.sub(r"^(goto\s+:?|:)", "", 벗김)
                assert 라벨.isascii(), f"{이름}: 라벨에 한글 — {라벨}"


def test_배포안내_문서가_있다():
    본문 = _읽기("배포안내.md")
    for 낱말 in ("SmartScreen", "코드 서명", "Unblock-File", "HWPKIT_ONEDIR", "signtool"):
        assert 낱말 in 본문, f"배포안내에 '{낱말}' 설명이 빠졌습니다"
