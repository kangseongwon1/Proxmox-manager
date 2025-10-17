#!/usr/bin/env python3
"""
서버 생성 디버깅 테스트 스크립트
"""
import requests
import json
import time
import sys

class ServerCreationTester:
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.cookies = None
        
    def login(self, username="admin", password="admin123!"):
        """로그인"""
        print("🔐 로그인 중...")
        login_data = {
            "username": username,
            "password": password
        }
        
        response = self.session.post(
            f"{self.base_url}/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"✅ 로그인 성공: {result['user']['username']}")
                self.cookies = self.session.cookies
                return True
            else:
                print(f"❌ 로그인 실패: {result.get('message', '알 수 없는 오류')}")
                return False
        else:
            print(f"❌ 로그인 요청 실패: {response.status_code}")
            return False
    
    def test_server_creation(self, server_name="test-debug"):
        """서버 생성 테스트"""
        print(f"🚀 서버 생성 테스트: {server_name}")
        
        # 서버 생성 요청
        server_data = {
            "name": server_name,
            "cpu": 2,
            "memory": 4,
            "os_type": "rocky",
            "role": "",
            "firewall_group": "",
            "disks": [
                {
                    "size": 20,
                    "interface": "scsi0",
                    "datastore_id": "HDD-Storage"
                }
            ],
            "network_devices": []
        }
        
        print(f"📋 서버 데이터: {json.dumps(server_data, indent=2, ensure_ascii=False)}")
        
        response = self.session.post(
            f"{self.base_url}/api/servers/async",
            json=server_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                task_id = result.get('task_id')
                print(f"✅ 서버 생성 요청 성공: {task_id}")
                return task_id
            else:
                print(f"❌ 서버 생성 요청 실패: {result.get('message', '알 수 없는 오류')}")
                return None
        else:
            print(f"❌ 서버 생성 요청 실패: {response.status_code}")
            return None
    
    def monitor_task(self, task_id, max_wait=300):
        """Task 상태 모니터링"""
        print(f"👀 Task 모니터링 시작: {task_id}")
        print(f"⏰ 최대 대기 시간: {max_wait}초")
        
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(f"{self.base_url}/api/tasks/{task_id}/status")
                
                if response.status_code == 200:
                    result = response.json()
                    status = result.get('status', 'unknown')
                    progress = result.get('progress', 0)
                    
                    # 상태가 변경되었을 때만 출력
                    if status != last_status:
                        print(f"📊 상태 변경: {last_status} → {status}")
                        last_status = status
                    
                    if status == 'completed':
                        print(f"✅ 작업 완료!")
                        print(f"📋 결과: {json.dumps(result.get('result', {}), indent=2, ensure_ascii=False)}")
                        return result
                    elif status == 'failed':
                        print(f"❌ 작업 실패!")
                        print(f"📋 오류: {json.dumps(result.get('result', {}), indent=2, ensure_ascii=False)}")
                        return result
                    elif status == 'running':
                        print(f"🔄 작업 진행 중... ({progress}%)")
                    else:
                        print(f"⏳ 작업 대기 중... ({status})")
                
                time.sleep(2)  # 2초마다 확인
                
            except Exception as e:
                print(f"❌ Task 상태 확인 실패: {e}")
                time.sleep(5)
        
        print(f"⏰ 타임아웃: {max_wait}초 초과")
        return None
    
    def test_datastore_loading(self):
        """Datastore 로딩 테스트"""
        print("🔧 Datastore 로딩 테스트")
        
        # Datastore 목록 조회
        response = self.session.get(f"{self.base_url}/api/datastores")
        if response.status_code == 200:
            result = response.json()
            print(f"📋 Datastore 목록: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            print(f"❌ Datastore 조회 실패: {response.status_code}")
            return None
    
    def test_datastore_refresh(self):
        """Datastore 새로고침 테스트"""
        print("🔄 Datastore 새로고침 테스트")
        
        response = self.session.post(f"{self.base_url}/api/datastores/refresh")
        if response.status_code == 200:
            result = response.json()
            print(f"📋 새로고침 결과: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            print(f"❌ Datastore 새로고침 실패: {response.status_code}")
            return None

def main():
    print("🧪 서버 생성 디버깅 테스트 시작")
    print("=" * 50)
    
    tester = ServerCreationTester()
    
    # 1. 로그인
    if not tester.login():
        print("❌ 로그인 실패로 테스트 중단")
        return
    
    # 2. Datastore 테스트
    print("\n" + "=" * 30)
    print("🔧 Datastore 테스트")
    print("=" * 30)
    
    datastore_result = tester.test_datastore_loading()
    if not datastore_result or not datastore_result.get('datastores'):
        print("⚠️ Datastore가 비어있음. 새로고침 시도...")
        tester.test_datastore_refresh()
        tester.test_datastore_loading()
    
    # 3. 서버 생성 테스트
    print("\n" + "=" * 30)
    print("🚀 서버 생성 테스트")
    print("=" * 30)
    
    server_name = f"test-debug-{int(time.time())}"
    task_id = tester.test_server_creation(server_name)
    
    if task_id:
        # 4. Task 모니터링
        print("\n" + "=" * 30)
        print("👀 Task 모니터링")
        print("=" * 30)
        
        result = tester.monitor_task(task_id, max_wait=300)
        
        if result:
            if result.get('status') == 'completed' and result.get('result', {}).get('success'):
                print("🎉 서버 생성 성공!")
            else:
                print("❌ 서버 생성 실패!")
                print(f"📋 오류: {result.get('result', {}).get('error', '알 수 없는 오류')}")
        else:
            print("⏰ Task 모니터링 타임아웃")
    else:
        print("❌ 서버 생성 요청 실패")
    
    print("\n" + "=" * 50)
    print("🏁 테스트 완료")

if __name__ == "__main__":
    main()
