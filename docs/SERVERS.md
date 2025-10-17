# 서버 관리

## 목록/요약
- GET `/api/servers`: 전체 목록
- GET `/api/servers/brief`: 요약 정보(간단)

## 생성/대량 생성
- POST `/api/servers`: 단일 생성(모듈/변수는 Terraform/Vault 연계)
- POST `/api/create_servers_bulk`: 다중 생성

## 서버 액션
- POST `/api/servers/<name>/start`
- POST `/api/servers/<name>/stop`
- POST `/api/servers/<name>/reboot`
- POST `/api/servers/<name>/delete`
- 기타 상태/백업 관련 보조 엔드포인트는 UI에서 호출

## 작업 상태 폴링
- GET `/api/tasks/status?task_id=...`
- GET `/api/tasks/config`: 폴링/타임아웃 설정

## Ansible/Node Exporter
- 역할 설치 시 SSH 준비 대기, known_hosts 충돌 회피
- 공통 시스템 설정은 node_exporter 역할로 이전(KST, PasswordAuth, SELinux 등)

## 트러블슈팅
- known_hosts 충돌: 삭제 후 재시도
- Terraform/Ansible 실패: 작업 로그 확인, 알림 드롭다운에서 에러 확인
