import sqlite3
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

def sync_vm_data():
    """Proxmox의 실제 VM 정보로 DB 동기화"""
    
    # Proxmox 인증
    auth_url = f"{Config.PROXMOX_ENDPOINT}/api2/json/access/ticket"
    auth_data = {'username': Config.PROXMOX_USERNAME, 'password': Config.PROXMOX_PASSWORD}
    
    print("🔐 Proxmox 인증 중...")
    auth_response = requests.post(auth_url, data=auth_data, verify=False)
    
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
    
    # 모든 노드의 VM 조회
    nodes_response = requests.get(f"{Config.PROXMOX_ENDPOINT}/api2/json/nodes", headers=headers, verify=False)
    nodes = nodes_response.json().get('data', [])
    
    all_vms = []
    for node in nodes:
        node_name = node['node']
        vms_response = requests.get(f"{Config.PROXMOX_ENDPOINT}/api2/json/nodes/{node_name}/qemu", headers=headers, verify=False)
        
        if vms_response.status_code == 200:
            vms = vms_response.json().get('data', [])
            for vm in vms:
                vm['node'] = node_name
            all_vms.extend(vms)
    
    print(f"🔍 Proxmox에서 {len(all_vms)}개 VM 발견")
    
    # DB 연결
    conn = sqlite3.connect('instance/proxmox_manager.db')
    cursor = conn.cursor()
    
    # 기존 서버 데이터 조회
    cursor.execute("SELECT id, name FROM servers")
    existing_servers = cursor.fetchall()
    
    print(f"🔍 DB에서 {len(existing_servers)}개 서버 발견")
    
    # VM 이름으로 매칭하여 vmid 업데이트
    updated_count = 0
    for server_id, server_name in existing_servers:
        for vm in all_vms:
            if vm.get('name') == server_name:
                vmid = vm.get('vmid')
                status = vm.get('status', 'unknown')
                
                cursor.execute("UPDATE servers SET vmid = ?, status = ? WHERE id = ?", (vmid, status, server_id))
                print(f"✅ 서버 '{server_name}' (ID: {server_id}) -> VMID: {vmid}, 상태: {status}")
                updated_count += 1
                break
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 총 {updated_count}개 서버 정보 업데이트 완료")

if __name__ == "__main__":
    sync_vm_data() 