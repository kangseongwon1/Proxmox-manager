"""
모니터링 시스템 설정 로더
config 파일에서 설정을 읽어와서 사용할 수 있도록 하는 모듈
"""
import configparser
import os
from typing import Dict, Any, Optional

class MonitoringConfig:
    """모니터링 시스템 설정 관리 클래스"""
    
    def __init__(self, config_file: str = 'config/monitoring_config.conf'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self) -> None:
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_file):
                self.config.read(self.config_file, encoding='utf-8')
                print(f"✅ 설정 파일 로드 완료: {self.config_file}")
            else:
                print(f"⚠️ 설정 파일이 없습니다: {self.config_file}")
                self.create_default_config()
        except Exception as e:
            print(f"❌ 설정 파일 로드 오류: {e}")
            self.create_default_config()
    
    def create_default_config(self) -> None:
        """기본 설정 생성"""
        self.config['GRAFANA'] = {
            'grafana_url': 'http://localhost:3000',
            'grafana_username': 'admin',
            'grafana_password': 'admin',
            'org_id': '1',
            'dashboard_uid': 'system_monitoring',
            'dashboard_id': '2',
            'dashboard_url': '/d/system_monitoring/system-monitoring-dashboard-10-servers',
            'allow_embedding': 'true',
            'anonymous_access': 'false',
            'kiosk_mode': 'true',
            'auto_refresh': '5s'
        }
        
        self.config['PROMETHEUS'] = {
            'prometheus_url': 'http://localhost:9090',
            'prometheus_username': '',
            'prometheus_password': ''
        }
        
        self.config['MONITORING'] = {
            'default_time_range': '1h',
            'default_refresh_interval': '5s',
            'max_data_points': '1000',
            'ping_timeout': '5s',
            'ssh_timeout': '10s',
            'health_check_interval': '30s',
            'auto_install_node_exporter': 'true',
            'node_exporter_port': '9100',
            'node_exporter_version': '1.6.1'
        }
        
        self.config['ALERTS'] = {
            'enable_alerts': 'true',
            'alert_email': 'admin@example.com',
            'alert_webhook': '',
            'cpu_warning_threshold': '80',
            'cpu_critical_threshold': '95',
            'memory_warning_threshold': '85',
            'memory_critical_threshold': '95',
            'disk_warning_threshold': '85',
            'disk_critical_threshold': '95'
        }
        
        self.config['SECURITY'] = {
            'enable_https': 'false',
            'ssl_cert_path': '',
            'ssl_key_path': '',
            'allowed_origins': '*',
            'enable_auth': 'true',
            'session_timeout': '3600',
            'max_login_attempts': '5'
        }
        
        print("✅ 기본 설정 생성 완료")
    
    def get_grafana_config(self) -> Dict[str, Any]:
        """Grafana 설정 반환"""
        return {
            'base_url': self.config.get('GRAFANA', 'grafana_url', fallback='http://localhost:3000'),
            'username': self.config.get('GRAFANA', 'grafana_username', fallback='admin'),
            'password': self.config.get('GRAFANA', 'grafana_password', fallback='admin'),
            'org_id': self.config.get('GRAFANA', 'org_id', fallback='1'),
            'dashboard_uid': self.config.get('GRAFANA', 'dashboard_uid', fallback='system_monitoring'),
            'dashboard_id': self.config.get('GRAFANA', 'dashboard_id', fallback='2'),
            'dashboard_url': self.config.get('GRAFANA', 'dashboard_url', fallback='/d/system_monitoring'),
            'allow_embedding': self.config.getboolean('GRAFANA', 'allow_embedding', fallback=True),
            'anonymous_access': self.config.getboolean('GRAFANA', 'anonymous_access', fallback=False),
            'kiosk_mode': self.config.getboolean('GRAFANA', 'kiosk_mode', fallback=True),
            'auto_refresh': self.config.get('GRAFANA', 'auto_refresh', fallback='5s')
        }
    
    def get_prometheus_config(self) -> Dict[str, Any]:
        """Prometheus 설정 반환"""
        return {
            'url': self.config.get('PROMETHEUS', 'prometheus_url', fallback='http://localhost:9090'),
            'username': self.config.get('PROMETHEUS', 'prometheus_username', fallback=''),
            'password': self.config.get('PROMETHEUS', 'prometheus_password', fallback='')
        }
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """모니터링 설정 반환"""
        return {
            'default_time_range': self.config.get('MONITORING', 'default_time_range', fallback='1h'),
            'default_refresh_interval': self.config.get('MONITORING', 'default_refresh_interval', fallback='5s'),
            'max_data_points': self.config.getint('MONITORING', 'max_data_points', fallback=1000),
            'ping_timeout': self.config.get('MONITORING', 'ping_timeout', fallback='5s'),
            'ssh_timeout': self.config.get('MONITORING', 'ssh_timeout', fallback='10s'),
            'health_check_interval': self.config.get('MONITORING', 'health_check_interval', fallback='30s'),
            'auto_install_node_exporter': self.config.getboolean('MONITORING', 'auto_install_node_exporter', fallback=True),
            'node_exporter_port': self.config.getint('MONITORING', 'node_exporter_port', fallback=9100),
            'node_exporter_version': self.config.get('MONITORING', 'node_exporter_version', fallback='1.6.1')
        }
    
    def get_alerts_config(self) -> Dict[str, Any]:
        """알림 설정 반환"""
        return {
            'enable_alerts': self.config.getboolean('ALERTS', 'enable_alerts', fallback=True),
            'alert_email': self.config.get('ALERTS', 'alert_email', fallback='admin@example.com'),
            'alert_webhook': self.config.get('ALERTS', 'alert_webhook', fallback=''),
            'cpu_warning_threshold': self.config.getfloat('ALERTS', 'cpu_warning_threshold', fallback=80.0),
            'cpu_critical_threshold': self.config.getfloat('ALERTS', 'cpu_critical_threshold', fallback=95.0),
            'memory_warning_threshold': self.config.getfloat('ALERTS', 'memory_warning_threshold', fallback=85.0),
            'memory_critical_threshold': self.config.getfloat('ALERTS', 'memory_critical_threshold', fallback=95.0),
            'disk_warning_threshold': self.config.getfloat('ALERTS', 'disk_warning_threshold', fallback=85.0),
            'disk_critical_threshold': self.config.getfloat('ALERTS', 'disk_critical_threshold', fallback=95.0)
        }
    
    def get_security_config(self) -> Dict[str, Any]:
        """보안 설정 반환"""
        return {
            'enable_https': self.config.getboolean('SECURITY', 'enable_https', fallback=False),
            'ssl_cert_path': self.config.get('SECURITY', 'ssl_cert_path', fallback=''),
            'ssl_key_path': self.config.get('SECURITY', 'ssl_key_path', fallback=''),
            'allowed_origins': self.config.get('SECURITY', 'allowed_origins', fallback='*'),
            'enable_auth': self.config.getboolean('SECURITY', 'enable_auth', fallback=True),
            'session_timeout': self.config.getint('SECURITY', 'session_timeout', fallback=3600),
            'max_login_attempts': self.config.getint('SECURITY', 'max_login_attempts', fallback=5)
        }
    
    def get_all_config(self) -> Dict[str, Any]:
        """모든 설정 반환"""
        return {
            'grafana': self.get_grafana_config(),
            'prometheus': self.get_prometheus_config(),
            'monitoring': self.get_monitoring_config(),
            'alerts': self.get_alerts_config(),
            'security': self.get_security_config()
        }
    
    def save_config(self) -> None:
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"✅ 설정 파일 저장 완료: {self.config_file}")
        except Exception as e:
            print(f"❌ 설정 파일 저장 오류: {e}")

# 전역 설정 인스턴스
monitoring_config = MonitoringConfig()

def get_monitoring_config() -> MonitoringConfig:
    """모니터링 설정 인스턴스 반환"""
    return monitoring_config
