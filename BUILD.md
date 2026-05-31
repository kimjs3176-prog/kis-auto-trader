# KIS Auto Trader — 윈도우 설치 패키지 빌드 가이드

## 프로젝트 구조

```
kis-auto-trader/
├── electron/
│   ├── main.js          # Electron 메인 프로세스 (윈도우, 트레이, IPC)
│   ├── preload.js       # 보안 브리지 (contextBridge)
│   └── installer.nsh    # NSIS 한국어 인스톨러 커스터마이징
├── src/                 # React 앱 (기존과 동일)
├── assets/
│   ├── icon.ico         # 앱 아이콘 (256x256)
│   └── tray.ico         # 트레이 아이콘
├── dist/                # Vite 빌드 결과물 (자동 생성)
├── release/             # .exe 인스톨러 출력 폴더 (자동 생성)
├── package.json
└── vite.config.js
```

---

## 윈도우 .exe 인스톨러 빌드 방법

### 요구사항

- Windows 10 / 11 (or WSL2)
- Node.js 18 이상
- Git

### 빌드 순서

```bash
# 1. 의존성 설치
npm install

# 2. x64 인스톨러 빌드 (Windows 64비트)
npm run build:win

# 3. 결과물 확인
# release/KIS Auto Trader Setup 1.0.0.exe
```

> **macOS/Linux에서 크로스컴파일:** `electron-builder` 는 Wine 없이도 NSIS 인스톨러를 빌드할 수 있지만, Windows 빌드는 Windows 환경을 권장합니다.

---

## 앱 기능 (Electron 전용)

| 기능 | 설명 |
|------|------|
| 시스템 트레이 | 닫기 버튼 클릭 시 트레이로 최소화, 완전 종료 없이 상주 |
| OS 알림 | 매수/매도 주문 체결 시 Windows 알림 팝업 |
| 자동 시작 | 트레이 메뉴 → "시작프로그램 등록" 체크 |
| 설정 영구 저장 | `%AppData%\kis-auto-trader\config.json` 에 자동 저장 |
| 커스텀 타이틀바 | 다크 테마 통일 윈도우 컨트롤 |

---

## 개발 모드 실행

```bash
# React 개발 서버 + Electron 동시 실행
npm run dev
```

---

## 아이콘 교체

`assets/icon.ico` 파일을 256×256 ICO 파일로 교체하면 앱 아이콘이 변경됩니다.

추천 도구: [https://icoconvert.com](https://icoconvert.com)

---

## 배포 체크리스트

- [ ] `package.json` 버전 업데이트
- [ ] `assets/icon.ico` 고해상도 아이콘 교체
- [ ] KIS API 키 (앱 내 설정 탭에서 입력, 코드에 절대 하드코딩 금지)
- [ ] `npm run build:win` 실행
- [ ] `release/` 폴더에서 `.exe` 파일 확인
- [ ] 테스트 PC에서 설치 → 실행 → 모의투자 테스트
