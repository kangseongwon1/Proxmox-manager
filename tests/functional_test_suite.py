#!/usr/bin/env python3
"""
🔧 Proxmox Manager 기능별 테스트 스위트

각 기능별로 상세한 테스트를 수행합니다.
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
        logging.FileHandler('logs/functional_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FunctionalTestSuite:
    """기능별 테스트 스위트 클래스"""
    
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.session = requests.Session()
        self.test_results = []
        
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

    def test_server_management(self) -> bool:
        """서버 관리 기능 테스트"""
        logger.info("🖥️ 서버 관리 기능 테스트 시작...")
        
        try:
            # 서버 목록 조회 테스트
            response = self.session.get(f"{self.base_url}/api/servers")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("server_list_api", True, f"서버 목록 API 응답: {response.status_code}")
            else:
                self.log_test_result("server_list_api", False, f"서버 목록 API 실패: {response.status_code}")
                return False
            
            # 서버 생성 폼 접근 테스트
            response = self.session.get(f"{self.base_url}/servers")
            if response.status_code == 200:
                self.log_test_result("server_creation_form", True, "서버 생성 폼 접근 성공")
            else:
                self.log_test_result("server_creation_form", False, f"서버 생성 폼 접근 실패: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("server_management", False, f"서버 관리 테스트 실패: {e}")
            return False

    def test_backup_management(self) -> bool:
        """백업 관리 기능 테스트"""
        logger.info("💾 백업 관리 기능 테스트 시작...")
        
        try:
            # 백업 목록 조회 테스트
            response = self.session.get(f"{self.base_url}/api/backups")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("backup_list_api", True, f"백업 목록 API 응답: {response.status_code}")
            else:
                self.log_test_result("backup_list_api", False, f"백업 목록 API 실패: {response.status_code}")
                return False
            
            # 백업 페이지 접근 테스트
            response = self.session.get(f"{self.base_url}/backups")
            if response.status_code == 200:
                self.log_test_result("backup_page_access", True, "백업 페이지 접근 성공")
            else:
                self.log_test_result("backup_page_access", False, f"백업 페이지 접근 실패: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("backup_management", False, f"백업 관리 테스트 실패: {e}")
            return False

    def test_user_management(self) -> bool:
        """사용자 관리 기능 테스트"""
        logger.info("👥 사용자 관리 기능 테스트 시작...")
        
        try:
            # 사용자 관리 페이지 접근 테스트
            response = self.session.get(f"{self.base_url}/admin")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("user_management_page", True, f"사용자 관리 페이지 응답: {response.status_code}")
            else:
                self.log_test_result("user_management_page", False, f"사용자 관리 페이지 실패: {response.status_code}")
                return False
            
            # IAM 페이지 접근 테스트
            response = self.session.get(f"{self.base_url}/admin/iam")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("iam_page", True, f"IAM 페이지 응답: {response.status_code}")
            else:
                self.log_test_result("iam_page", False, f"IAM 페이지 실패: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("user_management", False, f"사용자 관리 테스트 실패: {e}")
            return False

    def test_monitoring_system(self) -> bool:
        """모니터링 시스템 기능 테스트"""
        logger.info("📊 모니터링 시스템 기능 테스트 시작...")
        
        try:
            # 모니터링 페이지 접근 테스트
            response = self.session.get(f"{self.base_url}/monitoring")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("monitoring_page", True, f"모니터링 페이지 응답: {response.status_code}")
            else:
                self.log_test_result("monitoring_page", False, f"모니터링 페이지 실패: {response.status_code}")
                return False
            
            # 모니터링 상태 API 테스트
            response = self.session.get(f"{self.base_url}/api/monitoring/status")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("monitoring_status_api", True, f"모니터링 상태 API 응답: {response.status_code}")
            else:
                self.log_test_result("monitoring_status_api", False, f"모니터링 상태 API 실패: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("monitoring_system", False, f"모니터링 시스템 테스트 실패: {e}")
            return False

    def test_firewall_management(self) -> bool:
        """방화벽 관리 기능 테스트"""
        logger.info("🔥 방화벽 관리 기능 테스트 시작...")
        
        try:
            # 방화벽 페이지 접근 테스트
            response = self.session.get(f"{self.base_url}/firewall")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("firewall_page", True, f"방화벽 페이지 응답: {response.status_code}")
            else:
                self.log_test_result("firewall_page", False, f"방화벽 페이지 실패: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("firewall_management", False, f"방화벽 관리 테스트 실패: {e}")
            return False

    def test_notification_system(self) -> bool:
        """알림 시스템 기능 테스트"""
        logger.info("🔔 알림 시스템 기능 테스트 시작...")
        
        try:
            # 알림 API 테스트
            response = self.session.get(f"{self.base_url}/api/notifications")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("notification_api", True, f"알림 API 응답: {response.status_code}")
            else:
                self.log_test_result("notification_api", False, f"알림 API 실패: {response.status_code}")
                return False
            
            # 최신 알림 API 테스트
            response = self.session.get(f"{self.base_url}/api/notifications/latest")
            if response.status_code in [200, 401, 403]:
                self.log_test_result("latest_notification_api", True, f"최신 알림 API 응답: {response.status_code}")
            else:
                self.log_test_result("latest_notification_api", False, f"최신 알림 API 실패: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("notification_system", False, f"알림 시스템 테스트 실패: {e}")
            return False

    def test_database_operations(self) -> bool:
        """데이터베이스 작업 테스트"""
        logger.info("🗄️ 데이터베이스 작업 테스트 시작...")
        
        try:
            db_path = "instance/proxmox_manager.db"
            if not os.path.exists(db_path):
                self.log_test_result("database_operations", False, "데이터베이스 파일이 존재하지 않음")
                return False
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 사용자 테이블 조회 테스트
            try:
                cursor.execute("SELECT COUNT(*) FROM user")
                user_count = cursor.fetchone()[0]
                self.log_test_result("user_table_query", True, f"사용자 테이블 조회 성공, 사용자 수: {user_count}")
            except Exception as e:
                self.log_test_result("user_table_query", False, f"사용자 테이블 조회 실패: {e}")
                return False
            
            # 서버 테이블 조회 테스트
            try:
                cursor.execute("SELECT COUNT(*) FROM server")
                server_count = cursor.fetchone()[0]
                self.log_test_result("server_table_query", True, f"서버 테이블 조회 성공, 서버 수: {server_count}")
            except Exception as e:
                self.log_test_result("server_table_query", False, f"서버 테이블 조회 실패: {e}")
                return False
            
            # 알림 테이블 조회 테스트
            try:
                cursor.execute("SELECT COUNT(*) FROM notification")
                notification_count = cursor.fetchone()[0]
                self.log_test_result("notification_table_query", True, f"알림 테이블 조회 성공, 알림 수: {notification_count}")
            except Exception as e:
                self.log_test_result("notification_table_query", False, f"알림 테이블 조회 실패: {e}")
                return False
            
            conn.close()
            return True
            
        except Exception as e:
            self.log_test_result("database_operations", False, f"데이터베이스 작업 테스트 실패: {e}")
            return False

    def test_terraform_operations(self) -> bool:
        """Terraform 작업 테스트"""
        logger.info("🏗️ Terraform 작업 테스트 시작...")
        
        try:
            # Terraform 디렉토리 확인
            terraform_dir = "terraform"
            if not os.path.exists(terraform_dir):
                self.log_test_result("terraform_operations", False, "Terraform 디렉토리가 존재하지 않음")
                return False
            
            # terraform.tfvars.json 파일 확인
            tfvars_file = os.path.join(terraform_dir, "terraform.tfvars.json")
            if os.path.exists(tfvars_file):
                try:
                    with open(tfvars_file, 'r') as f:
                        tfvars = json.load(f)
                    self.log_test_result("terraform_tfvars", True, f"terraform.tfvars.json 로드 성공, 키: {list(tfvars.keys())}")
                except Exception as e:
                    self.log_test_result("terraform_tfvars", False, f"terraform.tfvars.json 로드 실패: {e}")
                    return False
            else:
                self.log_test_result("terraform_tfvars", True, "terraform.tfvars.json 파일이 없음 (정상)")
            
            # Terraform 상태 파일 확인
            state_file = os.path.join(terraform_dir, "terraform.tfstate")
            if os.path.exists(state_file):
                self.log_test_result("terraform_state", True, "Terraform 상태 파일 존재")
            else:
                self.log_test_result("terraform_state", True, "Terraform 상태 파일 없음 (정상)")
            
            return True
            
        except Exception as e:
            self.log_test_result("terraform_operations", False, f"Terraform 작업 테스트 실패: {e}")
            return False

    def test_ansible_operations(self) -> bool:
        """Ansible 작업 테스트"""
        logger.info("⚙️ Ansible 작업 테스트 시작...")
        
        try:
            # Ansible 디렉토리 확인
            ansible_dir = "ansible"
            if not os.path.exists(ansible_dir):
                self.log_test_result("ansible_operations", False, "Ansible 디렉토리가 존재하지 않음")
                return False
            
            # 동적 인벤토리 스크립트 확인
            inventory_script = os.path.join(ansible_dir, "dynamic_inventory.py")
            if os.path.exists(inventory_script):
                self.log_test_result("ansible_inventory", True, "동적 인벤토리 스크립트 존재")
            else:
                self.log_test_result("ansible_inventory", False, "동적 인벤토리 스크립트 없음")
                return False
            
            # 플레이북 파일 확인
            playbook_file = os.path.join(ansible_dir, "role_playbook.yml")
            if os.path.exists(playbook_file):
                self.log_test_result("ansible_playbook", True, "역할 플레이북 파일 존재")
            else:
                self.log_test_result("ansible_playbook", False, "역할 플레이북 파일 없음")
                return False
            
            # 그룹 변수 확인
            group_vars_dir = os.path.join(ansible_dir, "group_vars")
            if os.path.exists(group_vars_dir):
                group_files = os.listdir(group_vars_dir)
                yml_files = [f for f in group_files if f.endswith('.yml')]
                self.log_test_result("ansible_group_vars", True, f"그룹 변수 파일들: {yml_files}")
            else:
                self.log_test_result("ansible_group_vars", False, "그룹 변수 디렉토리 없음")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("ansible_operations", False, f"Ansible 작업 테스트 실패: {e}")
            return False

    def test_monitoring_operations(self) -> bool:
        """모니터링 작업 테스트"""
        logger.info("📊 모니터링 작업 테스트 시작...")
        
        try:
            # 모니터링 디렉토리 확인
            monitoring_dir = "monitoring"
            if not os.path.exists(monitoring_dir):
                self.log_test_result("monitoring_operations", False, "모니터링 디렉토리가 존재하지 않음")
                return False
            
            # Docker Compose 파일 확인
            docker_compose_file = os.path.join(monitoring_dir, "docker-compose.yml")
            if os.path.exists(docker_compose_file):
                self.log_test_result("monitoring_docker_compose", True, "Docker Compose 파일 존재")
            else:
                self.log_test_result("monitoring_docker_compose", False, "Docker Compose 파일 없음")
                return False
            
            # Prometheus 설정 확인
            prometheus_config = os.path.join(monitoring_dir, "prometheus.yml")
            if os.path.exists(prometheus_config):
                self.log_test_result("monitoring_prometheus_config", True, "Prometheus 설정 파일 존재")
            else:
                self.log_test_result("monitoring_prometheus_config", False, "Prometheus 설정 파일 없음")
                return False
            
            # Grafana 프로비저닝 확인
            grafana_dir = os.path.join(monitoring_dir, "grafana", "provisioning")
            if os.path.exists(grafana_dir):
                self.log_test_result("monitoring_grafana_provisioning", True, "Grafana 프로비저닝 디렉토리 존재")
            else:
                self.log_test_result("monitoring_grafana_provisioning", False, "Grafana 프로비저닝 디렉토리 없음")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("monitoring_operations", False, f"모니터링 작업 테스트 실패: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """모든 기능 테스트 실행"""
        logger.info("🔧 기능별 테스트 스위트 시작...")
        logger.info("=" * 60)
        
        # 테스트 실행 순서
        tests = [
            ("서버 관리", self.test_server_management),
            ("백업 관리", self.test_backup_management),
            ("사용자 관리", self.test_user_management),
            ("모니터링 시스템", self.test_monitoring_system),
            ("방화벽 관리", self.test_firewall_management),
            ("알림 시스템", self.test_notification_system),
            ("데이터베이스 작업", self.test_database_operations),
            ("Terraform 작업", self.test_terraform_operations),
            ("Ansible 작업", self.test_ansible_operations),
            ("모니터링 작업", self.test_monitoring_operations)
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
        logger.info("📊 기능별 테스트 결과 요약")
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
        
        with open("logs/functional_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n📄 상세 보고서가 logs/functional_test_report.json에 저장되었습니다.")
        
        return report

def main():
    """메인 함수"""
    print("🔧 Proxmox Manager 기능별 테스트 스위트")
    print("=" * 60)
    
    # 로그 디렉토리 생성
    os.makedirs("logs", exist_ok=True)
    
    # 테스트 스위트 실행
    test_suite = FunctionalTestSuite()
    report = test_suite.run_all_tests()
    
    # 종료 코드 설정
    if report["summary"]["success_rate"] >= 70:
        print("\n🎉 기능별 테스트 성공! (70% 이상 통과)")
        sys.exit(0)
    else:
        print("\n⚠️ 기능별 테스트 실패! (70% 미만 통과)")
        sys.exit(1)

if __name__ == "__main__":
    main()
