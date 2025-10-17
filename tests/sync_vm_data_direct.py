import requests
import sqlite3
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

def sync_vm_data_direct():
    """Proxmox API를 직접 호출해서 VM 정보를 가져와서 DB 동기화"""
    
    print("🔧 Proxmox API 직접 호출로 VM 데이터 동기화")
    print("=" * 60)
    
    # Config 설정 확인
    print(f"🔍 Config 설정 확인:")
    print(f"  - PROXMOX_ENDPOINT: {Config.PROXMOX_ENDPOINT}")
    print(f"  - PROXMOX_USERNAME: {Config.PROXMOX_USERNAME}")
    print(f"  - PROXMOX_NODE: {Config.PROXMOX_NODE}")
    
    # Proxmox 인증
    auth_url = f"{Config.PROXMOX_ENDPOINT}/api2/json/access/ticket"
    auth_data = {
        'username': Config.PROXMOX_USERNAME, 
        'password': Config.PROXMOX_PASSWORD
    }
    
    print(f"\n🔐 Proxmox 인증 중...")
    print(f"  - 인증 URL: {auth_url}")
    
    try:
        auth_response = requests.post(auth_url, data=auth_data, verify=False, timeout=10)
        
        if auth_response.status_code != 200:
            print(f"❌ 인증 실패: {auth_response.status_code}")
            print(f"  응답: {auth_response.text}")
            return
        
        auth_result = auth_response.json()
        ticket = auth_result['data']['ticket']
        csrf_token = auth_result['data']['CSRFPreventionToken']
        
        headers = {
            'Cookie': f'PVEAuthCookie={ticket}',
            'CSRFPreventionToken': csrf_token
        }
        
        print("✅ 인증 성공")
        
        # 노드 목록 조회
        print(f"\n🔍 노드 목록 조회 중...")
        nodes_url = f"{Config.PROXMOX_ENDPOINT}/api2/json/nodes"
        nodes_response = requests.get(nodes_url, headers=headers, verify=False, timeout=10)
        
        if nodes_response.status_code != 200:
            print(f"❌ 노드 조회 실패: {nodes_response.status_code}")
            return
        
        nodes_data = nodes_response.json()
        nodes = [node['node'] for node in nodes_data.get('data', [])]
        print(f"✅ 발견된 노드들: {nodes}")
        
        # 모든 노드의 VM 조회
        all_vms = []
        for node in nodes:
            print(f"\n🔍 노드 {node}의 VM 조회 중...")
            vms_url = f"{Config.PROXMOX_ENDPOINT}/api2/json/nodes/{node}/qemu"
            vms_response = requests.get(vms_url, headers=headers, verify=False, timeout=10)
            
            if vms_response.status_code == 200:
                vms = vms_response.json().get('data', [])
                for vm in vms:
                    vm['node'] = node
                all_vms.extend(vms)
                print(f"✅ 노드 {node}: {len(vms)}개 VM 발견")
            else:
                print(f"❌ 노드 {node} VM 조회 실패: {vms_response.status_code}")
        
        print(f"\n📋 총 {len(all_vms)}개 VM 발견:")
        for vm in all_vms:
            print(f"  - {vm.get('name')} (ID: {vm.get('vmid')}, 상태: {vm.get('status')}, 노드: {vm.get('node')})")
        
        # DB 연결
        print(f"\n💾 DB 동기화 시작...")
        conn = sqlite3.connect('instance/proxmox_manager.db')
        cursor = conn.cursor()
        
        # 기존 서버 데이터 조회
        cursor.execute("SELECT id, name, vmid FROM servers")
        existing_servers = cursor.fetchall()
        existing_server_names = {row[1]: {'id': row[0], 'vmid': row[2]} for row in existing_servers}
        
        print(f"🔍 DB에서 {len(existing_servers)}개 서버 발견")
        
        # VM 정보로 DB 업데이트
        updated_count = 0
        new_count = 0
        
        for vm in all_vms:
            vm_name = vm.get('name')
            vm_id = vm.get('vmid')
            vm_status = vm.get('status', 'unknown')
            vm_node = vm.get('node')
            
            if vm_name in existing_server_names:
                # 기존 서버 업데이트
                server_id = existing_server_names[vm_name]['id']
                old_vmid = existing_server_names[vm_name]['vmid']
                
                if old_vmid != vm_id:
                    cursor.execute(
                        "UPDATE servers SET vmid = ?, status = ?, updated_at = datetime('now') WHERE id = ?",
                        (vm_id, vm_status, server_id)
                    )
                    print(f"✅ 서버 업데이트: {vm_name} (ID: {server_id}) -> VMID: {old_vmid} → {vm_id}")
                    updated_count += 1
                else:
                    print(f"🔄 서버 상태만 업데이트: {vm_name} (VMID: {vm_id}) -> 상태: {vm_status}")
                    cursor.execute(
                        "UPDATE servers SET status = ?, updated_at = datetime('now') WHERE id = ?",
                        (vm_status, server_id)
                    )
                    updated_count += 1
            else:
                # 새 서버 추가
                cursor.execute(
                    "INSERT INTO servers (name, vmid, status, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                    (vm_name, vm_id, vm_status)
                )
                print(f"➕ 새 서버 추가: {vm_name} (VMID: {vm_id}, 상태: {vm_status})")
                new_count += 1
        
        # DB에 있지만 Proxmox에 없는 서버 처리
        proxmox_vm_names = {vm.get('name') for vm in all_vms}
        for server_name, server_info in existing_server_names.items():
            if server_name not in proxmox_vm_names:
                print(f"⚠️ Proxmox에 없는 서버: {server_name} (DB ID: {server_info['id']})")
                # 상태를 'deleted'로 변경하거나 삭제할 수 있음
                cursor.execute(
                    "UPDATE servers SET status = 'deleted', updated_at = datetime('now') WHERE id = ?",
                    (server_info['id'],)
                )
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 DB 동기화 완료!")
        print(f"  - 새로 추가된 서버: {new_count}개")
        print(f"  - 업데이트된 서버: {updated_count}개")
        print(f"  - 총 처리된 VM: {len(all_vms)}개")
        
        # 동기화 후 DB 확인
        print(f"\n📋 동기화 후 DB 확인:")
        conn = sqlite3.connect('instance/proxmox_manager.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, vmid, status FROM servers ORDER BY name")
        servers = cursor.fetchall()
        
        for server in servers:
            print(f"  - {server[0]} (VMID: {server[1]}, 상태: {server[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    sync_vm_data_direct() 