#!/usr/bin/env python3
"""
수정된 서버 생성 테스트 스크립트
"""

import requests
import json
import time
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
        print("🔧 로그인 시도...")
        login_response = session.post(f"{base_url}/auth/login", data=login_data)
        print(f"🔧 로그인 응답 상태: {login_response.status_code}")
        print(f"🔧 로그인 응답 헤더: {dict(login_response.headers)}")
        print(f"🔧 로그인 응답 내용: {login_response.text}")
        
        if login_response.status_code != 200:
            print(f"❌ 로그인 실패: {login_response.status_code}")
            print(f"응답: {login_response.text}")
            return
        
        print("✅ 로그인 성공")
        print(f"🔧 세션 쿠키: {dict(session.cookies)}")
        
        # 서버 생성 요청
        server_data = {
            "name": "test-fixed-server",
            "cpu": 2,
            "memory": 4096,
            "role": "web",
            "ip_address": ["192.168.1.100"],
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
                    "ip_address": "192.168.1.100",
                    "subnet": 24,
                    "gateway": "192.168.1.1"
                }
            ],
            "template_vm_id": 8000,
            "vm_username": "rocky",
            "vm_password": "rocky123"
        }
        
        print(f"🔧 서버 생성 요청: {json.dumps(server_data, indent=2)}")
        
        create_response = session.post(
            f"{base_url}/api/servers",
            json=server_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"🔧 서버 생성 응답 상태: {create_response.status_code}")
        print(f"🔧 서버 생성 응답 헤더: {dict(create_response.headers)}")
        
        if create_response.status_code != 200:
            print(f"❌ 서버 생성 요청 실패: {create_response.status_code}")
            print(f"응답: {create_response.text}")
            return
        
        create_result = create_response.json()
        print(f"✅ 서버 생성 요청 성공: {json.dumps(create_result, indent=2)}")
        
        if 'task_id' in create_result:
            task_id = create_result['task_id']
            print(f"🔧 Task ID: {task_id}")
            
            # Task 상태 확인
            max_attempts = 30
            attempt = 0
            
            while attempt < max_attempts:
                attempt += 1
                print(f"🔧 Task 상태 확인 시도 {attempt}/{max_attempts}")
                
                status_response = session.get(f"{base_url}/api/tasks/status")
                if status_response.status_code == 200:
                    tasks = status_response.json()
                    print(f"🔧 전체 Task 목록: {json.dumps(tasks, indent=2)}")
                    
                    # 특정 task 찾기
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
                            print(f"⏳ 서버 생성 진행 중... ({status})")
                    else:
                        print(f"⚠️ Task {task_id}를 찾을 수 없습니다.")
                else:
                    print(f"❌ Task 상태 확인 실패: {status_response.status_code}")
                
                time.sleep(5)  # 5초 대기
            
            if attempt >= max_attempts:
                print("❌ Task 상태 확인 타임아웃")
        else:
            print("⚠️ Task ID가 응답에 없습니다.")
        
    except Exception as e:
        print(f"💥 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_server_creation() 