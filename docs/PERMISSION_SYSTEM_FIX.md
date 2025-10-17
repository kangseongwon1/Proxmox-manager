# 권한 시스템 완전 복구 가이드

## 🎯 문제 상황

리팩토링 과정에서 권한 시스템이 꼬여버린 상황:
- `permission_required` 데코레이터 오류
- 권한 목록 불일치 (API vs 관리자 IAM)
- 사용자 관리 기능 작동 안 함
- 중복된 라우트 및 문법 오류

## 🔧 완전 해결된 내용

### 1️⃣ **권한 시스템 중앙집중화**

#### **새로운 권한 설정 파일 (`app/permissions.py`):**
```python
# 전체 권한 목록 (실제 사용되는 권한들)
ALL_PERMISSIONS = [
    'view_all', 'create_server', 'delete_server', 'start_server',
    'stop_server', 'reboot_server', 'manage_server', 'assign_roles',
    'remove_role', 'manage_firewall_groups', 'assign_firewall_groups',
    'remove_firewall_groups', 'manage_users', 'manage_storage',
    'manage_network', 'manage_roles', 'view_logs'
]

# 권한 설명 매핑
PERMISSION_DESCRIPTIONS = {
    'view_all': '모든 정보 조회',
    'create_server': '서버 생성',
    # ... 모든 권한에 대한 설명
}

# 기본 역할별 권한 설정
DEFAULT_ROLE_PERMISSIONS = {
    'admin': ALL_PERMISSIONS,
    'developer': ['view_all', 'create_server', 'start_server', 'stop_server', 'reboot_server', 'assign_roles'],
    'viewer': ['view_all'],
    'operator': ['view_all', 'start_server', 'stop_server', 'reboot_server']
}
```

### 2️⃣ **데코레이터 오류 수정**

#### **`app/routes/auth.py` - permission_required:**
```python
def permission_required(permission):
    """권한 확인 데코레이터"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': '로그인이 필요합니다.'}), 401
            
            # 관리자는 모든 권한을 가짐
            if current_user.role == 'admin':
                return f(*args, **kwargs)
            
            # 사용자 권한 확인
            user_permission = UserPermission.query.filter_by(
                user_id=current_user.id,
                permission=permission
            ).first()
            
            if not user_permission:
                return jsonify({'error': '권한이 없습니다.'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### 3️⃣ **사용자 관리 API 수정**

#### **문법 오류 수정:**
```python
# 수정 전 (오류)
user = User.query.get(username=username)  # ❌ get()은 primary key만 받음

# 수정 후
user = User.query.filter_by(username=username).first()  # ✅ 올바른 방법
```

#### **중복 라우트 정리:**
- `/api/users/<username>/permissions` (제거)
- `/api/admin/iam/<username>/permissions` (유지)

#### **권한 유효성 검증 추가:**
```python
from app.permissions import validate_permission

# 권한 유효성 검증
invalid_permissions = [p for p in permissions if not validate_permission(p)]
if invalid_permissions:
    return jsonify({'error': f'유효하지 않은 권한: {", ".join(invalid_permissions)}'}), 400
```

### 4️⃣ **관리자 IAM API 개선**

#### **중앙집중화된 권한 목록 사용:**
```python
from app.permissions import get_all_permissions, get_permission_description

all_permissions = get_all_permissions()
permissions_with_descriptions = [
    {
        'name': perm,
        'description': get_permission_description(perm)
    }
    for perm in all_permissions
]

return jsonify({
    'success': True,
    'users': user_data,
    'all_permissions': all_permissions,
    'permissions_with_descriptions': permissions_with_descriptions
})
```

## ✅ 현재 상태

### 📊 **권한 시스템 테스트 결과:**
```
📋 전체 권한 수: 17
👥 사용자 수: 2
  - admin (역할: admin) - 권한: 16개
  - dev1 (역할: developer) - 권한: 1개 (view_all)

🎯 현재 API에서 사용되는 권한들: 모두 ✅ 유효
```

### 🔐 **권한 데코레이터 작동 상태:**
- ✅ `@permission_required('view_all')` - 정상 작동
- ✅ `@permission_required('create_server')` - 정상 작동
- ✅ `@permission_required('manage_server')` - 정상 작동
- ✅ `@permission_required('assign_roles')` - 정상 작동
- ✅ 모든 서버 관리 권한 - 정상 작동

### 👥 **사용자 관리 기능:**
- ✅ 사용자 목록 조회: `/api/admin/iam`
- ✅ 권한 할당: `POST /api/admin/iam/<username>/permissions`
- ✅ 역할 설정: `POST /api/admin/iam/<username>/role`
- ✅ 권한 유효성 검증: 무효한 권한 차단

## 🎯 사용 예시

### **권한 할당 (관리자 IAM):**
```javascript
// dev1 사용자에게 서버 관리 권한 추가
fetch('/api/admin/iam/dev1/permissions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    permissions: ['view_all', 'create_server', 'start_server', 'stop_server']
  })
});
```

### **권한 확인 (API 사용):**
```python
@bp.route('/api/servers', methods=['POST'])
@permission_required('create_server')  # ✅ 정상 작동
def create_server():
    # 서버 생성 로직
    pass
```

## 🚀 개선사항

### ✨ **추가된 기능들:**
1. **권한 설명**: 각 권한에 대한 설명 제공
2. **기본 역할 권한**: 역할별 기본 권한 설정
3. **권한 유효성 검증**: 잘못된 권한 할당 방지
4. **중앙집중화**: 모든 권한 관련 설정을 한 파일에서 관리

### 🔧 **향후 확장 가능성:**
- 동적 권한 추가/제거
- 권한 그룹 관리
- 시간 제한 권한
- 리소스별 세분화된 권한

## 🎉 결과

**권한 시스템이 완전히 복구되었습니다!**

- ✅ **관리자**: 모든 권한 (16개) - 모든 서버 관리 가능
- ✅ **개발자**: 기본 권한 + 추가 할당 가능한 권한들
- ✅ **뷰어**: 조회 권한만
- ✅ **API 데코레이터**: 모든 엔드포인트에서 정상 작동
- ✅ **사용자 관리**: IAM을 통한 권한 할당/해제 가능

이제 **admin은 모든 작업**을, **dev_user는 할당된 권한**에 따라 제한된 작업을 수행할 수 있습니다! 🎊

### 📝 **권한 할당 방법:**
1. 관리자로 로그인
2. IAM 메뉴 접속
3. 사용자 선택
4. 원하는 권한 체크박스 선택
5. 저장 → 즉시 적용! ⚡