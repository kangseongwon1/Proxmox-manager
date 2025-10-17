import os
from datetime import timedelta

class VaultConfig:
    """Vault 설정"""
    VAULT_ADDR = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN')
    
    @classmethod
    def get_secret(cls, secret_path, key):
        """Vault에서 시크릿 가져오기"""
        try:
            import hvac
            client = hvac.Client(url=cls.VAULT_ADDR, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(path=secret_path)
                return response['data']['data'].get(key)
            else:
                raise ValueError("Vault 인증 실패")
        except ImportError:
            # hvac 패키지가 없으면 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')
        except Exception as e:
            print(f"Vault에서 시크릿 가져오기 실패: {e}")
            # 폴백: 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')


class TerraformConfig:
    """Terraform 변수 자동 매핑"""
    
    # 환경변수 → Terraform 변수 매핑 (.env 파일 기반)
    MAPPINGS = {
        'VAULT_TOKEN': 'TF_VAR_vault_token',
        'VAULT_ADDR': 'TF_VAR_vault_address',
        'PROXMOX_ENDPOINT': 'TF_VAR_proxmox_endpoint',
        'PROXMOX_USERNAME': 'TF_VAR_proxmox_username',
        'PROXMOX_PASSWORD': 'TF_VAR_proxmox_password',
        'PROXMOX_NODE': 'TF_VAR_proxmox_node',
        'SSH_USER': 'TF_VAR_vm_username',
        'SSH_PUBLIC_KEY_PATH': 'TF_VAR_ssh_keys',
        'ENVIRONMENT': 'TF_VAR_environment',
        'PROXMOX_HDD_DATASTORE': 'TF_VAR_proxmox_hdd_datastore',
        'PROXMOX_SSD_DATASTORE': 'TF_VAR_proxmox_ssd_datastore'
    }
    
    @classmethod
    def setup_terraform_vars(cls):
        """환경변수를 Terraform 변수로 자동 매핑"""
        for source_var, target_var in cls.MAPPINGS.items():
            value = os.getenv(source_var)
            if value and not os.getenv(target_var):
                os.environ[target_var] = value
                print(f"✅ {source_var} → {target_var}")
    
    @classmethod
    def get_terraform_var(cls, var_name):
        """Terraform 변수 가져오기"""
        return os.getenv(f'TF_VAR_{var_name}')
    
    @classmethod
    def get_all_terraform_vars(cls):
        """모든 Terraform 변수 가져오기"""
        return {k: v for k, v in os.environ.items() if k.startswith('TF_VAR_')}
    
    @classmethod
    def validate_terraform_vars(cls):
        """Terraform 변수 검증"""
        required_vars = ['vault_token', 'vault_address', 'proxmox_endpoint', 'proxmox_username', 'proxmox_password']
        missing_vars = []
        
        for var in required_vars:
            if not cls.get_terraform_var(var):
                missing_vars.append(f'TF_VAR_{var}')
        
        if missing_vars:
            print(f"⚠️ 누락된 Terraform 변수: {', '.join(missing_vars)}")
            return False
        
        print("✅ 모든 필수 Terraform 변수가 설정되었습니다")
        return True
    
    @classmethod
    def debug_terraform_vars(cls):
        """Terraform 변수 디버깅 정보 출력"""
        print("🔧 Terraform 변수 상태:")
        for source_var, target_var in cls.MAPPINGS.items():
            source_value = os.getenv(source_var, '❌ 없음')
            target_value = os.getenv(target_var, '❌ 없음')
            print(f"  {source_var}: {'✅ 설정됨' if source_value != '❌ 없음' else '❌ 없음'}")
            print(f"  {target_var}: {'✅ 설정됨' if target_value != '❌ 없음' else '❌ 없음'}")
            print()



class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # SQLAlchemy 설정
    basedir = os.path.abspath(os.path.dirname(__file__))
    # 프로젝트 루트 디렉토리로 이동 (config 디렉토리의 상위)
    project_root = os.path.dirname(basedir)
    instance_dir = os.path.join(project_root, "instance")
    
    # instance 디렉토리가 없으면 생성
    if not os.path.exists(instance_dir):
        try:
            os.makedirs(instance_dir, mode=0o755, exist_ok=True)
        except Exception as e:
            print(f"⚠️ instance 디렉토리 생성 실패: {e}")
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://proxmox:proxmox123@localhost:5432/proxmox_manager')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Proxmox 설정 (환경 변수 필수)
    PROXMOX_ENDPOINT = os.environ.get('PROXMOX_ENDPOINT', 'https://localhost:8006')
    PROXMOX_USERNAME = os.environ.get('PROXMOX_USERNAME', 'root@pam')
    PROXMOX_PASSWORD = os.environ.get('PROXMOX_PASSWORD', 'password')
    PROXMOX_NODE = os.environ.get('PROXMOX_NODE', 'pve')
    PROXMOX_DATASTORE = os.environ.get('PROXMOX_DATASTORE', 'local-lvm')
    
    # 스토리지 설정 (.env에서 설정)
    PROXMOX_HDD_DATASTORE = os.environ.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
    PROXMOX_SSD_DATASTORE = os.environ.get('PROXMOX_SSD_DATASTORE', 'local')
    
    @classmethod
    def get_datastore_config(cls):
        """환경변수에서 datastore 설정 반환"""
        return {
            'hdd': cls.PROXMOX_HDD_DATASTORE,
            'ssd': cls.PROXMOX_SSD_DATASTORE
        }
    
    # 세션 보안 설정
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Strict')
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 28800))  # 8시간으로 연장
    )
    
    # 로깅 설정
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', os.path.join(project_root, 'logs', 'proxmox_manager.log'))
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', '10485760'))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', '5'))
    
    # SSH 설정
    SSH_PRIVATE_KEY_PATH = os.environ.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
    SSH_PUBLIC_KEY_PATH = os.environ.get('SSH_PUBLIC_KEY_PATH', '~/.ssh/id_rsa.pub')
    SSH_USER = os.environ.get('SSH_USER', 'rocky')
    
    @classmethod
    def get_ssh_public_key_path(cls):
        """SSH 공개키 파일 경로 반환 (절대 경로)"""
        return os.path.expanduser(cls.SSH_PUBLIC_KEY_PATH)
    
    @classmethod
    def get_ssh_private_key_path(cls):
        """SSH 개인키 파일 경로 반환 (절대 경로)"""
        return os.path.expanduser(cls.SSH_PRIVATE_KEY_PATH)
    
    # 모니터링 설정 (환경 변수)
    GRAFANA_URL = os.environ.get('GRAFANA_URL', 'http://localhost:3000')
    GRAFANA_USERNAME = os.environ.get('GRAFANA_USERNAME', 'admin')
    GRAFANA_PASSWORD = os.environ.get('GRAFANA_PASSWORD', 'admin')
    GRAFANA_ORG_ID = os.environ.get('GRAFANA_ORG_ID', '1')
    GRAFANA_DASHBOARD_UID = os.environ.get('GRAFANA_DASHBOARD_UID', 'system_monitoring')
    GRAFANA_ANONYMOUS_ACCESS = os.environ.get('GRAFANA_ANONYMOUS_ACCESS', 'false').lower() == 'true'
    GRAFANA_AUTO_REFRESH = os.environ.get('GRAFANA_AUTO_REFRESH', '5s')
    
    PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    PROMETHEUS_USERNAME = os.environ.get('PROMETHEUS_USERNAME', '')
    PROMETHEUS_PASSWORD = os.environ.get('PROMETHEUS_PASSWORD', '')
    
    NODE_EXPORTER_AUTO_INSTALL = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
    NODE_EXPORTER_PORT = int(os.environ.get('NODE_EXPORTER_PORT', '9100'))
    NODE_EXPORTER_VERSION = os.environ.get('NODE_EXPORTER_VERSION', '1.6.1')
    
    MONITORING_DEFAULT_TIME_RANGE = os.environ.get('MONITORING_DEFAULT_TIME_RANGE', '1h')
    MONITORING_HEALTH_CHECK_INTERVAL = os.environ.get('MONITORING_HEALTH_CHECK_INTERVAL', '30s')
    MONITORING_PING_TIMEOUT = os.environ.get('MONITORING_PING_TIMEOUT', '5s')
    MONITORING_SSH_TIMEOUT = os.environ.get('MONITORING_SSH_TIMEOUT', '10s')
    
    ALERTS_ENABLED = os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true'
    ALERTS_EMAIL = os.environ.get('ALERTS_EMAIL', 'admin@example.com')
    ALERTS_CPU_WARNING_THRESHOLD = float(os.environ.get('ALERTS_CPU_WARNING_THRESHOLD', '80'))
    ALERTS_CPU_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_CPU_CRITICAL_THRESHOLD', '95'))
    ALERTS_MEMORY_WARNING_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_WARNING_THRESHOLD', '85'))
    ALERTS_MEMORY_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_CRITICAL_THRESHOLD', '95'))
    
    SECURITY_ENABLE_HTTPS = os.environ.get('SECURITY_ENABLE_HTTPS', 'false').lower() == 'true'
    SECURITY_ENABLE_AUTH = os.environ.get('SECURITY_ENABLE_AUTH', 'true').lower() == 'true'
    SECURITY_SESSION_TIMEOUT = int(os.environ.get('SECURITY_SESSION_TIMEOUT', '3600'))
    SECURITY_MAX_LOGIN_ATTEMPTS = int(os.environ.get('SECURITY_MAX_LOGIN_ATTEMPTS', '5'))

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

# 환경별 설정 매핑
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 
