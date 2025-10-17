"""
Prometheus 서비스
"""
import yaml
import os
import subprocess
import logging
from typing import List, Dict, Any
from app.models.server import Server
from app import db

logger = logging.getLogger(__name__)

class PrometheusService:
    """Prometheus 서비스"""
    
    def __init__(self):
        # Docker 모니터링 시스템 우선, 그 다음 환경별 경로 사용
        current_dir = os.getcwd()
        monitoring_path = os.path.join(current_dir, "monitoring", "prometheus.yml")
        
        print(f"🔧 PrometheusService 초기화")
        print(f"🔧 현재 작업 디렉토리: {current_dir}")
        print(f"🔧 모니터링 경로 확인: {monitoring_path}")
        print(f"🔧 모니터링 파일 존재: {os.path.exists(monitoring_path)}")
        
        if os.path.exists(monitoring_path):
            self.prometheus_config_path = monitoring_path
            self.is_docker_mode = True
            print(f"✅ Docker 모드 활성화: {self.prometheus_config_path}")
        elif os.path.exists("monitoring/prometheus.yml"):
            self.prometheus_config_path = "monitoring/prometheus.yml"
            self.is_docker_mode = True
            print(f"✅ Docker 모드 활성화 (상대경로): {self.prometheus_config_path}")
        elif os.name == 'nt':  # Windows
            self.prometheus_config_path = "prometheus.yml"
            self.is_docker_mode = False
            print(f"ℹ️ Windows 모드: {self.prometheus_config_path}")
        else:  # Linux/Unix
            self.prometheus_config_path = "/etc/prometheus/prometheus.yml"
            self.is_docker_mode = False
            print(f"ℹ️ Linux 모드: {self.prometheus_config_path}")
        
        self.node_exporter_port = 9100
        print(f"🔧 Docker 모드: {self.is_docker_mode}")
        print(f"🔧 설정 파일 경로: {self.prometheus_config_path}")
        
    def update_prometheus_config(self, server_ips: List[str] = None) -> bool:
        """Prometheus 설정 파일 업데이트 (기존 설정 유지)"""
        try:
            # 서버 IP 목록이 제공되지 않으면 DB에서 가져오기
            if server_ips is None:
                servers = Server.query.filter(Server.ip_address.isnot(None)).all()
                server_ips = []
                for server in servers:
                    if server.ip_address:
                        # IP 주소에서 첫 번째 IP 추출
                        first_ip = server.ip_address.split(',')[0].strip()
                        if first_ip and first_ip not in server_ips:
                            server_ips.append(first_ip)
            
            print(f"🔧 Prometheus 설정 업데이트: {len(server_ips)}개 서버")
            
            # 기존 설정 파일 읽기 (존재하는 경우)
            config = None
            if os.path.exists(self.prometheus_config_path):
                try:
                    with open(self.prometheus_config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    print(f"✅ 기존 Prometheus 설정 파일 로드 완료")
                except Exception as e:
                    print(f"⚠️ 기존 설정 파일 로드 실패: {e}")
                    config = None
            
            # 기존 설정이 없으면 기본 설정 생성
            if config is None:
                config = {
                    'global': {
                        'scrape_interval': '15s',
                        'evaluation_interval': '15s'
                    },
                    'rule_files': [],
                    'scrape_configs': [
                        {
                            'job_name': 'prometheus',
                            'static_configs': [
                                {'targets': ['prometheus:9090' if self.is_docker_mode else 'localhost:9090']}
                            ]
                        }
                    ]
                }
                print(f"🔧 기본 Prometheus 설정 생성")
            
            # Node Exporter job 찾기 또는 생성
            node_exporter_job = None
            for job in config['scrape_configs']:
                if job['job_name'] in ['node-exporter', 'proxmox-servers']:
                    node_exporter_job = job
                    break
            
            if node_exporter_job:
                # 기존 job 업데이트
                node_exporter_targets = [f"{ip}:{self.node_exporter_port}" for ip in server_ips]
                node_exporter_job['static_configs'][0]['targets'] = node_exporter_targets
                node_exporter_job['scrape_interval'] = '10s'
                if 'metrics_path' not in node_exporter_job:
                    node_exporter_job['metrics_path'] = '/metrics'
                print(f"🔧 기존 job 업데이트: {node_exporter_job['job_name']} - {node_exporter_targets}")
            else:
                # 새 job 생성
                if server_ips:
                    node_exporter_targets = [f"{ip}:{self.node_exporter_port}" for ip in server_ips]
                    config['scrape_configs'].append({
                        'job_name': 'node-exporter',
                        'scrape_interval': '10s',
                        'static_configs': [
                            {'targets': node_exporter_targets}
                        ],
                        'metrics_path': '/metrics'
                    })
                    print(f"🔧 새 Node Exporter job 생성: {node_exporter_targets}")
            
            # 설정 파일에 쓰기 (권한 문제 해결)
            if self._write_config_file(config):
                print(f"✅ Prometheus 설정 파일 업데이트 완료: {self.prometheus_config_path}")
            else:
                raise Exception("설정 파일 쓰기 실패")
            
            # Prometheus 서비스 재시작
            return self._restart_prometheus()
            
        except Exception as e:
            print(f"❌ Prometheus 설정 업데이트 실패: {e}")
            logger.error(f"Prometheus 설정 업데이트 실패: {e}")
            return False
    
    def add_server_to_prometheus(self, server_ip: str) -> bool:
        """새 서버를 Prometheus 설정에 추가"""
        try:
            print(f"🔧 Prometheus에 서버 추가: {server_ip}")
            
            # 현재 설정 파일 읽기
            if os.path.exists(self.prometheus_config_path):
                with open(self.prometheus_config_path, 'r') as f:
                    config = yaml.safe_load(f)
            else:
                # 기본 설정 생성
                config = {
                    'global': {
                        'scrape_interval': '15s',
                        'evaluation_interval': '15s'
                    },
                    'rule_files': [],
                    'scrape_configs': [
                        {
                            'job_name': 'prometheus',
                            'static_configs': [
                                {'targets': ['prometheus:9090' if self.is_docker_mode else 'localhost:9090']}
                            ]
                        }
                    ]
                }
            
            # Node Exporter job 찾기 또는 생성
            node_exporter_job = None
            for job in config['scrape_configs']:
                if job['job_name'] == 'node-exporter':
                    node_exporter_job = job
                    break
            
            if not node_exporter_job:
                # Node Exporter job 생성
                node_exporter_job = {
                    'job_name': 'node-exporter',
                    'scrape_interval': '10s',
                    'static_configs': [
                        {'targets': []}
                    ],
                    'metrics_path': '/metrics'
                }
                config['scrape_configs'].append(node_exporter_job)
            
            # 새 타겟 추가
            new_target = f"{server_ip}:{self.node_exporter_port}"
            targets = node_exporter_job['static_configs'][0]['targets']
            
            if new_target not in targets:
                targets.append(new_target)
                print(f"🔧 Node Exporter 타겟 추가: {new_target}")
                
                # 설정 파일에 쓰기 (권한 문제 해결)
                if not self._write_config_file(config):
                    raise Exception("설정 파일 쓰기 실패")
                
                print(f"✅ Prometheus 설정에 서버 추가 완료: {server_ip}")
                
                # Prometheus 서비스 재시작
                return self._restart_prometheus()
            else:
                print(f"ℹ️ 서버가 이미 Prometheus 설정에 존재: {server_ip}")
                return True
                
        except Exception as e:
            print(f"❌ Prometheus에 서버 추가 실패: {e}")
            logger.error(f"Prometheus에 서버 추가 실패: {e}")
            return False
    
    def remove_server_from_prometheus(self, server_ip: str) -> bool:
        """서버를 Prometheus 설정에서 제거"""
        try:
            print(f"🔧 Prometheus에서 서버 제거: {server_ip}")
            
            # 현재 설정 파일 읽기
            if not os.path.exists(self.prometheus_config_path):
                print(f"⚠️ Prometheus 설정 파일이 없습니다: {self.prometheus_config_path}")
                return True
            
            with open(self.prometheus_config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Node Exporter job에서 타겟 제거
            target_to_remove = f"{server_ip}:{self.node_exporter_port}"
            
            for job in config['scrape_configs']:
                if job['job_name'] == 'node-exporter':
                    targets = job['static_configs'][0]['targets']
                    if target_to_remove in targets:
                        targets.remove(target_to_remove)
                        print(f"🔧 Node Exporter 타겟 제거: {target_to_remove}")
                        
                        # 설정 파일에 쓰기 (권한 문제 해결)
                        if not self._write_config_file(config):
                            raise Exception("설정 파일 쓰기 실패")
                        
                        print(f"✅ Prometheus 설정에서 서버 제거 완료: {server_ip}")
                        
                        # Prometheus 서비스 재시작
                        return self._restart_prometheus()
                    break
            
            print(f"ℹ️ 서버가 Prometheus 설정에 존재하지 않음: {server_ip}")
            return True
                
        except Exception as e:
            print(f"❌ Prometheus에서 서버 제거 실패: {e}")
            logger.error(f"Prometheus에서 서버 제거 실패: {e}")
            return False
    
    def get_manual_setup_instructions(self) -> str:
        """수동 설정 안내 메시지 생성"""
        return f"""
🔧 Prometheus 수동 설정 안내:

1. sudo 권한 설정:
   sudo visudo
   # 다음 줄 추가: username ALL=(ALL) NOPASSWD: /bin/mv, /bin/chown

2. 또는 수동으로 설정 파일 복사:
   sudo cp /tmp/prometheus_config_*.yml /etc/prometheus/prometheus.yml
   sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
   sudo systemctl restart prometheus

3. Prometheus 서비스 상태 확인:
   sudo systemctl status prometheus
   curl http://localhost:9090/targets
"""

    def _check_file_permissions(self) -> Dict[str, Any]:
        """Prometheus 설정 파일 권한 확인"""
        try:
            # Docker 모드에서는 권한 문제 없음
            if self.is_docker_mode:
                return {
                    'exists': True,
                    'readable': True,
                    'writable': True,
                    'owner': 'docker',
                    'permissions': 'docker_mode',
                    'docker_mode': True
                }
            
            if not os.path.exists(self.prometheus_config_path):
                return {
                    'exists': False,
                    'readable': False,
                    'writable': False,
                    'owner': None,
                    'permissions': None
                }
            
            # 파일 정보 수집
            stat_info = os.stat(self.prometheus_config_path)
            
            # 권한 확인
            readable = os.access(self.prometheus_config_path, os.R_OK)
            writable = os.access(self.prometheus_config_path, os.W_OK)
            
            # 소유자 정보 (가능한 경우)
            owner = None
            try:
                import pwd
                owner = pwd.getpwuid(stat_info.st_uid).pw_name
            except (ImportError, KeyError):
                owner = f"UID:{stat_info.st_uid}"
            
            return {
                'exists': True,
                'readable': readable,
                'writable': writable,
                'owner': owner,
                'permissions': oct(stat_info.st_mode),
                'uid': stat_info.st_uid,
                'gid': stat_info.st_gid
            }
            
        except Exception as e:
            print(f"❌ 파일 권한 확인 실패: {e}")
            return {
                'exists': False,
                'readable': False,
                'writable': False,
                'owner': None,
                'permissions': None,
                'error': str(e)
            }

    def _check_sudo_permissions(self) -> bool:
        """sudo 권한 확인"""
        try:
            # sudo 명령어 존재 확인
            result = subprocess.run(['which', 'sudo'], capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ sudo 명령어가 설치되지 않았습니다")
                return False
            
            # sudo 권한 테스트
            test_result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
            if test_result.returncode == 0:
                print("✅ sudo 권한이 설정되어 있습니다")
                return True
            else:
                print("⚠️ sudo 권한이 설정되어 있지 않습니다")
                print(f"📋 sudo 테스트 결과: {test_result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ sudo 권한 확인 실패: {e}")
            return False

    def _check_user_groups(self) -> List[str]:
        """현재 사용자의 그룹 확인"""
        try:
            import grp
            import os
            
            # 현재 사용자의 그룹 ID 목록
            user_groups = os.getgroups()
            group_names = []
            
            for gid in user_groups:
                try:
                    group_info = grp.getgrgid(gid)
                    group_names.append(group_info.gr_name)
                except KeyError:
                    group_names.append(f"gid:{gid}")
            
            return group_names
            
        except Exception as e:
            print(f"❌ 사용자 그룹 확인 실패: {e}")
            return []

    def _try_prometheus_group_access(self) -> bool:
        """prometheus 그룹 접근 시도"""
        try:
            # prometheus 그룹 확인
            import grp
            try:
                prometheus_group = grp.getgrnam('prometheus')
                print(f"📋 prometheus 그룹 정보: GID={prometheus_group.gr_gid}")
            except KeyError:
                print("❌ prometheus 그룹이 존재하지 않습니다")
                return False
            
            # 현재 사용자의 그룹 확인
            user_groups = self._check_user_groups()
            print(f"📋 현재 사용자 그룹: {user_groups}")
            
            if 'prometheus' in user_groups:
                print("✅ prometheus 그룹에 속해있습니다")
                return True
            else:
                print("⚠️ prometheus 그룹에 속해있지 않습니다")
                return False
                
        except Exception as e:
            print(f"❌ prometheus 그룹 접근 확인 실패: {e}")
            return False

    def _write_config_file(self, config: Dict[str, Any]) -> bool:
        """Prometheus 설정 파일에 쓰기 (권한 문제 해결)"""
        try:
            # Docker 모드에서는 직접 쓰기 (권한 문제 없음)
            if self.is_docker_mode:
                with open(self.prometheus_config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                print(f"✅ Docker 모드: Prometheus 설정 파일 업데이트 완료")
                return True
            
            if os.name == 'nt':  # Windows
                # Windows에서는 직접 쓰기
                with open(self.prometheus_config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                return True
            else:  # Linux/Unix
                # 파일 권한 확인
                file_perms = self._check_file_permissions()
                print(f"🔧 파일 권한 확인: {file_perms}")
                
                # 방법 1: 직접 파일 수정 시도
                try:
                    print("🔧 직접 파일 수정 시도...")
                    with open(self.prometheus_config_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                    print("✅ 직접 파일 수정 성공")
                    return True
                except PermissionError as perm_error:
                    print(f"⚠️ 직접 파일 수정 실패 (권한 부족): {perm_error}")
                    print(f"📋 파일 소유자: {file_perms.get('owner', 'unknown')}")
                    print(f"📋 파일 권한: {file_perms.get('permissions', 'unknown')}")
                    print(f"📋 쓰기 권한: {file_perms.get('writable', False)}")
                    
                    # prometheus 그룹 접근 시도
                    if self._try_prometheus_group_access():
                        print("🔧 prometheus 그룹 접근으로 재시도...")
                        try:
                            with open(self.prometheus_config_path, 'w') as f:
                                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                            print("✅ prometheus 그룹 접근으로 파일 수정 성공")
                            return True
                        except PermissionError:
                            print("⚠️ prometheus 그룹 접근으로도 실패")
                    
                    # 방법 2: 임시 파일 생성 후 sudo로 이동
                    temp_config_path = f"/tmp/prometheus_config_{os.getpid()}.yml"
                    
                    # 임시 파일에 설정 쓰기
                    with open(temp_config_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                    
                    # sudo 권한 확인
                    if not self._check_sudo_permissions():
                        print("🔧 sudo 권한이 없으므로 수동 설정 안내를 제공합니다")
                        
                        # 수동 설정 안내
                        print("🔧 수동 설정 안내:")
                        print(f"1. 임시 파일을 수동으로 복사하세요:")
                        print(f"   sudo cp {temp_config_path} {self.prometheus_config_path}")
                        print(f"2. 파일 소유자를 변경하세요:")
                        print(f"   sudo chown prometheus:prometheus {self.prometheus_config_path}")
                        print(f"3. Prometheus 서비스를 재시작하세요:")
                        print(f"   sudo systemctl restart prometheus")
                        print(f"4. 임시 파일을 정리하세요:")
                        print(f"   rm {temp_config_path}")
                        
                        # 임시 파일 경로를 반환하여 사용자가 수동으로 처리할 수 있도록 함
                        raise Exception(f"sudo 권한이 필요합니다. 수동 설정을 위해 임시 파일이 생성되었습니다: {temp_config_path}")
                    
                    # sudo로 임시 파일을 실제 위치로 이동
                    try:
                        # sudo 명령어 실행
                        mv_result = subprocess.run([
                            'sudo', 'mv', temp_config_path, self.prometheus_config_path
                        ], capture_output=True, text=True, check=True)
                        
                        # 파일 소유자를 prometheus로 변경
                        chown_result = subprocess.run([
                            'sudo', 'chown', 'prometheus:prometheus', self.prometheus_config_path
                        ], capture_output=True, text=True, check=True)
                        
                        print("✅ sudo를 통한 파일 이동 성공")
                        return True
                        
                    except subprocess.CalledProcessError as e:
                        # sudo 실패 시 임시 파일 정리
                        if os.path.exists(temp_config_path):
                            os.remove(temp_config_path)
                        raise Exception(f"sudo 권한이 필요합니다: {e.stderr}")
                    
        except Exception as e:
            print(f"❌ 설정 파일 쓰기 실패: {e}")
            return False

    def _restart_prometheus(self) -> bool:
        """Prometheus 서비스 재시작 (자동 리로드 우선 시도)"""
        try:
            print("🔧 Prometheus 설정 적용 중...")
            
            # Docker 모드에서는 컨테이너 재시작
            if self.is_docker_mode:
                print("🔧 Docker 모드: Prometheus 컨테이너 재시작 중...")
                try:
                    # 현재 디렉토리에서 monitoring 디렉토리로 이동하여 실행
                    result = subprocess.run(
                        ['docker-compose', 'restart', 'prometheus'],
                        cwd='monitoring',
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        print("✅ Docker Prometheus 컨테이너 재시작 성공")
                        return True
                    else:
                        print(f"⚠️ docker-compose 실패, docker compose 시도: {result.stderr}")
                        # docker compose 명령어 시도 (최신 Docker)
                        result = subprocess.run(
                            ['docker', 'compose', 'restart', 'prometheus'],
                            cwd='monitoring',
                            capture_output=True, text=True, timeout=30
                        )
                        if result.returncode == 0:
                            print("✅ Docker Compose v2 Prometheus 컨테이너 재시작 성공")
                            return True
                        else:
                            print(f"⚠️ Docker Compose v2 재시작도 실패: {result.stderr}")
                except Exception as e:
                    print(f"⚠️ Docker Prometheus 컨테이너 재시작 오류: {e}")
                return True
            
            # Windows 환경에서는 서비스 재시작 스킵
            if os.name == 'nt':
                print("ℹ️ Windows 환경에서는 Prometheus 서비스 재시작을 스킵합니다.")
                return True
            
            # Prometheus 설정 파일 검증
            print(f"🔧 Docker 모드 상태: {self.is_docker_mode}")
            print(f"🔧 설정 파일 경로: {self.prometheus_config_path}")
            
            # Docker 모드이거나 monitoring/ 경로를 사용하는 경우 promtool 검증 스킵
            is_monitoring_path = 'monitoring' in self.prometheus_config_path
            if self.is_docker_mode or is_monitoring_path:
                print("ℹ️ Docker/모니터링 모드: promtool 검증을 스킵합니다.")
            else:
                print("🔧 Prometheus 설정 파일 검증 중...")
                try:
                    result = subprocess.run(
                        ['promtool', 'check', 'config', self.prometheus_config_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode != 0:
                        print(f"❌ Prometheus 설정 파일 검증 실패: {result.stderr}")
                        return False
                    else:
                        print("✅ Prometheus 설정 파일 검증 성공")
                except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                    print(f"⚠️ promtool 실행 실패: {e}")
                    print("⚠️ 설정 파일 검증을 스킵하고 계속 진행합니다.")
                except Exception as e:
                    print(f"⚠️ promtool 실행 중 오류: {e}")
                    print("⚠️ 설정 파일 검증을 스킵하고 계속 진행합니다.")
            
            # 방법 1: Prometheus API를 통한 설정 리로드 (가장 빠름)
            try:
                print("🔧 Prometheus API를 통한 설정 리로드 시도...")
                import requests
                import time
                
                # Prometheus API로 설정 리로드
                reload_response = requests.post('http://localhost:9090/-/reload', timeout=10)
                
                if reload_response.status_code == 200:
                    print("✅ Prometheus API 설정 리로드 성공")
                    
                    # 잠시 대기 후 타겟 상태 확인
                    time.sleep(2)
                    
                    # 타겟 상태 확인
                    targets_response = requests.get('http://localhost:9090/api/v1/targets', timeout=10)
                    if targets_response.status_code == 200:
                        print("✅ Prometheus 타겟 상태 확인 성공")
                        return True
                    else:
                        print("⚠️ Prometheus 타겟 상태 확인 실패")
                        return False
                else:
                    print(f"⚠️ Prometheus API 설정 리로드 실패: {reload_response.status_code}")
            except Exception as api_error:
                print(f"⚠️ Prometheus API 설정 리로드 오류: {api_error}")
            
            # 방법 2: sudo systemctl reload 시도 (설정만 다시 로드)
            try:
                print("🔧 sudo systemctl reload 시도...")
                result = subprocess.run(
                    ['sudo', 'systemctl', 'reload', 'prometheus'],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if result.returncode == 0:
                    print("✅ sudo systemctl reload 성공")
                    return True
                else:
                    print(f"⚠️ sudo systemctl reload 실패: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("⚠️ sudo systemctl reload 타임아웃")
            except Exception as reload_error:
                print(f"⚠️ sudo systemctl reload 오류: {reload_error}")
            
            # 방법 3: sudo systemctl restart 시도 (가장 확실한 방법)
            try:
                print("🔧 sudo systemctl restart 시도...")
                result = subprocess.run(
                    ['sudo', 'systemctl', 'restart', 'prometheus'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    print("✅ sudo systemctl restart 성공")
                    
                    # 서비스 상태 확인
                    status_result = subprocess.run(
                        ['sudo', 'systemctl', 'is-active', 'prometheus'],
                        capture_output=True,
                        text=True
                    )
                    
                    if status_result.returncode == 0 and status_result.stdout.strip() == 'active':
                        print("✅ Prometheus 서비스가 정상적으로 실행 중입니다")
                        return True
                    else:
                        print("⚠️ Prometheus 서비스 상태 확인 실패")
                        return False
                else:
                    print(f"❌ sudo systemctl restart 실패: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("⚠️ sudo systemctl restart 타임아웃")
            except Exception as restart_error:
                print(f"❌ sudo systemctl restart 오류: {restart_error}")
            
            # 방법 4: systemctl reload 시도 (권한 확인)
            try:
                print("🔧 systemctl reload 시도...")
                result = subprocess.run(
                    ['systemctl', 'reload', 'prometheus'],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if result.returncode == 0:
                    print("✅ systemctl reload 성공")
                    return True
                else:
                    print(f"⚠️ systemctl reload 실패: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("⚠️ systemctl reload 타임아웃")
            except Exception as reload_error:
                print(f"⚠️ systemctl reload 오류: {reload_error}")
            
            # 방법 5: 수동 재시작 안내
            print("🔧 수동 재시작 안내:")
            print("   sudo systemctl restart prometheus")
            print("   또는")
            print("   sudo systemctl reload prometheus")
            
            return False
                    
        except Exception as e:
            print(f"❌ Prometheus 서비스 재시작 중 오류: {e}")
            logger.error(f"Prometheus 서비스 재시작 중 오류: {e}")
            return False
    
    def get_prometheus_targets(self) -> List[str]:
        """현재 Prometheus 타겟 목록 조회"""
        try:
            if not os.path.exists(self.prometheus_config_path):
                return []
            
            with open(self.prometheus_config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            targets = []
            for job in config.get('scrape_configs', []):
                if job['job_name'] == 'node-exporter':
                    for static_config in job.get('static_configs', []):
                        targets.extend(static_config.get('targets', []))
                    break
            
            return targets
            
        except Exception as e:
            print(f"❌ Prometheus 타겟 조회 실패: {e}")
            logger.error(f"Prometheus 타겟 조회 실패: {e}")
            return []
    
    def remove_servers_from_prometheus(self, server_ips: List[str]) -> bool:
        """Prometheus 설정에서 특정 서버 IP들을 제거"""
        try:
            if not os.path.exists(self.prometheus_config_path):
                logger.warning("⚠️ Prometheus 설정 파일이 존재하지 않습니다.")
                return False
            
            # 현재 설정 로드
            with open(self.prometheus_config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # node-exporter job 찾기
            node_exporter_job = None
            for job in config.get('scrape_configs', []):
                if job['job_name'] == 'node-exporter':
                    node_exporter_job = job
                    break
            
            if not node_exporter_job:
                logger.warning("⚠️ node-exporter job을 찾을 수 없습니다.")
                return False
            
            # 제거할 IP들을 포트와 함께 변환
            targets_to_remove = [f"{ip}:{self.node_exporter_port}" for ip in server_ips]
            
            # static_configs에서 해당 타겟들 제거
            updated_targets = []
            for static_config in node_exporter_job.get('static_configs', []):
                current_targets = static_config.get('targets', [])
                # 제거할 타겟들을 필터링
                filtered_targets = [target for target in current_targets if target not in targets_to_remove]
                if filtered_targets:  # 빈 리스트가 아닌 경우만 유지
                    static_config['targets'] = filtered_targets
                    updated_targets.extend(filtered_targets)
            
            # 빈 static_configs 제거
            node_exporter_job['static_configs'] = [sc for sc in node_exporter_job.get('static_configs', []) if sc.get('targets')]
            
            # 설정 파일 저장
            with open(self.prometheus_config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"✅ Prometheus 설정에서 {len(targets_to_remove)}개 타겟 제거 완료")
            logger.info(f"🔧 제거된 타겟: {targets_to_remove}")
            logger.info(f"🔧 남은 타겟 수: {len(updated_targets)}")
            
            # Prometheus 서비스 재시작
            if self.is_docker_mode:
                self._restart_docker_prometheus()
            else:
                self._restart_systemd_prometheus()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Prometheus 설정에서 서버 제거 실패: {e}")
            return False
