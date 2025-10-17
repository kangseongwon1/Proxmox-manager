#!/usr/bin/env python3
"""
API 엔드포인트 직접 테스트 스크립트
"""

import requests
import json
import time

def test_api_direct():
    """API 엔드포인트 직접 테스트"""
    base_url = "http://127.0.0.1:5000"
    
    session = requests.Session()
    
    try:
        # 1. 로그인 API 직접 호출
        print("🔧 로그인 API 직접 호출...")
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        
        login_response = session.post(f"{base_url}/auth/login", data=login_data)
        print(f"🔧 로그인 응답: {login_response.status_code}")
        print(f"🔧 세션 쿠키: {dict(session.cookies)}")
        
        # 2. 서버 목록 조회 테스트
        print("\n🔧 서버 목록 조회 테스트...")
        servers_response = session.get(f"{base_url}/api/servers")
        print(f"🔧 서버 목록 응답: {servers_response.status_code}")
        if servers_response.status_code == 200:
            servers = servers_response.json()
            print(f"✅ 서버 목록 조회 성공: {len(servers)}개 서버")
        else:
            print(f"❌ 서버 목록 조회 실패: {servers_response.text}")
        
        # 3. Task 상태 조회 테스트
        print("\n🔧 Task 상태 조회 테스트...")
        tasks_response = session.get(f"{base_url}/api/tasks/status")
        print(f"🔧 Task 상태 응답: {tasks_response.status_code}")
        if tasks_response.status_code == 200:
            tasks = tasks_response.json()
            print(f"✅ Task 상태 조회 성공: {len(tasks)}개 Task")
        else:
            print(f"❌ Task 상태 조회 실패: {tasks_response.text}")
        
        # 4. 서버 생성 API 직접 호출
        print("\n🔧 서버 생성 API 직접 호출...")
        server_data = {
            "name": "test-api-direct",
            "cpu": 2,
            "memory": 4096,
            "role": "web",
            "ip_address": ["192.168.1.101"],
            "disks": [
                {
                    "size": 50,
                    "interface": "scsi0",
                    "file_format": "auto",
                    "disk_type": "ssd",
                    "datastore_id": "local-lvm"
                }
            ],
            "network_devices": [
                {
                    "bridge": "vmbr0",
                    "ip_address": "192.168.1.101",
                    "subnet": 24,
                    "gateway": "192.168.1.1"
                }
            ],
            "template_vm_id": 8000,
            "vm_username": "rocky",
            "vm_password": "rocky123"
        }
        
        create_response = session.post(
            f"{base_url}/api/servers",
            json=server_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"🔧 서버 생성 응답: {create_response.status_code}")
        print(f"🔧 서버 생성 응답 헤더: {dict(create_response.headers)}")
        
        if create_response.status_code == 200:
            result = create_response.json()
            print(f"✅ 서버 생성 요청 성공: {json.dumps(result, indent=2)}")
            
            if 'task_id' in result:
                task_id = result['task_id']
                print(f"🔧 Task ID: {task_id}")
                
                # Task 상태 모니터링
                for i in range(10):
                    time.sleep(3)
                    print(f"\n🔧 Task 상태 확인 {i+1}/10...")
                    
                    status_response = session.get(f"{base_url}/api/tasks/status")
                    if status_response.status_code == 200:
                        tasks = status_response.json()
                        target_task = None
                        for task in tasks:
                            if task.get('id') == task_id:
                                target_task = task
                                break
                        
                        if target_task:
                            status = target_task.get('status')
                            message = target_task.get('message', '')
                            print(f"🔧 Task 상태: {status} - {message}")
                            
                            if status == 'completed':
                                print("✅ 서버 생성 완료!")
                                break
                            elif status == 'failed':
                                print(f"❌ 서버 생성 실패: {message}")
                                break
                        else:
                            print(f"⚠️ Task {task_id}를 찾을 수 없습니다.")
                    else:
                        print(f"❌ Task 상태 확인 실패: {status_response.status_code}")
        else:
            print(f"❌ 서버 생성 요청 실패: {create_response.text}")
        
    except Exception as e:
        print(f"💥 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_direct() 