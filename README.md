# Stock Radar Live

기존 Stock-SY와 별도로 사용하는 코스피·코스닥 전 종목 스크리닝 및 실시간 수급 대시보드입니다.

## 포함 기능

- 평일 08:30 KST 자동 스크리닝, 08:40/08:50 누락 자동 재시도
- 코스피·코스닥 상장 종목 스캔 및 8개 조건 점수화
- 실시간 코스피·코스닥 지수 표시 영역
- 외국인·기관 순매수 상위 5종목 표시 영역
- 브라우저 알림 및 PWA 설치 기반
- 검색, 시장 구분, 최소점수 필터

## GitHub Pages

Repository Settings → Pages → Build and deployment → Source에서 `GitHub Actions`를 선택합니다. 포함된 `deploy-pages.yml`이 `/dist`를 자동 배포합니다. `dist/config.js`의 `apiBaseUrl`에 실시간 API 서버 주소를 입력합니다.

## 키움 연결 전 주의

토스증권은 개인 개발용 실시간 Open API가 확인되지 않아 실시간 데이터는 키움 REST API를 사용하도록 분리했습니다. 키움 앱키와 비밀키는 프론트엔드에 넣지 말고 API 서버 환경변수로만 등록해야 합니다. 키움 사용 승인을 받은 뒤 최신 공식 JSON 명세를 프로젝트에 제공하면 `backend/kiwoom.py`의 두 매핑을 완성할 수 있습니다.

## 로컬 확인

`python -m http.server 8000 -d dist` 실행 후 `http://localhost:8000`을 엽니다.
