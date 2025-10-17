"""
Ansible 변수 관리 서비스
"""
import os
import yaml
from typing import Dict, Any, Optional
from flask import current_app

class AnsibleVariableManager:
    """Ansible 변수 관리 클래스"""
    
    def __init__(self, ansible_dir: str = "ansible"):
        # 프로젝트 루트 디렉토리 찾기
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        
        self.ansible_dir = os.path.join(project_root, ansible_dir)
        self.group_vars_dir = os.path.join(self.ansible_dir, "group_vars")
        self.host_vars_dir = os.path.join(self.ansible_dir, "host_vars")
        
        # 변수 캐시
        self._variable_cache = {}
        self._cache_loaded = False
    
    def load_all_variables(self) -> Dict[str, Any]:
        """모든 변수 파일을 로드하여 통합된 변수 딕셔너리 반환"""
        if self._cache_loaded:
            return self._variable_cache
        
        variables = {}
        
        # 1. group_vars/all.yml 로드 (기본 변수)
        all_vars_file = os.path.join(self.group_vars_dir, "all.yml")
        if os.path.exists(all_vars_file):
            with open(all_vars_file, 'r', encoding='utf-8') as f:
                all_vars = yaml.safe_load(f) or {}
                variables.update(all_vars)
                print(f"✅ group_vars/all.yml 로드: {len(all_vars)}개 변수")
        
        # 2. 환경별 변수는 제거 (단순화)
        # 필요시 group_vars/all.yml에서 직접 관리
        
        # 3. 역할별 변수 로드 (web, db, was 등)
        role_vars_files = ['web.yml', 'db.yml', 'was.yml', 'search.yml', 'ftp.yml', 'java.yml']
        for role_file in role_vars_files:
            role_vars_path = os.path.join(self.group_vars_dir, role_file)
            if os.path.exists(role_vars_path):
                with open(role_vars_path, 'r', encoding='utf-8') as f:
                    role_vars = yaml.safe_load(f) or {}
                    # 역할별 변수는 접두사를 붙여서 구분
                    role_name = role_file.replace('.yml', '')
                    for key, value in role_vars.items():
                        variables[f"{role_name}_{key}"] = value
                print(f"✅ group_vars/{role_file} 로드: {len(role_vars)}개 변수")
        
        # 4. 환경 변수에서 보안 변수 로드
        security_vars = self._load_security_variables()
        variables.update(security_vars)
        
        # 5. Flask 앱 설정에서 변수 로드
        app_vars = self._load_app_config_variables()
        variables.update(app_vars)
        
        self._variable_cache = variables
        self._cache_loaded = True
        
        print(f"✅ 총 {len(variables)}개 변수 로드 완료")
        return variables
    
    def _load_security_variables(self) -> Dict[str, Any]:
        """환경 변수에서 보안 변수 로드"""
        security_vars = {}
        
        # MySQL 관련 보안 변수
        mysql_root_password = os.environ.get('ANSIBLE_MYSQL_ROOT_PASSWORD')
        if mysql_root_password:
            security_vars['mysql_root_password'] = mysql_root_password
            security_vars['ansible_mysql_root_password'] = mysql_root_password
        
        mysql_user_password = os.environ.get('ANSIBLE_MYSQL_USER_PASSWORD')
        if mysql_user_password:
            security_vars['mysql_user_password'] = mysql_user_password
            security_vars['ansible_mysql_user_password'] = mysql_user_password
        
        mysql_replication_password = os.environ.get('ANSIBLE_MYSQL_REPLICATION_PASSWORD')
        if mysql_replication_password:
            security_vars['mysql_slave_password'] = mysql_replication_password
            security_vars['ansible_mysql_replication_password'] = mysql_replication_password
        
        # FTP 관련 보안 변수
        ftp_password = os.environ.get('ANSIBLE_FTP_PASSWORD')
        if ftp_password:
            security_vars['ftp_password'] = ftp_password
            security_vars['ansible_ftp_password'] = ftp_password
        
        # Tomcat Manager 관련 보안 변수
        tomcat_manager_password = os.environ.get('ANSIBLE_TOMCAT_MANAGER_PASSWORD')
        if tomcat_manager_password:
            security_vars['tomcat_manager_password'] = tomcat_manager_password
            security_vars['ansible_tomcat_manager_password'] = tomcat_manager_password
        
        return security_vars
    
    def _load_app_config_variables(self) -> Dict[str, Any]:
        """Flask 앱 설정에서 변수 로드"""
        app_vars = {}
        
        try:
            if current_app:
                # SSH 설정
                ssh_user = current_app.config.get('SSH_USER')
                if ssh_user:
                    app_vars['ansible_user'] = ssh_user
                
                ssh_private_key = current_app.config.get('SSH_PRIVATE_KEY_PATH')
                if ssh_private_key:
                    app_vars['ansible_ssh_private_key_file'] = ssh_private_key
                
                # Proxmox 설정
                proxmox_endpoint = current_app.config.get('PROXMOX_ENDPOINT')
                if proxmox_endpoint:
                    app_vars['proxmox_endpoint'] = proxmox_endpoint
                
                # 기타 설정들
                for key, value in current_app.config.items():
                    if key.startswith('ANSIBLE_'):
                        app_vars[key.lower()] = value
        except Exception as e:
            print(f"⚠️ Flask 앱 설정 로드 중 오류: {e}")
        
        return app_vars
    
    def get_role_variables(self, role: str) -> Dict[str, Any]:
        """특정 역할에 대한 변수 반환 (역할별 필터링)"""
        all_vars = self.load_all_variables()
        role_vars = {}
        
        # 역할별 필요한 변수 정의
        role_specific_vars = self._get_role_specific_variables(role)
        
        # 역할별 변수 추출 (접두사 기반)
        role_prefix = f"{role}_"
        for key, value in all_vars.items():
            if key.startswith(role_prefix):
                # 접두사 제거하여 원래 변수명으로 변환
                original_key = key[len(role_prefix):]
                role_vars[original_key] = value
            elif not any(key.startswith(f"{other_role}_") for other_role in ['web', 'db', 'was', 'search', 'ftp', 'java']):
                # 다른 역할 접두사가 없는 공통 변수들
                role_vars[key] = value
        
        # 역할별 필터링 적용
        filtered_vars = {}
        for key, value in role_vars.items():
            if self._is_variable_needed_for_role(key, role, role_specific_vars):
                filtered_vars[key] = value
        
        print(f"🔧 {role} 역할 변수 필터링: {len(all_vars)}개 → {len(filtered_vars)}개")
        return filtered_vars
    
    def _get_role_specific_variables(self, role: str) -> Dict[str, list]:
        """역할별 필요한 변수 정의"""
        role_vars = {
            'web': {
                'nginx': ['nginx_user', 'nginx_port', 'nginx_worker_processes', 'nginx_worker_connections', 
                         'nginx_keepalive_timeout', 'nginx_gzip_enabled', 'nginx_gzip_types'],
                'ssl': ['ssl_enabled', 'ssl_cert_path', 'ssl_key_path'],
                'upstream': ['upstream_servers', 'load_balancer_method'],
                'cache': ['cache_enabled', 'cache_path', 'cache_size', 'cache_valid_time'],
                'security': ['security_headers_enabled', 'x_frame_options', 'x_content_type_options', 'x_xss_protection']
            },
            'db': {
                'mysql': ['mysql_root_password', 'mysql_database', 'mysql_user', 'mysql_user_password', 
                         'mysql_port', 'mysql_bind_address']
            },
            'was': {
                'tomcat': ['tomcat_version', 'tomcat_port', 'tomcat_manager_port', 'tomcat_ajp_port', 'tomcat_shutdown_port']
            },
            'search': {
                'elasticsearch': ['elasticsearch_version', 'elasticsearch_port', 'elasticsearch_cluster_name', 'elasticsearch_node_name'],
                'kibana': ['kibana_version', 'kibana_port']
            },
            'ftp': {
                'ftp': ['ftp_user', 'ftp_password', 'ftp_port', 'ftp_passive_ports']
            },
            'java': {
                'java': ['java_version', 'java_home', 'java_opts']
            }
        }
        
        return role_vars.get(role, {})
    
    def _is_variable_needed_for_role(self, var_name: str, role: str, role_specific_vars: Dict[str, list]) -> bool:
        """변수가 특정 역할에 필요한지 확인 (엄격한 필터링)"""
        # 공통 변수는 항상 포함 (최소한만)
        common_vars = [
            'timezone', 'locale', 'firewall_enabled', 'ssh_port', 'ssh_permit_root_login',
            'log_level', 'log_retention_days', 'backup_enabled', 'backup_retention_days', 'backup_schedule',
            'monitoring_enabled', 'node_exporter_version', 'node_exporter_port', 'node_exporter_user',
            'ansible_user', 'ansible_ssh_private_key_file', 'proxmox_endpoint', 'role', 'target_server'
        ]
        
        if var_name in common_vars:
            return True
        
        # 역할별 특정 변수 확인
        for category, vars_list in role_specific_vars.items():
            if var_name in vars_list:
                return True
        
        # 역할별 접두사가 있는 변수는 해당 역할에만 포함
        for other_role in ['web', 'db', 'was', 'search', 'ftp', 'java']:
            if other_role != role and var_name.startswith(f"{other_role}_"):
                return False
        
        # 역할별 특정 변수명 패턴 확인 (더 엄격한 필터링)
        if role == 'web':
            # Web 역할: nginx, ssl, upstream, cache, security 관련만
            if any(var_name.startswith(prefix) for prefix in ['nginx_', 'ssl_', 'upstream_', 'cache_', 'security_', 'x_']):
                return True
        elif role == 'db':
            # DB 역할: mysql 관련만
            if any(var_name.startswith(prefix) for prefix in ['mysql_']):
                return True
        elif role == 'was':
            # WAS 역할: tomcat 관련만
            if any(var_name.startswith(prefix) for prefix in ['tomcat_']):
                return True
        elif role == 'search':
            # Search 역할: elasticsearch, kibana 관련만
            if any(var_name.startswith(prefix) for prefix in ['elasticsearch_', 'kibana_']):
                return True
        elif role == 'ftp':
            # FTP 역할: ftp 관련만
            if any(var_name.startswith(prefix) for prefix in ['ftp_']):
                return True
        elif role == 'java':
            # Java 역할: java 관련만
            if any(var_name.startswith(prefix) for prefix in ['java_']):
                return True
        
        # 다른 역할의 변수는 제외
        return False
    
    def get_environment_variables(self) -> Dict[str, Any]:
        """현재 환경에 대한 변수 반환"""
        all_vars = self.load_all_variables()
        env_vars = {}
        
        # 환경별 변수 추출
        environment = os.environ.get('ANSIBLE_ENVIRONMENT', 'production')
        for key, value in all_vars.items():
            # 환경별 변수는 접두사 없이 직접 사용
            if not any(key.startswith(f"{role}_") for role in ['web', 'db', 'was', 'search', 'ftp', 'java']):
                env_vars[key] = value
        
        return env_vars
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """특정 변수 값 반환"""
        all_vars = self.load_all_variables()
        return all_vars.get(key, default)
    
    def set_variable(self, key: str, value: Any) -> None:
        """변수 캐시에 변수 설정 (임시)"""
        self._variable_cache[key] = value
    
    def clear_cache(self) -> None:
        """변수 캐시 초기화"""
        self._variable_cache = {}
        self._cache_loaded = False
        print("🔄 Ansible 변수 캐시 초기화")
    
    def get_ansible_extra_vars(self, role: str, additional_vars: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ansible 실행을 위한 extra_vars 딕셔너리 생성 (group_vars 활용)"""
        # group_vars를 사용하므로 최소한의 변수만 전달
        extra_vars = {
            'role': role,
            'target_server': additional_vars.get('target_server') if additional_vars else None
        }
        
        # 추가 변수 병합 (필요한 경우만)
        if additional_vars:
            # 중요한 변수만 추가
            important_vars = ['ansible_user', 'ansible_ssh_private_key_file', 'proxmox_endpoint']
            for key, value in additional_vars.items():
                if key in important_vars:
                    extra_vars[key] = value
        
        print(f"🔧 {role} 역할 extra_vars (group_vars 활용): {len(extra_vars)}개 변수")
        return extra_vars
