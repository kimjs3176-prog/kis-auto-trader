; KIS Auto Trader - NSIS 인스톨러 커스터마이징
; 한국어 설치 화면

!macro customHeader
  !system "echo '한국투자증권 자동매매 설치 패키지'"
!macroend

!macro customInstall
  ; 설치 완료 후 바탕화면 아이콘 생성 확인
  DetailPrint "KIS Auto Trader 설치가 완료되었습니다."
  DetailPrint "한국투자증권 Open API 키를 준비해주세요."
!macroend

!macro customUnInstall
  DetailPrint "KIS Auto Trader를 제거합니다."
  ; 사용자 설정 파일은 유지 (AppData)
  DetailPrint "사용자 설정 파일은 보존됩니다."
!macroend
