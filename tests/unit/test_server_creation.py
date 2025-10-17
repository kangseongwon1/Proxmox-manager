import requests
import json
import time

def test_server_creation():
    """서버 생성 테스트"""
    base_url = "http://127.0.0.1:5000"
    
    # 로그인 (필요한 경우)
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    session = requests.Session()
    
    try:
        # 로그인
        login_response = session.post(f"{base_url}/auth/login", data=login_data)
        if login_response.status_code != 200:
            print(f"❌ 로그인 실패: {login_response.status_code}")
            return
        
        print("✅ 로그인 성공")
        
        # 서버 생성 요청
        server_data = {
            "name": "test-new-server",
            "cpu_cores": 2,
            "memory_gb": 4
        }
        
        print(f"🔧 서버 생성 요청: {server_data}")
        
        create_response = session.post(
            f"{base_url}/api/servers",
            json=server_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if create_response.status_code != 200:
            print(f"❌ 서버 생성 요청 실패: {create_response.status_code}")
            print(f"응답: {create_response.text}")
            return
        
        create_result = create_response.json()
        print(f"✅ 서버 생성 요청 성공: {create_result}")
        
        if 'task_id' in create_result:
            task_id = create_result['task_id']
            print(f"🔧 Task ID: {task_id}")
            
            # Task 상태 확인
            for i in range(30):  # 최대 30초 대기
                time.sleep(2)
                
                status_response = session.get(f"{base_url}/api/tasks/status?task_id={task_id}")
                if status_response.status_code == 200:
                    task_status = status_response.json()
                    print(f"📊 Task 상태: {task_status['status']} - {task_status['message']}")
                    
                    if task_status['status'] in ['completed', 'failed']:
                        print(f"🎯 Task 완료: {task_status['status']}")
                        break
                else:
                    print(f"❌ Task 상태 조회 실패: {status_response.status_code}")
        
    except Exception as e:
        print(f"💥 테스트 실패: {e}")

if __name__ == "__main__":
    test_server_creation() 