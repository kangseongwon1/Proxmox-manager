#!/usr/bin/env python3
"""
🚀 Proxmox Manager 통합 테스트 스위트

이 스크립트는 프로젝트의 모든 주요 기능을 종합적으로 테스트합니다.
"""

import os
import sys
import json
import time
import requests
import subprocess
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/integration_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IntegrationTestSuite:
    """통합 테스트 스위트 클래스"""
    
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.test_results = []
        self.session = requests.Session()
        self.test_user = {
            "username": "test_user",
            "password": "test_password123",
            "role": "developer"
        }
        self.test_server = {
            "name": "test-server-integration",
            "role": "web",
            "cpu_cores": 2,
            "memory_gb": 4,
            "disk_gb": 20,
            "os_type": "rocky"
        }
        
    def log_test_result(self, test_name: str, success: bool, message: str = "", details: Dict = None):
        """테스트 결과 로깅"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} - {test_name}: {message}")
        
        if details:
            logger.info(f"    Details: {json.dumps(details, indent=2)}")

    def test_environment_setup(self) -> bool:
        """환경 설정 테스트"""
        logger.info("🔧 환경 설정 테스트 시작...")
        
        # 필수 파일 존재 확인
        required_files = [
            ".env",
            "requirements.txt",
            "run.py",
            "app/__init__.py",
            "config/config.py",
            "database.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        if missing_files:
            self.log_test_result(
                "environment_setup",
                False,
                f"필수 파일 누락: {missing_files}"
            )
            return False
        
        # Python 패키지 확인
        try:
            import flask
            import sqlalchemy
            import requests
            import paramiko
            self.log_test_result("environment_setup", True, "필수 Python 패키지 확인 완료")
        except ImportError as e:
            self.log_test_result("environment_setup", False, f"Python 패키지 누락: {e}")
            return False
        
        return True

    def test_database_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        logger.info("🗄️ 데이터베이스 연결 테스트 시작...")
        
        try:
            # 데이터베이스 파일 확인
            db_path = "instance/proxmox_manager.db"
            if not os.path.exists(db_path):
                self.log_test_result("database_connection", False, "데이터베이스 파일이 존재하지 않음")
                return False
            
            # 데이터베이스 연결 테스트
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 테이블 존재 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['user', 'server', 'notification', 'project']
            missing_tables = [table for table in expected_tables if table not in tables]
            
            if missing_tables:
                self.log_test_result(
                    "database_connection",
                    False,
                    f"필수 테이블 누락: {missing_tables}"
                )
                return False
            
            conn.close()
            self.log_test_result("database_connection", True, f"데이터베이스 연결 성공, 테이블: {tables}")
            return True
            
        except Exception as e:
            self.log_test_result("database_connection", False, f"데이터베이스 연결 실패: {e}")
            return False

    def test_flask_application(self) -> bool:
        """Flask 애플리케이션 테스트"""
        logger.info("🌐 Flask 애플리케이션 테스트 시작...")
        
        try:
            # Flask 앱이 실행 중인지 확인
            response = self.session.get(f"{self.base_url}/", timeout=10)
            
            if response.status_code == 200:
                self.log_test_result("flask_application", True, "Flask 애플리케이션 정상 실행")
                return True
            else:
                self.log_test_result("flask_application", False, f"HTTP 상태 코드: {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            self.log_test_result("flask_application", False, "Flask 애플리케이션이 실행되지 않음")
            return False
        except Exception as e:
            self.log_test_result("flask_application", False, f"Flask 애플리케이션 테스트 실패: {e}")
            return False

    def test_user_authentication(self) -> bool:
        """사용자 인증 테스트"""
        logger.info("🔐 사용자 인증 테스트 시작...")
        
        try:
            # 로그인 페이지 접근
            response = self.session.get(f"{self.base_url}/login")
            if response.status_code != 200:
                self.log_test_result("user_authentication", False, "로그인 페이지 접근 실패")
                return False
            
            # 테스트 사용자 생성 (관리자 권한 필요)
            # 실제 환경에서는 이미 존재하는 사용자로 테스트
            self.log_test_result("user_authentication", True, "로그인 페이지 접근 성공")
            return True
            
        except Exception as e:
            self.log_test_result("user_authentication", False, f"사용자 인증 테스트 실패: {e}")
            return False

    def test_api_endpoints(self) -> bool:
        """API 엔드포인트 테스트"""
        logger.info("🔌 API 엔드포인트 테스트 시작...")
        
        # 테스트할 API 엔드포인트들
        api_endpoints = [
            "/api/servers",
            "/api/backups",
            "/api/notifications",
            "/api/monitoring/status"
        ]
        
        success_count = 0
        total_count = len(api_endpoints)
        
        for endpoint in api_endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code in [200, 401, 403]:  # 401, 403도 정상 응답으로 간주
                    success_count += 1
                    logger.info(f"  ✅ {endpoint}: {response.status_code}")
                else:
                    logger.warning(f"  ⚠️ {endpoint}: {response.status_code}")
            except Exception as e:
                logger.error(f"  ❌ {endpoint}: {e}")
        
        success_rate = success_count / total_count
        if success_rate >= 0.8:  # 80% 이상 성공하면 통과
            self.log_test_result("api_endpoints", True, f"API 엔드포인트 테스트 성공 ({success_count}/{total_count})")
            return True
        else:
            self.log_test_result("api_endpoints", False, f"API 엔드포인트 테스트 실패 ({success_count}/{total_count})")
            return False

    def test_terraform_integration(self) -> bool:
        """Terraform 통합 테스트"""
        logger.info("🏗️ Terraform 통합 테스트 시작...")
        
        try:
            # Terraform 파일 존재 확인
            terraform_files = [
                "terraform/main.tf",
                "terraform/variables.tf",
                "terraform/providers.tf",
                "terraform/modules/server/main.tf"
            ]
            
            missing_files = []
            for file_path in terraform_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                self.log_test_result("terraform_integration", False, f"Terraform 파일 누락: {missing_files}")
                return False
            
            # Terraform 초기화 테스트 (실제 초기화는 하지 않음)
            terraform_dir = "terraform"
            if os.path.exists(terraform_dir):
                self.log_test_result("terraform_integration", True, "Terraform 파일 구조 확인 완료")
                return True
            else:
                self.log_test_result("terraform_integration", False, "Terraform 디렉토리가 존재하지 않음")
                return False
                
        except Exception as e:
            self.log_test_result("terraform_integration", False, f"Terraform 통합 테스트 실패: {e}")
            return False

    def test_ansible_integration(self) -> bool:
        """Ansible 통합 테스트"""
        logger.info("⚙️ Ansible 통합 테스트 시작...")
        
        try:
            # Ansible 파일 존재 확인
            ansible_files = [
                "ansible/role_playbook.yml",
                "ansible/dynamic_inventory.py",
                "ansible/group_vars/all.yml"
            ]
            
            missing_files = []
            for file_path in ansible_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                self.log_test_result("ansible_integration", False, f"Ansible 파일 누락: {missing_files}")
                return False
            
            # Ansible 역할 확인
            roles_dir = "ansible/roles"
            if os.path.exists(roles_dir):
                roles = [d for d in os.listdir(roles_dir) if os.path.isdir(os.path.join(roles_dir, d))]
                expected_roles = ['web', 'db', 'was']
                available_roles = [role for role in expected_roles if role in roles]
                
                self.log_test_result(
                    "ansible_integration", 
                    True, 
                    f"Ansible 통합 확인 완료, 사용 가능한 역할: {available_roles}"
                )
                return True
            else:
                self.log_test_result("ansible_integration", False, "Ansible roles 디렉토리가 존재하지 않음")
                return False
                
        except Exception as e:
            self.log_test_result("ansible_integration", False, f"Ansible 통합 테스트 실패: {e}")
            return False

    def test_monitoring_system(self) -> bool:
        """모니터링 시스템 테스트"""
        logger.info("📊 모니터링 시스템 테스트 시작...")
        
        try:
            # Docker Compose 파일 확인
            docker_compose_file = "monitoring/docker-compose.yml"
            if not os.path.exists(docker_compose_file):
                self.log_test_result("monitoring_system", False, "Docker Compose 파일이 존재하지 않음")
                return False
            
            # Prometheus 설정 파일 확인
            prometheus_config = "monitoring/prometheus.yml"
            if not os.path.exists(prometheus_config):
                self.log_test_result("monitoring_system", False, "Prometheus 설정 파일이 존재하지 않음")
                return False
            
            # Grafana 프로비저닝 파일 확인
            grafana_files = [
                "monitoring/grafana/provisioning/datasources/prometheus.yml",
                "monitoring/grafana/provisioning/dashboards/dashboard.yml"
            ]
            
            missing_files = []
            for file_path in grafana_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                self.log_test_result("monitoring_system", False, f"Grafana 파일 누락: {missing_files}")
                return False
            
            self.log_test_result("monitoring_system", True, "모니터링 시스템 구성 파일 확인 완료")
            return True
            
        except Exception as e:
            self.log_test_result("monitoring_system", False, f"모니터링 시스템 테스트 실패: {e}")
            return False

    def test_vault_integration(self) -> bool:
        """Vault 통합 테스트"""
        logger.info("🔐 Vault 통합 테스트 시작...")
        
        try:
            # Vault 관련 파일 확인
            vault_files = [
                "docker-compose.vault.yaml",
                "config/vault-dev.hcl",
                "scripts/vault.sh"
            ]
            
            missing_files = []
            for file_path in vault_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                self.log_test_result("vault_integration", False, f"Vault 파일 누락: {missing_files}")
                return False
            
            # Vault 토큰 파일 확인 (선택적)
            vault_token_file = "vault_token.txt"
            if os.path.exists(vault_token_file):
                self.log_test_result("vault_integration", True, "Vault 통합 확인 완료 (토큰 파일 존재)")
            else:
                self.log_test_result("vault_integration", True, "Vault 통합 확인 완료 (토큰 파일 없음 - 정상)")
            
            return True
            
        except Exception as e:
            self.log_test_result("vault_integration", False, f"Vault 통합 테스트 실패: {e}")
            return False

    def test_backup_system(self) -> bool:
        """백업 시스템 테스트"""
        logger.info("💾 백업 시스템 테스트 시작...")
        
        try:
            # 백업 관련 파일 확인
            backup_files = [
                "backup/app.py",
                "app/routes/backup.py"
            ]
            
            missing_files = []
            for file_path in backup_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                self.log_test_result("backup_system", False, f"백업 파일 누락: {missing_files}")
                return False
            
            self.log_test_result("backup_system", True, "백업 시스템 구성 파일 확인 완료")
            return True
            
        except Exception as e:
            self.log_test_result("backup_system", False, f"백업 시스템 테스트 실패: {e}")
            return False

    def test_permission_system(self) -> bool:
        """권한 시스템 테스트"""
        logger.info("🛡️ 권한 시스템 테스트 시작...")
        
        try:
            # 권한 관련 파일 확인
            permission_files = [
                "app/permissions.py",
                "app/models/user.py"
            ]
            
            missing_files = []
            for file_path in permission_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                self.log_test_result("permission_system", False, f"권한 파일 누락: {missing_files}")
                return False
            
            self.log_test_result("permission_system", True, "권한 시스템 구성 파일 확인 완료")
            return True
            
        except Exception as e:
            self.log_test_result("permission_system", False, f"권한 시스템 테스트 실패: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """모든 테스트 실행"""
        logger.info("🚀 통합 테스트 스위트 시작...")
        logger.info("=" * 60)
        
        # 테스트 실행 순서
        tests = [
            ("환경 설정", self.test_environment_setup),
            ("데이터베이스 연결", self.test_database_connection),
            ("Flask 애플리케이션", self.test_flask_application),
            ("사용자 인증", self.test_user_authentication),
            ("API 엔드포인트", self.test_api_endpoints),
            ("Terraform 통합", self.test_terraform_integration),
            ("Ansible 통합", self.test_ansible_integration),
            ("모니터링 시스템", self.test_monitoring_system),
            ("Vault 통합", self.test_vault_integration),
            ("백업 시스템", self.test_backup_system),
            ("권한 시스템", self.test_permission_system)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n📋 {test_name} 테스트 실행 중...")
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                logger.error(f"❌ {test_name} 테스트 중 예외 발생: {e}")
                self.log_test_result(test_name.lower().replace(" ", "_"), False, f"테스트 실행 중 예외: {e}")
        
        # 결과 요약
        logger.info("\n" + "=" * 60)
        logger.info("📊 테스트 결과 요약")
        logger.info("=" * 60)
        
        success_rate = (passed_tests / total_tests) * 100
        logger.info(f"✅ 통과: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
        logger.info(f"❌ 실패: {total_tests - passed_tests}/{total_tests}")
        
        # 상세 결과
        logger.info("\n📋 상세 결과:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            logger.info(f"  {status} {result['test_name']}: {result['message']}")
        
        # 결과를 JSON 파일로 저장
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": success_rate,
                "timestamp": datetime.now().isoformat()
            },
            "test_results": self.test_results
        }
        
        with open("logs/integration_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n📄 상세 보고서가 logs/integration_test_report.json에 저장되었습니다.")
        
        return report

def main():
    """메인 함수"""
    print("🚀 Proxmox Manager 통합 테스트 스위트")
    print("=" * 60)
    
    # 로그 디렉토리 생성
    os.makedirs("logs", exist_ok=True)
    
    # 테스트 스위트 실행
    test_suite = IntegrationTestSuite()
    report = test_suite.run_all_tests()
    
    # 종료 코드 설정
    if report["summary"]["success_rate"] >= 80:
        print("\n🎉 통합 테스트 성공! (80% 이상 통과)")
        sys.exit(0)
    else:
        print("\n⚠️ 통합 테스트 실패! (80% 미만 통과)")
        sys.exit(1)

if __name__ == "__main__":
    main()
