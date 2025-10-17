# API Reference

본 문서는 `app/routes/*`에 정의된 모든 API 엔드포인트를 체계적으로 정리한 참조입니다.

## 📋 목차

- [인증 (Auth)](#인증-auth)
- [서버 관리 (Servers)](#서버-관리-servers)
- [비동기 서버 작업 (Servers Async)](#비동기-서버-작업-servers-async)
- [역할 관리 (Roles)](#역할-관리-roles)
- [방화벽 관리 (Firewall)](#방화벽-관리-firewall)
- [백업 관리 (Backup)](#백업-관리-backup)
- [알림 시스템 (Notifications)](#알림-시스템-notifications)
- [모니터링 (Monitoring)](#모니터링-monitoring)
- [관리자 (Admin)](#관리자-admin)
- [정리 작업 (Cleanup)](#정리-작업-cleanup)
- [테스트 (Test)](#테스트-test)

---

## 인증 (Auth)

### 로그인/로그아웃
- `GET/POST /login` — 로그인 페이지/처리
- `GET /logout` — 로그아웃
- `POST /change-password` — 비밀번호 변경

### 세션 관리
- `GET /api/session/check` — 세션 상태 확인
- `POST /api/session/refresh` — 세션 갱신
- `GET /api/current-user` — 현재 사용자 정보
- `GET /api/profile` — 사용자 프로필

### 호환성 엔드포인트
- `GET /session/check` — 세션 상태 (호환성)
- `POST /session/refresh` — 세션 갱신 (호환성)

---

## 서버 관리 (Servers)

### 서버 조회
- `GET /api/servers` — 서버 목록 조회
- `GET /api/servers/brief` — 서버 간단 정보 조회
- `GET /api/all_server_status` — 전체 서버 상태 조회
- `GET /api/server_status/<server_name>` — 특정 서버 상태 조회

### 서버 생성
- `POST /api/servers` — 단일 서버 생성
- `POST /api/create_servers_bulk` — 대량 서버 생성

### 서버 작업
- `POST /api/servers/<server_name>/start` — 서버 시작
- `POST /api/servers/<server_name>/stop` — 서버 중지
- `POST /api/servers/<server_name>/reboot` — 서버 재시작
- `POST /api/servers/<server_name>/delete` — 서버 삭제

### 서버 설정
- `GET /api/server/config/<server_name>` — 서버 설정 조회
- `PUT /api/server/config/<server_name>` — 서버 설정 업데이트
- `GET /api/server/logs/<server_name>` — 서버 로그 조회
- `POST /api/server/disk/<server_name>` — 디스크 추가
- `DELETE /api/server/disk/<server_name>/<device>` — 디스크 삭제

### 작업 관리
- `GET /api/tasks/status` — 작업 상태 조회
- `GET /api/tasks/config` — 작업 설정 조회
- `GET /api/tasks/<task_id>/status` — 특정 작업 상태 조회

### Celery 상태
- `GET /api/celery/status` — Celery 작업 상태 조회

### Datastore 관리
- `GET /api/datastores` — Datastore 목록 조회
- `POST /api/datastores/refresh` — Datastore 새로고침
- `POST /api/datastores/default` — 기본 Datastore 설정
- `GET /api/proxmox_storage` — Proxmox 스토리지 조회

### 서버 동기화
- `POST /api/sync_servers` — 서버 동기화

---

## 비동기 서버 작업 (Servers Async)

### 비동기 서버 생성
- `POST /api/servers/async` — 비동기 서버 생성
- `POST /api/create_servers_bulk` — 비동기 대량 서버 생성

### 비동기 서버 작업
- `POST /api/servers/<server_name>/start` — 비동기 서버 시작
- `POST /api/servers/<server_name>/stop` — 비동기 서버 중지
- `POST /api/servers/<server_name>/reboot` — 비동기 서버 재시작
- `POST /api/servers/<server_name>/delete` — 비동기 서버 삭제

### 대량 작업
- `POST /api/servers/bulk_action` — 대량 서버 작업
- `POST /api/servers/bulk_action/async` — 비동기 대량 서버 작업

### 작업 상태
- `GET /api/tasks/<task_id>/status` — 비동기 작업 상태 조회

---

## 역할 관리 (Roles)

### 단일 역할 할당
- `POST /api/assign_role/<server_name>` — 서버에 역할 할당
- `POST /api/remove_role/<server_name>` — 서버에서 역할 제거

### 대량 역할 할당
- `POST /api/roles/assign_bulk` — 대량 역할 할당

### 역할 정보
- `GET /api/roles/available` — 사용 가능한 역할 목록
- `GET /api/roles/validate/<role_name>` — 역할 유효성 검증

---

## 방화벽 관리 (Firewall)

### 방화벽 그룹 관리
- `GET /api/firewall/groups` — 방화벽 그룹 목록 조회
- `POST /api/firewall/groups` — 방화벽 그룹 생성/수정
- `GET /api/firewall/groups/<group_name>` — 특정 그룹 상세 정보
- `DELETE /api/firewall/groups/<group_name>` — 방화벽 그룹 삭제

### 방화벽 규칙 관리
- `POST /api/firewall/groups/<group_name>/rules` — 방화벽 규칙 추가/수정
- `DELETE /api/firewall/groups/<group_name>/rules/<rule_id>` — 방화벽 규칙 삭제

### 방화벽 적용
- `POST /api/apply_security_group/<server_name>` — 서버에 보안 그룹 적용
- `POST /api/remove_firewall_group/<server_name>` — 서버에서 방화벽 그룹 제거
- `POST /api/firewall/assign_bulk` — 대량 방화벽 그룹 적용

---

## 백업 관리 (Backup)

### 서버 백업
- `POST /api/server/backup/<server_name>` — 서버 백업 실행
- `GET /api/server/backups/<server_name>` — 서버 백업 목록 조회
- `GET /api/server/backup/status/<server_name>` — 서버 백업 상태 조회
- `GET /api/server/backup/<server_name>/status` — 특정 서버 백업 상태

### 전체 백업 관리
- `GET /api/backups/nodes` — 노드별 백업 목록 조회
- `GET /api/backups/nodes/<node_name>` — 특정 노드 백업 목록
- `GET /api/server/backup/status` — 전체 백업 상태 조회

### 백업 복원
- `POST /api/backups/restore` — 백업 복원 실행

### 백업 삭제
- `POST /api/backups/delete` — 백업 삭제

### 테스트
- `POST /api/test/notification` — 알림 테스트

---

## 알림 시스템 (Notifications)

### 알림 조회
- `GET /api/notifications` — 전체 알림 목록 조회
- `GET /api/notifications/latest` — 최신 알림 조회
- `GET /api/notifications/<notification_id>` — 특정 알림 상세 조회
- `GET /api/notifications/unread-count` — 미읽음 알림 수 조회

### 알림 관리
- `POST /api/notifications/<notification_id>/read` — 알림 읽음 처리
- `DELETE /api/notifications/<notification_id>` — 특정 알림 삭제
- `POST /api/notifications/clear-all` — 전체 알림 삭제

### 실시간 알림
- `GET /api/notifications/stream` — SSE 실시간 알림 스트림

---

## 모니터링 (Monitoring)

### 서버 상태 모니터링
- `GET /api/servers/<server_ip>/health` — 서버 헬스 체크
- `GET /api/servers/health-summary` — 서버 헬스 요약
- `GET /api/servers` — 모니터링용 서버 목록
- `GET /api/servers/<server_ip>/metrics` — 서버 메트릭 조회

### 알림 관리
- `POST /api/alerts/<alert_id>/acknowledge` — 알림 확인 처리
- `POST /api/alerts/clear` — 알림 클리어

### Grafana 통합
- `GET /api/grafana-dashboard` — Grafana 대시보드 조회
- `GET /api/grafana-dashboard/embed` — Grafana 임베드 대시보드

### 모니터링 설정
- `GET /api/monitoring/config` — 모니터링 설정 조회
- `POST /api/monitoring/config` — 모니터링 설정 업데이트

### 페이지
- `GET /api/monitoring/content` — 모니터링 콘텐츠
- `GET /api/monitoring/summary` — 모니터링 요약
- `GET /api/monitoring/config-page` — 모니터링 설정 페이지

---

## 관리자 (Admin)

### 사용자 관리
- `GET /api/users` — 사용자 목록 조회
- `POST /api/users` — 사용자 생성
- `DELETE /api/users/<username>` — 사용자 삭제
- `POST /api/users/<username>/password` — 사용자 비밀번호 변경

### IAM 관리
- `GET /api/iam/data` — IAM 데이터 조회
- `POST /api/iam/<username>/permissions` — 사용자 권한 설정
- `POST /api/iam/<username>/role` — 사용자 역할 설정
- `POST /api/admin/iam/<username>/permissions` — 관리자 권한 설정
- `POST /api/admin/iam/<username>/role` — 관리자 역할 설정

### 디버그
- `GET /api/current-user` — 현재 사용자 정보
- `GET /api/debug/user-info` — 사용자 정보 디버그

### 페이지
- `GET /api/admin/` — 관리자 메인 페이지
- `GET /api/admin/users` — 사용자 관리 페이지
- `GET /api/admin/iam` — IAM 관리 페이지

---

## 정리 작업 (Cleanup)

### 정리 상태
- `GET /api/cleanup/status/<server_name>` — 서버 정리 상태 조회
- `GET /api/cleanup/failed-servers` — 실패한 서버 목록 조회

### 정리 작업
- `POST /api/cleanup/clean/<server_name>` — 특정 서버 정리
- `POST /api/cleanup/bulk-clean` — 대량 서버 정리

---

## 테스트 (Test)

### Celery 테스트
- `POST /api/test/simple` — 간단한 Celery 테스트
- `POST /api/test/error` — Celery 에러 테스트

---

## 공통 응답 형식

### 성공 응답
```json
{
  "success": true,
  "data": { ... },
  "message": "작업이 완료되었습니다."
}
```

### 에러 응답
```json
{
  "success": false,
  "error": "에러 메시지",
  "details": { ... }
}
```

### 페이지네이션
```json
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "pages": 5
  }
}
```

---

## 인증 및 권한

### 인증 요구사항
- 대부분의 API는 `@login_required` 데코레이터가 적용됨
- 세션 기반 인증 사용

### 권한 요구사항
- `@permission_required('permission_name')` 데코레이터로 세부 권한 제어
- 주요 권한:
  - `create_server`: 서버 생성
  - `manage_servers`: 서버 관리
  - `assign_roles`: 역할 할당
  - `manage_firewall`: 방화벽 관리
  - `manage_backups`: 백업 관리
  - `admin_access`: 관리자 접근

### CORS 설정
- API는 CORS 헤더를 포함하여 크로스 오리진 요청 지원

---

## SSE (Server-Sent Events)

### 실시간 알림 스트림
- `GET /api/notifications/stream` — 실시간 알림 수신
- Content-Type: `text/event-stream`
- 자동 재연결 지원

### 이벤트 형식
```
data: {"type": "notification", "title": "알림 제목", "message": "알림 내용"}

```

---

**최종 업데이트**: 2025-10-16  
**버전**: 2.0.0  
**주요 변경사항**: 
- 비동기 서버 작업 API 추가
- 역할 관리 API 추가
- 백업 관리 API 추가
- 모니터링 API 추가
- SSE 실시간 알림 시스템 추가