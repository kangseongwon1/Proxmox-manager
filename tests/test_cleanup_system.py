#!/usr/bin/env python3
"""
자동 정리 시스템 테스트 스크립트
"""
import requests
import json
import time

def test_cleanup_system():
    """자동 정리 시스템 테스트"""
    base_url = "http://127.0.0.1:5000"
    
    print("🧪 자동 정리 시스템 테스트 시작")
    print("=" * 50)
    
    # 1. 로그인
    print("1️⃣ 로그인 중...")
    login_data = {
        "username": "admin",
        "password": "admin123!"
    }
    
    session = requests.Session()
    login_response = session.post(f"{base_url}/login", json=login_data)
    
    if login_response.status_code == 200:
        print("✅ 로그인 성공")
    else:
        print("❌ 로그인 실패")
        return
    
    # 2. 실패한 서버 목록 조회
    print("\n2️⃣ 실패한 서버 목록 조회...")
    failed_response = session.get(f"{base_url}/api/cleanup/failed-servers")
    
    if failed_response.status_code == 200:
        failed_data = failed_response.json()
        print(f"📋 실패한 서버 수: {failed_data.get('count', 0)}")
        
        if failed_data.get('failed_servers'):
            for server in failed_data['failed_servers']:
                print(f"  - {server['name']}: {server['status']} (정리 필요: {server['needs_cleanup']})")
    else:
        print("❌ 실패한 서버 목록 조회 실패")
    
    # 3. 특정 서버 정리 상태 확인
    test_server = "test-cleanup"
    print(f"\n3️⃣ 서버 '{test_server}' 정리 상태 확인...")
    status_response = session.get(f"{base_url}/api/cleanup/status/{test_server}")
    
    if status_response.status_code == 200:
        status_data = status_response.json()
        print(f"📊 정리 상태: {status_data.get('status', {})}")
        print(f"🔧 정리 필요: {status_data.get('needs_cleanup', False)}")
    else:
        print("❌ 정리 상태 확인 실패")
    
    # 4. 수동 정리 실행 (테스트용)
    print(f"\n4️⃣ 서버 '{test_server}' 수동 정리 실행...")
    cleanup_response = session.post(f"{base_url}/api/cleanup/clean/{test_server}")
    
    if cleanup_response.status_code == 200:
        cleanup_data = cleanup_response.json()
        print(f"✅ 수동 정리 완료: {cleanup_data.get('cleanup_results', {})}")
    else:
        print("❌ 수동 정리 실패")
    
    # 5. 대량 정리 테스트
    print("\n5️⃣ 대량 정리 테스트...")
    bulk_data = {
        "server_names": ["test1", "test2", "test3"]
    }
    bulk_response = session.post(f"{base_url}/api/cleanup/bulk-clean", json=bulk_data)
    
    if bulk_response.status_code == 200:
        bulk_data = bulk_response.json()
        print(f"✅ 대량 정리 완료: {bulk_data.get('successful', 0)}/{bulk_data.get('total', 0)}")
    else:
        print("❌ 대량 정리 실패")
    
    print("\n" + "=" * 50)
    print("🧪 자동 정리 시스템 테스트 완료")

if __name__ == "__main__":
    test_cleanup_system()
