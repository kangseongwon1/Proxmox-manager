# 인증/세션

## 로그인/로그아웃
- GET/POST `/login`: 로그인 폼/처리
- GET `/logout`: 로그아웃 및 세션 정리

## 프로필/비밀번호 변경
- GET `/profile`: 프로필 페이지
- POST `/change-password`: 현재 사용자 비밀번호 변경 (JSON/Form 모두 지원)

## 세션 API
- GET `/api/session/check`: 세션 상태 확인
- POST `/api/session/refresh`: 세션 갱신(권한/역할 재적용)
- GET `/api/current-user`: 현재 사용자 정보(JSON)
- GET `/api/profile`: 프로필(JSON)
- 호환성: `/session/check`, `/session/refresh` 경로도 제공

## 동작 요약
- 로그인 성공 시 `session.permissions`, `session.user_role` 등 세션에 권한 정보 저장
- `permission_required` 데코레이터로 라우트 접근 제어

## 에러/트러블슈팅
- 401/403: 세션 만료 또는 권한 부족
- `TemplateNotFound` 등 템플릿 오류는 프론트 알림 시스템에 표시되며, 서버 로그로도 확인 가능
