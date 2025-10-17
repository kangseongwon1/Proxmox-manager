# 사용자/IAM 관리

## 개요
사용자 생성/삭제/비밀번호 변경, 역할/권한 설정을 웹 UI와 API로 제공합니다. 데이터는 SQLite DB의 `users`, `user_permissions`를 사용합니다.

## UI 경로
- 좌측 메뉴 → 관리자 → 사용자 관리(IAM)
- 요약 카드(전체/역할별 수), 사용자 테이블, 권한관리 오버레이, 비밀번호 변경 버튼

## API 엔드포인트
- GET `/admin/iam/data`
  - 설명: 사용자 목록과 전체 권한 목록 반환
  - 응답: `{ success, users:[{id,username,email,role,permissions[]}], all_permissions[], users_count, db_uri }`
- POST `/admin/api/users`
  - 설명: 사용자 생성 (권한 미지정 시 역할 기본 권한 자동 부여)
  - 본문: `{ username, password, email?, role? (default: developer), permissions?: string[] }`
- DELETE `/admin/api/users/<username>`
  - 설명: 사용자 삭제 (관리자 계정 삭제 불가)
- POST `/admin/api/users/<username>/password`
  - 설명: 관리자 권한으로 대상 사용자 비밀번호 변경
  - 본문: `{ new_password, confirm_password }`
- POST `/admin/iam/<username>/permissions`
  - 설명: 사용자 권한 일괄 설정(완전 치환)
  - 본문: `{ permissions: string[] }`
- POST `/admin/iam/<username>/role`
  - 설명: 사용자 역할 변경
  - 본문: `{ role: 'admin'|'developer'|'operator'|'viewer' }`

## 권한 모델 요약
- 전체 권한: `app/permissions.py`의 `ALL_PERMISSIONS`
- 역할별 기본 권한: `DEFAULT_ROLE_PERMISSIONS`
- 유효성 검증: `validate_permission`

## 권한 요구사항
- 사용자/권한/역할 관리 API는 보통 `manage_users`(또는 관리자) 권한이 필요합니다.

## 에러/트러블슈팅
- 404 NOT FOUND: 경로 접두사 확인(`/admin/api/...`)
- 400 BAD REQUEST: 필수값 누락(예: username/password), 중복 사용자
- 권한 부족(403): 로그인 계정의 권한 확인(`manage_users`)
- 목록에 사용자가 1명만 보일 때: 서버 DB와 로컬 DB 경로가 다른지 확인(`users_count`, `db_uri` 확인)
