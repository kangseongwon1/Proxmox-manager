"""
Proxmox API 서비스
"""
import requests
import logging
import sqlite3
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification
from app.utils.os_classifier import classify_os_type
from app.utils.redis_utils import redis_utils
from app import db

logger = logging.getLogger(__name__)

# terraform.tfvars.json 파일 경로
TFVARS_PATH = 'terraform/terraform.tfvars.json'

class ProxmoxService:
    """Proxmox API 서비스"""
    
    def __init__(self):
        self.endpoint = current_app.config['PROXMOX_ENDPOINT']
        self.username = current_app.config['PROXMOX_USERNAME']
        self.password = current_app.config['PROXMOX_PASSWORD']
        self.node = current_app.config['PROXMOX_NODE']
        
        # requests session 초기화
        self.session = requests.Session()
        self.session.verify = False  # SSL 인증서 검증 비활성화
    
    def get_server_info(self, server_name: str) -> Optional[Dict[str, Any]]:
        """서버 정보 조회"""
        try:
            # VM ID로 서버 찾기
            server = Server.query.filter_by(name=server_name).first()
            if not server or not server.vmid:
                return None
            
            # Proxmox API로 VM 상태 조회
            url = f"{self.endpoint}/api2/json/nodes/{current_app.config['PROXMOX_NODE']}/qemu/{server.vmid}/status/current"
            response = requests.get(url, auth=(self.username, self.password), verify=False)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': data.get('data', {}).get('status', 'unknown'),
                    'vmid': server.vmid,
                    'name': server_name
                }
            return None
        except Exception as e:
            logger.error(f"서버 정보 조회 실패: {e}")
            return None
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Proxmox API 요청을 위한 공통 메서드"""
        try:
            # 인증 정보 가져오기
            headers, error = self.get_proxmox_auth()
            if error:
                logger.error(f"Proxmox 인증 실패: {error}")
                raise Exception(f"Proxmox 인증 실패: {error}")
            
            # 요청 실행
            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, timeout=10, **kwargs)
            elif method.upper() == 'POST':
                response = self.session.post(url, headers=headers, timeout=10, **kwargs)
            elif method.upper() == 'PUT':
                response = self.session.put(url, headers=headers, timeout=10, **kwargs)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, headers=headers, timeout=10, **kwargs)
            else:
                raise Exception(f"지원하지 않는 HTTP 메서드: {method}")
            
            return response
        except Exception as e:
            logger.error(f"Proxmox API 요청 실패: {e}")
            raise e

    def get_datastores(self) -> List[Dict[str, Any]]:
        """사용 가능한 datastore 목록 조회"""
        try:
            # Proxmox API로 datastore 목록 가져오기
            url = f"{self.endpoint}/api2/json/storage"
            print(f"🔧 Proxmox API 요청 URL: {url}")
            print(f"🔧 Proxmox 엔드포인트: {self.endpoint}")
            response = self._make_request('GET', url)
            
            if response.status_code == 200:
                datastores = response.json()['data']
                logger.info(f"🔧 Proxmox에서 {len(datastores)}개 datastore 발견")
                
                # 각 datastore의 상세 정보 가져오기
                detailed_datastores = []
                for datastore in datastores:
                    try:
                        # datastore 상세 정보 조회
                        detail_url = f"{self.endpoint}/api2/json/storage/{datastore['storage']}"
                        detail_response = self._make_request('GET', detail_url)
                        
                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()['data']
                            detailed_datastores.append({
                                'id': datastore['storage'],
                                'type': detail_data.get('type', 'unknown'),
                                'size': detail_data.get('size', 0),
                                'used': detail_data.get('used', 0),
                                'available': detail_data.get('available', 0),
                                'content': detail_data.get('content', ''),
                                'enabled': detail_data.get('enabled', True)
                            })
                            logger.info(f"🔧 Datastore {datastore['storage']} 상세 정보 조회 성공")
                        else:
                            logger.warning(f"Datastore {datastore['storage']} 상세 정보 조회 실패: {detail_response.status_code}")
                            # 기본 정보만 사용
                            detailed_datastores.append({
                                'id': datastore['storage'],
                                'type': 'unknown',
                                'size': 0,
                                'used': 0,
                                'available': 0,
                                'content': '',
                                'enabled': True
                            })
                    except Exception as e:
                        logger.warning(f"Datastore {datastore['storage']} 상세 정보 조회 실패: {e}")
                        # 기본 정보만 사용
                        detailed_datastores.append({
                            'id': datastore['storage'],
                            'type': 'unknown',
                            'size': 0,
                            'used': 0,
                            'available': 0,
                            'content': '',
                            'enabled': True
                        })
                
                logger.info(f"🔧 총 {len(detailed_datastores)}개 datastore 정보 수집 완료")
                return detailed_datastores
            else:
                logger.error(f"Datastore 목록 조회 실패: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Datastore 목록 조회 실패: {str(e)}")
            return []        
    
    def _get_db_connection(self):
        """데이터베이스 연결 (PostgreSQL)"""
        from app.main import db
        return db.session
    
    def get_proxmox_auth(self) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
        """Proxmox API 인증 정보 반환 (공통 함수)"""
        try:
            print(f"🔐 Proxmox 인증 시도: {self.endpoint}")
            auth_url = f"{self.endpoint}/api2/json/access/ticket"
            auth_data = {'username': self.username, 'password': self.password}
            
            auth_response = self.session.post(auth_url, data=auth_data, timeout=3)
            print(f"📡 인증 응답 상태: {auth_response.status_code}")
            
            if auth_response.status_code != 200:
                return None, 'Proxmox 인증 실패'
            
            auth_result = auth_response.json()
            print(f"🔑 인증 결과: {auth_result}")
            
            if 'data' not in auth_result:
                return None, '인증 토큰을 가져올 수 없습니다'
            
            ticket = auth_result['data']['ticket']
            csrf_token = auth_result['data']['CSRFPreventionToken']
            
            headers = {
                'Cookie': f'PVEAuthCookie={ticket}',
                'CSRFPreventionToken': csrf_token
            }
            
            print(f"✅ 인증 성공: {headers}")
            return headers, None
        except Exception as e:
            print(f"❌ Proxmox 인증 실패: {e}")
            return None, f'인증 중 예외 발생: {str(e)}'
    
    def get_proxmox_vms(self, headers: Dict[str, str]) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Proxmox에서 모든 VM 목록 조회 (공통 함수)"""
        try:
            print(f"🔍 VM 목록 조회 시작")
            
            # 모든 노드에서 VM 검색
            nodes_url = f"{self.endpoint}/api2/json/nodes"
            nodes_response = self.session.get(nodes_url, headers=headers, timeout=3)
            
            if nodes_response.status_code != 200:
                return None, '노드 정보를 가져올 수 없습니다'
            
            nodes = nodes_response.json().get('data', [])
            all_vms = []
            
            for node in nodes:
                node_name = node['node']
                vms_url = f"{self.endpoint}/api2/json/nodes/{node_name}/qemu"
                vms_response = self.session.get(vms_url, headers=headers, timeout=3)
                
                if vms_response.status_code == 200:
                    vms = vms_response.json().get('data', [])
                    for vm in vms:
                        vm['node'] = node_name
                    all_vms.extend(vms)
            
            print(f"📋 총 VM 수: {len(all_vms)}")
            return all_vms, None
        except Exception as e:
            print(f"❌ VM 목록 조회 실패: {e}")
            return None, f'VM 목록 조회 중 예외 발생: {str(e)}'
    
    def read_servers_from_tfvars(self):
        """terraform.tfvars.json에서 서버 정보 읽기"""
        try:
            with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
                obj = json.load(f)
                return obj.get('servers', {})
        except FileNotFoundError:
            print(f"⚠️ terraform.tfvars.json 파일이 존재하지 않습니다: {TFVARS_PATH}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ terraform.tfvars.json 파일 파싱 오류: {e}")
            return {}
        except Exception as e:
            print(f"❌ terraform.tfvars.json 파일 읽기 오류: {e}")
            return {}
    
    def get_all_vms(self) -> Dict[str, Any]:
        """모든 VM 정보 조회 (API 호환)"""
        try:
            print(f"🔍 get_all_vms 시작")
            
            # Proxmox 인증
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return {
                    'success': False,
                    'message': error,
                    'data': {
                        'vms': [],
                        'total': 0,
                        'running': 0,
                        'stopped': 0
                    }
                }
            
            # Proxmox 노드 정보 조회 (전체 리소스 확인)
            node_url = f"{self.endpoint}/api2/json/nodes/{self.node}/status"
            node_response = self.session.get(node_url, headers=headers, verify=False, timeout=3)
            
            if node_response.status_code != 200:
                print(f"❌ 노드 정보 조회 실패: {node_response.status_code}")
                return {
                    'success': False,
                    'message': '노드 정보를 가져올 수 없습니다',
                    'data': {
                        'vms': [],
                        'total': 0,
                        'running': 0,
                        'stopped': 0
                    }
                }
            
            node_data = node_response.json()['data']
            print(f"📊 노드 데이터: {node_data}")
            
            node_cpu_count = node_data.get('cpuinfo', {}).get('cpus', 0)
            node_memory_total = node_data.get('memory', {}).get('total', 0)
            node_memory_used = node_data.get('memory', {}).get('used', 0)
            
            # Proxmox에서 VM 목록 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return {
                    'success': False,
                    'message': error,
                    'data': {
                        'vms': [],
                        'total': 0,
                        'running': 0,
                        'stopped': 0
                    }
                }
            
            # terraform.tfvars.json에 있는 서버만 필터링
            servers = self.read_servers_from_tfvars()
            print(f"📋 tfvars 서버 수: {len(servers)}")
            
            all_servers = {}
            vm_total_cpu = 0
            vm_total_memory = 0
            vm_used_cpu = 0
            vm_used_memory = 0
            running_count = 0
            stopped_count = 0
            
            for vm in vms:
                if vm['name'] in servers:
                    server_data = servers[vm['name']]
                    print(f"🔍 VM 처리: {vm['name']}")
                    
                    # IP 정보 추출 (network_devices 또는 ip_addresses)
                    ip_list = []
                    if 'network_devices' in server_data and server_data['network_devices']:
                        ip_list = [nd.get('ip_address') for nd in server_data['network_devices'] if nd.get('ip_address')]
                    elif 'ip_addresses' in server_data and server_data['ip_addresses']:
                        ip_list = server_data['ip_addresses']
                    
                    # CPU 정보 추출 (tfvars에서 가져오거나 기본값 사용)
                    vm_cpu = server_data.get('cpu', 1)
                    
                    # DB에서 역할 및 방화벽 그룹 정보 가져오기
                    firewall_group = None
                    db_role = None
                    try:
                        with self._get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('SELECT role, firewall_group FROM servers WHERE name = ?', (vm['name'],))
                            db_server = cursor.fetchone()
                            if db_server:
                                db_role = db_server['role']
                                firewall_group = db_server['firewall_group']
                                print(f"🔍 DB에서 {vm['name']} 역할 조회: {db_role} (타입: {type(db_role)})")
                    except Exception as e:
                        print(f"⚠️ DB 조회 실패: {e}")
                    
                    # 역할 정보 우선순위: DB > tfvars > 기본값
                    # DB에서 None이면 빈 문자열로 처리 (역할 없음)
                    final_role = db_role if db_role is not None else server_data.get('role', '')
                    
                    # 할당된 리소스 정보만 사용 (실시간 사용률 제거)
                    cpu_usage = 0.0  # 할당된 CPU 코어 수만 표시
                    memory_usage = 0.0  # 할당된 메모리 크기만 표시
                    disk_usage = 0.0  # 할당된 디스크 크기만 표시
                    
                    # 디스크 정보 조회
                    disks = []
                    total_disk_gb = 0
                    try:
                        # VM 설정에서 디스크 정보 가져오기
                        vm_config_url = f"{self.endpoint}/api2/json/nodes/{vm['node']}/qemu/{vm['vmid']}/config"
                        vm_config_response = self.session.get(vm_config_url, headers=headers, verify=False, timeout=5)
                        
                        if vm_config_response.status_code == 200:
                            vm_config = vm_config_response.json().get('data', {})
                            
                            for key, value in vm_config.items():
                                if key.startswith('scsi') or key.startswith('sata') or key.startswith('virtio'):
                                    if key == 'scsihw':
                                        continue
                                    
                                    size_gb = 0
                                    storage = 'unknown'
                                    
                                    # 스토리지 추출
                                    if ':' in value:
                                        storage = value.split(':')[0]
                                    
                                    # 패턴 1: size= 파라미터 (예: size=10G, size=10737418240)
                                    if 'size=' in value:
                                        size_match = value.split('size=')[1].split(',')[0]
                                        try:
                                            if size_match.endswith('G'):
                                                size_gb = int(size_match[:-1])
                                            else:
                                                size_bytes = int(size_match)
                                                size_gb = size_bytes // (1024 * 1024 * 1024)
                                        except ValueError:
                                            pass
                                    
                                    disk_info = {
                                        'device': key,
                                        'size_gb': size_gb,
                                        'storage': storage
                                    }
                                    disks.append(disk_info)
                                    total_disk_gb += size_gb
                    except Exception as e:
                        print(f"⚠️ {vm['name']} 디스크 정보 조회 실패: {e}")
                    
                    status_info = {
                        'name': vm['name'],
                        'status': vm['status'],
                        'vmid': vm['vmid'],
                        'node': vm['node'],
                        'cpu': vm.get('cpu', 0),
                        'memory': vm.get('mem', 0),
                        'maxmem': vm.get('maxmem', 0),
                        'uptime': vm.get('uptime', 0),
                        'disk': vm.get('disk', 0),
                        'maxdisk': vm.get('maxdisk', 0),
                        'role': final_role,
                        'firewall_group': firewall_group,
                        'ip_addresses': ip_list,
                        'vm_cpu': vm_cpu,  # tfvars에서 가져온 CPU 코어 수
                        'cpu_usage_percent': cpu_usage,
                        'memory_usage_percent': memory_usage,
                        'disk_usage_percent': disk_usage,
                        'total_disk_gb': total_disk_gb,  # 모든 디스크의 총합
                        'disks': disks  # 개별 디스크 정보
                    }
                    all_servers[vm['name']] = status_info
                    
                    # VM 통계 계산
                    if vm['status'] == 'running':
                        running_count += 1
                        vm_total_memory += vm.get('maxmem', 0)
                        vm_used_memory += vm.get('mem', 0)  # 현재 사용 중인 메모리
                        vm_total_cpu += vm_cpu
                        vm_used_cpu += vm_cpu  # 실행 중인 서버는 CPU를 모두 사용 중
                    else:
                        stopped_count += 1
                        vm_total_memory += vm.get('maxmem', 0)
                        vm_total_cpu += vm_cpu
                        # 중지된 서버는 CPU/메모리 사용량 0
            
            # 노드 기준 통계 정보 추가
            stats = {
                'total_servers': len(all_servers),
                'running_servers': running_count,
                'stopped_servers': stopped_count,
                # 노드 전체 리소스
                'node_total_cpu': node_cpu_count,
                'node_total_memory_gb': round(node_memory_total / (1024 * 1024 * 1024), 1),
                'node_used_memory_gb': round(node_memory_used / (1024 * 1024 * 1024), 1),
                # VM 할당된 리소스
                'vm_total_cpu': vm_total_cpu,
                'vm_total_memory_gb': round(vm_total_memory / (1024 * 1024 * 1024), 1),
                'vm_used_cpu': vm_used_cpu,
                'vm_used_memory_gb': round(vm_used_memory / (1024 * 1024 * 1024), 1),
                # 사용률 계산
                'cpu_usage_percent': round((vm_used_cpu / node_cpu_count * 100) if node_cpu_count > 0 else 0, 1),
                'memory_usage_percent': round((vm_used_memory / node_memory_total * 100) if node_memory_total > 0 else 0, 1),
                'cpu_allocation_percent': round((vm_total_cpu / node_cpu_count * 100) if node_cpu_count > 0 else 0, 1),
                'memory_allocation_percent': round((vm_total_memory / node_memory_total * 100) if node_memory_total > 0 else 0, 1)
            }
            
            result = {
                'success': True,
                'data': {
                    'servers': all_servers,
                    'stats': stats
                }
            }
            print(f"✅ get_all_vms 완료: {result}")
            return result
                
        except Exception as e:
            print(f"❌ get_all_vms 실패: {e}")
            return {
                'success': False,
                'message': str(e),
                'data': {
                    'vms': [],
                    'total': 0,
                    'running': 0,
                    'stopped': 0
                }
            }

    def get_storage_info(self) -> Dict[str, Any]:
        """스토리지 정보 조회 (API 호환, Redis 캐싱 적용)"""
        try:
            # Redis 캐시 확인
            cache_key = "proxmox:storage_info"
            cached_data = redis_utils.get_cache(cache_key)
            if cached_data:
                logger.info("📦 Redis 캐시에서 스토리지 데이터 로드")
                return cached_data
            
            logger.info("🌐 Proxmox API에서 스토리지 데이터 조회")
            print(f"🔍 get_storage_info 시작")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return {
                    'success': False,
                    'message': error,
                    'data': []
                }
            
            url = f"{self.endpoint}/api2/json/nodes/{self.node}/storage"
            
            print(f"🌐 스토리지 API URL: {url}")
            response = self.session.get(url, headers=headers, timeout=3)
            print(f"📡 스토리지 API 응답 상태: {response.status_code}")
            
            response.raise_for_status()
            
            storage_data = response.json()
            print(f"📋 스토리지 데이터: {storage_data}")
            
            storage_list = storage_data['data']
            print(f"📋 스토리지 수: {len(storage_list)}")
            
            processed_storage = []
            for storage in storage_list:
                storage_info = {
                    'storage': storage.get('storage'),
                    'type': storage.get('type', 'unknown'),
                    'content': storage.get('content', []),
                    'shared': storage.get('shared', False),
                    'active': storage.get('active', False),
                    'avail': storage.get('avail', 0),
                    'total': storage.get('total', 0),
                    'used': storage.get('used', 0)
                }
                processed_storage.append(storage_info)
            
            result = {
                'success': True,
                'data': processed_storage
            }
            
            # Redis에 캐시 저장 (10분)
            redis_utils.set_cache(cache_key, result, expire=600)
            logger.info("💾 스토리지 데이터를 Redis에 캐시 저장")
            
            print(f"✅ get_storage_info 완료: {result}")
            return result
                
        except Exception as e:
            print(f"❌ get_storage_info 실패: {e}")
            return {
                'success': False,
                'message': str(e),
                'data': []
            }

    def start_vm(self, server_name: str) -> Dict[str, Any]:
        """VM 시작 (API 호환)"""
        try:
            # 서버명으로 VM ID 찾기
            vm_list = self.get_vm_list()
            target_vm = None
            
            for vm in vm_list:
                if vm.get('name') == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {
                    'success': False,
                    'message': f'서버 {server_name}을(를) 찾을 수 없습니다.'
                }
            
            vmid = target_vm['vmid']
            if self.vm_action(vmid, 'start'):
                return {
                    'success': True,
                    'message': f'서버 {server_name}이(가) 시작되었습니다.'
                }
            else:
                return {
                    'success': False,
                    'message': f'서버 {server_name} 시작에 실패했습니다.'
                }
                
        except Exception as e:
            logger.error(f"VM 시작 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def stop_vm(self, server_name: str) -> Dict[str, Any]:
        """VM 중지 (API 호환)"""
        try:
            # 서버명으로 VM ID 찾기
            vm_list = self.get_vm_list()
            target_vm = None
            
            for vm in vm_list:
                if vm.get('name') == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {
                    'success': False,
                    'message': f'서버 {server_name}을(를) 찾을 수 없습니다.'
                }
            
            vmid = target_vm['vmid']
            if self.vm_action(vmid, 'stop'):
                return {
                    'success': True,
                    'message': f'서버 {server_name}이(가) 중지되었습니다.'
                }
            else:
                return {
                    'success': False,
                    'message': f'서버 {server_name} 중지에 실패했습니다.'
                }
                
        except Exception as e:
            logger.error(f"VM 중지 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def reboot_vm(self, server_name: str) -> Dict[str, Any]:
        """VM 재부팅 (API 호환)"""
        try:
            print(f"🔧 VM 재부팅 시작: {server_name}")
            # 서버명으로 VM ID 찾기
            vm_list = self.get_vm_list()
            target_vm = None
            
            for vm in vm_list:
                if vm.get('name') == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                print(f"❌ VM을 찾을 수 없음: {server_name}")
                return {
                    'success': False,
                    'message': f'서버 {server_name}을(를) 찾을 수 없습니다.'
                }
            
            vmid = target_vm['vmid']
            print(f"🔧 VM 액션 호출: {vmid} - reset")
            if self.vm_action(vmid, 'reset'):
                print(f"✅ VM 재부팅 성공: {server_name}")
                return {
                    'success': True,
                    'message': f'서버 {server_name}이(가) 재부팅되었습니다.'
                }
            else:
                print(f"❌ VM 재부팅 실패: {server_name}")
                return {
                    'success': False,
                    'message': f'서버 {server_name} 재부팅에 실패했습니다.'
                }
                
        except Exception as e:
            print(f"❌ VM 재부팅 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def check_vm_exists(self, name: str) -> bool:
        """VM 존재 여부 확인"""
        try:
            headers, error = self.get_proxmox_auth()
            if error:
                return False
            
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return False
            
            return any(vm['name'] == name for vm in vms)
        except Exception as e:
            print(f"❌ VM 존재 확인 실패: {e}")
            return False

    def get_vm_info(self, name: str) -> Optional[Dict[str, Any]]:
        """특정 VM의 상세 정보 조회"""
        try:
            print(f"🔍 VM 정보 조회: {name}")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return None
            
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return None
            
            # 특정 VM 찾기
            for vm in vms:
                if vm['name'] == name:
                    print(f"✅ VM 정보 찾음: {name} - {vm.get('status', 'unknown')}")
                    return vm
            
            print(f"❌ VM을 찾을 수 없음: {name}")
            return None
        except Exception as e:
            print(f"❌ VM 정보 조회 실패: {e}")
            return None

    def get_vm_by_name(self, vm_name: str) -> Optional[Dict[str, Any]]:
        """이름으로 VM 정보 조회"""
        try:
            print(f"🔍 VM 정보 조회: {vm_name}")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return None
            
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return None
            
            # 이름으로 VM 찾기
            for vm in vms:
                if vm.get('name') == vm_name:
                    print(f"✅ VM 발견: {vm_name} (ID: {vm.get('vmid')})")
                    return vm
            
            print(f"❌ VM을 찾을 수 없음: {vm_name}")
            return None
        except Exception as e:
            print(f"❌ VM 정보 조회 실패: {e}")
            return None





    def get_vm_list(self) -> List[Dict[str, Any]]:
        """VM 목록 조회 (API 호환)"""
        try:
            print("🔍 VM 목록 조회 (API 호환)")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return []
            
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return []
            
            # 각 VM의 상세 정보 가져오기
            detailed_vms = []
            for vm in vms:
                try:
                    node = vm.get('node', self.node)
                    vmid = vm.get('vmid')
                    
                    # VM 상세 정보 조회
                    vm_detail_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/status/current"
                    detail_response = self.session.get(vm_detail_url, headers=headers, timeout=3)
                    
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json().get('data', {})
                        
                        # 상세 정보와 기본 정보 병합
                        vm.update({
                            'cpu': detail_data.get('cpu', 0),
                            'memory': detail_data.get('memory', 0),
                            'maxmem': detail_data.get('maxmem', 0),
                            'cpus': detail_data.get('cpus', 0),
                            'network_devices': detail_data.get('netin', []),  # 네트워크 정보
                            'ip_addresses': self._extract_ip_addresses(detail_data)
                        })
                    
                    detailed_vms.append(vm)
                except Exception as e:
                    print(f"⚠️ VM 상세 정보 조회 실패 ({vm.get('name', 'unknown')}): {e}")
                    detailed_vms.append(vm)  # 기본 정보라도 포함
            
            print(f"✅ VM 목록 조회 완료: {len(detailed_vms)}개")
            return detailed_vms
        except Exception as e:
            print(f"❌ VM 목록 조회 실패: {e}")
            return []

    def _extract_ip_addresses(self, vm_data: Dict[str, Any]) -> List[str]:
        """VM 데이터에서 IP 주소 추출"""
        ip_addresses = []
        try:
            # 네트워크 인터페이스에서 IP 주소 추출
            for key, value in vm_data.items():
                if key.startswith('net') and isinstance(value, str):
                    # net0, net1 등의 네트워크 인터페이스에서 IP 추출
                    if 'ip=' in value:
                        ip_parts = value.split('ip=')
                        if len(ip_parts) > 1:
                            ip_part = ip_parts[1].split(',')[0]
                            if ip_part and ip_part != 'dhcp':
                                ip_addresses.append(ip_part)
        except Exception as e:
            print(f"⚠️ IP 주소 추출 실패: {e}")
        
        return ip_addresses

    def vm_action(self, vmid: int, action: str) -> bool:
        """VM 액션 수행 (시작/중지/재부팅)"""
        try:
            print(f"🔧 VM 액션 수행: {vmid} - {action}")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # VM 정보 조회로 노드 확인
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return False
            
            target_vm = None
            for vm in vms:
                if vm.get('vmid') == vmid:
                    target_vm = vm
                    break
            
            if not target_vm:
                print(f"❌ VM을 찾을 수 없음: {vmid}")
                return False
            
            node = target_vm.get('node', self.node)
            
            # 액션 URL 구성
            action_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/status/{action}"
            
            # 액션 수행
            response = self.session.post(action_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ VM 액션 성공: {vmid} - {action}")
                return True
            else:
                print(f"❌ VM 액션 실패: {vmid} - {action} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ VM 액션 실패: {e}")
            return False

    def start_server(self, server_name: str) -> Dict[str, Any]:
        """서버 시작 (API 호환)"""
        try:
            print(f"🔧 서버 시작: {server_name}")
            return self.start_vm(server_name)
        except Exception as e:
            print(f"❌ 서버 시작 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def stop_server(self, server_name: str) -> Dict[str, Any]:
        """서버 중지 (API 호환)"""
        try:
            print(f"🔧 서버 중지: {server_name}")
            return self.stop_vm(server_name)
        except Exception as e:
            print(f"❌ 서버 중지 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def reboot_server(self, server_name: str) -> Dict[str, Any]:
        """서버 재부팅 (API 호환)"""
        try:
            print(f"🔧 서버 재부팅: {server_name}")
            return self.reboot_vm(server_name)
        except Exception as e:
            print(f"❌ 서버 재부팅 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def wait_for_vm_status(self, vmid: int, target_status: str, timeout: int = 300) -> bool:
        """VM 상태 대기"""
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            vm_info = self.get_vm_info(vmid)
            if vm_info and vm_info.get('status') == target_status:
                return True
            time.sleep(5)
        
        return False
    
    def get_firewall_groups(self) -> List[Dict[str, Any]]:
        """Proxmox Datacenter Security Group 목록 조회"""
        try:
            print("🔍 Proxmox Datacenter Security Group 목록 조회")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return []
            
            # Proxmox Datacenter Security Group API 호출
            firewall_url = f"{self.endpoint}/api2/json/cluster/firewall/groups"
            response = self.session.get(firewall_url, headers=headers, timeout=10)
            
            print(f"🔍 Datacenter Security Group API 호출: {firewall_url}")
            print(f"🔍 응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                firewall_data = response.json().get('data', {})
                groups = []
                
                print(f"🔍 Proxmox 응답 데이터: {firewall_data}")
                
                                # Security Group 데이터 파싱
                if isinstance(firewall_data, list):
                    print("🔍 응답이 리스트 형태입니다. 리스트 파싱 시작")
                    for group_item in firewall_data:
                        print(f"🔍 그룹 아이템: {group_item}")
                        if isinstance(group_item, dict) and 'group' in group_item:
                            group_name = group_item['group']
                            group_comment = group_item.get('comment', f'{group_name} Security Group')
                            
                            groups.append({
                                'name': group_name,
                                'description': group_comment,
                                'instance_count': 0,  # 규칙 수는 별도 API로 조회 필요
                                'rules': []
                            })
                            print(f"✅ 그룹 '{group_name}' 파싱 완료")
                elif isinstance(firewall_data, dict):
                    print("🔍 응답이 딕셔너리 형태입니다. 딕셔너리 파싱 시작")
                    for group_name, group_info in firewall_data.items():
                        # 각 그룹의 규칙 수 계산
                        rules_count = len(group_info.get('rules', []))
                        
                        groups.append({
                            'name': group_name,
                            'description': group_info.get('comment', f'{group_name} Security Group'),
                            'instance_count': rules_count,
                            'rules': group_info.get('rules', [])
                        })
                else:
                    print(f"⚠️ 예상치 못한 응답 형태: {type(firewall_data)}")
                
                print(f"✅ Datacenter Security Group 조회 완료: {len(groups)}개")
                return groups
                
            elif response.status_code == 501:
                print("⚠️ Datacenter Security Group API가 지원되지 않음 (501)")
            else:
                print(f"❌ Datacenter Security Group 조회 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                
        except Exception as e:
            print(f"❌ Datacenter Security Group 조회 실패: {e}")

    def get_firewall_group_detail(self, group_name: str) -> Dict[str, Any]:
        """Proxmox Datacenter Security Group 상세 정보 조회"""
        try:
            print(f"🔍 Datacenter Security Group '{group_name}' 상세 정보 조회")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return {}
            
            # Security Group 정보 조회 (이미 Rules가 포함되어 있음)
            group_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{group_name}"
            response = self.session.get(group_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                group_data = response.json().get('data', [])
                
                # group_data는 이미 Rules 배열임
                rules = group_data if isinstance(group_data, list) else []
                
                # Security Group 목록에서 comment 정보 가져오기
                groups_url = f"{self.endpoint}/api2/json/cluster/firewall/groups"
                groups_response = self.session.get(groups_url, headers=headers, timeout=10)
                
                description = f'{group_name} Security Group'
                if groups_response.status_code == 200:
                    groups = groups_response.json().get('data', [])
                    for group in groups:
                        if group.get('group') == group_name:
                            description = group.get('comment', description)
                            break
                
                group_detail = {
                    'name': group_name,
                    'description': description,
                    'rules': rules,
                    'group_info': {
                        'comment': description,
                        'rules_count': len(rules)
                    }
                }
                
                print(f"✅ Datacenter Security Group '{group_name}' 상세 조회 완료: {len(rules)}개 규칙")
                return group_detail
            else:
                print(f"❌ Datacenter Security Group '{group_name}' 상세 조회 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                return {}
                
        except Exception as e:
            print(f"❌ Datacenter Security Group '{group_name}' 상세 조회 실패: {e}")
            return {}

    def create_firewall_group(self, group_name: str, description: str = '') -> bool:
        """Proxmox Datacenter Security Group 생성"""
        try:
            print(f"🔍 Datacenter Security Group '{group_name}' 생성 시도")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # Proxmox Datacenter Security Group 생성 API
            firewall_url = f"{self.endpoint}/api2/json/cluster/firewall/groups"
            # Proxmox API는 그룹 생성 시 'group'과 'comment'만 허용
            payload = {
                'group': group_name,
                'comment': description
            }
            
            print(f"🔍 Datacenter Security Group 생성 API 호출: {firewall_url}")
            print(f"🔍 Payload: {payload}")
            
            response = self.session.post(firewall_url, headers=headers, data=payload, timeout=10)
            created_ok = False
            if response.status_code in [200, 201]:
                print(f"✅ Datacenter Security Group '{group_name}' 생성 성공")
                created_ok = True
            elif response.status_code == 409:
                print(f"⚠️ 그룹 '{group_name}' 이미 존재 → 멱등 처리")
                created_ok = True
            else:
                print(f"❌ Datacenter Security Group '{group_name}' 생성 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                return False

            # 생성(또는 이미 존재) 후 enable=1로 활성화
            try:
                from urllib.parse import quote
                encoded_group = quote(group_name, safe='')
                enable_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{encoded_group}"
                enable_payload = {'enable': '1'}
                put_resp = self.session.put(enable_url, headers=headers, data=enable_payload, timeout=10)
                if put_resp.status_code in [200, 201]:
                    print(f"✅ Security Group '{group_name}' 활성화(enable=1) 완료")
                    return True
                else:
                    print(f"⚠️ Security Group 활성화 실패: status={put_resp.status_code} resp={put_resp.text}")
                    # 일부 버전에서는 그룹 레벨 enable이 없을 수 있어 실패해도 생성 자체는 성공으로 본다
                    return created_ok
            except Exception as en_err:
                print(f"⚠️ Security Group 활성화 중 예외: {en_err}")
                return created_ok
                
        except Exception as e:
            print(f"❌ Datacenter Security Group '{group_name}' 생성 실패: {e}")
            return False

    def add_firewall_rule(self, group_name: str, rule_data: Dict[str, Any]) -> bool:
        """Datacenter Security Group에 규칙 추가"""
        try:
            print(f"🔍 Datacenter Security Group '{group_name}'에 규칙 추가")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # Security Group에 규칙 추가 (올바른 API 엔드포인트)
            rules_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{group_name}"
            
            # Proxmox API 형식에 맞게 규칙 데이터 변환
            payload = {
                'type': 'in',  # 기본값: 인바운드
                'action': rule_data.get('action', 'ACCEPT'),
                'proto': rule_data.get('protocol', 'tcp'),
                'dport': rule_data.get('port', ''),
                'source': rule_data.get('source_ip', ''),
                'dest': rule_data.get('dest_ip', ''),
                'comment': rule_data.get('description', ''),
                'enable': '1'  # 규칙 기본 활성화
            }
            
            # 매크로 정보가 있으면 추가
            macro = rule_data.get('macro')
            if macro:
                payload['macro'] = macro
                print(f"🔍 매크로 추가: {macro}")
            
            print(f"🔍 Security Group 규칙 추가 API 호출: {rules_url}")
            print(f"🔍 원본 데이터: {rule_data}")
            print(f"🔍 변환된 Payload: {payload}")
            
            response = self.session.post(rules_url, headers=headers, data=payload, timeout=10)
            
            print(f"🔍 API 응답 상태: {response.status_code}")
            print(f"🔍 API 응답 내용: {response.text}")
            
            if response.status_code in [200, 201]:
                print(f"✅ Security Group '{group_name}'에 규칙 추가 성공")
                return True
            else:
                print(f"❌ Security Group '{group_name}'에 규칙 추가 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Security Group '{group_name}'에 규칙 추가 실패: {e}")
            return False

    def delete_firewall_rule(self, group_name: str, rule_id: int) -> bool:
        """Datacenter Security Group에서 규칙 삭제 (대안 방법)"""
        try:
            print(f"🔍 Datacenter Security Group '{group_name}'에서 규칙 {rule_id} 삭제")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # 먼저 현재 규칙 목록을 가져와서 올바른 규칙 ID 확인
            rules_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{group_name}"
            print(f"🔍 규칙 목록 조회: {rules_url}")
            
            rules_response = self.session.get(rules_url, headers=headers, timeout=10)
            if rules_response.status_code != 200:
                print(f"❌ 규칙 목록 조회 실패: {rules_response.status_code}")
                return False
            
            rules_data = rules_response.json()
            print(f"🔍 현재 규칙 목록: {rules_data}")
            
            # 규칙 목록에서 해당 규칙 찾기
            rules = rules_data.get('data', [])
            target_rule = None
            
            for rule in rules:
                if rule.get('pos') == rule_id or rule.get('id') == rule_id:
                    target_rule = rule
                    break
            
            if not target_rule:
                print(f"❌ 규칙 ID {rule_id}를 찾을 수 없습니다.")
                return False
            
            # 실제 규칙 위치(pos) 사용
            actual_pos = target_rule.get('pos')
            print(f"🔍 실제 규칙 위치: {actual_pos}")
            
            # 방법 1: 올바른 API 엔드포인트로 DELETE 요청 시도 (규칙 삭제)
            rule_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{group_name}/{actual_pos}"
            
            print(f"🔍 규칙 삭제 시도 (올바른 엔드포인트): {rule_url}")
            delete_response = self.session.delete(rule_url, headers=headers, timeout=10)
            
            print(f"🔍 DELETE 요청 응답 상태: {delete_response.status_code}")
            print(f"🔍 DELETE 요청 응답 내용: {delete_response.text}")
            
            if delete_response.status_code in [200, 204]:
                print(f"✅ Datacenter Security Group '{group_name}'에서 규칙 {rule_id} 삭제 성공")
                return True
            
            # 방법 2: PUT 요청으로 규칙을 비활성화 시도 (대안)
            print(f"🔍 DELETE 실패, 규칙 비활성화 시도: {rule_url}")
            
            # 규칙을 비활성화하는 방법 (enable=0)
            disable_payload = {'enable': '0'}
            response = self.session.put(rule_url, headers=headers, data=disable_payload, timeout=10)
            
            print(f"🔍 PUT 요청 응답 상태: {response.status_code}")
            print(f"🔍 PUT 요청 응답 내용: {response.text}")
            
            if response.status_code in [200, 204]:
                print(f"✅ Datacenter Security Group '{group_name}'에서 규칙 {rule_id} 비활성화 성공 (삭제 대신)")
                return True
            
            print(f"🔍 DELETE 요청 응답 상태: {delete_response.status_code}")
            print(f"🔍 DELETE 요청 응답 내용: {delete_response.text}")
            
            if delete_response.status_code in [200, 204]:
                print(f"✅ Datacenter Security Group '{group_name}'에서 규칙 {rule_id} 삭제 성공")
                return True
            
            # 방법 3: Security Group을 삭제하고 다시 생성 (Proxmox API 제한으로 인한 대안)
            print("🔍 Proxmox API 제한으로 인해 Security Group 재생성 방법 사용")
            
            # 현재 모든 규칙을 저장 (삭제할 규칙 제외)
            remaining_rules = [rule for rule in rules if rule.get('pos') != actual_pos]
            print(f"🔍 남은 규칙들: {remaining_rules}")
            
            # Security Group 삭제
            group_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{group_name}"
            delete_group_response = self.session.delete(group_url, headers=headers, timeout=10)
            
            if delete_group_response.status_code in [200, 204]:
                print(f"✅ Security Group '{group_name}' 삭제 성공")
                
                # Security Group 다시 생성
                create_group_response = self.session.post(group_url, headers=headers, timeout=10)
                
                if create_group_response.status_code in [200, 201]:
                    print(f"✅ Security Group '{group_name}' 재생성 성공")
                    
                    # 남은 규칙들을 다시 추가
                    for rule in remaining_rules:
                        rule_payload = {
                            'type': rule.get('type', 'in'),
                            'action': rule.get('action', 'ACCEPT'),
                            'proto': rule.get('proto', 'tcp'),
                            'dport': rule.get('dport', ''),
                            'source': rule.get('source', ''),
                            'dest': rule.get('dest', ''),
                            'comment': rule.get('comment', '')
                        }
                        
                        # 매크로 정보가 있으면 추가
                        if rule.get('macro'):
                            rule_payload['macro'] = rule.get('macro')
                        
                        add_rule_response = self.session.post(group_url, headers=headers, data=rule_payload, timeout=10)
                        if add_rule_response.status_code not in [200, 201]:
                            print(f"⚠️ 규칙 재추가 실패: {rule}")
                        else:
                            print(f"✅ 규칙 재추가 성공: {rule.get('comment', 'Unknown')}")
                    
                    print(f"✅ Datacenter Security Group '{group_name}'에서 규칙 {rule_id} 삭제 완료 (재생성 방법)")
                    return True
                else:
                    print(f"❌ Security Group 재생성 실패: {create_group_response.status_code}")
            else:
                print(f"❌ Security Group 삭제 실패: {delete_group_response.status_code}")
            
            print(f"❌ 규칙 삭제 실패: Proxmox API 제한")
            return False
                
        except Exception as e:
            print(f"❌ Datacenter Security Group '{group_name}'에서 규칙 {rule_id} 삭제 실패: {e}")
            return False

    def delete_firewall_group(self, group_name: str) -> bool:
        """Datacenter Security Group 삭제"""
        try:
            print(f"🔍 Datacenter Security Group '{group_name}' 삭제")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # Datacenter Security Group 삭제 API (그룹명 URL 인코딩)
            from urllib.parse import quote
            encoded_group = quote(group_name, safe='')
            group_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{encoded_group}"
            
            print(f"🔍 Datacenter Security Group 삭제 API 호출: {group_url}")
            
            response = self.session.delete(group_url, headers=headers, timeout=10)
            if response.status_code in [200, 204]:
                print(f"✅ 1차 삭제 성공 응답 수신: {response.status_code}")
                # 실제로 사라졌는지 확인
                try:
                    groups = self.get_firewall_groups() or []
                    exists = any(g.get('name') == group_name for g in groups)
                    if not exists:
                        print(f"✅ Datacenter Security Group '{group_name}' 실제 삭제 확인")
                        return True
                    else:
                        print(f"⚠️ 삭제 응답은 성공이나 그룹이 여전히 존재: {group_name} → 규칙 제거 후 재시도")
                except Exception as chk_err:
                    print(f"⚠️ 삭제 확인 중 오류: {chk_err}")
            else:
                print(f"❌ Datacenter Security Group '{group_name}' 삭제 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                # 계속하여 규칙 제거 후 재시도

            # 대안 절차: 그룹 내 규칙 전체 삭제 후 그룹 삭제 재시도
            try:
                rules_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{encoded_group}"
                print(f"🔍 그룹 규칙 조회: {rules_url}")
                rules_resp = self.session.get(rules_url, headers=headers, timeout=10)
                rules = rules_resp.json().get('data', []) if rules_resp.status_code == 200 else []
                for rule in rules:
                    pos = rule.get('pos')
                    if pos is None:
                        continue
                    delete_rule_url = f"{rules_url}/{pos}"
                    dr = self.session.delete(delete_rule_url, headers=headers, timeout=10)
                    if dr.status_code in [200, 204]:
                        print(f"✅ 규칙 삭제: pos={pos}")
                    else:
                        print(f"⚠️ 규칙 삭제 실패: pos={pos} status={dr.status_code} resp={dr.text}")
            except Exception as rule_err:
                print(f"⚠️ 규칙 일괄 삭제 중 오류: {rule_err}")

            # 그룹 삭제 재시도
            retry_resp = self.session.delete(group_url, headers=headers, timeout=10)
            if retry_resp.status_code in [200, 204]:
                try:
                    groups = self.get_firewall_groups() or []
                    exists = any(g.get('name') == group_name for g in groups)
                    if not exists:
                        print(f"✅ Datacenter Security Group '{group_name}' 삭제 완료(재시도)")
                        return True
                except Exception:
                    pass
                print(f"⚠️ 재시도 응답은 성공이나 삭제 확인 실패")
                return True
            else:
                print(f"❌ 그룹 삭제 재시도 실패: status={retry_resp.status_code} resp={retry_resp.text}")
                return False
                
        except Exception as e:
            print(f"❌ Datacenter Security Group '{group_name}' 삭제 실패: {e}")
            return False

    def apply_security_group_to_vm(self, vm_name: str, group_name: str) -> bool:
        """VM에 Security Group 할당 (올바른 구현)"""
        try:
            print(f"🔍 VM '{vm_name}'에 Security Group '{group_name}' 할당 시작")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # VM 정보 조회
            vm_info = self.get_vm_info(vm_name)
            if not vm_info:
                print(f"❌ VM '{vm_name}'을 찾을 수 없습니다.")
                return False
            
            vmid = vm_info.get('vmid')
            node = vm_info.get('node', self.node)
            
            print(f"🔍 VM 정보: vmid={vmid}, node={node}")
            
            # 1단계: Security Group이 존재하는지 확인
            print("🔧 1단계: Security Group 존재 확인")
            group_exists = self._check_security_group_exists(group_name, headers)
            if not group_exists:
                print(f"❌ Security Group '{group_name}'이 존재하지 않습니다.")
                return False
            
            # 2단계: VM의 모든 네트워크 디바이스에 Firewall 설정을 0→1로 변경
            print("🔧 2단계: 네트워크 디바이스 Firewall 설정 활성화")
            firewall_enabled = self._enable_vm_firewall(node, vmid, headers)
            if not firewall_enabled:
                print("⚠️ Firewall 설정 활성화 실패, 계속 진행")
            # 2-1단계: VM Firewall 전역 옵션 enable=1 설정
            print("🔧 2-1단계: VM Firewall 전역 옵션 enable=1 설정")
            try:
                self._enable_vm_firewall_options(node, vmid, headers)
            except Exception as opt_err:
                print(f"⚠️ VM Firewall 옵션 활성화 중 오류: {opt_err}")
            
            # 3단계: VM을 Security Group에 할당
            print("🔧 3단계: VM을 Security Group에 할당")
            assignment_success = self._assign_vm_to_security_group(node, vmid, group_name, headers)
            if not assignment_success:
                print("❌ VM을 Security Group에 할당 실패")
                return False
            
            print(f"✅ VM '{vm_name}'에 Security Group '{group_name}' 할당 완료")
            return True
            
        except Exception as e:
            print(f"❌ VM '{vm_name}'에 Security Group '{group_name}' 할당 실패: {e}")
            return False

    def _enable_vm_firewall_options(self, node: str, vmid: int, headers: Dict[str, str]) -> bool:
        """VM Firewall 전역 옵션(enable)을 확인 후 필요 시 1로 설정"""
        try:
            options_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/firewall/options"
            # 현재 옵션 조회
            get_resp = self.session.get(options_url, headers=headers, timeout=10)
            if get_resp.status_code == 200:
                data = get_resp.json().get('data', {})
                current = str(data.get('enable', '0'))
                print(f"🔍 VM {vmid} Firewall 옵션 현재값: enable={current}")
                if current in ['1', 'true', 'True']:
                    print(f"✅ VM {vmid} Firewall 옵션이 이미 활성화되어 있음")
                    return True
            else:
                print(f"⚠️ VM {vmid} Firewall 옵션 조회 실패: status={get_resp.status_code} resp={get_resp.text}")
            
            # 비활성 상태일 때만 활성화 요청
            payload = { 'enable': '1' }
            put_resp = self.session.put(options_url, headers=headers, data=payload, timeout=10)
            if put_resp.status_code in [200, 201]:
                print(f"✅ VM {vmid} Firewall 옵션 활성화 완료")
                return True
            else:
                print(f"⚠️ VM {vmid} Firewall 옵션 활성화 실패: status={put_resp.status_code} resp={put_resp.text}")
                return False
        except Exception as e:
            print(f"⚠️ VM Firewall 옵션 활성화 예외: {e}")
            return False

    def _check_security_group_exists(self, group_name: str, headers: Dict[str, str]) -> bool:
        """Security Group이 존재하는지 확인"""
        try:
            print(f"🔍 Security Group '{group_name}' 존재 확인")
            
            # Security Group 조회
            group_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{group_name}"
            response = self.session.get(group_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Security Group '{group_name}' 존재 확인")
                return True
            elif response.status_code == 404:
                print(f"❌ Security Group '{group_name}'이 존재하지 않습니다.")
                return False
            else:
                print(f"⚠️ Security Group 조회 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Security Group 존재 확인 실패: {e}")
            return False

    def _assign_vm_to_security_group(self, node: str, vmid: int, group_name: str, headers: Dict[str, str]) -> bool:
        """VM을 Security Group에 할당 (올바른 API 방식)"""
        try:
            print(f"🔧 VM {vmid}을 Security Group '{group_name}'에 할당")
            
            # Proxmox 공식 API 사용: POST /api2/json/nodes/{node}/qemu/{vmid}/firewall/rules
            # type='group', action=GROUP_NAME
            firewall_rules_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/firewall/rules"
            
            # Security Group 할당을 위한 방화벽 규칙 생성
            # Proxmox API 문서에 따르면 type='group', action=GROUP_NAME
            rule_payload = {
                'type': 'group',
                'action': group_name,
                'comment': f'Security Group: {group_name}',
                'enable': '1'  # 규칙 자동 활성화
            }
            
            print(f"🔧 Security Group 할당 규칙 생성: {rule_payload}")
            
            print(f"🔧 Security Group 할당 API 호출: {firewall_rules_url}")
            print(f"🔧 요청 데이터: {rule_payload}")
            
            response = self.session.post(firewall_rules_url, headers=headers, data=rule_payload, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"✅ VM을 Security Group '{group_name}'에 할당 성공")
                return True
            else:
                print(f"❌ VM을 Security Group '{group_name}'에 할당 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ VM을 Security Group에 할당 실패: {e}")
            return False

    def _enable_vm_firewall(self, node: str, vmid: int, headers: Dict[str, str]) -> bool:
        """VM의 모든 네트워크 디바이스에 Firewall 설정을 0→1로 변경"""
        try:
            print(f"🔧 VM {vmid}의 네트워크 디바이스 Firewall 설정 활성화")
            
            # VM 설정 조회
            config_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            config_response = self.session.get(config_url, headers=headers, timeout=10)
            
            if config_response.status_code != 200:
                print(f"❌ VM 설정 조회 실패: {config_response.status_code}")
                return False
            
            vm_config = config_response.json().get('data', {})
            print(f"🔍 VM 설정: {vm_config}")
            
            # 네트워크 디바이스 찾기
            network_devices = []
            for key, value in vm_config.items():
                if key.startswith('net'):
                    print(f"🔍 네트워크 디바이스 발견: {key} = {value}")
                    network_devices.append(key)
            
            if not network_devices:
                print("⚠️ 네트워크 디바이스가 없습니다.")
                return True  # 네트워크 디바이스가 없어도 성공으로 처리
            
            # 각 네트워크 디바이스에 Firewall 설정 추가
            success_count = 0
            for device in network_devices:
                current_value = vm_config[device]
                
                # Firewall 설정이 이미 있는지 확인
                if 'firewall=1' in current_value:
                    print(f"✅ {device}에 이미 Firewall 설정이 활성화되어 있음")
                    success_count += 1
                    continue
                
                # Firewall 설정 추가 (기존 firewall 설정이 있으면 교체)
                if 'firewall=' in current_value:
                    # 기존 firewall 설정을 1로 교체
                    new_value = re.sub(r'firewall=\d+', 'firewall=1', current_value)
                else:
                    # firewall 설정이 없으면 추가
                    new_value = current_value + ',firewall=1'
                print(f"🔧 {device} Firewall 설정 변경: {current_value} → {new_value}")
                
                # VM 설정 업데이트
                update_payload = {device: new_value}
                update_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
                
                update_response = self.session.put(update_url, headers=headers, data=update_payload, timeout=10)
                
                if update_response.status_code in [200, 201]:
                    print(f"✅ {device} Firewall 설정 활성화 성공")
                    success_count += 1
                else:
                    print(f"❌ {device} Firewall 설정 활성화 실패: {update_response.status_code}")
                    print(f"   응답: {update_response.text}")
            
            print(f"✅ 네트워크 디바이스 Firewall 설정 완료: {success_count}/{len(network_devices)}개")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ VM Firewall 설정 활성화 실패: {e}")
            return False

    def _apply_security_group_rules(self, node: str, vmid: int, group_name: str, headers: Dict[str, str]) -> bool:
        """Security Group 규칙을 VM에 적용"""
        try:
            print(f"🔧 Security Group '{group_name}' 규칙을 VM {vmid}에 적용")
            
            # Security Group 규칙 조회
            rules_url = f"{self.endpoint}/api2/json/cluster/firewall/groups/{group_name}"
            rules_response = self.session.get(rules_url, headers=headers, timeout=10)
            
            if rules_response.status_code != 200:
                print(f"❌ Security Group '{group_name}' 규칙 조회 실패: {rules_response.status_code}")
                return False
            
            rules = rules_response.json().get('data', [])
            print(f"🔍 Security Group '{group_name}' 규칙 {len(rules)}개 발견")
            
            if not rules:
                print("⚠️ Security Group에 규칙이 없습니다.")
                return True  # 규칙이 없어도 성공으로 처리
            
            # VM 방화벽 규칙 URL
            vm_rules_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/firewall/rules"
            
            # 기존 VM 방화벽 규칙 삭제 (특정 Security Group 관련 규칙만)
            print("🔧 기존 VM 방화벽 규칙 정리")
            self._clear_vm_firewall_rules(node, vmid, headers, group_name)
            
            # Security Group 규칙을 VM에 적용
            success_count = 0
            for rule in rules:
                # VM 방화벽 규칙 형식으로 변환
                vm_rule_payload = {
                    'type': rule.get('type', 'in'),
                    'action': rule.get('action', 'ACCEPT'),
                    'proto': rule.get('proto', 'tcp'),
                    'dport': rule.get('dport', ''),
                    'source': rule.get('source', ''),
                    'dest': rule.get('dest', ''),
                    'comment': f"SG-{group_name}: {rule.get('comment', '')}"
                }
                
                print(f"🔧 VM에 규칙 적용: {vm_rule_payload}")
                
                response = self.session.post(vm_rules_url, headers=headers, data=vm_rule_payload, timeout=10)
                
                if response.status_code in [200, 201]:
                    success_count += 1
                    print(f"✅ VM에 규칙 적용 성공")
                else:
                    print(f"❌ VM에 규칙 적용 실패: {response.status_code}")
                    print(f"   응답: {response.text}")
            
            print(f"✅ Security Group 규칙 적용 완료: {success_count}/{len(rules)}개")
            return success_count > 0 or len(rules) == 0
            
        except Exception as e:
            print(f"❌ Security Group 규칙 적용 실패: {e}")
            return False

    def _clear_vm_firewall_rules(self, node: str, vmid: int, headers: Dict[str, str], group_name: str = None) -> bool:
        """VM의 기존 방화벽 규칙 삭제 (특정 Security Group 관련 규칙만)"""
        try:
            print(f"🔧 VM {vmid}의 기존 방화벽 규칙 정리 (Security Group: {group_name})")
            
            # Security Group이 지정되지 않은 경우 규칙 삭제하지 않음
            if not group_name:
                print("⚠️ Security Group이 지정되지 않아 기존 규칙을 삭제하지 않습니다.")
                return True
            
            # VM 방화벽 규칙 조회
            rules_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/firewall/rules"
            rules_response = self.session.get(rules_url, headers=headers, timeout=10)
            
            if rules_response.status_code != 200:
                print(f"⚠️ VM 방화벽 규칙 조회 실패: {rules_response.status_code}")
                print(f"   응답: {rules_response.text}")
                return True  # 실패해도 계속 진행
            
            rules = rules_response.json().get('data', [])
            print(f"🔍 기존 VM 방화벽 규칙 {len(rules)}개 발견")
            
            # 지정된 Security Group 관련 규칙만 삭제
            deleted_count = 0
            for rule in rules:
                comment = rule.get('comment', '')
                # Security Group 관련 규칙인지 확인 (SG-{group_name} 형식)
                if comment.startswith(f'SG-{group_name}') or comment.startswith(f'Security Group: {group_name}'):
                    rule_id = rule.get('id')
                    if rule_id:
                        delete_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/firewall/rules/{rule_id}"
                        delete_response = self.session.delete(delete_url, headers=headers, timeout=10)
                        
                        if delete_response.status_code in [200, 204]:
                            print(f"✅ 기존 Security Group 규칙 삭제: {comment}")
                            deleted_count += 1
                        else:
                            print(f"⚠️ 기존 Security Group 규칙 삭제 실패: {delete_response.status_code}")
                            print(f"   응답: {delete_response.text}")
                else:
                    print(f"🔍 다른 규칙 유지: {comment}")
            
            print(f"✅ Security Group '{group_name}' 관련 규칙 {deleted_count}개 삭제 완료")
            return True
            
        except Exception as e:
            print(f"⚠️ VM 방화벽 규칙 정리 실패: {e}")
            return True  # 실패해도 계속 진행

    def _save_security_group_assignment(self, node: str, vmid: int, group_name: str, headers: Dict[str, str]) -> bool:
        """VM에 Security Group 할당 정보 저장"""
        try:
            print(f"🔧 VM {vmid}에 Security Group '{group_name}' 할당 정보 저장")
            
            # VM 설정에 Security Group 정보 추가
            config_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            
            # 기존 설정에 Security Group 정보 추가
            update_payload = {
                'security_group': group_name,
                'comment': f"Security Group: {group_name}"
            }
            
            response = self.session.put(config_url, headers=headers, data=update_payload, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"✅ Security Group 할당 정보 저장 성공")
                return True
            else:
                print(f"⚠️ Security Group 할당 정보 저장 실패: {response.status_code}")
                return True  # 실패해도 성공으로 처리 (선택사항)
                
        except Exception as e:
            print(f"⚠️ Security Group 할당 정보 저장 실패: {e}")
            return True  # 실패해도 성공으로 처리

    def remove_security_group_from_vm(self, vm_name: str) -> bool:
        """VM에서 Security Group 제거 (올바른 구현)"""
        try:
            print(f"🔍 VM '{vm_name}'에서 Security Group 제거")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # VM 정보 조회
            vm_info = self.get_vm_info(vm_name)
            if not vm_info:
                print(f"❌ VM '{vm_name}'을 찾을 수 없습니다.")
                return False
            
            vmid = vm_info.get('vmid')
            node = vm_info.get('node', self.node)
            
            print(f"🔍 VM 정보: vmid={vmid}, node={node}")
            
            # 1단계: VM 설정에서 Security Group 할당 제거
            print("🔧 1단계: Security Group 할당 제거")
            assignment_removed = self._remove_vm_from_security_group(node, vmid, headers)
            if not assignment_removed:
                print("⚠️ Security Group 할당 제거 실패, 계속 진행")
            
            # 2단계: 네트워크 디바이스에서 Firewall 설정 제거
            print("🔧 2단계: 네트워크 디바이스 Firewall 설정 제거")
            firewall_disabled = self._disable_vm_firewall(node, vmid, headers)
            if not firewall_disabled:
                print("⚠️ Firewall 설정 제거 실패, 계속 진행")
            
            print(f"✅ VM '{vm_name}'에서 Security Group 제거 완료")
            return True
            
        except Exception as e:
            print(f"❌ VM '{vm_name}'에서 Security Group 제거 실패: {e}")
            return False

    def delete_server(self, server_name: str) -> bool:
        """서버 삭제 (Terraform 기반)
        
        이 메서드는 Terraform을 통해 서버를 삭제합니다.
        Proxmox API를 직접 호출하지 않고 TerraformService를 사용합니다.
        """
        try:
            print(f"🗑️ Terraform 기반 서버 삭제 시작: {server_name}")
            
            # TerraformService를 사용하여 서버 삭제
            from app.services.terraform_service import TerraformService
            terraform_service = TerraformService()
            
            # 1. terraform.tfvars.json에서 서버 설정 제거
            print(f"🔧 terraform.tfvars.json에서 서버 설정 제거: {server_name}")
            if not terraform_service.delete_server_config(server_name):
                print(f"❌ 서버 설정 제거 실패: {server_name}")
                return False
            
            # 2. Terraform apply로 실제 삭제 실행
            print(f"🔧 Terraform apply로 서버 삭제 실행: {server_name}")
            target = f'module.server["{server_name}"]'
            apply_result = terraform_service.apply([target])
            
            if apply_result:
                print(f"✅ Terraform으로 서버 삭제 성공: {server_name}")
                return True
            else:
                print(f"❌ Terraform으로 서버 삭제 실패: {server_name}")
                return False
                
        except Exception as e:
            print(f"❌ 서버 삭제 중 오류: {server_name} - {str(e)}")
            return False

    def _disable_vm_firewall(self, node: str, vmid: int, headers: Dict[str, str]) -> bool:
        """VM의 모든 네트워크 디바이스에서 Firewall 설정을 1→0으로 변경"""
        try:
            print(f"🔧 VM {vmid}의 네트워크 디바이스 Firewall 설정 비활성화")
            
            # VM 설정 조회
            config_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            config_response = self.session.get(config_url, headers=headers, timeout=10)
            
            if config_response.status_code != 200:
                print(f"❌ VM 설정 조회 실패: {config_response.status_code}")
                return False
            
            vm_config = config_response.json().get('data', {})
            print(f"🔍 VM 설정: {vm_config}")
            
            # 네트워크 디바이스 찾기
            network_devices = []
            for key, value in vm_config.items():
                if key.startswith('net'):
                    print(f"🔍 네트워크 디바이스 발견: {key} = {value}")
                    network_devices.append(key)
            
            if not network_devices:
                print("⚠️ 네트워크 디바이스가 없습니다.")
                return True  # 네트워크 디바이스가 없어도 성공으로 처리
            
            # 각 네트워크 디바이스에서 Firewall 설정 제거
            success_count = 0
            for device in network_devices:
                current_value = vm_config[device]
                
                # Firewall 설정이 있는지 확인
                if 'firewall=' in current_value:
                    # Firewall 설정 제거 (정규식 사용)
                    new_value = re.sub(r',?firewall=\d+', '', current_value)
                    # 시작이나 끝에 남은 쉼표 정리
                    new_value = re.sub(r'^,|,$', '', new_value)
                    print(f"🔧 {device} Firewall 설정 제거: {current_value} → {new_value}")
                    
                    # VM 설정 업데이트
                    update_payload = {device: new_value}
                    update_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
                    
                    update_response = self.session.put(update_url, headers=headers, data=update_payload, timeout=10)
                    
                    if update_response.status_code in [200, 201]:
                        print(f"✅ {device} Firewall 설정 제거 성공")
                        success_count += 1
                    else:
                        print(f"❌ {device} Firewall 설정 제거 실패: {update_response.status_code}")
                        print(f"   응답: {update_response.text}")
                else:
                    print(f"✅ {device}에 Firewall 설정이 없음")
                    success_count += 1
            
            print(f"✅ 네트워크 디바이스 Firewall 설정 제거 완료: {success_count}/{len(network_devices)}개")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ VM Firewall 설정 제거 실패: {e}")
            return False

    def _remove_vm_from_security_group(self, node: str, vmid: int, headers: Dict[str, str]) -> bool:
        """VM에서 Security Group 할당 제거 (올바른 API 방식)"""
        try:
            print(f"🔧 VM {vmid}에서 Security Group 할당 제거")
            
            # 먼저 VM 설정에서 현재 Security Group 확인
            config_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            config_response = self.session.get(config_url, headers=headers, timeout=10)
            
            current_group = None
            if config_response.status_code == 200:
                vm_config = config_response.json().get('data', {})
                current_group = vm_config.get('security_group')
                print(f"🔍 현재 VM Security Group: {current_group}")
            
            # VM의 방화벽 규칙을 조회하여 Security Group 규칙 찾기
            firewall_rules_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/firewall/rules"
            print(f"🔍 VM 방화벽 규칙 조회 URL: {firewall_rules_url}")
            
            rules_response = self.session.get(firewall_rules_url, headers=headers, timeout=10)
            
            if rules_response.status_code != 200:
                print(f"⚠️ VM 방화벽 규칙 조회 실패: {rules_response.status_code}")
                print(f"   응답: {rules_response.text}")
                return True  # 실패해도 성공으로 처리
            
            rules = rules_response.json().get('data', [])
            print(f"🔍 VM 방화벽 규칙 {len(rules)}개 발견")
            
            # Security Group 관련 규칙 찾기 (현재 설정된 Security Group만)
            security_group_rules = []
            for rule in rules:
                print(f"🔍 규칙 검사: {rule}")
                
                # 현재 Security Group이 설정된 경우, 해당 그룹의 규칙만 찾기
                if current_group:
                    # type이 'group'이고 action이 현재 Security Group 이름인 규칙
                    if (rule.get('type') == 'group' and rule.get('action') == current_group):
                        security_group_rules.append(rule)
                        print(f"🔍 현재 Security Group '{current_group}' 규칙 발견: {rule}")
                    # comment에 현재 Security Group이 포함된 규칙
                    elif (rule.get('comment') and 
                          (f'SG-{current_group}' in rule.get('comment') or 
                           f'Security Group: {current_group}' in rule.get('comment'))):
                        security_group_rules.append(rule)
                        print(f"🔍 현재 Security Group '{current_group}' 관련 규칙 발견: {rule}")
                else:
                    # Security Group이 설정되지 않은 경우, 일반적인 Security Group 규칙 찾기
                    if rule.get('type') == 'group' or (rule.get('action') and 'security_group' in rule.get('action', '').lower()):
                        security_group_rules.append(rule)
                        print(f"🔍 Security Group 규칙 발견: {rule}")
            
            if not security_group_rules:
                print("✅ Security Group 규칙이 없습니다.")
                return True
            
            # Security Group 규칙 삭제
            deleted_count = 0
            for rule in security_group_rules:
                # Proxmox에서 규칙 ID는 보통 'pos' 필드에 있음
                # pos가 0일 수 있으므로 None 체크를 명시적으로 해야 함
                pos_value = rule.get('pos')
                id_value = rule.get('id')
                rule_id = pos_value if pos_value is not None else id_value
                
                print(f"🔍 규칙 ID (pos): {pos_value}")
                print(f"🔍 규칙 ID (id): {id_value}")
                print(f"🔍 사용할 규칙 ID: {rule_id}")
                
                if rule_id is not None:
                    delete_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/firewall/rules/{rule_id}"
                    print(f"🔍 삭제 URL: {delete_url}")
                    
                    delete_response = self.session.delete(delete_url, headers=headers, timeout=10)
                    
                    if delete_response.status_code in [200, 204]:
                        print(f"✅ Security Group 규칙 삭제 성공: {rule.get('action')}")
                        deleted_count += 1
                    else:
                        print(f"❌ Security Group 규칙 삭제 실패: {delete_response.status_code}")
                        print(f"   응답: {delete_response.text}")
                else:
                    print(f"⚠️ 규칙 ID가 없습니다: {rule}")
            
            print(f"✅ Security Group 할당 제거 완료: {deleted_count}/{len(security_group_rules)}개 규칙")
            return deleted_count > 0 or len(security_group_rules) == 0
                
        except Exception as e:
            print(f"⚠️ Security Group 할당 제거 실패: {e}")
            import traceback
            traceback.print_exc()
            return True  # 실패해도 성공으로 처리

    def _remove_security_group_assignment(self, node: str, vmid: int, headers: Dict[str, str]) -> bool:
        """VM에서 Security Group 할당 정보 제거"""
        try:
            print(f"🔧 VM {vmid}에서 Security Group 할당 정보 제거")
            
            # 먼저 현재 VM 설정을 조회
            config_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            config_response = self.session.get(config_url, headers=headers, timeout=10)
            
            if config_response.status_code != 200:
                print(f"⚠️ VM 설정 조회 실패: {config_response.status_code}")
                return True  # 실패해도 성공으로 처리
            
            vm_config = config_response.json().get('data', {})
            print(f"🔍 현재 VM 설정: {vm_config}")
            
            # Security Group 관련 필드가 있는지 확인
            has_security_group = 'security_group' in vm_config
            has_security_comment = 'comment' in vm_config and 'Security Group:' in str(vm_config.get('comment', ''))
            
            if not has_security_group and not has_security_comment:
                print("✅ Security Group 관련 설정이 없습니다.")
                return True
            
            # Security Group 관련 설정 제거
            update_payload = {}
            
            if has_security_group:
                # DELETE 방식으로 필드 제거
                delete_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
                delete_payload = {'delete': 'security_group'}
                delete_response = self.session.put(delete_url, headers=headers, data=delete_payload, timeout=10)
                
                if delete_response.status_code in [200, 201]:
                    print(f"✅ Security Group 필드 제거 성공")
                else:
                    print(f"⚠️ Security Group 필드 제거 실패: {delete_response.status_code}")
                    print(f"   응답: {delete_response.text}")
            
            if has_security_comment:
                # comment에서 Security Group 관련 내용 제거
                current_comment = vm_config.get('comment', '')
                if 'Security Group:' in current_comment:
                    # Security Group 부분만 제거
                    new_comment = current_comment.replace('Security Group: ', '').replace('Security Group:', '')
                    new_comment = new_comment.strip()
                    
                    if new_comment:
                        update_payload['comment'] = new_comment
                    else:
                        # comment가 비어있으면 제거
                        delete_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
                        delete_payload = {'delete': 'comment'}
                        delete_response = self.session.put(delete_url, headers=headers, data=delete_payload, timeout=10)
                        
                        if delete_response.status_code in [200, 201]:
                            print(f"✅ Security Group comment 제거 성공")
                        else:
                            print(f"⚠️ Security Group comment 제거 실패: {delete_response.status_code}")
            
            # 추가 업데이트가 필요한 경우
            if update_payload:
                response = self.session.put(config_url, headers=headers, data=update_payload, timeout=10)
                
                if response.status_code in [200, 201]:
                    print(f"✅ Security Group 관련 설정 업데이트 성공")
                    return True
                else:
                    print(f"⚠️ Security Group 관련 설정 업데이트 실패: {response.status_code}")
                    print(f"   응답: {response.text}")
                    return True  # 실패해도 성공으로 처리
            
            print(f"✅ Security Group 할당 정보 제거 완료")
            return True
                
        except Exception as e:
            print(f"⚠️ Security Group 할당 정보 제거 실패: {e}")
            return True  # 실패해도 성공으로 처리

    def sync_vm_data(self):
        """VM 데이터 동기화"""
        try:
            vm_list = self.get_vm_list()
            
            for vm_data in vm_list:
                server = Server.get_by_name(vm_data['name'])
                if server:
                    # 기존 서버 정보 업데이트
                    server.vmid = vm_data['vmid']
                    server.status = vm_data['status']
                    server.update_vm_info(vm_data['vmid'])
                else:
                    # 새 서버 정보 추가
                    server = Server(
                        name=vm_data['name'],
                        vmid=vm_data['vmid'],
                        status=vm_data['status'],
                        os_type=classify_os_type(str(vm_data['name']))  # 동적으로 분류된 OS 타입
                    )
                    db.session.add(server)
            
            db.session.commit()
            logger.info("VM 데이터 동기화 완료")
            
        except Exception as e:
            logger.error(f"VM 데이터 동기화 실패: {e}")
            db.session.rollback()
            raise 

    def get_server_config(self, server_name: str) -> Dict[str, Any]:
        """서버 설정 정보 조회"""
        try:
            print(f"🔍 서버 설정 조회: {server_name}")
            
            # Proxmox 인증
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': error}
            
            # VM 정보 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return {'success': False, 'message': error}
            
            # 해당 서버 찾기
            target_vm = None
            for vm in vms:
                if vm['name'] == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {'success': False, 'message': f'서버 {server_name}을 찾을 수 없습니다.'}
            
            # VM 상세 설정 조회
            vm_config_url = f"{self.endpoint}/api2/json/nodes/{target_vm['node']}/qemu/{target_vm['vmid']}/config"
            vm_config_response = self.session.get(vm_config_url, headers=headers, verify=False, timeout=10)
            
            if vm_config_response.status_code != 200:
                return {'success': False, 'message': 'VM 설정을 가져올 수 없습니다.'}
            
            vm_config = vm_config_response.json().get('data', {})
            
            # tfvars에서 서버 정보 가져오기
            servers = self.read_servers_from_tfvars()
            server_data = servers.get(server_name, {})
            
            # DB에서 역할 및 방화벽 그룹 정보 가져오기
            firewall_group = None
            db_role = None
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT role, firewall_group FROM servers WHERE name = ?', (server_name,))
                    db_server = cursor.fetchone()
                    if db_server:
                        db_role = db_server['role']
                        firewall_group = db_server['firewall_group']
            except Exception as e:
                print(f"⚠️ DB 조회 실패: {e}")
            
            # 설정 정보 구성
            config = {
                'name': server_name,
                'vmid': target_vm['vmid'],
                'node': target_vm['node'],
                'status': target_vm['status'],
                'cpu': {
                    'cores': int(vm_config.get('cores', server_data.get('cpu', 1))),
                    'sockets': int(vm_config.get('sockets', 1)),
                    'type': vm_config.get('cpu', 'host').replace('cputype=', '') if vm_config.get('cpu', '').startswith('cputype=') else vm_config.get('cpu', 'host')
                },
                'memory': {
                    'size_mb': int(vm_config.get('memory', server_data.get('memory', 1024))),
                    'balloon': int(vm_config.get('balloon', 0))
                },
                'disks': [],
                'network': [],
                'role': db_role if db_role else server_data.get('role', ''),
                'firewall_group': firewall_group,
                'description': vm_config.get('description', ''),
                'tags': vm_config.get('tags', '')
            }
            
            # 디스크 정보 파싱
            print(f"🔍 {server_name} VM 설정: {vm_config}")
            for key, value in vm_config.items():
                if key.startswith('scsi') or key.startswith('sata') or key.startswith('virtio'):
                    try:
                        # 디스크 크기 추출
                        size_gb = 0
                        storage = 'unknown'
                        
                        print(f"🔍 디스크 파싱: {key} = {value}")
                        
                        # scsihw는 하드웨어 타입이므로 제외
                        if key == 'scsihw':
                            continue
                        
                        # 스토리지 추출 (예: local-lvm:vm-104-disk-0)
                        if ':' in value:
                            storage = value.split(':')[0]
                        
                        # 크기 정보 추출 - 패턴 1을 우선적으로 사용 (size= 파라미터가 가장 정확)
                        size_gb = 0
                        
                        # 패턴 1: size= 파라미터 (예: size=10G, size=10737418240) - 가장 정확한 방법
                        if 'size=' in value:
                            size_match = value.split('size=')[1].split(',')[0]
                            try:
                                # GB 단위인지 확인 (예: size=10G)
                                if size_match.endswith('G'):
                                    size_gb = int(size_match[:-1])
                                    print(f"✅ 패턴 1 성공: {size_gb} GB (G 단위)")
                                else:
                                    # 바이트 단위인지 확인 (예: size=10737418240)
                                    size_bytes = int(size_match)
                                    size_gb = size_bytes // (1024 * 1024 * 1024)
                                    print(f"✅ 패턴 1 성공: {size_bytes} bytes = {size_gb} GB")
                            except ValueError:
                                pass
                        
                        # 패턴 2: 파일명에서 크기 추출 (예: vm-104-disk-0) - 백업 방법
                        if size_gb == 0 and ('disk-' in value or storage != 'unknown'):
                            try:
                                # 실제 디스크 파일 크기 조회
                                disk_file_url = f"{self.endpoint}/api2/json/nodes/{target_vm['node']}/storage/{storage}/content"
                                disk_response = self.session.get(disk_file_url, headers=headers, verify=False, timeout=10)
                                
                                if disk_response.status_code == 200:
                                    disk_files = disk_response.json().get('data', [])
                                    for disk_file in disk_files:
                                        volid = disk_file.get('volid', '')
                                        # 여러 패턴으로 디스크 파일 매칭
                                        disk_patterns = [
                                            f"vm-{target_vm['vmid']}-disk-{key.replace('scsi', '').replace('sata', '').replace('virtio', '')}",
                                            f"vm-{target_vm['vmid']}-disk-{key}",
                                            f"vm-{target_vm['vmid']}-disk-{key.replace('scsi', '').replace('sata', '').replace('virtio', '')}.raw",
                                            f"vm-{target_vm['vmid']}-disk-{key}.raw"
                                        ]
                                        
                                        for pattern in disk_patterns:
                                            if volid.endswith(pattern):
                                                size_bytes = disk_file.get('size', 0)
                                                size_gb = size_bytes // (1024 * 1024 * 1024)
                                                print(f"✅ 패턴 2 성공: {size_bytes} bytes = {size_gb} GB (매칭: {pattern})")
                                                break
                                        if size_gb > 0:
                                            break
                            except Exception as e:
                                print(f"⚠️ 디스크 파일 크기 조회 실패: {e}")
                        
                        # 패턴 3: 직접 크기 (예: local-lvm:10) - 최후 수단
                        if size_gb == 0 and ':' in value:
                            parts = value.split(':')
                            if len(parts) >= 2:
                                try:
                                    # 마지막 부분이 숫자인지 확인
                                    last_part = parts[-1]
                                    if last_part.isdigit():
                                        size_gb = int(last_part)
                                        print(f"✅ 패턴 3 성공: {size_gb} GB")
                                except ValueError:
                                    pass
                        
                        disk_info = {
                            'device': key,
                            'size_gb': size_gb,
                            'storage': storage
                        }
                        config['disks'].append(disk_info)
                        print(f"💾 디스크 정보: {disk_info}")
                        
                    except Exception as e:
                        print(f"⚠️ 디스크 정보 파싱 실패 ({key}): {e}")
                        if key != 'scsihw':
                            disk_info = {
                                'device': key,
                                'size_gb': 0,
                                'storage': 'unknown'
                            }
                            config['disks'].append(disk_info)
            
            # 디스크 총합 계산
            total_disk_gb = sum(disk['size_gb'] for disk in config['disks'])
            config['total_disk_gb'] = total_disk_gb
            print(f"📊 총 디스크 크기: {total_disk_gb} GB")
            
            # 네트워크 정보 파싱
            for key, value in vm_config.items():
                if key.startswith('net'):
                    net_info = {
                        'device': key,
                        'model': value.split(',')[0] if ',' in value else 'e1000',
                        'bridge': value.split('bridge=')[1].split(',')[0] if 'bridge=' in value else 'vmbr0'
                    }
                    config['network'].append(net_info)
            
            return {'success': True, 'config': config}
            
        except Exception as e:
            print(f"❌ 서버 설정 조회 실패: {e}")
            return {'success': False, 'message': str(e)}
    
    def update_server_config(self, server_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """서버 설정 업데이트"""
        try:
            print(f"🔧 서버 설정 업데이트: {server_name}")
            
            # Proxmox 인증
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': error}
            
            # VM 정보 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return {'success': False, 'message': error}
            
            # 해당 서버 찾기
            target_vm = None
            for vm in vms:
                if vm['name'] == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {'success': False, 'message': f'서버 {server_name}을 찾을 수 없습니다.'}
            
            # 업데이트할 설정 구성
            update_config = {}
            
            # CPU 설정
            if 'cpu' in config_data:
                cpu_config = config_data['cpu']
                if 'cores' in cpu_config:
                    update_config['cores'] = cpu_config['cores']
                if 'sockets' in cpu_config:
                    update_config['sockets'] = cpu_config['sockets']
                if 'type' in cpu_config:
                    update_config['cpu'] = cpu_config['type']
            
            # 메모리 설정
            if 'memory' in config_data:
                memory_config = config_data['memory']
                if 'size_mb' in memory_config:
                    update_config['memory'] = memory_config['size_mb']
                if 'balloon' in memory_config:
                    update_config['balloon'] = memory_config['balloon']
            
            # 설명 설정
            if 'description' in config_data:
                update_config['description'] = config_data['description']
            
            # 태그 설정
            if 'tags' in config_data:
                update_config['tags'] = config_data['tags']
            
            # VM 설정 업데이트 API 호출
            vm_config_url = f"{self.endpoint}/api2/json/nodes/{target_vm['node']}/qemu/{target_vm['vmid']}/config"
            response = self.session.put(vm_config_url, headers=headers, data=update_config, verify=False, timeout=30)
            
            if response.status_code != 200:
                return {'success': False, 'message': f'설정 업데이트 실패: {response.text}'}
            
            # DB 업데이트 (역할, 방화벽 그룹)
            if 'role' in config_data or 'firewall_group' in config_data:
                try:
                    with self._get_db_connection() as conn:
                        cursor = conn.cursor()
                        update_fields = []
                        update_values = []
                        
                        if 'role' in config_data:
                            update_fields.append('role = ?')
                            update_values.append(config_data['role'])
                        
                        if 'firewall_group' in config_data:
                            update_fields.append('firewall_group = ?')
                            update_values.append(config_data['firewall_group'])
                        
                        if update_fields:
                            update_values.append(server_name)
                            query = f"UPDATE servers SET {', '.join(update_fields)} WHERE name = ?"
                            cursor.execute(query, update_values)
                            conn.commit()
                except Exception as e:
                    print(f"⚠️ DB 업데이트 실패: {e}")
            
            # 방화벽 그룹 해제 처리 (firewall_group이 비어있거나 'none'일 때)
            if 'firewall_group' in config_data:
                fg = (config_data.get('firewall_group') or '').strip().lower()
                if fg in ['', 'none', 'null']:
                    try:
                        print("🔧 방화벽 그룹 해제 요청 감지 → VM에서 SG 제거 및 방화벽 비활성화")
                        self.remove_security_group_from_vm(server_name)
                        # 전역 옵션도 비활성화
                        # VM 식별
                        vms2, _ = self.get_proxmox_vms(headers)
                        target_vm2 = next((vm for vm in vms2 if vm['name'] == server_name), None)
                        if target_vm2:
                            node2 = target_vm2['node']
                            vmid2 = target_vm2['vmid']
                            # options 조회 후 enable=0
                            options_url = f"{self.endpoint}/api2/json/nodes/{node2}/qemu/{vmid2}/firewall/options"
                            get_resp = self.session.get(options_url, headers=headers, timeout=10)
                            current = str((get_resp.json().get('data', {}) if get_resp.status_code == 200 else {}).get('enable', '1'))
                            if current in ['1', 'true', 'True']:
                                put_resp = self.session.put(options_url, headers=headers, data={'enable': '0'}, timeout=10)
                                print(f"🔧 VM Firewall 옵션 비활성화 결과: status={put_resp.status_code}")
                    except Exception as e:
                        print(f"⚠️ 방화벽 그룹 해제 처리 중 오류: {e}")
            
            return {'success': True, 'data': update_config}
            
        except Exception as e:
            print(f"❌ 서버 설정 업데이트 실패: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_server_logs(self, server_name: str, log_type: str = 'system', lines: int = 100) -> Dict[str, Any]:
        """서버 로그 조회"""
        try:
            print(f"📋 서버 로그 조회: {server_name}, 타입: {log_type}, 라인: {lines}")
            
            # Proxmox 인증
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': error}
            
            # VM 정보 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return {'success': False, 'message': error}
            
            # 해당 서버 찾기
            target_vm = None
            for vm in vms:
                if vm['name'] == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {'success': False, 'message': f'서버 {server_name}을 찾을 수 없습니다.'}
            
            # 로그 조회 API 호출
            log_url = f"{self.endpoint}/api2/json/nodes/{target_vm['node']}/qemu/{target_vm['vmid']}/monitor"
            
            # QEMU Monitor에서 지원하는 명령어들
            log_commands = {
                'system': 'info status',
                'dmesg': 'info status',
                'auth': 'info status',
                'nginx': 'info status',
                'mysql': 'info status',
                'custom': 'info status'
            }
            
            command = log_commands.get(log_type, log_commands['system'])
            
            # QEMU Monitor 명령 실행
            monitor_data = {
                'command': command
            }
            
            response = self.session.post(log_url, headers=headers, json=monitor_data, verify=False, timeout=30)
            
            if response.status_code != 200:
                return {'success': False, 'message': f'로그 조회 실패: {response.text}'}
            
            monitor_data = response.json().get('data', '')
            
            # VM 상태 정보 추가 조회
            vm_status_url = f"{self.endpoint}/api2/json/nodes/{target_vm['node']}/qemu/{target_vm['vmid']}/status/current"
            status_response = self.session.get(vm_status_url, headers=headers, verify=False, timeout=10)
            
            status_info = ""
            if status_response.status_code == 200:
                status_data = status_response.json().get('data', {})
                status_info = f"""
=== VM 상태 정보 ===
상태: {status_data.get('status', 'unknown')}
CPU 사용률: {status_data.get('cpu', 0):.2f}%
메모리 사용률: {status_data.get('memory', 0) / (1024*1024*1024):.2f} GB
업타임: {status_data.get('uptime', 0)} 초
네트워크: {status_data.get('netin', 0)} / {status_data.get('netout', 0)} bytes
디스크: {status_data.get('diskread', 0)} / {status_data.get('diskwrite', 0)} bytes
"""
            
            # 로그 타입에 따른 정보 구성
            log_content = f"""
=== {log_type.upper()} 정보 ===
{monitor_data}

{status_info}

=== 시스템 정보 ===
서버명: {server_name}
VM ID: {target_vm['vmid']}
노드: {target_vm['node']}
조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return {
                'success': True,
                'data': {
                    'server_name': server_name,
                    'log_type': log_type,
                    'lines': lines,
                    'content': log_content,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            print(f"❌ 서버 로그 조회 실패: {e}")
            return {'success': False, 'message': str(e)}
    
    def create_server_backup(self, server_name: str, backup_config: Dict[str, Any]) -> Dict[str, Any]:
        """서버 백업 생성 (vzdump 사용)"""
        try:
            print(f"💾 서버 백업 생성 시작: {server_name}")
            print(f"📋 백업 설정: {backup_config}")
            
            # Proxmox 인증
            print(f"🔐 Proxmox 인증 시도...")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return {'success': False, 'message': error}
            print(f"✅ 인증 성공")
            
            # VM 정보 조회
            print(f"🔍 VM 정보 조회 시도...")
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 조회 실패: {error}")
                return {'success': False, 'message': error}
            print(f"✅ VM 조회 성공: {len(vms)}개 VM 발견")
            
            # 해당 서버 찾기
            target_vm = None
            for vm in vms:
                if vm['name'] == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                print(f"❌ 서버를 찾을 수 없음: {server_name}")
                return {'success': False, 'message': f'서버 {server_name}을 찾을 수 없습니다.'}
            print(f"✅ 타겟 VM 발견: {target_vm}")
            
            # vzdump 백업 생성 (올바른 API 경로 사용)
            vzdump_url = f"{self.endpoint}/api2/json/nodes/{target_vm['node']}/vzdump"
            
            # vzdump 설정 (Proxmox API 문서에 따른 파라미터)
            vzdump_data = {
                'vmid': target_vm['vmid'],
                'storage': backup_config.get('storage', 'local'),
                'compress': backup_config.get('compress', 'zstd'),
                'mode': backup_config.get('mode', 'snapshot'),
                'remove': 0,  # 기존 백업 유지
                'notes-template': f'{server_name}'
            }
            
            # 설명이 있으면 notes-template에 포함
            if backup_config.get('description'):
                vzdump_data['notes-template'] = f'{server_name} - {backup_config.get("description")}'
            
            print(f"🔧 vzdump 설정: {vzdump_data}")
            print(f"🔧 vzdump URL: {vzdump_url}")
            
            # POST 요청으로 vzdump 실행
            print(f"🚀 vzdump API 호출 시도...")
            response = self.session.post(vzdump_url, headers=headers, data=vzdump_data, verify=False, timeout=60)
            print(f"📊 응답 상태 코드: {response.status_code}")
            print(f"📊 응답 내용: {response.text}")
            
            if response.status_code != 200:
                error_text = response.text
                print(f"❌ vzdump API 호출 실패: {error_text}")
                if "snapshot feature is not available" in error_text:
                    return {
                        'success': False, 
                        'message': f'이 VM에서는 백업 기능이 지원되지 않습니다. VM의 디스크 구성이나 설정을 확인해주세요.'
                    }
                else:
                    return {'success': False, 'message': f'백업 생성 실패: {error_text}'}
            
            vzdump_result = response.json()
            task_id = vzdump_result.get('data', '')
            
            print(f"✅ vzdump 백업 시작됨: Task ID {task_id}")
            
            return {
                'success': True,
                'data': {
                    'server_name': server_name,
                    'task_id': task_id,
                    'description': backup_config.get('description', f'Backup of {server_name}'),
                    'timestamp': datetime.now().isoformat(),
                    'message': f'백업 작업이 시작되었습니다. Task ID: {task_id}'
                }
            }
            
        except Exception as e:
            print(f"❌ 서버 백업 생성 실패: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_server_backups(self, server_name: str) -> Dict[str, Any]:
        """서버 백업 목록 조회 (vzdump 백업 파일)"""
        try:
            print(f"📋 서버 백업 목록 조회: {server_name}")
            
            # Proxmox 인증
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': error}
            
            # VM 정보 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return {'success': False, 'message': error}
            
            # 해당 서버 찾기
            target_vm = None
            for vm in vms:
                if vm['name'] == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {'success': False, 'message': f'서버 {server_name}을 찾을 수 없습니다.'}
            
            # 스토리지에서 백업 파일 조회
            backups = []
            
            # 여러 스토리지에서 백업 파일 찾기
            storages = ['local', 'local-lvm', 'ssd']
            
            for storage in storages:
                try:
                    storage_url = f"{self.endpoint}/api2/json/nodes/{target_vm['node']}/storage/{storage}/content"
                    storage_response = self.session.get(storage_url, headers=headers, verify=False, timeout=10)
                    
                    if storage_response.status_code == 200:
                        storage_data = storage_response.json().get('data', [])
                        
                        for file_info in storage_data:
                            volid = file_info.get('volid', '')
                            
                            # vzdump 백업 파일 패턴 확인 (예: vzdump-qemu-104-2025_08_18-17_30_00.vma.zst)
                            if 'vzdump-qemu' in volid and str(target_vm['vmid']) in volid:
                                backup_info = {
                                    'name': file_info.get('volid', ''),
                                    'storage': storage,
                                    'size': file_info.get('size', 0),
                                    'size_gb': round(file_info.get('size', 0) / (1024 * 1024 * 1024), 2),
                                    'content': file_info.get('content', ''),
                                    'format': file_info.get('format', ''),
                                    'ctime': file_info.get('ctime', 0),
                                    'timestamp': datetime.fromtimestamp(file_info.get('ctime', 0)).isoformat() if file_info.get('ctime') else None
                                }
                                backups.append(backup_info)
                                print(f"✅ 백업 파일 발견: {backup_info['name']} ({backup_info['size_gb']}GB)")
                except Exception as e:
                    print(f"⚠️ 스토리지 {storage} 조회 실패: {e}")
                    continue
            
            # 생성 시간 기준으로 정렬 (최신순)
            backups.sort(key=lambda x: x.get('ctime', 0), reverse=True)
            
            return {
                'success': True,
                'data': {
                    'server_name': server_name,
                    'backups': backups,
                    'total_count': len(backups)
                }
            }
            
        except Exception as e:
            print(f"❌ 서버 백업 목록 조회 실패: {e}")
            return {'success': False, 'message': str(e)}

    def add_server_disk(self, server_name: str, disk_data: Dict[str, Any]) -> Dict[str, Any]:
        """서버에 새 디스크 추가"""
        try:
            print(f"💾 디스크 추가: {server_name}")
            
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': f'인증 실패: {error}'}

            # 서버 정보 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return {'success': False, 'message': f'서버 조회 실패: {error}'}

            # 서버 찾기
            server = None
            for vm in vms:
                if vm.get('name') == server_name:
                    server = vm
                    break

            if not server:
                return {'success': False, 'message': f'서버를 찾을 수 없습니다: {server_name}'}

            vmid = server.get('vmid')
            node = server.get('node')

            # 다음 사용 가능한 디스크 번호 찾기
            config_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            config_response = self.session.get(config_url, headers=headers, verify=False, timeout=10)
            
            if config_response.status_code != 200:
                return {'success': False, 'message': f'서버 설정 조회 실패: {config_response.text}'}

            config = config_response.json().get('data', {})
            
            # 기존 디스크 번호들 찾기
            existing_disks = []
            for key, value in config.items():
                if key.startswith(('scsi', 'sata', 'virtio')) and key != 'scsihw':
                    existing_disks.append(key)

            # 사용자가 지정한 디스크 번호 사용
            disk_type = disk_data.get('type', 'scsi')
            disk_number = disk_data.get('number', 0)
            disk_size = disk_data.get('size_gb', 10)
            storage = disk_data.get('storage', 'local')
            
            # 디스크 번호 중복 확인
            target_device = f'{disk_type}{disk_number}'
            if target_device in existing_disks:
                return {
                    'success': False,
                    'message': f'디스크 {target_device}가 이미 존재합니다. 다른 번호를 선택해주세요.'
                }
            
            disk_config = {
                target_device: f'{storage}:{disk_size}'
            }

            # Proxmox API로 디스크 추가
            update_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            update_data = disk_config

            response = self.session.post(update_url, headers=headers, json=update_data, verify=False, timeout=30)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': f'디스크 {target_device}가 추가되었습니다.'
                }
            else:
                return {
                    'success': False,
                    'message': f'디스크 추가 실패: {response.text}'
                }

        except Exception as e:
            print(f"❌ 디스크 추가 실패: {str(e)}")
            return {
                'success': False,
                'message': f'디스크 추가 실패: {str(e)}'
            }

    def remove_server_disk(self, server_name: str, device: str) -> Dict[str, Any]:
        """서버에서 디스크 삭제"""
        try:
            print(f"🗑️ 디스크 삭제: {server_name} - {device}")
            
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': f'인증 실패: {error}'}

            # 서버 정보 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return {'success': False, 'message': f'서버 조회 실패: {error}'}

            # 서버 찾기
            server = None
            for vm in vms:
                if vm.get('name') == server_name:
                    server = vm
                    break

            if not server:
                return {'success': False, 'message': f'서버를 찾을 수 없습니다: {server_name}'}

            vmid = server.get('vmid')
            node = server.get('node')

            # 디스크 삭제 (delete=1 파라미터로 설정)
            delete_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/config"
            delete_data = {
                'delete': device
            }

            response = self.session.post(delete_url, headers=headers, json=delete_data, verify=False, timeout=30)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': f'디스크 {device}가 삭제되었습니다.'
                }
            else:
                return {
                    'success': False,
                    'message': f'디스크 삭제 실패: {response.text}'
                }

        except Exception as e:
            print(f"❌ 디스크 삭제 실패: {str(e)}")
            return {
                'success': False,
                'message': f'디스크 삭제 실패: {str(e)}'
            }

    def get_node_backups(self, node_name: str = None) -> Dict[str, Any]:
        """노드별 백업 목록 조회"""
        try:
            print(f"🔍 get_node_backups 시작: node_name={node_name}")
            
            # 인증
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return {'success': False, 'message': error}
            
            print("✅ 인증 성공")
            
            # 모든 노드 조회
            nodes_response = requests.get(f"{self.endpoint}/api2/json/nodes", headers=headers, verify=False)
            if nodes_response.status_code != 200:
                print(f"❌ 노드 조회 실패: {nodes_response.status_code}")
                return {'success': False, 'message': f'노드 조회 실패: {nodes_response.status_code}'}
            
            nodes_data = nodes_response.json()
            nodes = [node['node'] for node in nodes_data.get('data', [])]
            print(f"🔍 발견된 노드들: {nodes}")
            
            # 특정 노드만 필터링
            if node_name:
                if node_name not in nodes:
                    print(f"❌ 노드 {node_name}을 찾을 수 없습니다")
                    return {'success': False, 'message': f'노드 {node_name}을 찾을 수 없습니다'}
                nodes = [node_name]
            
            all_backups = []
            node_stats = {}
            
            for node in nodes:
                node_stats[node] = {'backup_count': 0, 'total_size_gb': 0}
                
                # local 스토리지만 조회 (백업 파일은 local에만 저장됨)
                storages = ['local']
                
                # 백업 파일들을 먼저 수집
                backup_files = []
                
                for storage in storages:
                    # 백업 파일만 조회 (성능 최적화)
                    content_response = requests.get(f"{self.endpoint}/api2/json/nodes/{node}/storage/{storage}/content?content=backup", headers=headers, verify=False)
                    if content_response.status_code != 200:
                        continue
                    
                    content_data = content_response.json()
                    content_items = content_data.get('data', [])
                    
                    for item in content_items:
                        content_type = item.get('content')
                        volid = item.get('volid', '')
                        
                        if content_type == 'backup' and 'vzdump-qemu' in volid:
                            # vzdump-qemu 파일 파싱
                            filename = item.get('volid', '')
                            if 'vzdump-qemu' in filename:
                                # 파일명에서 VM ID와 날짜 추출
                                filename_parts = filename.split('/')[-1]  # vzdump-qemu-101-2025_08_19-09_48_37.vma.zst
                                parts = filename_parts.split('-')  # ['vzdump', 'qemu', '101', '2025_08_19', '09_48_37.vma.zst']
                                
                                if len(parts) >= 4:
                                    vm_id = parts[2]  # '101'
                                    backup_date = parts[3]  # '2025_08_19'
                                    
                                    backup_files.append({
                                        'filename': filename,
                                        'node': node,
                                        'storage': storage,
                                        'vm_id': vm_id,
                                        'backup_date': backup_date,
                                        'size': item.get('size', 0),
                                        'size_gb': round(item.get('size', 0) / (1024**3), 2),
                                        'content': item.get('content'),
                                        'format': item.get('format'),
                                        'ctime': item.get('ctime'),
                                        'timestamp': item.get('ctime')
                                    })
                
                # DB에서 VM 이름 조회 (성능 최적화)
                vm_ids = list(set([bf['vm_id'] for bf in backup_files]))
                vm_names = {}
                
                if vm_ids:
                    try:
                        from app.main import db
                        from app.models.server import Server
                        
                        # VM ID를 정수로 변환하여 조회
                        vm_ids_int = []
                        for vm_id in vm_ids:
                            try:
                                vm_ids_int.append(int(vm_id))
                            except (ValueError, TypeError):
                                continue
                        
                        if vm_ids_int:
                            # SQLAlchemy를 사용한 조회
                            results = db.session.query(Server.vmid, Server.name).filter(Server.vmid.in_(vm_ids_int)).all()
                            
                            for vm_id, name in results:
                                vm_names[str(vm_id)] = name  # 문자열 키로 저장
                    except Exception as e:
                        print(f"⚠️ DB 조회 실패: {e}")
                        pass  # 조용히 실패 처리
                
                # DB에서 찾지 못한 VM들은 기본값 사용
                for vm_id in vm_ids:
                    if vm_id not in vm_names:
                        vm_names[vm_id] = f"VM-{vm_id}"
                
                # 백업 정보에 VM 이름 추가
                for backup_file in backup_files:
                    vm_id = backup_file['vm_id']
                    backup_info = {
                        'name': backup_file['filename'],
                        'filename': backup_file['filename'].split('/')[-1],
                        'node': backup_file['node'],
                        'storage': backup_file['storage'],
                        'vm_id': vm_id,
                        'vm_name': vm_names.get(vm_id, f"VM-{vm_id}"),
                        'backup_date': backup_file['backup_date'],
                        'size': backup_file['size'],
                        'size_gb': backup_file['size_gb'],
                        'content': backup_file['content'],
                        'format': backup_file['format'],
                        'ctime': backup_file['ctime'],
                        'timestamp': backup_file['timestamp']
                    }
                    
                    all_backups.append(backup_info)
                    node_stats[node]['backup_count'] += 1
                    node_stats[node]['total_size_gb'] += backup_info['size_gb']
            
            # 생성 시간 기준으로 정렬 (최신순)
            all_backups.sort(key=lambda x: x.get('ctime', 0), reverse=True)
            
            total_count = len(all_backups)
            total_size_gb = sum(backup['size_gb'] for backup in all_backups)
            
            result = {
                'success': True,
                'data': {
                    'backups': all_backups,
                    'node_stats': node_stats,
                    'total_count': total_count,
                    'total_size_gb': round(total_size_gb, 2)
                }
            }
            
            return result
            
        except Exception as e:
            print(f"💥 get_node_backups 예외: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'백업 목록 조회 실패: {str(e)}'}

    def restore_backup(self, node: str, vm_id: str, filename: str) -> Dict[str, Any]:
        """백업 복원"""
        try:
            print(f"🔄 백업 복원 시작: 노드={node}, VM ID={vm_id}, 파일={filename}")
            
            # 인증
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': error}
            
            # VM이 실행 중인지 확인하고 중지
            vm_status_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vm_id}/status/current"
            status_response = requests.get(vm_status_url, headers=headers, verify=False, timeout=10)
            
            if status_response.status_code == 200:
                vm_status = status_response.json().get('data', {})
                if vm_status.get('status') == 'running':
                    print(f"⚠️ VM {vm_id}이 실행 중입니다. 중지 후 복원을 진행합니다.")
                    
                    # VM 중지
                    stop_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vm_id}/status/stop"
                    stop_response = requests.post(stop_url, headers=headers, verify=False, timeout=30)
                    
                    if stop_response.status_code != 200:
                        return {'success': False, 'message': f'VM 중지 실패: {stop_response.text}'}
                    
                    # VM이 완전히 중지될 때까지 대기
                    import time
                    for i in range(30):  # 최대 30초 대기
                        time.sleep(1)
                        status_response = requests.get(vm_status_url, headers=headers, verify=False, timeout=10)
                        if status_response.status_code == 200:
                            vm_status = status_response.json().get('data', {})
                            if vm_status.get('status') == 'stopped':
                                break
                    else:
                        return {'success': False, 'message': 'VM 중지 대기 시간 초과'}
            
            # 기존 VM이 있는지 확인
            existing_vm = None
            try:
                vms, error = self.get_proxmox_vms(headers)
                if not error:
                    for vm in vms:
                        if vm.get('vmid') == int(vm_id):
                            existing_vm = vm
                            break
            except:
                pass
            
            # 백업 복원 API 호출 - /nodes/{node}/qemu 엔드포인트 사용 (force 파라미터로 덮어쓰기)
            restore_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu"
            
            # 백업 복원 파라미터 설정
            restore_data = {
                'vmid': vm_id,  # 기존 VM ID 사용
                'archive': f'local:backup/{filename}',
                'force': '1'  # 강제 덮어쓰기 플래그
            }
            
            if existing_vm:
                print(f"⚠️ 기존 VM 발견: {existing_vm.get('name')} (ID: {vm_id}). force 플래그로 덮어쓰기 복원합니다.")
            else:
                print(f"✅ 새 VM ID {vm_id}로 복원합니다.")
            
            print(f"🔧 백업 복원 API 호출: {restore_url}")
            print(f"🔧 복원 데이터: {restore_data}")
            
            response = requests.post(restore_url, headers=headers, data=restore_data, verify=False, timeout=300)
            
            print(f"📊 복원 응답 상태: {response.status_code}")
            print(f"📊 복원 응답 내용: {response.text}")
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': f'백업 복원이 완료되었습니다. (VM ID: {vm_id})',
                    'data': {
                        'vm_id': vm_id,
                        'filename': filename,
                        'node': node,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            else:
                error_message = response.text
                if "already exists" in error_message:
                    return {
                        'success': False,
                        'message': f'VM ID {vm_id}가 이미 존재합니다. 다른 VM ID를 사용하거나 기존 VM을 삭제 후 다시 시도해주세요.'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'백업 복원 실패: {error_message}'
                    }
                    
        except Exception as e:
            print(f"❌ 백업 복원 실패: {e}")
            return {'success': False, 'message': f'백업 복원 중 오류가 발생했습니다: {str(e)}'}

    def delete_backup(self, node: str, filename: str) -> Dict[str, Any]:
        """백업 파일 삭제"""
        try:
            print(f"🗑️ 백업 삭제 시작: 노드={node}, 파일={filename}")
            
            # 인증
            headers, error = self.get_proxmox_auth()
            if error:
                return {'success': False, 'message': error}
            
            # 백업 파일 삭제 API 호출 - volid 형식 사용
            import urllib.parse
            volid = f"local:backup/{filename}"
            encoded_volid = urllib.parse.quote(volid)
            delete_url = f"{self.endpoint}/api2/json/nodes/{node}/storage/local/content/{encoded_volid}"
            
            print(f"🔧 백업 삭제 API 호출: {delete_url}")
            
            response = requests.delete(delete_url, headers=headers, verify=False, timeout=60)
            
            print(f"📊 삭제 응답 상태: {response.status_code}")
            print(f"📊 삭제 응답 내용: {response.text}")
            
            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'message': f'백업 파일이 삭제되었습니다.',
                    'data': {
                        'filename': filename,
                        'node': node,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            else:
                return {
                    'success': False,
                    'message': f'백업 삭제 실패: {response.text}'
                }
                
        except Exception as e:
            print(f"❌ 백업 삭제 실패: {e}")
            return {'success': False, 'message': f'백업 삭제 중 오류가 발생했습니다: {str(e)}'}