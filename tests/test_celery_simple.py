#!/usr/bin/env python3
"""
간단한 Celery 테스트 스크립트
"""
import requests
import json
import time

def test_celery_async():
    """Celery 비동기 작업 테스트"""
    base_url = "http://localhost:5000"
    
    print("🔍 Celery 비동기 작업 테스트 시작...")
    
    try:
        # 1. 로그인
        print("\n1. 로그인 테스트...")
        session = requests.Session()
        
        login_data = {
            'username': 'admin',
            'password': 'admin123!'
        }
        
        login_response = session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
        print(f"📊 로그인 응답: {login_response.status_code}")
        
        if login_response.status_code not in [200, 302]:
            print("❌ 로그인 실패")
            return False
        
        print("✅ 로그인 성공")
        
        # 2. 비동기 서버 생성 테스트
        print("\n2. 비동기 서버 생성 테스트...")
        server_data = {
            'name': 'test-celery-server',
            'cpu': 2,
            'memory': 4,
            'disk': 20,
            'os_type': 'ubuntu'
        }
        
        async_response = session.post(f"{base_url}/api/servers/async", json=server_data)
        print(f"📊 비동기 응답: {async_response.status_code}")
        
        if async_response.status_code == 200:
            result = async_response.json()
            print(f"✅ 비동기 작업 시작: {result}")
            
            if 'task_id' in result:
                task_id = result['task_id']
                print(f"📋 작업 ID: {task_id}")
                
                # 3. 작업 상태 폴링
                print("\n3. 작업 상태 폴링...")
                for i in range(10):  # 최대 10번 폴링
                    status_response = session.get(f"{base_url}/api/tasks/{task_id}/status")
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"📊 상태 {i+1}: {status_data.get('status', 'unknown')} - {status_data.get('message', '')}")
                        
                        if status_data.get('status') in ['SUCCESS', 'FAILURE']:
                            print(f"✅ 작업 완료: {status_data}")
                            break
                    else:
                        print(f"❌ 상태 조회 실패: {status_response.status_code}")
                    
                    time.sleep(2)  # 2초 대기
                
                return True
            else:
                print("❌ task_id가 없습니다")
                return False
        else:
            print(f"❌ 비동기 작업 시작 실패: {async_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    test_celery_async()
