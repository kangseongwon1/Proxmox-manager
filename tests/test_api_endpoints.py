#!/usr/bin/env python3
"""
API 엔드포인트 테스트 스크립트
시작/중지/재시작 API가 정상 호출되는지, 로그가 찍히는지 확인
"""

import requests
import json
import time
import sys

def test_api_endpoints():
    """API 엔드포인트 테스트"""
    print("🧪 API 엔드포인트 테스트 시작")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:5000"
    server_name = "test"
    
    # 로그인 세션 생성
    print("1️⃣ 로그인 중...")
    session = requests.Session()
    
    try:
        login_response = session.post(f"{base_url}/login", 
                                    json={"username": "admin", "password": "admin123!"})
        if login_response.status_code == 200:
            print("✅ 로그인 성공")
        else:
            print(f"❌ 로그인 실패: {login_response.status_code}")
            print(f"   응답: {login_response.text}")
            return
    except Exception as e:
        print(f"❌ 로그인 요청 실패: {e}")
        return
    
    # 테스트할 엔드포인트들
    endpoints = [
        ("시작", f"/api/servers/{server_name}/start"),
        ("중지", f"/api/servers/{server_name}/stop"), 
        ("재시작", f"/api/servers/{server_name}/reboot")
    ]
    
    for action, endpoint in endpoints:
        print(f"\n2️⃣ {action} API 테스트...")
        print(f"   엔드포인트: {endpoint}")
        
        try:
            # API 호출
            response = session.post(f"{base_url}{endpoint}")
            print(f"   상태 코드: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   응답: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                if 'task_id' in result:
                    print(f"   태스크 ID: {result['task_id']}")
                    
                    # 태스크 상태 확인
                    print(f"   태스크 상태 확인 중...")
                    task_response = session.get(f"{base_url}/api/tasks/{result['task_id']}/status")
                    if task_response.status_code == 200:
                        task_result = task_response.json()
                        print(f"   태스크 상태: {json.dumps(task_result, ensure_ascii=False, indent=2)}")
                    else:
                        print(f"   태스크 상태 확인 실패: {task_response.status_code}")
            else:
                print(f"   응답: {response.text}")
                
        except Exception as e:
            print(f"❌ {action} API 호출 실패: {e}")
        
        # 다음 테스트 전 잠시 대기
        time.sleep(2)
    
    print("\n" + "=" * 50)
    print("🧪 API 테스트 완료")
    print("\n📋 확인 사항:")
    print("1. Flask 로그에 '📨 Celery 브로커(broker_url): ...' 라인이 찍혔는지")
    print("2. Flask 로그에 '서버 시작/중지/재시작 작업 시작: ...' 라인이 찍혔는지")
    print("3. Celery 워커 로그에 'received' 또는 'started' 라인이 찍혔는지")

if __name__ == "__main__":
    test_api_endpoints()
