import requests
import json
try:
    from config.config import Config
except ImportError:
    # 대안 방법으로 config 로드
    import importlib.util
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.py')
    spec = importlib.util.spec_from_file_location("config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    Config = config_module.Config

def check_backup_files():
    """실제 백업 파일명 확인"""
    
    # Proxmox 인증
    auth_url = f"{Config.PROXMOX_ENDPOINT}/api2/json/access/ticket"
    auth_data = {'username': Config.PROXMOX_USERNAME, 'password': Config.PROXMOX_PASSWORD}
    
    print("🔐 Proxmox 인증 중...")
    try:
        auth_response = requests.post(auth_url, data=auth_data, verify=False, timeout=5)
        
        if auth_response.status_code != 200:
            print("❌ 인증 실패")
            return
        
        auth_result = auth_response.json()
        ticket = auth_result['data']['ticket']
        csrf_token = auth_result['data']['CSRFPreventionToken']
        
        headers = {
            'Cookie': f'PVEAuthCookie={ticket}',
            'CSRFPreventionToken': csrf_token
        }
        
        print("✅ 인증 성공")
        
        # local 스토리지의 백업 파일 조회
        content_url = f"{Config.PROXMOX_ENDPOINT}/api2/json/nodes/prox/storage/local/content?content=backup"
        content_response = requests.get(content_url, headers=headers, verify=False, timeout=5)
        
        if content_response.status_code == 200:
            content_data = content_response.json()
            backup_files = content_data.get('data', [])
            
            print(f"🔍 {len(backup_files)}개 백업 파일 발견:")
            print("=" * 60)
            
            for i, backup in enumerate(backup_files, 1):
                volid = backup.get('volid', '')
                size = backup.get('size', 0)
                size_gb = round(size / (1024**3), 2)
                ctime = backup.get('ctime', 0)
                
                print(f"\n📁 백업 {i}:")
                print(f"  파일명: {volid}")
                print(f"  크기: {size_gb} GB")
                print(f"  생성시간: {ctime}")
                
                # 파일명 파싱
                if 'vzdump-qemu' in volid:
                    filename = volid.split('/')[-1]
                    parts = filename.split('-')
                    if len(parts) >= 4:
                        vm_id = parts[2]
                        backup_date = parts[3]
                        print(f"  VM ID: {vm_id}")
                        print(f"  백업 날짜: {backup_date}")
        else:
            print(f"❌ 백업 파일 조회 실패: {content_response.status_code}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    check_backup_files() 