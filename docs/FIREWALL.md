# 방화벽/보안그룹

## 그룹 관리
- GET `/api/firewall/groups`: 목록
- POST `/api/firewall/groups`: 생성/갱신
- GET `/api/firewall/groups/<group_name>`: 상세
- DELETE `/api/firewall/groups/<group_name>`: 삭제

## 룰 관리
- POST `/api/firewall/groups/<group_name>/rules`: 룰 추가/갱신
- DELETE `/api/firewall/groups/<group_name>/rules/<rule_id>`: 룰 삭제

## 서버 적용
- POST `/api/apply_security_group/<server_name>`: 단일 적용
- POST `/api/firewall/assign_bulk`: 일괄 적용
- POST `/api/remove_firewall_group/<server_name>`: 제거

## 주의사항
- 중복 firewall 파라미터 방지: `proxmox_service.py`에서 안전 처리
- 권한: `manage_firewall_groups`/`assign_firewall_groups`/`remove_firewall_groups`
