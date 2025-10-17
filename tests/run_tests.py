#!/usr/bin/env python3
"""
🚀 Proxmox Manager 테스트 실행기

통합 테스트와 기능별 테스트를 실행하는 메인 스크립트입니다.
"""

import os
import sys
import argparse
import subprocess
import json
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestRunner:
    """테스트 실행기 클래스"""
    
    def __init__(self):
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.test_dir)
        
    def run_integration_tests(self) -> bool:
        """통합 테스트 실행"""
        logger.info("🚀 통합 테스트 실행 중...")
        
        try:
            # 통합 테스트 스크립트 실행
            result = subprocess.run([
                sys.executable, 
                os.path.join(self.test_dir, "integration_test_suite.py")
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ 통합 테스트 성공")
                return True
            else:
                logger.error(f"❌ 통합 테스트 실패: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 통합 테스트 실행 중 오류: {e}")
            return False
    
    def run_functional_tests(self) -> bool:
        """기능별 테스트 실행"""
        logger.info("🔧 기능별 테스트 실행 중...")
        
        try:
            # 기능별 테스트 스크립트 실행
            result = subprocess.run([
                sys.executable, 
                os.path.join(self.test_dir, "functional_test_suite.py")
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ 기능별 테스트 성공")
                return True
            else:
                logger.error(f"❌ 기능별 테스트 실패: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 기능별 테스트 실행 중 오류: {e}")
            return False
    
    def run_unit_tests(self) -> bool:
        """단위 테스트 실행"""
        logger.info("🧪 단위 테스트 실행 중...")
        
        try:
            # 단위 테스트 디렉토리 확인
            unit_test_dir = os.path.join(self.test_dir, "unit")
            if not os.path.exists(unit_test_dir):
                logger.warning("⚠️ 단위 테스트 디렉토리가 존재하지 않습니다.")
                return True
            
            # 단위 테스트 파일들 실행
            unit_test_files = [f for f in os.listdir(unit_test_dir) if f.endswith('.py') and f.startswith('test_')]
            
            if not unit_test_files:
                logger.warning("⚠️ 단위 테스트 파일이 없습니다.")
                return True
            
            success_count = 0
            total_count = len(unit_test_files)
            
            for test_file in unit_test_files:
                test_path = os.path.join(unit_test_dir, test_file)
                logger.info(f"  📋 {test_file} 실행 중...")
                
                result = subprocess.run([
                    sys.executable, test_path
                ], cwd=self.project_root, capture_output=True, text=True)
                
                if result.returncode == 0:
                    success_count += 1
                    logger.info(f"    ✅ {test_file} 성공")
                else:
                    logger.error(f"    ❌ {test_file} 실패: {result.stderr}")
            
            success_rate = (success_count / total_count) * 100
            logger.info(f"📊 단위 테스트 결과: {success_count}/{total_count} ({success_rate:.1f}%)")
            
            return success_rate >= 70
            
        except Exception as e:
            logger.error(f"❌ 단위 테스트 실행 중 오류: {e}")
            return False
    
    def generate_test_report(self) -> dict:
        """테스트 보고서 생성"""
        logger.info("📄 테스트 보고서 생성 중...")
        
        # 로그 디렉토리 확인
        logs_dir = os.path.join(self.project_root, "logs")
        if not os.path.exists(logs_dir):
            logger.warning("⚠️ 로그 디렉토리가 존재하지 않습니다.")
            return {}
        
        # 보고서 파일들 확인
        integration_report = os.path.join(logs_dir, "integration_test_report.json")
        functional_report = os.path.join(logs_dir, "functional_test_report.json")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "integration_test": {},
            "functional_test": {},
            "summary": {
                "overall_success": False,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "success_rate": 0
            }
        }
        
        # 통합 테스트 보고서 로드
        if os.path.exists(integration_report):
            try:
                with open(integration_report, 'r', encoding='utf-8') as f:
                    report["integration_test"] = json.load(f)
            except Exception as e:
                logger.error(f"❌ 통합 테스트 보고서 로드 실패: {e}")
        
        # 기능별 테스트 보고서 로드
        if os.path.exists(functional_report):
            try:
                with open(functional_report, 'r', encoding='utf-8') as f:
                    report["functional_test"] = json.load(f)
            except Exception as e:
                logger.error(f"❌ 기능별 테스트 보고서 로드 실패: {e}")
        
        # 전체 요약 계산
        total_tests = 0
        passed_tests = 0
        
        if "summary" in report["integration_test"]:
            total_tests += report["integration_test"]["summary"]["total_tests"]
            passed_tests += report["integration_test"]["summary"]["passed_tests"]
        
        if "summary" in report["functional_test"]:
            total_tests += report["functional_test"]["summary"]["total_tests"]
            passed_tests += report["functional_test"]["summary"]["passed_tests"]
        
        if total_tests > 0:
            report["summary"]["total_tests"] = total_tests
            report["summary"]["passed_tests"] = passed_tests
            report["summary"]["failed_tests"] = total_tests - passed_tests
            report["summary"]["success_rate"] = (passed_tests / total_tests) * 100
            report["summary"]["overall_success"] = report["summary"]["success_rate"] >= 75
        
        # 전체 보고서 저장
        overall_report_path = os.path.join(logs_dir, "overall_test_report.json")
        try:
            with open(overall_report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"📄 전체 테스트 보고서가 {overall_report_path}에 저장되었습니다.")
        except Exception as e:
            logger.error(f"❌ 전체 테스트 보고서 저장 실패: {e}")
        
        return report
    
    def print_summary(self, report: dict):
        """테스트 결과 요약 출력"""
        print("\n" + "=" * 80)
        print("📊 테스트 결과 요약")
        print("=" * 80)
        
        summary = report.get("summary", {})
        total_tests = summary.get("total_tests", 0)
        passed_tests = summary.get("passed_tests", 0)
        failed_tests = summary.get("failed_tests", 0)
        success_rate = summary.get("success_rate", 0)
        overall_success = summary.get("overall_success", False)
        
        print(f"📋 전체 테스트: {total_tests}")
        print(f"✅ 통과: {passed_tests}")
        print(f"❌ 실패: {failed_tests}")
        print(f"📊 성공률: {success_rate:.1f}%")
        
        if overall_success:
            print("🎉 전체 테스트 성공! (75% 이상 통과)")
        else:
            print("⚠️ 전체 테스트 실패! (75% 미만 통과)")
        
        # 세부 결과
        if "integration_test" in report and "summary" in report["integration_test"]:
            integration_summary = report["integration_test"]["summary"]
            print(f"\n🔧 통합 테스트: {integration_summary['passed_tests']}/{integration_summary['total_tests']} ({integration_summary['success_rate']:.1f}%)")
        
        if "functional_test" in report and "summary" in report["functional_test"]:
            functional_summary = report["functional_test"]["summary"]
            print(f"⚙️ 기능별 테스트: {functional_summary['passed_tests']}/{functional_summary['total_tests']} ({functional_summary['success_rate']:.1f}%)")
        
        print("=" * 80)

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Proxmox Manager 테스트 실행기")
    parser.add_argument("--integration", action="store_true", help="통합 테스트만 실행")
    parser.add_argument("--functional", action="store_true", help="기능별 테스트만 실행")
    parser.add_argument("--unit", action="store_true", help="단위 테스트만 실행")
    parser.add_argument("--all", action="store_true", help="모든 테스트 실행 (기본값)")
    parser.add_argument("--report-only", action="store_true", help="보고서만 생성")
    
    args = parser.parse_args()
    
    print("🚀 Proxmox Manager 테스트 실행기")
    print("=" * 60)
    
    # 로그 디렉토리 생성
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    test_runner = TestRunner()
    
    # 보고서만 생성하는 경우
    if args.report_only:
        report = test_runner.generate_test_report()
        test_runner.print_summary(report)
        return
    
    # 테스트 실행
    integration_success = True
    functional_success = True
    unit_success = True
    
    if args.integration or args.all:
        integration_success = test_runner.run_integration_tests()
    
    if args.functional or args.all:
        functional_success = test_runner.run_functional_tests()
    
    if args.unit or args.all:
        unit_success = test_runner.run_unit_tests()
    
    # 보고서 생성 및 출력
    report = test_runner.generate_test_report()
    test_runner.print_summary(report)
    
    # 종료 코드 설정
    if integration_success and functional_success and unit_success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
