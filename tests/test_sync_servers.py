import requests
import json

def test_sync_servers():
    """서버 동기화 테스트"""
    
    print("🔧 서버 동기화 테스트")
    print("=" * 50)
    
    # 서버 동기화 API 호출
    sync_url = "http://localhost:5000/api/sync_servers"
    
    try:
        print("1️⃣ 서버 동기화 API 호출 중...")
        response = requests.post(sync_url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 동기화 성공: {result.get('message', '알 수 없음')}")
        else:
            print(f"❌ 동기화 실패: {response.status_code}")
            print(f"응답: {response.text}")
            
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
    
    print("\n2️⃣ 동기화 후 DB 확인...")
    try:
        # 서버 목록 조회
        servers_url = "http://localhost:5000/api/servers"
        response = requests.get(servers_url, timeout=10)
        
        if response.status_code == 200:
            servers = response.json()
            print(f"✅ 서버 목록 조회 성공: {len(servers)}개 서버")
            
            for server in servers:
                print(f"  - {server.get('name')} (VMID: {server.get('vmid', 'None')}, 상태: {server.get('status')})")
        else:
            print(f"❌ 서버 목록 조회 실패: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 서버 목록 조회 실패: {e}")

if __name__ == "__main__":
    test_sync_servers() 