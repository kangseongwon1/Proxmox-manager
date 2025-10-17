#!/usr/bin/env python3
# """
# Dynamic Inventory Script for Proxmox Manager
# Ansible에서 --list 또는 --host <hostname> 인자로 호출됨
# """

import json
import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Any

def get_os_family(os_type: str) -> str:
    """OS 타입을 기반으로 OS 계열을 반환합니다."""
    # RedHat 계열
    redhat_family = ['rocky', 'centos', 'rhel', 'alma', 'fedora']
    if os_type in redhat_family:
        return 'RedHat'
    
    # Debian 계열
    debian_family = ['ubuntu', 'debian']
    if os_type in debian_family:
        return 'Debian'
    
    # SUSE 계열
    suse_family = ['suse', 'opensuse', 'sles']
    if os_type in suse_family:
        return 'Suse'
    
    # 기본값
    return 'RedHat'

class DynamicInventory:
    def __init__(self):
        # PostgreSQL 연결 정보
        self.db_url = os.environ.get('DATABASE_URL', 'postgresql://proxmox:proxmox123@localhost:5432/proxmox_manager')
    
    def get_servers_from_db(self) -> List[Dict[str, Any]]:
        """DB에서 서버 정보 조회"""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT name, ip_address, role, status, cpu, memory, os_type 
                FROM servers 
                WHERE ip_address IS NOT NULL AND ip_address != ''
            """)
            
            servers = []
            for row in cursor.fetchall():
                name = row['name']
                ip_address = row['ip_address']
                role = row['role']
                status = row['status']
                cpu = row['cpu']
                memory = row['memory']
                os_type = row['os_type']
                
                servers.append({
                    'name': name,
                    'ip_address': ip_address,
                    'role': role,
                    'status': status,
                    'cpu': cpu,
                    'memory': memory,
                    'os_type': os_type
                })
            
            conn.close()
            return servers
            
        except Exception as e:
            print(f"DB 조회 오류: {e}", file=sys.stderr)
            return []
    
    def generate_inventory(self, target_server_ip: str = None) -> Dict[str, Any]:
        """전체 inventory 생성 (--list)"""
        servers = self.get_servers_from_db()
        
        # 특정 서버만 필터링 (명령행 인자 또는 환경 변수에서)
        if target_server_ip:
            servers = [s for s in servers if s['ip_address'] == target_server_ip]
        else:
            # 환경 변수에서 특정 서버 IP 확인
            env_target = os.environ.get('TARGET_SERVER_IP')
            if env_target:
                servers = [s for s in servers if s['ip_address'] == env_target]
        
        # 기본 그룹 설정
        inventory = {
            'all': {
                'children': ['ungrouped']
            },
            'ungrouped': {
                'hosts': []
            },
            '_meta': {
                'hostvars': {}
            }
        }
        
        # 역할별 그룹 매핑
        role_groups = {
            'web': 'webservers',
            'db': 'dbservers',
            'was': 'was_servers',
            'java': 'java_servers',
            'search': 'search_servers',
            'ftp': 'ftp_servers',
            'monitoring': 'monitoring_servers'
        }
        
        # 서버별로 그룹에 추가
        for server in servers:
            hostname = server['ip_address']
            role = server.get('role', 'none')
            
            # ungrouped에 추가
            inventory['ungrouped']['hosts'].append(hostname)
            
            # 역할별 그룹에 추가
            if role in role_groups:
                group_name = role_groups[role]
                
                if group_name not in inventory:
                    inventory[group_name] = {'hosts': []}
                    inventory['all']['children'].append(group_name)
                
                inventory[group_name]['hosts'].append(hostname)
            
            # OS 타입에 따른 설정
            os_type = server.get('os_type', 'rocky')
            os_family = get_os_family(os_type)
            
            # OS별 기본 사용자명
            username_map = {
                'rocky': 'rocky',
                'centos': 'centos',
                'rhel': 'rhel',
                'ubuntu': 'ubuntu',
                'debian': 'debian',
                'alma': 'alma',
                'fedora': 'fedora',
                'suse': 'suse'
            }
            ansible_user = username_map.get(os_type, 'rocky')
            
            # 호스트 변수 설정
            inventory['_meta']['hostvars'][hostname] = {
                'ansible_host': hostname,
                'server_name': server['name'],
                'server_role': role,
                'server_status': server['status'],
                'ansible_user': ansible_user,
                'ansible_ssh_private_key_file': '~/.ssh/id_rsa',
                'ansible_host_key_checking': False,
                'ansible_os_family': os_family  # 동적으로 결정된 OS 계열
            }
        
        return inventory
    
    def get_host_vars(self, hostname: str) -> Dict[str, Any]:
        """특정 호스트의 변수 조회 (--host)"""
        servers = self.get_servers_from_db()
        
        for server in servers:
            if server['ip_address'] == hostname:
                # OS 타입에 따른 설정
                os_type = server.get('os_type', 'rocky')
                os_family = get_os_family(os_type)
                
                # OS별 기본 사용자명
                username_map = {
                    'rocky': 'rocky',
                    'centos': 'centos',
                    'rhel': 'rhel',
                    'ubuntu': 'ubuntu',
                    'debian': 'debian',
                    'alma': 'alma',
                    'fedora': 'fedora',
                    'suse': 'suse'
                }
                ansible_user = username_map.get(os_type, 'rocky')
                
                return {
                    'ansible_host': hostname,
                    'server_name': server['name'],
                    'server_role': server.get('role', 'none'),
                    'server_status': server['status'],
                    'ansible_user': ansible_user,
                    'ansible_ssh_private_key_file': '~/.ssh/id_rsa',
                    'ansible_host_key_checking': False,
                    'ansible_os_family': os_family  # 동적으로 결정된 OS 계열
                }
        
        return {}

def main():
    inventory = DynamicInventory()
    
    if len(sys.argv) == 2 and sys.argv[1] == '--list':
        # 전체 inventory 반환
        result = inventory.generate_inventory()
        print(json.dumps(result, indent=2))
    
    elif len(sys.argv) == 3 and sys.argv[1] == '--list':
        # 특정 서버만 대상으로 하는 inventory 반환
        target_server_ip = sys.argv[2]
        result = inventory.generate_inventory(target_server_ip)
        print(json.dumps(result, indent=2))
    
    elif len(sys.argv) == 3 and sys.argv[1] == '--host':
        # 특정 호스트 변수 반환
        hostname = sys.argv[2]
        result = inventory.get_host_vars(hostname)
        print(json.dumps(result, indent=2))
    
    else:
        print("Usage: python dynamic_inventory.py --list")
        print("       python dynamic_inventory.py --list <target_server_ip>")
        print("       python dynamic_inventory.py --host <hostname>")
        sys.exit(1)

if __name__ == '__main__':
    main()
