# 알림 시스템

## API
- GET `/api/notifications`: 전체(사용자+시스템)
- GET `/api/notifications/latest`: 최신 1건
- GET `/api/notifications/<id>`: 상세
- POST `/api/notifications/<id>/read`: 읽음 처리
- DELETE `/api/notifications/<id>`: 삭제
- POST `/api/notifications/clear-all`: 전체 삭제
- GET `/api/notifications/unread-count`: 미읽음 개수
- GET `/api/notifications/stream`: SSE(현재는 폴링 사용)

## 프론트 통합
- `app/static/instances.js`의 폴링(5초) 및 드롭다운 렌더링
- 전역 에러 캐치(자바스크립트/Promise/AJAX/console) → 알림에 노출

## 운영 팁
- 알림 과다 방지: 심각도 필터링, 중복 방지 로직 포함
