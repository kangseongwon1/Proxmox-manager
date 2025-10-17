# 권한 시스템(Permissions)

## 개요
권한은 세밀한 기능 접근을 제어합니다. 역할(Role)과 매핑되며, 사용자별 개별 권한 부여도 가능합니다.

## 권한 목록
코드 기준 `app/permissions.py`의 `ALL_PERMISSIONS`:
- view_all, create_server, delete_server, start_server, stop_server, reboot_server, manage_server
- assign_roles, remove_role
- manage_firewall_groups, assign_firewall_groups, remove_firewall_groups
- backup_management
- manage_users, manage_storage, manage_network, manage_roles, view_logs

## 역할별 기본 권한
`DEFAULT_ROLE_PERMISSIONS`를 참고:
- admin: 모든 권한
- developer: 서버 조작 중심(view_all, create/delete/start/stop/reboot 등)
- operator, viewer: 제한된 읽기/조작 권한

## 관리 방법
- UI: Admin → 사용자 관리 → 권한관리
- API: `/admin/iam/<username>/permissions` POST

## 주의사항
- 유효성 검증: `validate_permission`으로 화이트리스트 검증
- 역할 변경 시 기본 권한과 충돌하지 않도록 정책 합치 필요


