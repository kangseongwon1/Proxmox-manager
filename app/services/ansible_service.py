"""
Ansible 서비스
"""
import subprocess
import yaml
import os
import logging
import tempfile
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification
from app.services.ansible_variables import AnsibleVariableManager
from app import db

# ansible-runner import
try:
    import ansible_runner
    ANSIBLE_RUNNER_AVAILABLE = True
except ImportError:
    ANSIBLE_RUNNER_AVAILABLE = False
    print("⚠️ ansible-runner가 설치되지 않았습니다. subprocess를 사용합니다.")

logger = logging.getLogger(__name__)

class AnsibleService:
    """Ansible 서비스"""
    
    def __init__(self, ansible_dir: str = "ansible"):
        # 프로젝트 루트 디렉토리 찾기 (리팩토링에 강건한 방식)
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        
        # Ansible 디렉토리 설정
        self.ansible_dir = os.path.join(project_root, ansible_dir)
        self.dynamic_inventory_script = os.path.join(self.ansible_dir, "dynamic_inventory.py")
        # 정적 인벤토리 파일 경로 (다중 서버 동시 실행용)
        self.inventory_file = os.path.join(self.ansible_dir, "inventory.ini")
        self.playbook_file = os.path.join(self.ansible_dir, "role_playbook.yml")
        self.role_playbook = os.path.join(self.ansible_dir, "role_playbook.yml")
        self.simple_test_playbook = os.path.join(self.ansible_dir, "simple_test_playbook.yml")
        self.minimal_test_playbook = os.path.join(self.ansible_dir, "minimal_test_playbook.yml")
        
        print(f"🔧 프로젝트 루트: {project_root}")
        print(f"🔧 Ansible 디렉토리: {self.ansible_dir}")
        print(f"🔧 Dynamic Inventory 스크립트: {self.dynamic_inventory_script}")
        print(f"🔧 Playbook 파일: {self.playbook_file}")
        print(f"🔧 Role Playbook 파일: {self.role_playbook}")
        
        # 파일 존재 확인
        if not os.path.exists(self.playbook_file):
            print(f"⚠️ 플레이북 파일이 존재하지 않습니다: {self.playbook_file}")
        else:
            print(f"✅ 플레이북 파일 확인됨: {self.playbook_file}")
        
        if not os.path.exists(self.role_playbook):
            print(f"⚠️ Role 플레이북 파일이 존재하지 않습니다: {self.role_playbook}")
        else:
            print(f"✅ Role 플레이북 파일 확인됨: {self.role_playbook}")
        
        if not os.path.exists(self.dynamic_inventory_script):
            print(f"⚠️ Dynamic Inventory 스크립트가 존재하지 않습니다: {self.dynamic_inventory_script}")
        else:
            print(f"✅ Dynamic Inventory 스크립트 확인됨: {self.dynamic_inventory_script}")
        
        # Ansible 변수 관리자 초기화
        self.variable_manager = AnsibleVariableManager(ansible_dir)
    

    
    def _run_ansible_command(self, command: List[str], cwd: str = None, env: Dict[str, str] = None) -> Tuple[int, str, str]:
        """Ansible 명령어 실행"""
        if cwd is None:
            cwd = self.ansible_dir
        
        print(f"🔧 작업 디렉토리: {cwd}")
        print(f"🔧 현재 작업 디렉토리: {os.getcwd()}")
        
        try:
            # 환경 변수 설정
            if env is None:
                env = os.environ.copy()
            else:
                base_env = os.environ.copy()
                base_env.update(env)
                env = base_env
            
            # SSH 설정 환경 변수 추가
            ssh_user = current_app.config.get('SSH_USER', 'rocky')
            ssh_private_key = current_app.config.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
            
            env['ANSIBLE_USER'] = ssh_user
            env['ANSIBLE_SSH_PRIVATE_KEY_FILE'] = ssh_private_key
            env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'  # 호스트 키 검증 비활성화
            env['ANSIBLE_PIPELINING'] = 'True'  # SSH 파이프라이닝으로 오버헤드 감소
            env['ANSIBLE_SSH_ARGS'] = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR'  # SSH 추가 옵션
            env['ANSIBLE_STDOUT_CALLBACK'] = 'yaml'  # 출력 포맷
            env['ANSIBLE_STDERR_CALLBACK'] = 'yaml'  # 에러 출력 포맷
            
            print(f"🔧 Ansible 명령어 실행: {' '.join(command)}")
            print(f"🔧 SSH 사용자: {ssh_user}")
            print(f"🔧 SSH 키: {ssh_private_key}")
            
            # Windows 환경에서 Ansible 명령어 경로 확인 및 수정
            if os.name == 'nt':  # Windows 환경
                # Windows에서 Ansible 실행 방법들 시도
                possible_commands = [
                    command,  # 원래 명령어
                    ['python', '-m', 'ansible'] + command[1:],  # Python 모듈로 실행
                    ['ansible.cmd'] + command[1:],  # .cmd 확장자
                    ['ansible.exe'] + command[1:],  # .exe 확장자
                ]
                
                for cmd in possible_commands:
                    try:
                        print(f"🔧 Windows에서 Ansible 명령어 시도: {' '.join(cmd)}")
                        result = subprocess.run(
                            cmd,
                            cwd=cwd,
                            env=env,
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=1800
                        )
                        
                        print(f"🔧 Ansible 명령어 완료: returncode={result.returncode}")
                        print(f"🔧 Ansible stdout: {result.stdout[:500]}..." if len(result.stdout) > 500 else f"🔧 Ansible stdout: {result.stdout}")
                        print(f"🔧 Ansible stderr: {result.stderr[:500]}..." if len(result.stderr) > 500 else f"🔧 Ansible stderr: {result.stderr}")
                        
                        return result.returncode, result.stdout, result.stderr
                        
                    except FileNotFoundError:
                        print(f"🔧 명령어 실패, 다음 시도: {' '.join(cmd)}")
                        continue
                    except Exception as e:
                        print(f"🔧 명령어 실행 중 오류: {e}")
                        continue
                
                # 모든 시도 실패
                error_msg = "Windows 환경에서 Ansible 명령어를 찾을 수 없습니다. Ansible이 설치되어 있고 PATH에 추가되었는지 확인하세요."
                logger.error(error_msg)
                return -1, "", error_msg
            else:
                # Linux/Mac 환경
                result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=1800
            )
                
                print(f"🔧 Ansible 명령어 완료: returncode={result.returncode}")
                print(f"🔧 Ansible stdout: {result.stdout[:500]}..." if len(result.stdout) > 500 else f"🔧 Ansible stdout: {result.stdout}")
                print(f"🔧 Ansible stderr: {result.stderr[:500]}..." if len(result.stderr) > 500 else f"🔧 Ansible stderr: {result.stderr}")
                
            return result.returncode, result.stdout, result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error("Ansible 명령어 실행 타임아웃")
            return -1, "", "Ansible 명령어 실행 타임아웃"
        except Exception as e:
            logger.error(f"Ansible 명령어 실행 실패: {e}")
            return -1, "", str(e)
    
    def create_inventory(self, servers: List[Dict[str, Any]]) -> bool:
        """Ansible 인벤토리 파일 생성"""
        try:
            inventory_content = []
            
            # SSH 설정 가져오기
            ssh_user = current_app.config.get('SSH_USER', 'rocky')
            ssh_private_key = current_app.config.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
            
            for server in servers:
                if server.get('ip_address'):
                    # SSH 사용자명과 키 설정을 포함한 인벤토리 항목
                    inventory_item = f"{server['ip_address']} ansible_user={ssh_user} ansible_ssh_private_key_file={ssh_private_key}"
                    inventory_content.append(inventory_item)
            
            # 인벤토리 파일 저장
            with open(self.inventory_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(inventory_content))
            
            logger.info(f"Ansible 인벤토리 파일 생성 성공: {len(inventory_content)}개 서버")
            return True
            
        except Exception as e:
            logger.error(f"Ansible 인벤토리 파일 생성 실패: {e}")
            return False
    
    def run_playbook(self, role: str, extra_vars: Dict[str, Any] = None, target_server: str = None, inventory: str = None, limit_hosts: str = None) -> Tuple[bool, str]:
        """Ansible 플레이북 실행 (ansible-runner 사용)

        Args:
            role: 실행할 역할(로le)
            extra_vars: 추가 변수
            target_server: 단일 서버 타겟(IP 또는 호스트) - 지정 시 단일 실행
            inventory: 정적 인벤토리 파일 경로 - 지정 시 이 인벤토리를 사용해 전체 실행
        """
        try:
            print(f"🔧 Ansible 플레이북 실행 시작: {role}")
            if target_server:
                print(f"🔧 대상 서버: {target_server}")
            
            if ANSIBLE_RUNNER_AVAILABLE:
                return self._run_playbook_with_runner(role, extra_vars, target_server, inventory, limit_hosts)
            else:
                return self._run_playbook_with_subprocess(role, extra_vars, target_server, inventory, limit_hosts)
                
        except Exception as e:
            logger.error(f"Ansible 플레이북 실행 실패: {e}")
            return False, str(e)
    
    def _run_playbook_with_runner(self, role: str, extra_vars: Dict[str, Any] = None, target_server: str = None, inventory: str = None, limit_hosts: str = None) -> Tuple[bool, str]:
        """ansible-runner를 사용한 플레이북 실행"""
        try:
            print(f"🔧 ansible-runner를 사용한 플레이북 실행: {role}")
            
            # 임시 디렉토리 생성
            with tempfile.TemporaryDirectory() as temp_dir:
            # 플레이북 파일 생성
                playbook_path = os.path.join(temp_dir, 'playbook.yml')
                playbook_content = [{
                'hosts': 'all',
                'become': True,
                'roles': [role]
                }]
            
            if extra_vars:
                playbook_content[0]['vars'] = extra_vars
                
                with open(playbook_path, 'w', encoding='utf-8') as f:
                    yaml.dump(playbook_content, f, default_flow_style=False, allow_unicode=True)
                
                # inventory 파일 복사 (지정된 인벤토리가 있으면 사용, 없으면 동적 인벤토리 스크립트 출력 사용 불가 → 정적 인벤토리 필요)
                inventory_path = os.path.join(temp_dir, 'inventory')
                src_path = inventory or self.inventory_file
                with open(src_path, 'r', encoding='utf-8') as src:
                    with open(inventory_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                
                # ansible-runner 실행
                print(f"🔧 ansible-runner 실행: {playbook_path}")
                run_kwargs = dict(
                    private_data_dir=temp_dir,
                    playbook='playbook.yml',
                    inventory=inventory_path,
                    quiet=False,
                    json_mode=False
                )
                if limit_hosts:
                    run_kwargs['limit'] = limit_hosts
                result = ansible_runner.run(**run_kwargs)
                
                print(f"🔧 ansible-runner 결과: returncode={result.rc}")
                print(f"🔧 ansible-runner 상태: {result.status}")
                
                if result.rc == 0:
                    success_msg = f"Ansible 플레이북 실행 성공 (role: {role})"
                    print(f"✅ {success_msg}")
                    return True, success_msg
                else:
                    error_msg = f"Ansible 플레이북 실행 실패 (role: {role}, returncode: {result.rc})"
                    print(f"❌ {error_msg}")
                    return False, error_msg
                    
        except Exception as e:
            error_msg = f"ansible-runner 실행 중 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    def _run_playbook_with_subprocess(self, role: str, extra_vars: Dict[str, Any] = None, target_server: str = None, inventory: str = None, limit_hosts: str = None) -> Tuple[bool, str]:
        """subprocess를 사용한 플레이북 실행 (기존 방식)"""
        try:
            print(f"🔧 subprocess를 사용한 플레이북 실행: {role}")
            
            # bulk/전체 실행에서도 role 변수가 필요하므로 보장
            extra_vars = extra_vars or {}
            if 'role' not in extra_vars:
                extra_vars['role'] = role

            # 대상 서버가 지정된 경우 개별 서버 플레이북 사용
            if target_server:
                print(f"🔧 개별 서버 플레이북 사용: {target_server}")
                
                # 개별 서버 플레이북에 extra_vars 추가
                extra_vars = extra_vars or {}
                extra_vars.update({
                    'target_server': target_server,
                    'role': role
                })
                
                # Ansible 플레이북 실행 (개별 서버 플레이북 사용)
                command = [
                'ansible-playbook',
                    '-i', self.dynamic_inventory_script,
                    self.role_playbook,
                    '--extra-vars', json.dumps(extra_vars),
                    '--limit', target_server,
                    '--ssh-common-args=-o StrictHostKeyChecking=no -o ControlMaster=auto -o ControlPersist=60s'
                ]
            else:
                # 전체 서버 대상 - 정적 인벤토리 또는 동적 인벤토리 사용
                print(f"🔧 전체 서버 플레이북 사용")
                
                # 역할 중심 플레이북 그대로 사용 (role_playbook.yml)
                command = ['ansible-playbook']
                if inventory and os.path.exists(inventory):
                    # 정적 인벤토리 사용
                    command.extend(['-i', inventory, self.role_playbook])
                else:
                    # 동적 인벤토리 스크립트 사용 (기존 동작 유지)
                    command.extend(['-i', self.dynamic_inventory_script, self.role_playbook])
                
                if extra_vars:
                    command.extend(['--extra-vars', json.dumps(extra_vars)])
                if limit_hosts:
                    command.extend(['--limit', limit_hosts])
                command.append('--ssh-common-args=-o StrictHostKeyChecking=no -o ControlMaster=auto -o ControlPersist=60s')
            
            print(f"🔧 Ansible 명령어: {' '.join(command)}")
            print(f"🔧 플레이북 파일 존재 확인: {os.path.exists(self.playbook_file)}")
            print(f"🔧 Dynamic Inventory 스크립트 존재 확인: {os.path.exists(self.dynamic_inventory_script)}")
            
            returncode, stdout, stderr = self._run_ansible_command(command)
            
            if returncode == 0:
                logger.info(f"Ansible 플레이북 실행 성공 (role: {role})")
                return True, stdout or f"Ansible 플레이북 실행 성공 (role: {role})"
            else:
                error_msg = stderr or stdout or f"알 수 없는 Ansible 플레이북 실행 오류 (role: {role})"
                logger.error(f"Ansible 플레이북 실행 실패 (role: {role}): {error_msg}")
                return False, error_msg
                
        except Exception as e:
            logger.error(f"subprocess Ansible 플레이북 실행 실패: {e}")
            return False, str(e)
    
    def assign_role_to_server(self, server_name: str, role: str, extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """서버에 역할 할당 (DB 기반)"""
        try:
            print(f"🔧 서버 역할 할당 시작: {server_name} - {role}")
            print(f"🔧 호출 스택: {__name__}.assign_role_to_server")
            print(f"🔧 매개변수: server_name={server_name}, role={role}, extra_vars={extra_vars}")
            
            # 1. DB에서 서버 정보 조회
            server = Server.get_by_name(server_name)
            if not server:
                return False, f"서버 {server_name}을 DB에서 찾을 수 없습니다"
            
            # 2. 현재 역할 확인 (로그용)
            current_role = server.role
            print(f"🔧 현재 역할: {current_role}")
            print(f"🔧 요청된 역할: {role}")
            
            # 3. 역할 변경 감지 및 제거 처리
            # 빈 문자열이나 None인 경우 역할 제거로 처리 (먼저 체크)
            if role is None or role.strip() == "" or role.lower() in ["none", "역할 없음", "no role"]:
                # 역할 제거 요청
                print(f"🔧 역할 제거 요청: {current_role} → 없음")
                
                # 1. DB에서 역할 제거
                server.role = None
                db.session.commit()
                print(f"✅ DB에서 역할 제거 완료: {server_name}")
                
                # 2. tfvars에서 역할 제거
                try:
                    from app.services.terraform_service import TerraformService
                    terraform_service = TerraformService()
                    
                    # tfvars 로드
                    tfvars = terraform_service.load_tfvars()
                    if 'servers' in tfvars and server_name in tfvars['servers']:
                        # 역할 제거 (빈 문자열로 설정)
                        tfvars['servers'][server_name]['role'] = ""
                        terraform_service.save_tfvars(tfvars)
                        print(f"✅ tfvars에서 역할 제거 완료: {server_name}")
                    else:
                        print(f"⚠️ tfvars에서 서버를 찾을 수 없음: {server_name}")
                except Exception as e:
                    print(f"⚠️ tfvars 업데이트 실패: {e}")
                
                print(f"✅ 역할 제거 시 Ansible 실행 생략 (불필요)")
                return True, f"서버 {server_name}에서 역할이 제거되었습니다"
            
            elif current_role == role:
                print(f"🔧 역할 변경 없음: {current_role} → {role}")
                # 역할이 같아도 Ansible 실행 (강제 적용)
                print(f"🔧 강제 Ansible 실행 진행")
            
            # 4. 서버 IP 주소 확인
            if not server.ip_address:
                return False, f"서버 {server_name}의 IP 주소가 설정되지 않았습니다"
            
            # 5. 서버 데이터 준비 (로그용)
            server_data = {
                'name': server.name,
                'role': role,
                'ip_address': server.ip_address
            }
            print(f"🔧 서버 데이터: {server_data}")
            print(f"🔧 Dynamic Inventory 스크립트 사용: {self.dynamic_inventory_script}")
            
            # 6. Node Exporter 자동 설치는 서버 생성 시에만 실행 (역할 부여 시에는 실행하지 않음)
            # self._install_node_exporter_if_needed(server_name, server.ip_address)
            
            # 7. 역할별 변수 설정 (새로운 변수 관리 시스템 사용)
            role_vars = self.variable_manager.get_ansible_extra_vars(role, extra_vars)
            
            print(f"🔧 역할 변수 설정: {role_vars}")
            
            # 8. 직접 Ansible 실행 (중복 실행 방지)
            print(f"🔧 직접 Ansible 실행: {server_name} - {role}")
            
            # 직접 run_playbook 호출 (중복 실행 방지)
            import time
            start_time = time.time()
            
            success, message = self.run_playbook(role, role_vars, target_server=server.ip_address)
            
            elapsed_time = time.time() - start_time
            
            if success:
                # DB 업데이트
                server.role = role
                db.session.commit()
                print(f"✅ DB 역할 업데이트 완료: {server_name} → {role}")
                
                # 3분 이상 걸린 경우 안내 메시지 추가
                if elapsed_time > 180:  # 3분 = 180초
                    message += f"\n\n⏰ 주의: Ansible 작업이 {elapsed_time:.1f}초 소요되었습니다.\n서버가 완전히 준비되지 않았을 수 있습니다. 잠시 후 다시 시도해보세요."
                
                return True, f"서버 {server_name}에 역할 {role}이 성공적으로 할당되었습니다"
            else:
                return False, f"Ansible 실행 실패: {message}"
            
        except Exception as e:
            logger.error(f"서버 {server_name}에 대한 역할 {role} 할당 실패: {e}")
            return False, str(e)
    
    def run_role_for_server(self, server_name: str, role: str, extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """특정 서버에 대해 역할 실행 (기존 호환성 유지)"""
        try:
            print(f"🔧 Ansible 역할 실행 시작: {server_name} - {role}")
            
            # 서버 정보 조회 (DB 또는 Proxmox에서)
            server_data = None
            
            # 1. DB에서 서버 정보 조회
            server = Server.get_by_name(server_name)
            if server:
                server_data = {
                    'name': server.name,
                    'role': server.role or role,
                    'networks': [{'ip': server.ip_address}] if server.ip_address else []
                }
                print(f"🔧 DB에서 서버 정보 조회: {server_data}")
            else:
                # 2. Proxmox에서 서버 정보 조회
                from app.services.proxmox_service import ProxmoxService
                proxmox_service = ProxmoxService()
                result = proxmox_service.get_all_vms()
                
                if result['success']:
                    servers = result['data']['servers']
                    for vm_key, s_data in servers.items():
                        if s_data.get('name') == server_name:
                            ip_addresses = s_data.get('ip_addresses', [])
                            if ip_addresses:
                                server_data = {
                                    'name': server_name,
                                    'role': role,
                                    'networks': [{'ip': ip_addresses[0]}]
                                }
                                print(f"🔧 Proxmox에서 서버 정보 조회: {server_data}")
                                break
            
            if not server_data:
                return False, f"서버 {server_name}의 정보를 찾을 수 없습니다"
            
            # 동적 inventory는 이미 스크립트로 처리되므로 별도 생성 불필요
            
            # 역할별 변수 설정 (새로운 변수 관리 시스템 사용)
            role_vars = self.variable_manager.get_ansible_extra_vars(role, extra_vars)
            
            print(f"🔧 역할 변수 설정: {role_vars}")
            
            # 플레이북 실행
            return self.run_playbook(role, role_vars)
            
        except Exception as e:
            logger.error(f"서버 {server_name}에 대한 역할 {role} 실행 실패: {e}")
            return False, str(e)
    
    def run_role_for_multiple_servers(self, servers: List[Dict[str, Any]], role: str, 
                                    extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """여러 서버에 대해 역할 실행 (동적 인벤토리 + --limit)

        - DB/파라미터 기반 서버 목록에서 IP만 추려서 --limit 로 한 번에 실행
        - 정적 인벤토리 파일 유지/생성 없이 동적 인벤토리 스크립트만 사용
        """
        try:
            # IP 주소가 있는 서버만 필터링
            valid_servers = [s for s in servers if s.get('ip_address')]
            
            if not valid_servers:
                return False, "유효한 IP 주소를 가진 서버가 없습니다"
            
            # --limit 에 사용할 호스트 목록 (IP 기준)
            limit_hosts = ','.join([s['ip_address'] for s in valid_servers])
            
            # 동적 인벤토리 + --limit 로 단 한 번 실행
            return self.run_playbook(role, extra_vars, target_server=None, inventory=None, limit_hosts=limit_hosts)
            
        except Exception as e:
            logger.error(f"여러 서버에 대한 역할 {role} 실행 실패: {e}")
            return False, str(e)
    
    def ping_servers(self, servers: List[Dict[str, Any]]) -> Dict[str, bool]:
        """서버 연결 테스트"""
        try:
            # 인벤토리 생성
            if not self.create_inventory(servers):
                return {}
            
            # ping 명령어 실행
            command = [
                'ansible', 'all', '-i', self.inventory_file,
                '-m', 'ping',
                '--ssh-common-args="-o StrictHostKeyChecking=no"'
            ]
            
            returncode, stdout, stderr = self._run_ansible_command(command)
            
            # 결과 파싱
            results = {}
            for server in servers:
                ip = server.get('ip_address')
                if ip:
                    # stdout에서 해당 IP의 ping 결과 확인
                    if ip in stdout and 'SUCCESS' in stdout:
                        results[ip] = True
                    else:
                        results[ip] = False
            
            return results
            
        except Exception as e:
            logger.error(f"서버 ping 테스트 실패: {e}")
            return {}
    
    def get_available_roles(self) -> List[str]:
        """사용 가능한 역할 목록 조회"""
        try:
            roles_dir = os.path.join(self.ansible_dir, "roles")
            if os.path.exists(roles_dir):
                return [d for d in os.listdir(roles_dir) 
                       if os.path.isdir(os.path.join(roles_dir, d))]
            return []
        except Exception as e:
            logger.error(f"사용 가능한 역할 목록 조회 실패: {e}")
            return []
    
    def validate_role(self, role: str) -> bool:
        """역할 유효성 검사"""
        try:
            role_dir = os.path.join(self.ansible_dir, "roles", role)
            tasks_file = os.path.join(role_dir, "tasks", "main.yml")
            return os.path.exists(tasks_file)
        except Exception as e:
            logger.error(f"역할 {role} 유효성 검사 실패: {e}")
            return False 
    
    def check_ansible_installation(self) -> Tuple[bool, str]:
        """Ansible 설치 상태 확인"""
        try:
            # ansible-runner가 있으면 사용 가능
            if ANSIBLE_RUNNER_AVAILABLE:
                return True, "ansible-runner를 사용하여 Ansible 실행 가능"
            
            if os.name == 'nt':  # Windows 환경
                # Windows에서 Ansible 설치 확인
                possible_commands = [
                    ['ansible', '--version'],
                    ['ansible.cmd', '--version'],
                    ['ansible.exe', '--version'],
                    ['python', '-m', 'ansible', '--version']
                ]
                
                for cmd in possible_commands:
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            return True, f"Ansible 설치됨: {' '.join(cmd)}"
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
                
                return False, "Windows에서 Ansible이 설치되지 않았습니다. 'pip install ansible' 또는 WSL을 사용하세요."
            else:
                # Linux/Mac 환경
                result = subprocess.run(
                    ['ansible', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, "Ansible 설치됨"
                else:
                    return False, "Linux/Mac에서 Ansible이 설치되지 않았습니다. 'sudo apt install ansible' 또는 'brew install ansible'을 사용하세요."
                    
        except Exception as e:
            return False, f"Ansible 설치 확인 중 오류: {str(e)}"

    def _update_prometheus_target(self, server_ip: str) -> None:
        """Prometheus에 Node Exporter 타겟 추가"""
        try:
            import subprocess
            
            print(f"🔧 Prometheus 타겟 업데이트 중: {server_ip}")
            
            # update_prometheus_targets.py 스크립트 실행
            result = subprocess.run([
                'python3', 'monitoring/update_prometheus_targets.py', 'add', server_ip, '9100'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"✅ Prometheus 타겟 추가 성공: {server_ip}:9100")
            else:
                print(f"⚠️ Prometheus 타겟 추가 실패: {server_ip}:9100")
                print(f"   오류: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️ Prometheus 타겟 업데이트 중 오류: {e}")

    def _update_tfvars_role(self, server_name: str, role: str) -> bool:
        """terraform.tfvars.json에서 서버 역할 업데이트"""
        try:
            from app.services.terraform_service import TerraformService
            terraform_service = TerraformService()
            
            # tfvars 로드
            tfvars = terraform_service.load_tfvars()
            if 'servers' in tfvars and server_name in tfvars['servers']:
                # 역할 업데이트
                tfvars['servers'][server_name]['role'] = role
                terraform_service.save_tfvars(tfvars)
                print(f"✅ tfvars에서 역할 업데이트 완료: {server_name} - {role}")
                return True
            else:
                print(f"⚠️ tfvars에서 서버를 찾을 수 없음: {server_name}")
                return False
        except Exception as e:
            print(f"⚠️ tfvars 업데이트 실패: {e}")
            return False

    def _run_ansible_async(self, server_name: str, role: str, extra_vars: Dict[str, Any] = None) -> str:
        """Ansible을 비동기로 실행하고 알림 생성"""
        def run_ansible():
            try:
                # Flask 앱 컨텍스트 생성
                from app import create_app
                app = create_app()
                with app.app_context():
                    print(f"🔧 비동기 Ansible 실행 시작: {server_name} - {role}")
                    
                    # 서버 정보 조회
                    server = Server.query.filter_by(name=server_name).first()
                    if not server or not server.ip_address:
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            f"서버 정보를 찾을 수 없거나 IP 주소가 설정되지 않았습니다.",
                            "error"
                        )
                        return
                
                    # 환경 변수 설정
                    env = os.environ.copy()
                    env['TARGET_SERVER_IP'] = server.ip_address
                    
                    # 역할 변수 설정 (새로운 변수 관리 시스템 사용)
                    role_vars = self.variable_manager.get_ansible_extra_vars(role, extra_vars)
                    role_vars['target_server'] = server.ip_address
                    
                    # Ansible 명령어 구성
                    command = [
                        'ansible-playbook',
                        '-i', self.dynamic_inventory_script,
                        self.role_playbook,
                        '--extra-vars', json.dumps(role_vars),
                        '--limit', server.ip_address,
                        '--ssh-common-args=-o StrictHostKeyChecking=no -o ControlMaster=auto -o ControlPersist=60s',
                        '-vv'  # 상세한 로그 출력
                    ]
                    
                    # Ansible 실행
                    print(f"🔧 Ansible 명령어 실행 시작: {' '.join(command)}")
                    returncode, stdout, stderr = self._run_ansible_command(command, env=env)
                    print(f"🔧 Ansible 실행 완료: returncode={returncode}")
                    print(f"🔧 Ansible stdout 길이: {len(stdout) if stdout else 0}")
                    
                    # Ansible 실행 성공 시 Prometheus 타겟 업데이트
                    if returncode == 0:
                        self._update_prometheus_target(server.ip_address)
                    print(f"🔧 Ansible stderr 길이: {len(stderr) if stderr else 0}")
                    
                    # 상세 로그 출력 (전체)
                    if stdout:
                        print(f"🔧 Ansible stdout (전체):")
                        print(stdout)
                    if stderr:
                        print(f"🔧 Ansible stderr (전체):")
                        print(stderr)
                    
                    if returncode == 0:
                        # 성공 시 DB 업데이트
                        server.role = role
                        db.session.commit()
                        self._update_tfvars_role(server_name, role)
                        
                        # 성공 로그 구성
                        success_log = f"""✅ Ansible 실행 성공
서버: {server_name}
역할: {role}
명령어: {' '.join(command)}

출력:
{stdout}"""
                        
                        print(f"🔧 알림 생성 시작: 성공 알림")
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 완료",
                            f"역할 '{role}'이 성공적으로 적용되었습니다.",
                            "success",
                            success_log
                        )
                        print(f"✅ 비동기 Ansible 실행 성공: {server_name} - {role}")
                        print(f"✅ 알림 생성 완료: 성공 알림")
                        print(f"🔧 성공 로그 길이: {len(success_log)}")
                    else:
                        # 실패 시 알림 (상세 로그 포함)
                        error_log = f"""❌ Ansible 실행 실패
서버: {server_name}
역할: {role}
명령어: {' '.join(command)}
Return Code: {returncode}

표준 출력:
{stdout}

오류 출력:
{stderr}"""
                        
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            f"Ansible 실행 중 오류가 발생했습니다. (Return Code: {returncode})",
                            "error",
                            error_log
                        )
                        print(f"❌ 비동기 Ansible 실행 실패: {server_name} - {role}")
                        
            except Exception as e:
                # Flask 컨텍스트가 없을 때도 알림 생성 시도
                try:
                    from app import create_app
                    app = create_app()
                    with app.app_context():
                        error_msg = f"비동기 Ansible 실행 중 예외 발생: {str(e)}"
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            error_msg,
                            "error"
                        )
                except:
                    print(f"❌ 알림 생성 실패: {e}")
                print(f"❌ 비동기 Ansible 실행 중 예외 발생: {str(e)}")
                
                # 예외 발생 시에도 로그 포함하여 알림 생성
                try:
                    from app import create_app
                    app = create_app()
                    with app.app_context():
                        error_log = f"""❌ Ansible 실행 중 예외 발생
서버: {server_name}
역할: {role}
예외: {str(e)}
타입: {type(e).__name__}"""
                        
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            f"Ansible 실행 중 예외가 발생했습니다: {type(e).__name__}",
                            "error",
                            error_log
                        )
                except:
                    pass
        
        # 백그라운드 스레드에서 실행
        thread = threading.Thread(target=run_ansible)
        thread.daemon = True
        thread.start()
        
        return f"Ansible 실행이 백그라운드에서 시작되었습니다. 완료 시 알림을 확인하세요."

    def _wait_for_server_ready(self, server_ip: str, max_attempts: int = 30, delay: int = 10) -> bool:
        """서버가 SSH 연결 가능할 때까지 대기"""
        import time
        import socket
        
        print(f"🔧 서버 준비 대기 중: {server_ip}")
        
        for attempt in range(max_attempts):
            try:
                # SSH 포트(22) 연결 테스트
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((server_ip, 22))
                sock.close()
                
                if result == 0:
                    print(f"✅ 서버 SSH 포트 연결 성공: {server_ip} (시도 {attempt + 1}/{max_attempts})")
                    # 추가로 잠시 대기 (SSH 서비스 완전 준비)
                    time.sleep(5)
                    return True
                else:
                    print(f"⏳ 서버 SSH 포트 연결 대기 중: {server_ip} (시도 {attempt + 1}/{max_attempts})")
                    
            except Exception as e:
                print(f"⏳ 서버 연결 테스트 중 오류: {e} (시도 {attempt + 1}/{max_attempts})")
            
            if attempt < max_attempts - 1:
                time.sleep(delay)
        
        print(f"❌ 서버 준비 대기 시간 초과: {server_ip}")
        return False

    def _install_node_exporter_if_needed(self, server_name: str, server_ip: str) -> bool:
        """Node Exporter 자동 설치 (모니터링 설정이 활성화된 경우)"""
        try:
            # 모니터링 설정 확인 (환경변수 기반)
            import os
            auto_install_node_exporter = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
            
            # Node Exporter 자동 설치가 비활성화된 경우 스킵
            if not auto_install_node_exporter:
                print(f"🔧 Node Exporter 자동 설치가 비활성화됨: {server_name}")
                return True
            
            print(f"🔧 Node Exporter 자동 설치 시작: {server_name} ({server_ip})")
            
            # 서버가 SSH 연결 가능할 때까지 대기
            if not self._wait_for_server_ready(server_ip):
                print(f"❌ 서버 준비 대기 실패: {server_ip}")
                return False
            
            # Node Exporter 설치 Playbook 경로
            node_exporter_playbook = os.path.join(self.ansible_dir, "install_node_exporter.yml")
            
            if not os.path.exists(node_exporter_playbook):
                print(f"⚠️ Node Exporter 설치 Playbook이 없습니다: {node_exporter_playbook}")
                return False
            
            # Node Exporter 설치 Playbook 실행 (--limit 옵션으로 특정 서버만 제한)
            success, result = self._run_node_exporter_playbook(
                playbook_file=node_exporter_playbook,
                extra_vars=None,  # extra_vars 제거, --limit 옵션만 사용
                target_server=server_ip
            )
            
            if success:
                print(f"✅ Node Exporter 설치 완료: {server_name} ({server_ip})")
                
                # Prometheus 설정에 서버 추가
                try:
                    from app.services.prometheus_service import PrometheusService
                    prometheus_service = PrometheusService()
                    prometheus_updated = prometheus_service.add_server_to_prometheus(server_ip)
                    
                    if prometheus_updated:
                        print(f"✅ Prometheus 설정 업데이트 완료: {server_ip}")
                    else:
                        print(f"⚠️ Prometheus 설정 업데이트 실패: {server_ip}")
                except Exception as e:
                    print(f"⚠️ Prometheus 설정 업데이트 중 오류: {e}")
                
                # 성공 알림 생성
                self._create_notification(
                    f"Node Exporter 설치 완료 - {server_name}",
                    f"서버 {server_name}에 Node Exporter가 성공적으로 설치되었습니다.\n메트릭 URL: http://{server_ip}:9100/metrics\nPrometheus 설정 업데이트: {'완료' if prometheus_updated else '실패'}",
                    "success"
                )
                return True
            else:
                print(f"❌ Node Exporter 설치 실패: {server_name} ({server_ip})")
                
                # 실패 알림 생성
                self._create_notification(
                    f"Node Exporter 설치 실패 - {server_name}",
                    f"서버 {server_name}에 Node Exporter 설치 중 오류가 발생했습니다.\n오류: {result}",
                    "error"
                )
                return False
                
        except Exception as e:
            print(f"❌ Node Exporter 자동 설치 중 오류: {e}")
            
            # 오류 알림 생성
            try:
                self._create_notification(
                    f"Node Exporter 설치 오류 - {server_name}",
                    f"서버 {server_name}에 Node Exporter 설치 중 예외가 발생했습니다.\n오류: {str(e)}",
                    "error"
                )
            except:
                pass
            
            return False

    def _run_node_exporter_playbook(self, playbook_file: str, extra_vars: Dict[str, Any] = None, target_server: str = None) -> Tuple[bool, str]:
        """Node Exporter 전용 Playbook 실행 (Dynamic Inventory 사용)"""
        try:
            print(f"🔧 Node Exporter Playbook 실행: {playbook_file}")
            print(f"🔧 대상 서버: {target_server}")
            
            # Dynamic Inventory 스크립트 경로
            dynamic_inventory_script = os.path.join(self.ansible_dir, "dynamic_inventory.py")
            
            if not os.path.exists(dynamic_inventory_script):
                print(f"❌ Dynamic Inventory 스크립트를 찾을 수 없습니다: {dynamic_inventory_script}")
                return False, "Dynamic Inventory 스크립트 없음"
            
            # Ansible 명령어 구성 (Dynamic Inventory 사용)
            cmd = [
                'ansible-playbook',
                '-i', dynamic_inventory_script,
                playbook_file,
                '--become',
                '--become-method=sudo',
                '--become-user=root',
                '--limit', target_server,  # 특정 서버만 제한
                '--ssh-common-args=-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=30',
                '--timeout=60'
            ]
            
            # 추가 변수 추가
            if extra_vars:
                for key, value in extra_vars.items():
                    cmd.extend(['-e', f'{key}={value}'])
            
            print(f"🔧 실행 명령어: {' '.join(cmd)}")
            
            # 환경변수 설정 (Dynamic Inventory에서 사용)
            env = os.environ.copy()
            env['TARGET_SERVER_IP'] = target_server
            
            # Ansible 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.ansible_dir,
                env=env
            )
            
            if result.returncode == 0:
                print(f"✅ Node Exporter Playbook 실행 성공")
                print(f"📋 실행 결과: {result.stdout}")
                return True, result.stdout
            else:
                print(f"❌ Node Exporter Playbook 실행 실패")
                print(f"📋 오류 내용: {result.stderr}")
                print(f"📋 표준 출력: {result.stdout}")
                return False, result.stderr
                
        except Exception as e:
            print(f"❌ Node Exporter Playbook 실행 중 오류: {e}")
            return False, str(e)

    def _run_node_exporter_playbook_batch(self, playbook_file: str, target_servers: List[str], extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """Node Exporter 일괄 설치 Playbook 실행 (여러 서버 동시 처리)"""
        try:
            print(f"🔧 Node Exporter 일괄 설치 시작: {len(target_servers)}개 서버")
            print(f"🔧 대상 서버들: {target_servers}")
            
            # Dynamic Inventory 스크립트 경로
            dynamic_inventory_script = os.path.join(self.ansible_dir, "dynamic_inventory.py")
            
            if not os.path.exists(dynamic_inventory_script):
                print(f"❌ Dynamic Inventory 스크립트를 찾을 수 없습니다: {dynamic_inventory_script}")
                return False, "Dynamic Inventory 스크립트 없음"
            
            # --limit 옵션으로 여러 서버 지정 (쉼표로 구분)
            limit_hosts = ','.join(target_servers)
            
            # Ansible 명령어 구성 (일괄 처리)
            cmd = [
                'ansible-playbook',
                '-i', dynamic_inventory_script,
                playbook_file,
                '--become',
                '--become-method=sudo',
                '--become-user=root',
                '--limit', limit_hosts,  # 여러 서버 동시 처리
                '--forks', '10',  # 병렬 처리 포크 수 (동시 실행할 서버 수)
                '--ssh-common-args=-o StrictHostKeyChecking=no -o ControlMaster=auto -o ControlPersist=60s'
            ]
            
            # 추가 변수 추가
            if extra_vars:
                for key, value in extra_vars.items():
                    cmd.extend(['-e', f'{key}={value}'])
            
            print(f"🔧 일괄 실행 명령어: {' '.join(cmd)}")
            
            # 환경변수 설정 (Dynamic Inventory에서 사용)
            env = os.environ.copy()
            # 일괄 처리 시에는 TARGET_SERVER_IP를 설정하지 않음 (모든 서버 대상)
            
            # Ansible 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.ansible_dir,
                env=env,
                timeout=1800  # 30분 타임아웃
            )
            
            if result.returncode == 0:
                print(f"✅ Node Exporter 일괄 설치 성공: {len(target_servers)}개 서버")
                return True, result.stdout
            else:
                print(f"❌ Node Exporter 일괄 설치 실패: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            print(f"❌ Node Exporter 일괄 설치 타임아웃: 30분 초과")
            return False, "일괄 설치 타임아웃 (30분 초과)"
        except Exception as e:
            print(f"❌ Node Exporter 일괄 설치 중 오류: {e}")
            return False, str(e)

    def _install_node_exporter_batch(self, server_ips: List[str]) -> Tuple[bool, str]:
        """Node Exporter 일괄 설치 (여러 서버 동시 처리)"""
        try:
            # 모니터링 설정 확인 (환경변수 기반)
            import os
            auto_install_node_exporter = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
            
            # Node Exporter 자동 설치가 비활성화된 경우 스킵
            if not auto_install_node_exporter:
                print(f"🔧 Node Exporter 자동 설치가 비활성화됨")
                return True, "Node Exporter 자동 설치 비활성화됨"
            
            print(f"🔧 Node Exporter 일괄 설치 시작: {len(server_ips)}개 서버")
            print(f"🔧 대상 서버 IP들: {server_ips}")
            
            # Node Exporter 설치 Playbook 경로
            node_exporter_playbook = os.path.join(self.ansible_dir, "install_node_exporter.yml")
            
            if not os.path.exists(node_exporter_playbook):
                print(f"⚠️ Node Exporter 설치 Playbook이 없습니다: {node_exporter_playbook}")
                return False, "Node Exporter 설치 Playbook 없음"
            
            # Node Exporter 일괄 설치 실행
            extra_vars = {
                'target_hosts': ','.join(server_ips)
            }
            
            # Node Exporter 일괄 설치 Playbook 실행
            success, result = self._run_node_exporter_playbook_batch(
                playbook_file=node_exporter_playbook,
                target_servers=server_ips,
                extra_vars=extra_vars
            )
            
            if success:
                print(f"✅ Node Exporter 일괄 설치 완료: {len(server_ips)}개 서버")
                
                # Prometheus 설정에 모든 서버 추가
                prometheus_updated_count = 0
                try:
                    from app.services.prometheus_service import PrometheusService
                    prometheus_service = PrometheusService()
                    
                    for server_ip in server_ips:
                        if prometheus_service.add_server_to_prometheus(server_ip):
                            prometheus_updated_count += 1
                            print(f"✅ Prometheus 설정 업데이트 완료: {server_ip}")
                        else:
                            print(f"⚠️ Prometheus 설정 업데이트 실패: {server_ip}")
                except Exception as e:
                    print(f"⚠️ Prometheus 설정 업데이트 중 오류: {e}")
                
                # 성공 알림 생성
                self._create_notification(
                    f"Node Exporter 일괄 설치 완료",
                    f"{len(server_ips)}개 서버에 Node Exporter가 성공적으로 설치되었습니다.\n대상 서버: {', '.join(server_ips)}\nPrometheus 설정 업데이트: {prometheus_updated_count}/{len(server_ips)}개 완료",
                    "success"
                )
                return True, f"일괄 설치 성공: {len(server_ips)}개 서버, Prometheus 업데이트: {prometheus_updated_count}개"
            else:
                print(f"❌ Node Exporter 일괄 설치 실패")
                
                # 실패 알림 생성
                self._create_notification(
                    f"Node Exporter 일괄 설치 실패",
                    f"{len(server_ips)}개 서버에 Node Exporter 설치 중 오류가 발생했습니다.\n대상 서버: {', '.join(server_ips)}\n오류: {result}",
                    "error"
                )
                return False, f"일괄 설치 실패: {result}"
                
        except Exception as e:
            print(f"❌ Node Exporter 일괄 설치 중 오류: {e}")
            
            # 오류 알림 생성
            try:
                self._create_notification(
                    f"Node Exporter 일괄 설치 오류",
                    f"{len(server_ips)}개 서버에 Node Exporter 설치 중 예외가 발생했습니다.\n대상 서버: {', '.join(server_ips)}\n오류: {str(e)}",
                    "error"
                )
            except:
                pass
            
            return False, f"일괄 설치 중 예외 발생: {str(e)}"

    def _create_notification(self, title: str, message: str, severity: str = "info", details: str = None):
        """알림 생성"""
        try:
            print(f"🔧 알림 생성 시작: {title}")
            notification = Notification(
                type="ansible_role",
                title=title,
                message=message,
                severity=severity,
                details=details,
                created_at=datetime.now()
            )
            db.session.add(notification)
            db.session.commit()
            print(f"✅ 알림 생성 완료: {title} (ID: {notification.id})")
        except Exception as e:
            print(f"❌ 알림 생성 실패: {e}")
            import traceback
            traceback.print_exc() 