"""
권한 시스템 설정
"""

# 전체 권한 목록 (실제 사용되는 권한들)
ALL_PERMISSIONS = [
    # 기본 권한
    'view_all',              # 모든 정보 조회
    
    # 서버 관리 권한
    'create_server',         # 서버 생성
    'delete_server',         # 서버 삭제
    'start_server',          # 서버 시작
    'stop_server',           # 서버 중지
    'reboot_server',         # 서버 재시작
    'manage_server',         # 서버 일반 관리 (대량 작업 등)
    
    # 역할 및 설정 관리
    'assign_roles',          # 서버 역할 할당
    'remove_role',           # 서버 역할 제거
    
    # 방화벽 관리
    'manage_firewall_groups',    # 방화벽 그룹 관리
    'assign_firewall_groups',    # 방화벽 그룹 할당
    'remove_firewall_groups',    # 방화벽 그룹 제거
    
    # 백업 관리
    'backup_management',     # 백업 관리 (복원, 삭제)
    
    # 시스템 관리 권한
    'manage_users',          # 사용자 관리
    'manage_storage',        # 스토리지 관리
    'manage_network',        # 네트워크 관리
    'manage_roles',          # 역할 관리
    'view_logs',             # 로그 조회
]

# 권한 설명 매핑
PERMISSION_DESCRIPTIONS = {
    'view_all': '모든 정보 조회',
    'create_server': '서버 생성',
    'delete_server': '서버 삭제',
    'start_server': '서버 시작',
    'stop_server': '서버 중지',
    'reboot_server': '서버 재시작',
    'manage_server': '서버 일반 관리',
    'assign_roles': '서버 역할 할당',
    'remove_role': '서버 역할 제거',
    'manage_firewall_groups': '방화벽 그룹 관리',
    'assign_firewall_groups': '방화벽 그룹 할당',
    'remove_firewall_groups': '방화벽 그룹 제거',
    'backup_management': '백업 관리',
    'manage_users': '사용자 관리',
    'manage_storage': '스토리지 관리',
    'manage_network': '네트워크 관리',
    'manage_roles': '역할 관리',
    'view_logs': '로그 조회',
}

# 기본 역할별 권한 설정
DEFAULT_ROLE_PERMISSIONS = {
    'admin': ALL_PERMISSIONS,  # 관리자는 모든 권한
    'developer': ['view_all', 'create_server', 'start_server', 'stop_server', 'reboot_server', 'assign_roles', 'backup_management'],
    'viewer': ['view_all'],
    'operator': ['view_all', 'start_server', 'stop_server', 'reboot_server', 'backup_management']
}

def get_all_permissions():
    """모든 권한 목록 반환"""
    return ALL_PERMISSIONS.copy()

def get_permission_description(permission):
    """권한 설명 반환"""
    return PERMISSION_DESCRIPTIONS.get(permission, permission)

def get_default_permissions_for_role(role):
    """역할별 기본 권한 반환"""
    return DEFAULT_ROLE_PERMISSIONS.get(role, ['view_all']).copy()

def validate_permission(permission):
    """권한이 유효한지 확인"""
    return permission in ALL_PERMISSIONS