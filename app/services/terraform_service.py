"""
Terraform 서비스
"""
import subprocess
import json
import os
import logging
import tempfile
from typing import Tuple, Dict, List, Any, Optional
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification

logger = logging.getLogger(__name__)

class TerraformService:
    """Terraform 서비스"""
    
    def __init__(self, terraform_dir: str = "terraform", remote_server: dict = None):
        self.terraform_dir = terraform_dir
        self.remote_server = remote_server
        self.is_remote = remote_server is not None
        
        # 로컬 환경: 상대 경로 사용
        if os.path.isabs(terraform_dir):
            self.tfvars_file = os.path.join(terraform_dir, "terraform.tfvars.json")
        else:
            # 상대 경로인 경우 프로젝트 루트 기준으로 절대 경로 생성
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.tfvars_file = os.path.join(project_root, terraform_dir, "terraform.tfvars.json")
    
    def _run_terraform_command(self, command: List[str], cwd: str = None) -> Tuple[int, str, str]:
        """Terraform 명령어 실행"""
        if self.is_remote:
            return self._run_remote_terraform_command(command, cwd)
        else:
            return self._run_local_terraform_command(command, cwd)
    
    def _run_local_terraform_command(self, command: List[str], cwd: str = None) -> Tuple[int, str, str]:
        """로컬 Terraform 명령어 실행"""
        if cwd is None:
            # 상대 경로인 경우 프로젝트 루트 기준으로 절대 경로 생성
            if os.path.isabs(self.terraform_dir):
                cwd = self.terraform_dir
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                cwd = os.path.join(project_root, self.terraform_dir)
        
        # SSL 검증 비활성화를 위한 환경변수 설정
        env = os.environ.copy()
        env['TF_VAR_proxmox_insecure'] = 'true'
        env['PROXMOX_INSECURE'] = 'true'
        
        print(f"🔧 Terraform 명령어 실행: {' '.join(command)} (cwd: {cwd})")
        print(f"🔍 현재 작업 디렉토리: {os.getcwd()}")
        print(f"🔍 Terraform 디렉토리 존재 여부: {os.path.exists(cwd)}")
        print(f"🔍 Terraform 명령어 존재 여부: {os.path.exists(os.path.join(cwd, 'terraform')) if os.path.exists(cwd) else False}")
        
        # PATH에서 terraform 명령어 찾기
        import shutil
        terraform_path = shutil.which('terraform')
        print(f"🔍 PATH에서 terraform 찾기: {terraform_path}")
        
        # terraform 디렉토리 내용 확인
        if os.path.exists(cwd):
            print(f"🔍 Terraform 디렉토리 내용: {os.listdir(cwd)}")
        else:
            print(f"❌ Terraform 디렉토리가 존재하지 않음: {cwd}")
        
        # terraform 명령어가 PATH에 없을 경우 대안
        if not terraform_path:
            print("❌ terraform 명령어를 PATH에서 찾을 수 없습니다.")
            print("💡 해결 방법:")
            print("   1. terraform이 설치되어 있는지 확인")
            print("   2. PATH에 terraform 경로가 추가되어 있는지 확인")
            print("   3. 또는 terraform 바이너리 경로를 직접 지정")
            
            # terraform 바이너리 직접 찾기
            possible_paths = [
                "/usr/local/bin/terraform",
                "/usr/bin/terraform", 
                "./terraform",
                "terraform"
            ]
            
            for path in possible_paths:
                if shutil.which(path):
                    print(f"✅ 대안 경로 발견: {path}")
                    command[0] = path
                    break
            else:
                print("❌ 사용 가능한 terraform 경로를 찾을 수 없습니다.")
        
        # Docker 컨테이너에서 호스트의 terraform 실행
        # 로컬 terraform 디렉토리에서 실행
        if os.path.exists("terraform"):
            print("✅ 로컬 terraform 디렉토리 발견: terraform")
            # terraform 바이너리 경로 확인
            terraform_binary_paths = [
                "/usr/local/bin/terraform",  # 호스트 terraform
                "/usr/bin/terraform",       # 호스트 terraform
                "terraform"                # PATH에서 찾기
            ]
            
            for path in terraform_binary_paths:
                if shutil.which(path):
                    print(f"✅ terraform 바이너리 발견: {path}")
                    command[0] = path
                    break
            else:
                print("❌ terraform 바이너리를 찾을 수 없습니다.")
                print("💡 해결 방법:")
                print("   1. 호스트에 terraform 설치 확인")
                print("   2. Docker 볼륨 마운트 확인")
                print("   3. terraform 디렉토리 내용 확인")
        else:
            print("❌ 마운트된 terraform 디렉토리를 찾을 수 없습니다.")
            print("💡 해결 방법:")
            print("   1. Docker 볼륨 마운트 확인")
            print("   2. terraform 디렉토리 존재 확인")
            print("   3. Docker 컨테이너 재시작")
        
        try:
            # 환경변수 설정 (Vault 토큰 포함)
            env = os.environ.copy()
            
            # Vault 환경변수 확인 및 설정
            vault_addr = os.environ.get('VAULT_ADDR')
            vault_token = os.environ.get('VAULT_TOKEN')
            tf_var_vault_token = os.environ.get('TF_VAR_vault_token')
            tf_var_vault_address = os.environ.get('TF_VAR_vault_address')
            
            # Terraform 변수 자동 매핑
            terraform_mappings = {
                'PROXMOX_HDD_DATASTORE': 'TF_VAR_proxmox_hdd_datastore',
                'PROXMOX_SSD_DATASTORE': 'TF_VAR_proxmox_ssd_datastore',
                'ENVIRONMENT': 'TF_VAR_environment'
            }
            
            for source_var, target_var in terraform_mappings.items():
                value = os.environ.get(source_var)
                if value and not os.environ.get(target_var):
                    env[target_var] = value
                    print(f"🔧 {source_var} → {target_var}: {value}")
            
            print(f"🔧 Vault 환경변수 확인:")
            print(f"   VAULT_ADDR: {vault_addr}")
            print(f"   VAULT_TOKEN: {'설정됨' if vault_token else '없음'}")
            print(f"   TF_VAR_vault_token: {'설정됨' if tf_var_vault_token else '없음'}")
            print(f"   TF_VAR_vault_address: {tf_var_vault_address}")
            print(f"   TF_VAR_proxmox_hdd_datastore: {env.get('TF_VAR_proxmox_hdd_datastore', '없음')}")
            print(f"   TF_VAR_proxmox_ssd_datastore: {env.get('TF_VAR_proxmox_ssd_datastore', '없음')}")
            
            # Windows 환경에서 인코딩 문제 해결을 위해 UTF-8 명시적 지정
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,  # 환경변수 전달
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # 디코딩 에러 시 대체 문자 사용
                timeout=300  # 5분 타임아웃
            )
            print(f"🔧 Terraform 명령어 완료: returncode={result.returncode}")
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error("Terraform 명령어 실행 타임아웃")
            print("❌ Terraform 명령어 실행 타임아웃")
            return -1, "", "Terraform 명령어 실행 타임아웃"
        except Exception as e:
            logger.error(f"Terraform 명령어 실행 실패: {e}")
            print(f"❌ Terraform 명령어 실행 실패: {e}")
            return -1, "", str(e)
    
    def init(self) -> bool:
        """Terraform 초기화"""
        logger.info("Terraform 초기화 시작")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "init"])
        
        if returncode == 0:
            logger.info("Terraform 초기화 성공")
            return True
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 초기화 오류"
            logger.error(f"Terraform 초기화 실패: {error_msg}")
            return False
    
    def plan(self) -> Tuple[bool, str]:
        """Terraform 계획"""
        logger.info("Terraform 계획 시작")
        print("🔧 Terraform plan 명령어 실행")
        
        # 실행 중인 VM의 파괴적 변경 감지 및 차단
        try:
            destructive_changes = self.detect_destructive_changes()
            if destructive_changes:
                error_msg = f"실행 중인 서버의 파괴적 변경이 감지되어 차단되었습니다:\n{destructive_changes}"
                print(f"❌ {error_msg}")
                return False, error_msg
        except Exception as plan_check_err:
            print(f"⚠️ 파괴적 변경 감지 중 경고: {plan_check_err}")
        
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "plan"])
        print(f"🔧 Terraform plan 결과: returncode={returncode}, stdout_length={len(stdout) if stdout else 0}, stderr_length={len(stderr) if stderr else 0}")
        
        if returncode == 0:
            logger.info("Terraform 계획 성공")
            result_msg = stdout or "Terraform 계획이 성공적으로 완료되었습니다."
            print(f"✅ Terraform 계획 성공: {len(result_msg)} 문자")
            return True, result_msg
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 계획 오류"
            logger.error(f"Terraform 계획 실패: {error_msg}")
            print(f"❌ Terraform 계획 실패: {error_msg}")
            return False, error_msg
    
    def apply(self, targets: List[str] = None, lock_timeout: str = "180s") -> Tuple[bool, str]:
        """Terraform 적용
        
        Args:
            targets: 특정 리소스만 대상으로 적용할 때 사용 (예: ["module.server[\"server1\"]"])
        """
        logger.info("Terraform 적용 시작")
        command = ["terraform", "apply", "-auto-approve", f"-lock-timeout={lock_timeout}"]
        
        if targets:
            for target in targets:
                command.extend(["-target", target])
            logger.info(f"Targeted apply 실행: {targets}")
            print(f"🔧 Targeted Terraform apply 실행: {targets}")
        
        returncode, stdout, stderr = self._run_terraform_command(command)
        
        if returncode == 0:
            logger.info("Terraform 적용 성공")
            return True, stdout or "Terraform 적용이 성공적으로 완료되었습니다."
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 적용 오류"
            logger.error(f"Terraform 적용 실패: {error_msg}")
            return False, error_msg
    
    def destroy(self, target: str = None) -> Tuple[bool, str]:
        """Terraform 삭제 (단일 타겟)"""
        logger.info("Terraform 삭제 시작")
        command = ["terraform", "destroy", "-auto-approve"]
        if target:
            command.extend(["-target", target])
        
        returncode, stdout, stderr = self._run_terraform_command(command)
        
        if returncode == 0:
            logger.info("Terraform 삭제 성공")
            return True, stdout or "Terraform 삭제가 성공적으로 완료되었습니다."
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 삭제 오류"
            logger.error(f"Terraform 삭제 실패: {error_msg}")
            return False, error_msg
    
    def destroy_targets(self, targets: List[str]) -> Tuple[bool, str]:
        """Terraform 대량 삭제 (여러 타겟)
        
        Args:
            targets: 삭제할 리소스 목록 (예: ["module.server[\"server1\"]", "module.server[\"server2\"]"])
        """
        if not targets:
            return False, "삭제할 타겟이 지정되지 않았습니다."
        
        logger.info(f"Terraform 대량 삭제 시작: {targets}")
        command = ["terraform", "destroy", "-auto-approve"]
        
        # 모든 타겟을 -target 옵션으로 추가
        for target in targets:
            command.extend(["-target", target])
        
        logger.info(f"Targeted destroy 실행: {targets}")
        print(f"🔥 Targeted Terraform destroy 실행: {targets}")
        
        returncode, stdout, stderr = self._run_terraform_command(command)
        
        if returncode == 0:
            logger.info(f"Terraform 대량 삭제 성공: {targets}")
            return True, stdout or f"{len(targets)}개 리소스 삭제가 성공적으로 완료되었습니다."
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 삭제 오류"
            logger.error(f"Terraform 대량 삭제 실패: {error_msg}")
            return False, error_msg
    
    def output(self) -> Dict[str, Any]:
        """Terraform 출력값 조회"""
        logger.info("Terraform 출력값 조회")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "output", "-json"])
        
        if returncode == 0:
            try:
                return json.loads(stdout) if stdout.strip() else {}
            except json.JSONDecodeError:
                logger.error("Terraform 출력값 파싱 실패")
                return {}
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 출력값 조회 오류"
            logger.error(f"Terraform 출력값 조회 실패: {error_msg}")
            return {}
    
    def load_tfvars(self) -> Dict[str, Any]:
        """terraform.tfvars.json 파일 로드"""
        try:
            if os.path.exists(self.tfvars_file):
                with open(self.tfvars_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"terraform.tfvars.json 파일이 존재하지 않습니다: {self.tfvars_file}")
                return {}
        except Exception as e:
            logger.error(f"terraform.tfvars.json 파일 로드 실패: {e}")
            return {}

    def sync_tfvars_with_proxmox(self) -> Dict[str, Any]:
        """Proxmox의 실제 VM 상태를 기준으로 tfvars를 안전하게 동기화

        - 살아있는(실행 중) VM은 삭제/생성 같은 파괴적 변경에서 제외
        - 수동 변경(코어/메모리 등) 발생 시, tfvars에 반영하여 drift 최소화
        """
        try:
            from app.services.proxmox_service import ProxmoxService
            prox = ProxmoxService()

            # 인증 및 VM 목록
            headers, error = prox.get_proxmox_auth()
            if error:
                raise RuntimeError(f"Proxmox 인증 실패: {error}")
            vms, error = prox.get_proxmox_vms(headers)
            if error:
                raise RuntimeError(f"VM 목록 조회 실패: {error}")

            # tfvars 로드
            tfvars = self.load_tfvars()
            servers = tfvars.get('servers', {})

            updated = 0
            protected = []

            # VM 이름 기준으로 매핑
            vm_by_name = {vm['name']: vm for vm in vms}

            for name, cfg in list(servers.items()):
                vm = vm_by_name.get(name)
                if not vm:
                    # tfvars에는 있는데 실제 VM이 없으면 유지(생성 대상)로 둠
                    continue

                # 실행 중인 VM은 파괴적 변경 보호를 위해 플래그만 남김
                if vm.get('status') == 'running':
                    cfg.setdefault('_protect_running', True)
                    protected.append(name)

                # 드리프트 최소화: Proxmox의 실제 CPU/메모리 값을 tfvars에 반영
                try:
                    # CPU 값 동기화
                    vm_cpu = vm.get('cpus', 0)
                    if vm_cpu and vm_cpu != cfg.get('cpu', 0):
                        print(f"🔄 {name}: CPU {cfg.get('cpu', 0)} → {vm_cpu} (Proxmox 기준으로 동기화)")
                        cfg['cpu'] = int(vm_cpu)
                        updated += 1
                    
                    # 메모리 값 동기화 (MB 단위)
                    vm_memory_mb = int((vm.get('maxmem', 0)) / (1024*1024))
                    if vm_memory_mb and vm_memory_mb != cfg.get('memory', 0):
                        print(f"🔄 {name}: 메모리 {cfg.get('memory', 0)}MB → {vm_memory_mb}MB (Proxmox 기준으로 동기화)")
                        cfg['memory'] = int(vm_memory_mb)
                        updated += 1
                        
                except Exception as e:
                    print(f"⚠️ {name} 리소스 동기화 실패: {e}")

                servers[name] = cfg

            # 저장
            tfvars['servers'] = servers
            self.save_tfvars(tfvars)

            return {'updated': updated, 'protected': protected}

        except Exception as e:
            raise

    def detect_destructive_changes(self) -> str:
        """실행 중인 VM의 파괴적 변경(destroy/recreate) 감지"""
        try:
            from app.services.proxmox_service import ProxmoxService
            prox = ProxmoxService()

            # Proxmox에서 실행 중인 VM 목록 조회
            headers, error = prox.get_proxmox_auth()
            if error:
                return f"Proxmox 인증 실패: {error}"
            
            vms, error = prox.get_proxmox_vms(headers)
            if error:
                return f"VM 목록 조회 실패: {error}"

            # tfvars 로드
            tfvars = self.load_tfvars()
            servers = tfvars.get('servers', {})

            # 실행 중인 VM만 필터링
            running_vms = {vm['name']: vm for vm in vms if vm.get('status') == 'running'}
            
            destructive_changes = []
            
            for name, vm in running_vms.items():
                if name not in servers:
                    continue
                
                tfvars_config = servers[name]
                
                # CPU 변경 감지
                tfvars_cpu = tfvars_config.get('cpu', 0)
                vm_cpu = vm.get('cpus', 0)
                if tfvars_cpu != vm_cpu:
                    destructive_changes.append(f"- {name}: CPU {vm_cpu} → {tfvars_cpu} (재생성 필요)")
                
                # 메모리 변경 감지 (MB 단위로 변환)
                tfvars_memory = tfvars_config.get('memory', 0)
                vm_memory_mb = int((vm.get('maxmem', 0)) / (1024*1024))
                if tfvars_memory != vm_memory_mb:
                    destructive_changes.append(f"- {name}: 메모리 {vm_memory_mb}MB → {tfvars_memory}MB (재생성 필요)")
                
                # 디스크 변경 감지 (크기나 스토리지)
                # ... 추가 디스크 변경 감지 로직 필요시 여기에 추가

            if destructive_changes:
                return "\n".join(destructive_changes)
            
            return ""

        except Exception as e:
            return f"파괴적 변경 감지 중 오류: {str(e)}"
    
    def save_tfvars(self, data: Dict[str, Any]) -> bool:
        """terraform.tfvars.json 파일 저장"""
        try:
            with open(self.tfvars_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("terraform.tfvars.json 파일 저장 성공")
            return True
        except Exception as e:
            logger.error(f"terraform.tfvars.json 파일 저장 실패: {e}")
            return False
    
    def delete_server_config(self, server_name: str) -> bool:
        """terraform.tfvars.json에서 서버 설정 삭제"""
        try:
            # 기존 tfvars 로드
            tfvars = self.load_tfvars()
            servers = tfvars.get('servers', {})
            
            # 해당 서버가 존재하는지 확인
            if server_name not in servers:
                logger.warning(f"서버 {server_name}가 tfvars에 존재하지 않습니다.")
                return False
            
            # 서버 설정 삭제
            del servers[server_name]
            tfvars['servers'] = servers
            
            # 수정된 tfvars 저장
            success = self.save_tfvars(tfvars)
            
            if success:
                logger.info(f"✅ 서버 설정 삭제 성공: {server_name}")
            else:
                logger.error(f"❌ 서버 설정 삭제 실패: {server_name}")
                
            return success
            
        except Exception as e:
            logger.error(f"서버 설정 삭제 중 오류: {e}")
            return False
    
    def create_server_config(self, server_data: Dict[str, Any]) -> bool:
        """서버 설정 생성"""
        try:
            print(f"🔧 create_server_config 시작: {server_data.get('name', 'unknown')}")
            # 기존 설정 로드
            tfvars = self.load_tfvars()
            print(f"🔧 기존 tfvars 로드 완료: {len(tfvars)} 항목")
            
            # 서버 설정 추가
            if 'servers' not in tfvars:
                tfvars['servers'] = {}
            
            server_name = server_data['name']
            
            # 서버 데이터 상세 로그
            print(f"🔧 서버 데이터 상세 정보:")
            print(f"   서버명: {server_name}")
            print(f"   전체 데이터: {json.dumps(server_data, indent=2)}")
            
            # 디스크 정보 상세 로그 및 기본값 보정
            if 'disks' in server_data:
                print(f"🔧 디스크 정보:")
                for i, disk in enumerate(server_data['disks']):
                    # file_format 기본값 보정: raw 강제 (요구사항)
                    if not disk.get('file_format') or str(disk.get('file_format')).lower() in ('auto', 'qcow2', 'none', 'null'):
                        disk['file_format'] = 'raw'
                    print(f"   디스크 {i}: {disk}")
                    if 'datastore_id' in disk:
                        print(f"     datastore_id: {disk['datastore_id']}")
                    if 'disk_type' in disk:
                        print(f"     disk_type: {disk['disk_type']}")
            
            tfvars['servers'][server_name] = server_data
            print(f"🔧 서버 설정 추가 완료: {server_name}")
            
            # Proxmox 설정 자동 추가 (없는 경우에만)
            if 'proxmox_endpoint' not in tfvars:
                try:
                    from config.config import Config
                except ImportError:
                    # 대안 방법으로 config 로드
                    import importlib.util
                    import os
                    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'config.py')
                    spec = importlib.util.spec_from_file_location("config", config_path)
                    config_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(config_module)
                    Config = config_module.Config
                tfvars['proxmox_endpoint'] = Config.PROXMOX_ENDPOINT
                tfvars['proxmox_username'] = Config.PROXMOX_USERNAME
                tfvars['proxmox_node'] = Config.PROXMOX_NODE
                tfvars['proxmox_datastore'] = Config.PROXMOX_DATASTORE
                print("🔧 Proxmox 설정 자동 추가 완료")
            
            # VM 기본 설정 추가 (없는 경우에만)
            if 'vm_username' not in tfvars:
                try:
                    from config.config import Config
                except ImportError:
                    # 대안 방법으로 config 로드
                    import importlib.util
                    import os
                    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'config.py')
                    spec = importlib.util.spec_from_file_location("config", config_path)
                    config_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(config_module)
                    Config = config_module.Config
                tfvars['vm_username'] = Config.SSH_USER
                print("🔧 VM 기본 설정 자동 추가 완료")
            
            # 설정 저장
            result = self.save_tfvars(tfvars)
            print(f"🔧 tfvars 저장 결과: {result}")
            return result
            
        except Exception as e:
            print(f"💥 create_server_config 실패: {e}")
            logger.error(f"서버 설정 생성 실패: {e}")
            return False
    
    def test_ssh_connection(self, server_name: str, ip_address: str, username: str = None) -> Tuple[bool, str]:
        """SSH 연결 테스트"""
        try:
            import paramiko
            import socket
            
            if username is None:
                try:
                    from config.config import Config
                except ImportError:
                    # 대안 방법으로 config 로드
                    import importlib.util
                    import os
                    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'config.py')
                    spec = importlib.util.spec_from_file_location("config", config_path)
                    config_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(config_module)
                    Config = config_module.Config
                username = Config.SSH_USER
            
            # SSH 클라이언트 생성
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # SSH 키 파일 경로
            try:
                from config.config import Config
            except ImportError:
                # 대안 방법으로 config 로드
                import importlib.util
                import os
                config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'config.py')
                spec = importlib.util.spec_from_file_location("config", config_path)
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)
                Config = config_module.Config
            ssh_key_path = Config.SSH_PRIVATE_KEY_PATH.replace('~', os.path.expanduser('~'))
            
            print(f"🔍 SSH 연결 테스트: {username}@{ip_address}")
            print(f"🔑 SSH 키 경로: {ssh_key_path}")
            
            # SSH 연결 시도
            ssh.connect(
                hostname=ip_address,
                username=username,
                key_filename=ssh_key_path,
                timeout=10,
                banner_timeout=10
            )
            
            # 간단한 명령어 실행 테스트
            stdin, stdout, stderr = ssh.exec_command('echo "SSH 연결 성공"')
            result = stdout.read().decode().strip()
            
            ssh.close()
            
            print(f"✅ SSH 연결 성공: {result}")
            return True, f"SSH 연결 성공: {result}"
            
        except paramiko.AuthenticationException:
            error_msg = f"SSH 인증 실패: {username}@{ip_address}"
            print(f"❌ {error_msg}")
            return False, error_msg
        except paramiko.SSHException as e:
            error_msg = f"SSH 연결 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
        except socket.timeout:
            error_msg = f"SSH 연결 시간 초과: {ip_address}"
            print(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"SSH 연결 테스트 실패: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    def remove_server_config(self, server_name: str) -> bool:
        """서버 설정 제거"""
        try:
            # 기존 설정 로드
            tfvars = self.load_tfvars()
            
            # 서버 설정 제거
            if 'servers' in tfvars and server_name in tfvars['servers']:
                del tfvars['servers'][server_name]
                
                # 설정 저장
                return self.save_tfvars(tfvars)
            
            return True
            
        except Exception as e:
            logger.error(f"서버 설정 제거 실패: {e}")
            return False
    
    def deploy_infrastructure(self) -> Tuple[bool, str]:
        """인프라 배포"""
        try:
            print("🔧 deploy_infrastructure 시작")
            
            # 배포 전 Proxmox 실제 상태와 tfvars 일치화 (수동 변경 대비)
            try:
                sync_changed = self.sync_tfvars_with_proxmox()
                print(f"🧭 프리플라이트 동기화 완료: 변경된 서버 수={sync_changed.get('updated', 0)}")
            except Exception as pre_err:
                print(f"⚠️ 프리플라이트 동기화 경고: {pre_err}")
            
            # tfvars 파일 존재 확인
            if not os.path.exists(self.tfvars_file):
                error_msg = f"terraform.tfvars.json 파일이 존재하지 않습니다: {self.tfvars_file}"
                print(f"❌ {error_msg}")
                return False, error_msg
            
            # tfvars 파일 내용 확인
            try:
                tfvars = self.load_tfvars()
                if not tfvars or 'servers' not in tfvars:
                    error_msg = "terraform.tfvars.json 파일에 서버 설정이 없습니다."
                    print(f"❌ {error_msg}")
                    return False, error_msg
                print(f"✅ tfvars 파일 로드 성공: {len(tfvars.get('servers', {}))}개 서버")
            except Exception as e:
                error_msg = f"tfvars 파일 로드 실패: {e}"
                print(f"❌ {error_msg}")
                return False, error_msg
            
            # 초기화
            print("🔧 Terraform 초기화 시작")
            if not self.init():
                print("❌ Terraform 초기화 실패")
                return False, "Terraform 초기화 실패"
            print("✅ Terraform 초기화 완료")
            
            # 계획
            print("🔧 Terraform 계획 시작")
            plan_success, plan_output = self.plan()
            print(f"🔧 Terraform 계획 결과: success={plan_success}, output_length={len(plan_output) if plan_output else 0}")
            if not plan_success:
                print(f"❌ Terraform 계획 실패: {plan_output}")
                return False, f"Terraform 계획 실패: {plan_output}"
            print("✅ Terraform 계획 완료")
            
            # 적용
            print("🔧 Terraform 적용 시작")
            apply_success, apply_output = self.apply()
            if not apply_success:
                print(f"❌ Terraform 적용 실패: {apply_output}")
                return False, f"Terraform 적용 실패: {apply_output}"
            print("✅ Terraform 적용 완료")
            
            print("✅ 인프라 배포 성공")
            return True, "인프라 배포 성공"
            
        except Exception as e:
            print(f"💥 deploy_infrastructure 실패: {e}")
            logger.error(f"인프라 배포 실패: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def destroy_infrastructure(self, server_name: str = None) -> Tuple[bool, str]:
        """인프라 삭제"""
        try:
            target = None
            if server_name:
                target = f"module.server[\"{server_name}\"]"
            
            success, output = self.destroy(target)
            return success, output
            
        except Exception as e:
            logger.error(f"인프라 삭제 실패: {e}")
            return False, str(e)

    def delete_server(self, server_name: str) -> Dict[str, Any]:
        """서버 삭제 (중지 후 Terraform apply)
        
        @deprecated: 이 메서드는 더 이상 권장되지 않습니다. 
        대신 destroy_targets() 메서드를 사용하세요.
        """
        try:
            print(f"🔧 서버 삭제 시작: {server_name}")
            
            # 1. 먼저 서버 중지
            print(f"🔧 서버 중지 시작: {server_name}")
            from app.services.proxmox_service import ProxmoxService
            proxmox_service = ProxmoxService()
            stop_result = proxmox_service.stop_server(server_name)
            
            if not stop_result['success']:
                print(f"❌ 서버 중지 실패: {server_name} - {stop_result['message']}")
                return {
                    'success': False,
                    'message': f'서버 중지 실패: {stop_result["message"]}'
                }
            
            print(f"✅ 서버 중지 완료: {server_name}")
            
            # 2. 잠시 대기 (서버 중지 완료 대기)
            import time
            print(f"⏳ 서버 중지 완료 대기: {server_name}")
            time.sleep(10)
            
            # 3. tfvars.json에서 서버 설정 제거
            print(f"🔧 tfvars.json에서 서버 설정 제거: {server_name}")
            if not self.remove_server_config(server_name):
                return {
                    'success': False,
                    'message': f'서버 설정 제거 실패: {server_name}'
                }
            
            # 4. Terraform 적용 (변경사항 적용으로 서버 삭제)
            print(f"🔧 Terraform apply로 서버 삭제 시작: {server_name}")
            success, message = self.deploy_infrastructure()
            
            if success:
                print(f"✅ Terraform으로 서버 삭제 성공: {server_name}")
                return {
                    'success': True,
                    'message': f'서버 {server_name}이 중지 후 Terraform으로 삭제되었습니다.'
                }
            else:
                print(f"❌ Terraform으로 서버 삭제 실패: {server_name} - {message}")
                return {
                    'success': False,
                    'message': f'Terraform 서버 삭제 실패: {message}'
                }
                
        except Exception as e:
            error_msg = f'서버 삭제 중 오류: {str(e)}'
            print(f"💥 서버 삭제 예외: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
    
    def _run_remote_terraform_command(self, command: List[str], cwd: str = None) -> Tuple[int, str, str]:
        """원격 서버에서 Terraform 명령어 실행"""
        import paramiko
        
        try:
            # SSH 연결 설정
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 원격 서버 연결 (SSH 키 우선, 패스워드 대안)
            if self.remote_server.get('key_file'):
                # SSH 키 기반 인증 (권장)
                ssh.connect(
                    hostname=self.remote_server['host'],
                    port=self.remote_server.get('port', 22),
                    username=self.remote_server['username'],
                    key_filename=self.remote_server.get('key_file')
                )
            elif self.remote_server.get('password'):
                # 패스워드 기반 인증
                ssh.connect(
                    hostname=self.remote_server['host'],
                    port=self.remote_server.get('port', 22),
                    username=self.remote_server['username'],
                    password=self.remote_server.get('password')
                )
            else:
                # SSH 에이전트 사용 (가장 간단)
                ssh.connect(
                    hostname=self.remote_server['host'],
                    port=self.remote_server.get('port', 22),
                    username=self.remote_server['username']
                )
            
            # 원격 디렉토리 설정
            if cwd is None:
                remote_cwd = self.remote_server.get('terraform_dir', '/opt/terraform')
            else:
                remote_cwd = cwd
            
            # 명령어 실행
            full_command = f"cd {remote_cwd} && {' '.join(command)}"
            print(f"🔧 원격 Terraform 명령어 실행: {full_command}")
            
            stdin, stdout, stderr = ssh.exec_command(full_command)
            
            # 결과 수집
            returncode = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')
            
            ssh.close()
            
            return returncode, stdout_text, stderr_text
            
        except Exception as e:
            logger.error(f"원격 Terraform 실행 실패: {str(e)}")
            return 1, "", str(e) 