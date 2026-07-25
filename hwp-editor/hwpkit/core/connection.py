"""한/글 COM 연결 관리.

원본 `한컴열기` 를 다음과 같이 보강했다.

1. 실행 중인 한/글에 먼저 붙고(ROT 조회), 없을 때만 새로 띄운다. (원본과 동일)
2. **보안 모듈을 등록**해 `PutFieldText`/`Open`/`SaveAs` 때마다 뜨는
   "스크립트가 파일에 접근하려 합니다" 팝업을 없앤다. 원본은 이 등록이 없어
   메일머지·일괄처리에서 매번 확인 창이 떴다.
3. 연결이 끊긴 뒤(사용자가 한/글을 닫음) 다시 부르면 자동으로 재연결한다.
4. 윈도우가 아니거나 pywin32 가 없으면 한국말로 원인을 알려준다.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from typing import Any

from .errors import 연결오류, 환경오류

__all__ = ["한글연결", "사용가능"]

로그 = logging.getLogger(__name__)

_프로그램ID = "HWPFrame.HwpObject"
_ROT접두어 = "!HwpObject"
#: 보안 모듈(파일 접근 확인 창 억제)에 쓰는 등록 이름
_보안모듈 = ("FilePathCheckDLL", "FilePathCheckerModule")


def 사용가능() -> tuple[bool, str]:
    """지금 환경에서 한/글 자동화를 쓸 수 있는지 확인한다.

    UI 시작 화면과 CLI 에서 미리 안내하기 위한 함수다.
    """
    if sys.platform != "win32":
        return False, "한/글 자동화는 윈도우에서만 됩니다. (현재: %s)" % sys.platform
    if importlib.util.find_spec("win32com.client") is None:
        return False, "pywin32 가 없습니다. `pip install pywin32` 후 다시 실행하세요."
    return True, ""


class 한글연결:
    """한/글 COM 객체를 감싼 연결 객체.

    `연결.한글` 로 원본 COM 객체를 그대로 쓸 수 있으므로, 이 프로그램이 감싸지 않은
    기능도 필요하면 바로 호출할 수 있다.
    """

    def __init__(self, 보이기: bool = True, 보안모듈등록: bool = True) -> None:
        self._한글: Any | None = None
        self._보이기 = 보이기
        self._보안모듈등록 = 보안모듈등록
        self.새로띄움 = False

    # ------------------------------------------------------------------ 연결
    @property
    def 한글(self) -> Any:
        """살아 있는 COM 객체. 필요하면 그 자리에서 연결한다."""
        if self._한글 is None or not self._살아있나():
            self.연결()
        return self._한글

    def _살아있나(self) -> bool:
        try:
            _ = self._한글.Version  # 죽은 COM 객체면 예외
            return True
        except Exception:  # noqa: BLE001 - COM 은 별별 예외를 낸다
            return False

    def 연결(self) -> Any:
        """한/글에 연결한다. 실행 중이면 붙고, 없으면 새로 띄운다."""
        가능, 이유 = 사용가능()
        if not 가능:
            raise 환경오류("한/글에 연결할 수 없습니다.", 이유)

        from win32com.client import gencache  # 지연 임포트(윈도우 전용)

        기존 = self._실행중찾기()
        if 기존 is not None:
            self._한글 = 기존
            self.새로띄움 = False
            로그.info("실행 중인 한/글에 연결했습니다.")
        else:
            try:
                self._한글 = gencache.EnsureDispatch(_프로그램ID)
            except Exception as 오류:  # noqa: BLE001
                raise 연결오류(
                    "한/글을 실행할 수 없습니다.",
                    "한/글(또는 한컴오피스)이 설치돼 있는지, 32/64비트 파이썬이 "
                    "설치된 한/글과 맞는지 확인하세요.",
                ) from 오류
            self.새로띄움 = True
            로그.info("한/글을 새로 실행했습니다.")

        if self._보안모듈등록:
            self.보안모듈등록()
        if self._보이기:
            self.보이기()
        return self._한글

    def _실행중찾기(self) -> Any | None:
        """실행 중인 한/글 인스턴스를 ROT(Running Object Table)에서 찾는다."""
        try:
            import pythoncom
            from win32com.client import gencache

            바인딩 = pythoncom.CreateBindCtx(0)
            표 = pythoncom.GetRunningObjectTable()
            for 이름객체 in 표.EnumRunning():
                표시이름 = 이름객체.GetDisplayName(바인딩, 이름객체)
                if not 표시이름.startswith(_ROT접두어):
                    continue
                객체 = 표.GetObject(이름객체)
                return gencache.EnsureDispatch(
                    객체.QueryInterface(pythoncom.IID_IDispatch)
                )
        except Exception as 오류:  # noqa: BLE001
            로그.debug("실행 중인 한/글 조회 실패: %s", 오류)
        return None

    # -------------------------------------------------------------- 부가 설정
    def 보안모듈등록(self) -> bool:
        """파일 접근 확인 창을 없애는 보안 모듈을 등록한다.

        등록 모듈이 없어도 동작 자체는 되므로, 실패하면 경고만 남긴다.
        """
        try:
            self._한글.RegisterModule(*_보안모듈)
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
            self._한글.XHwpWindows.Item(0).Visible = bool(켜기)
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
        if self._한글 is None:
            return
        try:
            if self.새로띄움:
                self._한글.Clear(1 if 문서저장 else 3)  # 3 = 저장하지 않고 버림
                self._한글.Quit()
        except Exception as 오류:  # noqa: BLE001
            로그.debug("한/글 종료 실패: %s", 오류)
        finally:
            self._한글 = None

    def __enter__(self) -> "한글연결":
        self.연결()
        return self

    def __exit__(self, *_예외) -> None:
        self.닫기()

    @staticmethod
    def genpy정리() -> int:
        """win32com 캐시(gen_py)를 지운다.

        한/글을 새 버전으로 올린 뒤 `AttributeError: CLSIDToClassMap` 같은 오류가
        날 때 쓰는 복구 수단이다. 원본에도 `genpy폴더제거` 가 있었지만 시작할 때마다
        무조건 지워서 매번 캐시를 다시 만들었다. 여기서는 필요할 때만 부른다.
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
