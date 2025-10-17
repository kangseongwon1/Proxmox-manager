import requests
import json

def test_backup_api():
    print("🔍 백업 API 테스트")
    print("=" * 50)
    
    try:
        response = requests.get('http://localhost:5000/api/backups/nodes')
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            backups = data.get('data', {}).get('backups', [])
            print(f"총 백업 개수: {len(backups)}")
            
            print("\n📋 VM 이름 확인:")
            for i, backup in enumerate(backups[:5]):  # 처음 5개만
                vm_id = backup.get('vm_id')
                vm_name = backup.get('vm_name')
                print(f"  {i+1}. VM ID: {vm_id} → 이름: {vm_name}")
        else:
            print(f"❌ API 호출 실패: {response.text}")
            
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    test_backup_api() 