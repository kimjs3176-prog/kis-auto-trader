"""한/글 COM 연결 관리.

원본 `한컴열기` 를 다음과 같이 보강했다.

1. 실행 중인 한/글에 먼저 붙고(ROT 조회), 없을 때만 새로 띄운다. (원본과 동일)
2. **늦은 바인딩(late binding)** 으로 연결한다.
   원본은 `gencache.EnsureDispatch` 를 썼는데, 이 방식은 win32com 이 만든 래퍼
   모듈을 `site-packages/win32com/gen_py` 에 **써야** 한다. 실행 파일(exe)로 묶으면
   그 경로가 읽기 전용 임시 폴더라 실패한다. 원본 exe 는 PyInstaller 가 넣어 주던
   `pyi_rth_win32comgenpy` 런타임 훅 덕분에 넘어갔지만, 요즘 PyInstaller 에는 그
   훅이 없다. `Dispatch` 는 코드 생성이 필요 없어 exe·소스 양쪽에서 똑같이 된다.
3. **스레드마다 COM 을 초기화**하고 연결 객체도 스레드별로 보관한다.
   화면(UI)은 기능을 작업 스레드에서 실행하므로, 이 처리가 없으면
   "CoInitialize has not been called" 오류가 난다.
4. 보안 모듈을 등록해 파일 접근 확인 창을 없앤다.
5. 실패하면 **무엇이 왜 실패했는지** 실제 COM 오류와 함께 알려준다.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import threading
from typing import Any

from .errors import 연결오류, 환경오류

__all__ = ["한글연결", "사용가능", "진단"]

로그 = logging.getLogger(__name__)

#: 한/글 자동화 ProgID (버전에 따라 뒤에 .1 이 붙은 것만 등록된 경우가 있다)
프로그램ID들 = ("HWPFrame.HwpObject", "HWPFrame.HwpObject.1")
_ROT접두어 = "!HwpObject"
#: 보안 모듈(파일 접근 확인 창 억제)에 쓰는 등록 이름
_보안모듈 = ("FilePathCheckDLL", "FilePathCheckerModule")

#: COM 은 스레드마다 초기화해야 하고, 연결 객체도 스레드별로 두는 편이 안전하다.
_지역 = threading.local()


def 사용가능() -> tuple[bool, str]:
    """지금 환경에서 한/글 자동화를 쓸 수 있는지 확인한다."""
    if sys.platform != "win32":
        return False, "한/글 자동화는 윈도우에서만 됩니다. (현재: %s)" % sys.platform
    if importlib.util.find_spec("win32com.client") is None:
        return False, "pywin32 가 없습니다. `pip install pywin32` 후 다시 실행하세요."
    return True, ""


def _COM준비() -> None:
    """이 스레드에서 COM 을 쓸 수 있게 한다. (한 번만 초기화)"""
    if getattr(_지역, "COM초기화", False):
        return
    import pythoncom

    try:
        pythoncom.CoInitialize()
    except Exception as 오류:  # noqa: BLE001 - 이미 다른 모드로 초기화된 스레드
        로그.debug("CoInitialize 건너뜀: %s", 오류)
    _지역.COM초기화 = True


class 한글연결:
    """한/글 COM 객체를 감싼 연결 객체.

    `연결.한글` 로 원본 COM 객체를 그대로 쓸 수 있으므로, 이 프로그램이 감싸지 않은
    기능도 필요하면 바로 호출할 수 있다.
    """

    def __init__(self, 보이기: bool = True, 보안모듈등록: bool = True) -> None:
        self._보이기 = 보이기
        self._보안모듈등록 = 보안모듈등록
        self.새로띄움 = False
        self.마지막오류: str = ""

    # ------------------------------------------------------------------ 연결
    @property
    def 한글(self) -> Any:
        """살아 있는 COM 객체. 필요하면 그 자리에서 연결한다."""
        객체 = getattr(_지역, "한글", None)
        if 객체 is None or not self._살아있나(객체):
            객체 = self.연결()
        return 객체

    @staticmethod
    def _살아있나(객체: Any) -> bool:
        try:
            _ = 객체.Version  # 죽은 COM 객체면 예외
            return True
        except Exception:  # noqa: BLE001 - COM 은 별별 예외를 낸다
            return False

    def 연결(self) -> Any:
        """한/글에 연결한다. 실행 중이면 붙고, 없으면 새로 띄운다."""
        가능, 이유 = 사용가능()
        if not 가능:
            raise 환경오류("한/글에 연결할 수 없습니다.", 이유)

        _COM준비()

        객체 = self._실행중찾기()
        if 객체 is not None:
            self.새로띄움 = False
            로그.info("실행 중인 한/글에 연결했습니다.")
        else:
            객체 = self._새로만들기()
            self.새로띄움 = True
            로그.info("한/글을 새로 실행했습니다.")

        _지역.한글 = 객체
        if self._보안모듈등록:
            self.보안모듈등록()
        if self._보이기:
            self.보이기()
        return 객체

    def _새로만들기(self) -> Any:
        """ProgID 로 한/글을 띄운다. 실패 이유를 모아 안내에 담는다."""
        from win32com.client import Dispatch

        실패: list[str] = []
        for 이름 in 프로그램ID들:
            try:
                return Dispatch(이름)
            except Exception as 오류:  # noqa: BLE001
                실패.append(f"{이름}: {오류}")

        self.마지막오류 = " / ".join(실패)
        raise 연결오류(
            "한/글을 실행할 수 없습니다.",
            "확인해 주세요.\n"
            "  · 한/글을 관리자 권한으로 실행했다면, 이 프로그램도 관리자 권한으로 실행하세요.\n"
            "    (권한이 다르면 실행 중인 한/글에 붙지 못합니다)\n"
            "  · 한/글이 아닌 한워드·다른 제품만 설치된 경우 연결할 수 없습니다.\n"
            "  · 한컴오피스 설치 관리자에서 '복구'를 한 번 실행해 자동화 등록을 되살려 보세요.\n"
            "  · '도구 → 한/글 연결 진단' 을 실행하면 더 자세한 원인을 볼 수 있습니다.\n"
            f"\n실제 오류\n  {self.마지막오류}",
        )

    def _실행중찾기(self) -> Any | None:
        """실행 중인 한/글 인스턴스를 ROT(Running Object Table)에서 찾는다."""
        try:
            import pythoncom
            from win32com.client import Dispatch

            바인딩 = pythoncom.CreateBindCtx(0)
            표 = pythoncom.GetRunningObjectTable()
            for 이름객체 in 표.EnumRunning():
                표시이름 = 이름객체.GetDisplayName(바인딩, 이름객체)
                if not 표시이름.startswith(_ROT접두어):
                    continue
                객체 = 표.GetObject(이름객체)
                return Dispatch(객체.QueryInterface(pythoncom.IID_IDispatch))
        except Exception as 오류:  # noqa: BLE001
            로그.debug("실행 중인 한/글 조회 실패: %s", 오류)
            self.마지막오류 = f"ROT 조회: {오류}"
        return None

    # -------------------------------------------------------------- 부가 설정
    def 보안모듈등록(self) -> bool:
        """파일 접근 확인 창을 없애는 보안 모듈을 등록한다.

        등록 모듈이 없어도 동작 자체는 되므로, 실패하면 경고만 남긴다.
        """
        try:
            getattr(_지역, "한글").RegisterModule(*_보안모듈)
            return True
        except Exception as 오류:  # noqa: BLE001
            로그.warning(
                "보안 모듈 등록에 실패했습니다(%s). 파일 접근 확인 창이 뜰 수 있습니다.",
                오류,
            )
            return False

    def 보이기(self, 켜기: bool = True) -> None:
        """한/글 창을 화면에 보이거나 숨긴다. (일괄처리 때는 숨기면 훨씬 빠르다)"""
        try:
            getattr(_지역, "한글").XHwpWindows.Item(0).Visible = bool(켜기)
        except Exception as 오류:  # noqa: BLE001
            로그.debug("창 표시 설정 실패: %s", 오류)

    @property
    def 버전(self) -> str:
        try:
            return str(self.한글.Version)
        except Exception:  # noqa: BLE001 # pragma: no cover
            return "알 수 없음"

    # ------------------------------------------------------------------ 정리
    def 닫기(self, 문서저장: bool = False) -> None:
        """연결을 놓는다. 이 프로그램이 띄운 한/글이면 종료까지 한다."""
        객체 = getattr(_지역, "한글", None)
        if 객체 is None:
            return
        try:
            if self.새로띄움:
                객체.Clear(1 if 문서저장 else 3)  # 3 = 저장하지 않고 버림
                객체.Quit()
        except Exception as 오류:  # noqa: BLE001
            로그.debug("한/글 종료 실패: %s", 오류)
        finally:
            _지역.한글 = None

    def __enter__(self) -> "한글연결":
        self.연결()
        return self

    def __exit__(self, *_예외) -> None:
        self.닫기()

    @staticmethod
    def genpy정리() -> int:
        """win32com 캐시(gen_py)를 지운다.

        이 프로그램은 늦은 바인딩을 쓰므로 캐시가 없어도 되지만, 예전에 만들어진
        캐시가 남아 오류를 내는 경우가 있어 지우는 수단을 남겨 둔다.
        """
        import shutil
        import tempfile

        지운수 = 0
        후보 = [os.path.join(tempfile.gettempdir(), "gen_py")]
        try:
            import win32com

            후보.append(os.path.join(os.path.dirname(win32com.__file__), "gen_py"))
        except ImportError:
            pass
        for 경로 in 후보:
            if os.path.isdir(경로):
                shutil.rmtree(경로, ignore_errors=True)
                지운수 += 1
        return 지운수


# ===================================================================== 진단
def 진단() -> str:
    """연결이 안 될 때 원인을 찾기 위한 점검 보고서를 만든다.

    화면·명령줄에서 '한/글 연결 진단' 으로 부른다. 원격에서 원인을 알아내기 어려운
    COM 문제(자동화 등록 누락, 권한 불일치, 다른 제품 설치)를 사용자가 직접 확인해
    알려줄 수 있게 하는 것이 목적이다.
    """
    import struct

    줄들: list[str] = ["[실행 환경]"]
    줄들.append(f"  운영체제: {sys.platform}")
    줄들.append(f"  비트: {struct.calcsize('P') * 8}비트")
    줄들.append(f"  파이썬: {sys.version.split()[0]}")
    묶음 = getattr(sys, "frozen", False)
    줄들.append(f"  실행 형태: {'실행 파일(exe)' if 묶음 else '소스'}")
    줄들.append(f"  실행 경로: {sys.executable}")

    가능, 이유 = 사용가능()
    if not 가능:
        줄들.append("")
        줄들.append(f"[중단] {이유}")
        return "\n".join(줄들)

    줄들.append("")
    줄들.append("[자동화 등록(레지스트리)]")
    줄들 += _레지스트리점검()

    줄들.append("")
    줄들.append("[실행 중인 한/글(ROT)]")
    줄들 += _ROT점검()

    줄들.append("")
    줄들.append("[연결 시도]")
    줄들 += _연결시도점검()
    return "\n".join(줄들)


def _레지스트리점검() -> list[str]:
    try:
        import winreg
    except ImportError:  # pragma: no cover - 윈도우 아님
        return ["  확인할 수 없습니다(윈도우 아님)."]

    결과: list[str] = []
    for 이름 in 프로그램ID들:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{이름}\CLSID") as 키:
                clsid = winreg.QueryValueEx(키, "")[0]
            결과.append(f"  ○ {이름} → {clsid}")
            결과.append(f"     {_서버경로(clsid)}")
        except OSError as 오류:
            결과.append(f"  × {이름} 등록 없음 ({오류.strerror})")
    if all(줄.startswith("  ×") for 줄 in 결과):
        결과.append("  → 한컴오피스 설치 관리자에서 '복구' 를 실행해 보세요.")
    return 결과


def _서버경로(clsid: str) -> str:
    import winreg

    for 갈래 in ("LocalServer32", "InprocServer32"):
        try:
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\{갈래}"
            ) as 키:
                return f"{갈래}: {winreg.QueryValueEx(키, '')[0]}"
        except OSError:
            continue
    return "실행 파일 경로를 찾지 못했습니다."


def _ROT점검() -> list[str]:
    try:
        import pythoncom

        _COM준비()
        바인딩 = pythoncom.CreateBindCtx(0)
        표 = pythoncom.GetRunningObjectTable()
        이름들 = []
        for 이름객체 in 표.EnumRunning():
            표시 = 이름객체.GetDisplayName(바인딩, 이름객체)
            if 표시.startswith(_ROT접두어):
                이름들.append(표시)
        if not 이름들:
            return [
                "  실행 중인 한/글을 찾지 못했습니다.",
                "  → 한/글이 켜져 있는데도 이렇게 나오면 권한이 다른 경우입니다.",
                "     (한쪽만 관리자 권한으로 실행된 상태)",
            ]
        return [f"  ○ {len(이름들)}개 찾음"] + [f"     {이름}" for 이름 in 이름들[:5]]
    except Exception as 오류:  # noqa: BLE001
        return [f"  × 조회 실패: {오류}"]


def _연결시도점검() -> list[str]:
    from win32com.client import Dispatch

    _COM준비()
    결과: list[str] = []
    붙은객체 = None

    연결 = 한글연결(보이기=False, 보안모듈등록=False)
    실행중 = 연결._실행중찾기()
    if 실행중 is not None:
        결과.append("  ○ 실행 중인 한/글에 붙었습니다.")
        붙은객체 = 실행중
    else:
        결과.append("  - 실행 중인 한/글에는 붙지 못했습니다(새로 띄우기를 시도).")
        for 이름 in 프로그램ID들:
            try:
                붙은객체 = Dispatch(이름)
                결과.append(f"  ○ {이름} 으로 새로 띄웠습니다.")
                break
            except Exception as 오류:  # noqa: BLE001
                결과.append(f"  × {이름} 실패: {오류}")

    if 붙은객체 is None:
        결과.append("  → 연결하지 못했습니다. 위 오류 내용을 그대로 알려 주세요.")
        return 결과

    _지역.한글 = 붙은객체
    try:
        결과.append(f"  한/글 버전: {붙은객체.Version}")
    except Exception as 오류:  # noqa: BLE001
        결과.append(f"  버전 조회 실패: {오류}")
    결과.append(
        "  보안 모듈 등록: "
        + ("성공" if 연결.보안모듈등록() else "실패(파일 접근 확인 창이 뜰 수 있음)")
    )
    return 결과
