#!/usr/bin/env python3
"""
모든 테스트를 실행하는 통합 스크립트
"""
import subprocess
import sys
import os
import time
from datetime import datetime

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def run_test(test_file, description):
    """개별 테스트 실행"""
    log(f"🧪 {description} 시작...")
    
    try:
        result = subprocess.run([
            sys.executable, test_file
        ], capture_output=True, text=True, timeout=300)  # 5분 타임아웃
        
        if result.returncode == 0:
            log(f"✅ {description} 성공")
            return True
        else:
            log(f"❌ {description} 실패")
            log(f"   stdout: {result.stdout}")
            log(f"   stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"⏰ {description} 타임아웃 (5분)")
        return False
    except Exception as e:
        log(f"💥 {description} 예외 발생: {e}")
        return False

def check_prerequisites():
    """사전 조건 확인"""
    log("🔍 사전 조건 확인 중...")
    
    # Flask 앱 연결 확인
    try:
        import requests
        response = requests.get("http://localhost:5000", timeout=5)
        if response.status_code == 200:
            log("✅ Flask 앱 연결 확인")
        else:
            log(f"⚠️ Flask 앱 응답 이상: {response.status_code}")
    except Exception as e:
        log(f"❌ Flask 앱 연결 실패: {e}")
        return False
    
    # Redis 연결 확인
    try:
        from app.utils.redis_utils import redis_utils
        if redis_utils.is_available():
            log("✅ Redis 연결 확인")
        else:
            log("⚠️ Redis 연결 실패 (선택사항)")
    except Exception as e:
        log(f"⚠️ Redis 확인 실패: {e}")
    
    return True

def main():
    """메인 테스트 실행 함수"""
    log("🚀 Proxmox Manager 테스트 스위트 시작")
    log("=" * 60)
    
    # 사전 조건 확인
    if not check_prerequisites():
        log("❌ 사전 조건 확인 실패. 테스트를 중단합니다.")
        return 1
    
    # 테스트 목록
    tests = [
        ("test_datastore_api.py", "Datastore API 테스트"),
        ("test_redis_celery.py", "Redis & Celery 연결 테스트"),
        ("test_celery_simple.py", "Celery 간단 테스트"),
        ("test_celery_integration.py", "Celery 통합 테스트"),
    ]
    
    # 테스트 실행
    results = []
    start_time = time.time()
    
    for test_file, description in tests:
        if os.path.exists(test_file):
            success = run_test(test_file, description)
            results.append((description, success))
            log("-" * 40)
        else:
            log(f"⚠️ {test_file} 파일을 찾을 수 없습니다.")
            results.append((description, False))
    
    # 결과 요약
    end_time = time.time()
    duration = end_time - start_time
    
    log("\n" + "=" * 60)
    log("📊 테스트 결과 요약")
    log("=" * 60)
    
    passed = 0
    total = len(results)
    
    for description, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        log(f"  {description}: {status}")
        if success:
            passed += 1
    
    log("-" * 60)
    log(f"총 테스트: {total}개")
    log(f"성공: {passed}개")
    log(f"실패: {total - passed}개")
    log(f"소요 시간: {duration:.1f}초")
    log(f"성공률: {(passed/total)*100:.1f}%")
    
    if passed == total:
        log("\n🎉 모든 테스트 통과!")
        return 0
    else:
        log(f"\n❌ {total - passed}개 테스트 실패")
        return 1

if __name__ == "__main__":
    exit(main())
