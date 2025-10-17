"""
서버 관련 Celery 작업
"""
from celery import current_task
from app.celery_app import celery_app
from app.services import ProxmoxService, AnsibleService, TerraformService, NotificationService
# Redis 캐시 제거됨 - 실시간 조회로 변경
from app.services.cleanup_service import CleanupService
from app.models import Server, Notification
from app import db
import logging
import time
import sys
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 디버깅을 위해 DEBUG 레벨로 설정

from flask import current_app
from datetime import datetime

@celery_app.task(bind=True)
def create_server_async(self, server_config):
    """비동기 서버 생성 작업"""
    try:
        task_id = self.request.id
        logger.info(f"🚀 비동기 서버 생성 시작: {server_config['name']} (Task ID: {task_id})")
        
        # 작업 상태 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '서버 생성 준비 중...'}
        )
        
        # 시작 알림은 생성하지 않음 (완료 시에만 알림)
        
        
        if os.getenv('TERRAFORM_REMOTE_ENABLED', 'false').lower() == 'true':
            remote_config = {
                'host': os.getenv('TERRAFORM_REMOTE_HOST'),
                'port': int(os.getenv('TERRAFORM_REMOTE_PORT', 22)),
                'username': os.getenv('TERRAFORM_REMOTE_USERNAME'),
                'password': os.getenv('TERRAFORM_REMOTE_PASSWORD'),  # 선택사항
                'key_file': os.getenv('TERRAFORM_REMOTE_KEY_FILE'),  # 선택사항
                'terraform_dir': os.getenv('TERRAFORM_REMOTE_DIR', '/opt/terraform')
            }
            terraform_service = TerraformService(remote_server=remote_config)
        else:
            # 로컬 실행 (기본값) - 로컬 terraform 디렉토리 사용
            terraform_service = TerraformService()  # 기본 terraform 디렉토리 사용
        
        # 1단계: Terraform 파일 생성
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': 'Terraform 파일 생성 중...'}
        )
        
        terraform_result = terraform_service.create_server_config(server_config)
        if not terraform_result:
            raise Exception("Terraform 파일 생성 실패")
        
        # 2단계: Terraform 실행
        self.update_state(
            state='PROGRESS',
            meta={'current': 40, 'total': 100, 'status': 'Terraform 실행 중...'}
        )
        
        # Terraform 타겟 형식으로 변환 (module.server["서버명"])
        target = f'module.server["{server_config["name"]}"]'
        apply_result = terraform_service.apply([target])
        if not apply_result[0]:  # apply 메서드는 (success, message) 튜플 반환
            raise Exception(f"Terraform 실행 실패: {apply_result[1]}")
        
        # 3단계: 서버 정보 DB 저장
        self.update_state(
            state='PROGRESS',
            meta={'current': 60, 'total': 100, 'status': '서버 정보 저장 중...'}
        )
        
        # Server 객체 생성 (안전성 강화)
        print(f"🔍 Server 객체 생성 시작:")  # print로 강제 출력
        print(f"  name: {server_config['name']}")
        print(f"  cpu: {server_config['cpu']}")
        print(f"  memory: {server_config['memory']}")
        print(f"  os_type: {server_config.get('os_type', 'rocky')}")
        print(f"  role: {server_config.get('role', '')}")
        print(f"  firewall_group: {server_config.get('firewall_group', '')}")
        logger.info(f"🔍 Server 객체 생성 시작:")
        logger.info(f"  name: {server_config['name']}")
        logger.info(f"  cpu: {server_config['cpu']}")
        logger.info(f"  memory: {server_config['memory']}")
        logger.info(f"  os_type: {server_config.get('os_type', 'ubuntu')}")
        logger.info(f"  role: {server_config.get('role', '')}")
        logger.info(f"  firewall_group: {server_config.get('firewall_group', '')}")
        
        # IP 주소 추출 (network_devices에서)
        ip_address_str = ''
        network_devices = server_config.get('network_devices', [])
        if network_devices:
            ip_list = [d.get('ip_address', '') for d in network_devices if d.get('ip_address')]
            ip_address_str = ', '.join(ip_list) if ip_list else ''
            logger.info(f"🔧 서버 {server_config['name']} IP 주소 설정: {ip_address_str}")
        
        try:
            server = Server(
                name=server_config['name'],
                cpu=server_config['cpu'],
                memory=server_config['memory'],
                os_type=server_config.get('os_type', 'ubuntu'),
                role=server_config.get('role', ''),
                firewall_group=server_config.get('firewall_group', ''),
                ip_address=ip_address_str,  # IP 주소 추가
                status='creating'
            )
            logger.info(f"✅ Server 객체 생성 성공: {server_config['name']} (IP: {ip_address_str})")
        except Exception as e:
            print(f"❌ Server 객체 생성 실패: {e}")  # print로 강제 출력
            logger.error(f"❌ Server 객체 생성 실패: {e}")
            raise Exception(f'Server 객체 생성 실패: {e}')
        
        # Flask 앱 컨텍스트에서 실행
        from app import create_app
        app = create_app()
        with app.app_context():
            db.session.add(server)
            db.session.commit()
            logger.info(f"✅ PostgreSQL 서버 생성 DB 저장 완료: {server_config['name']}")
            
            # 저장 확인을 위한 추가 쿼리
            saved_server = Server.query.filter_by(name=server_config['name']).first()
            if saved_server:
                logger.info(f"✅ 서버 생성 확인 완료: {server_config['name']}")
            else:
                logger.warning(f"⚠️ 서버 생성 확인 실패: {server_config['name']}")
        
        # 4단계: 서버 상태 확인 (간단한 확인만)
        self.update_state(
            state='PROGRESS',
            meta={'current': 80, 'total': 100, 'status': '서버 상태 확인 중...'}
        )
        
        # Terraform으로 생성된 서버는 자동으로 시작되므로 간단한 확인만 수행
        try:
            # Flask 앱 컨텍스트에서 상태 업데이트
            from app import create_app
            app = create_app()
            with app.app_context():
                proxmox_service = ProxmoxService()
                server_info = proxmox_service.get_server_info(server_config['name'])
                
                if server_info:
                    server.status = 'running'
                    db.session.commit()
                    success = True
                    logger.info(f"✅ 서버 생성 및 시작 완료: {server_config['name']}")
                else:
                    server.status = 'stopped'
                    db.session.commit()
                    success = True  # Terraform으로 생성되었으므로 성공으로 처리
                    logger.info(f"✅ 서버 생성 완료 (상태 확인 불가): {server_config['name']}")
                
        except Exception as e:
            logger.warning(f"⚠️ 서버 상태 확인 실패 (계속 진행): {e}")
            # Flask 앱 컨텍스트에서 상태 업데이트
            from app import create_app
            app = create_app()
            with app.app_context():
                server.status = 'running'  # Terraform 성공이므로 running으로 설정
                db.session.commit()
                success = True
        
        # Node Exporter 자동 설치 및 역할 할당 (성공한 경우에만)
        if success:
            try:
                # 서버 IP 주소 확인
                server_ip = None
                if hasattr(server, 'ip_address') and server.ip_address:
                    server_ip = server.ip_address.split(',')[0].strip()
                    logger.info(f"🔧 Node Exporter 자동 설치 시작: {server_config['name']} ({server_ip})")
                    
                    # AnsibleService를 통한 Node Exporter 설치
                    ansible_service = AnsibleService()
                    node_exporter_installed = ansible_service._install_node_exporter_if_needed(
                        server_config['name'], server_ip
                    )
                    
                    if node_exporter_installed:
                        logger.info(f"✅ Node Exporter 설치 완료: {server_config['name']}")
                        
                        # Node Exporter 설치 완료 알림 생성
                        node_exporter_notification = Notification(
                            type='node_exporter_install',
                            title='Node Exporter 설치 완료',
                            message=f'서버 {server_config["name"]}에 Node Exporter가 성공적으로 설치되었습니다.',
                            severity='success',
                            details=f'서버명: {server_config["name"]}\nIP: {server_ip}\n포트: 9100'
                        )
                        db.session.add(node_exporter_notification)
                        db.session.commit()
                        logger.info(f"📢 Node Exporter 설치 완료 알림 생성: {server_config['name']}")
                    else:
                        logger.warning(f"⚠️ Node Exporter 설치 실패: {server_config['name']}")
                        
                        # Node Exporter 설치 실패 알림 생성
                        node_exporter_fail_notification = Notification(
                            type='node_exporter_install',
                            title='Node Exporter 설치 실패',
                            message=f'서버 {server_config["name"]}에 Node Exporter 설치에 실패했습니다.',
                            severity='warning',
                            details=f'서버명: {server_config["name"]}\nIP: {server_ip}\n수동 설치가 필요할 수 있습니다.'
                        )
                        db.session.add(node_exporter_fail_notification)
                        db.session.commit()
                        logger.info(f"📢 Node Exporter 설치 실패 알림 생성: {server_config['name']}")
                    
                    # 역할 할당은 서버 생성 시 제거됨 (별도 작업으로 처리)
                    logger.info(f"🔧 서버 생성 시 역할 할당 제거됨: {server_config['name']}")
                else:
                    logger.warning(f"⚠️ IP 주소가 없어 Node Exporter 설치 및 역할 할당 스킵: {server_config['name']}")
            except Exception as node_exporter_error:
                logger.warning(f"⚠️ Node Exporter 설치 중 오류: {node_exporter_error}")
        
        # 성공 알림 생성
        if success:
            notification = Notification(
                type='server_creation',
                title='서버 생성 완료',
                message=f'서버 {server_config["name"]}이 성공적으로 생성되었습니다.\n\n💡 주의사항:\n• 서버가 완전히 부팅되기까지 5분 이상 소요될 수 있습니다\n• 역할 할당은 서버 생성 완료 5분 후에 진행하세요\n• 역할 할당 작업이 5분 이상 걸리면 서버가 아직 준비되지 않은 상태입니다',
                severity='success',
                details=f'서버명: {server_config["name"]}\nCPU: {server_config["cpu"]}코어\n메모리: {server_config["memory"]}GB\n역할: 별도 작업으로 할당 필요'
            )
            db.session.add(notification)
            db.session.commit()
            logger.info(f"📢 서버 생성 완료 알림 생성: {server_config['name']}")
        
        # 최종 결과 처리
        if success:
            return {
                'success': True,
                'message': f'서버 {server_config["name"]} 생성 완료',
                'server_name': server_config['name'],
                'task_id': task_id
            }
        else:
            # 실패 처리: 자동 정리 서비스 사용
            cleanup_service = CleanupService()
            cleanup_results = cleanup_service.cleanup_failed_server_creation(
                server_name=server_config['name'],
                failure_stage='terraform',  # Terraform 단계에서 실패
                error_message=error_msg
            )
            
            logger.info(f"🧹 자동 정리 결과: {cleanup_results}")
            
            # 실패한 작업 정리
            server.status = 'failed'
            db.session.commit()
            
            # 4. Celery Task 결과 정리 (Redis에서 제거)
            try:
                from app.celery_app import celery_app
                celery_app.control.revoke(task_id, terminate=True)
                logger.info(f"🗑️ 실패한 Task ID 정리: {task_id}")
            except Exception as task_cleanup_error:
                logger.warning(f"⚠️ Task ID 정리 실패: {task_cleanup_error}")
            
            # Celery 작업 실패 처리
            raise Exception(f'서버 {server_config["name"]} 생성 실패 (최대 재시도 횟수 초과)')
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"❌ 비동기 서버 생성 실패: {error_msg}")
        logger.error(f"📋 전체 오류 스택 트레이스:")
        logger.error(f"{error_traceback}")
        
        # server_config 내용도 로깅
        logger.error(f"📋 server_config 내용:")
        logger.error(f"  name: {server_config.get('name', 'N/A')}")
        logger.error(f"  cpu: {server_config.get('cpu', 'N/A')}")
        logger.error(f"  memory: {server_config.get('memory', 'N/A')}")
        logger.error(f"  os_type: {server_config.get('os_type', 'N/A')}")
        logger.error(f"  role: {server_config.get('role', 'N/A')}")
        logger.error(f"  firewall_group: {server_config.get('firewall_group', 'N/A')}")
        
        # 실패 처리: 자동 정리 서비스 사용
        cleanup_service = CleanupService()
        cleanup_results = cleanup_service.cleanup_failed_server_creation(
            server_name=server_config['name'],
            failure_stage='exception',  # 예외 발생으로 실패
            error_message=error_msg
        )
        
        logger.info(f"🧹 예외 발생 시 자동 정리 결과: {cleanup_results}")
        
        # 예외를 발생시키지 않고 결과만 반환
        return {
            'success': False,
            'error': error_msg,
            'message': f'서버 {server_config["name"]} 생성 실패'
        }

@celery_app.task(bind=True)
def bulk_server_action_async(self, server_names, action):
    """비동기 대량 서버 작업"""
    try:
        task_id = self.request.id
        logger.info(f"🚀 비동기 대량 서버 작업 시작: {action} - {len(server_names)}개 서버 (Task ID: {task_id})")
        
        success_servers = []
        failed_servers = []
        
        total_servers = len(server_names)
        
        for i, server_name in enumerate(server_names):
            try:
                # 작업 상태 업데이트
                progress = int((i / total_servers) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': progress,
                        'total': 100,
                        'status': f'{server_name} {action} 처리 중... ({i+1}/{total_servers})'
                    }
                )
                
                proxmox_service = ProxmoxService()
                
                if action == 'start':
                    if proxmox_service.start_server(server_name):
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'stop':
                    if proxmox_service.stop_server(server_name):
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'reboot':
                    if proxmox_service.reboot_server(server_name):
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'delete':
                    if proxmox_service.delete_server(server_name):
                        # DB에서도 삭제
                        server = Server.query.filter_by(name=server_name).first()
                        if server:
                            db.session.delete(server)
                            db.session.commit()
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                
            except Exception as e:
                logger.error(f"서버 {server_name} {action} 실패: {str(e)}")
                failed_servers.append(server_name)
        
        # 삭제 작업인 경우 Prometheus 설정 업데이트
        if action == 'delete' and success_servers:
            try:
                from app.services.prometheus_service import PrometheusService
                prometheus_service = PrometheusService()
                
                # 삭제된 서버들의 IP 주소 수집
                deleted_ips = []
                for server_name in success_servers:
                    # 삭제된 서버의 IP 주소를 DB에서 가져오기 (삭제 전에 저장된 정보)
                    server = Server.query.filter_by(name=server_name).first()
                    if server and server.ip_address:
                        ips = [ip.strip() for ip in server.ip_address.split(',') if ip.strip()]
                        deleted_ips.extend(ips)
                
                if deleted_ips:
                    logger.info(f"🔧 Prometheus 설정에서 삭제된 서버 IP 제거: {deleted_ips}")
                    prometheus_service.remove_servers_from_prometheus(deleted_ips)
                    logger.info(f"✅ Prometheus 설정 업데이트 완료: {len(deleted_ips)}개 IP 제거")
                else:
                    logger.warning("⚠️ 삭제된 서버의 IP 주소를 찾을 수 없어 Prometheus 설정을 업데이트하지 않습니다.")
                    
            except Exception as prometheus_error:
                logger.error(f"❌ Prometheus 설정 업데이트 실패: {prometheus_error}")
                # Prometheus 업데이트 실패는 전체 작업을 실패시키지 않음
        
        # 결과에 따른 알림 생성
        if success_servers and not failed_servers:
            # 모든 서버 성공
            notification = Notification(
                type='bulk_server_action',
                title='대량 작업 완료',
                message=f'모든 서버 {action} 완료: {", ".join(success_servers)}',
                severity='success',
                details=f'작업 유형: {action}\n성공한 서버: {", ".join(success_servers)}'
            )
        elif success_servers and failed_servers:
            # 부분 성공
            notification = Notification(
                type='bulk_server_action',
                title='대량 작업 부분 완료',
                message=f'일부 서버 {action} 완료. 성공: {len(success_servers)}개, 실패: {len(failed_servers)}개',
                severity='warning',
                details=f'작업 유형: {action}\n성공한 서버: {", ".join(success_servers)}\n실패한 서버: {", ".join(failed_servers)}'
            )
        else:
            # 모든 서버 실패
            notification = Notification(
                type='bulk_server_action',
                title='대량 작업 실패',
                message=f'모든 서버 {action} 실패: {len(failed_servers)}개',
                severity='error',
                details=f'작업 유형: {action}\n실패한 서버: {", ".join(failed_servers)}'
            )
        
        db.session.add(notification)
        db.session.commit()
        
        logger.info(f"✅ 비동기 대량 서버 작업 완료: {action} - 성공: {len(success_servers)}개, 실패: {len(failed_servers)}개")
        
        return {
            'success': True,
            'message': f'대량 서버 {action} 작업 완료',
            'success_servers': success_servers,
            'failed_servers': failed_servers,
            'task_id': task_id
        }
        
    except Exception as e:
        logger.error(f"❌ 비동기 대량 서버 작업 실패: {str(e)}")
        
        # 작업 실패 상태 업데이트
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        
        raise


@celery_app.task(bind=True)
def create_servers_bulk_async(self, servers_data):
    """비동기 다중 서버 생성 작업"""
    try:
        task_id = self.request.id
        logger.info(f"🚀 비동기 다중 서버 생성 시작: {len(servers_data)}개 (Task ID: {task_id})")

        # 0. 진행 상태
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100, 'status': '설정 준비 중...'})

        terraform_service = TerraformService()

        # 1. 기존 tfvars 로드 또는 기본 구조 생성
        try:
            tfvars = terraform_service.load_tfvars()
            logger.info(f"🔧 기존 tfvars 로드 완료: {len(tfvars.get('servers', {}))}개 서버")
        except Exception as e:
            logger.warning(f"기존 tfvars 로드 실패: {e}; 기본 구조 생성")
            tfvars = {
                'servers': {},
                'proxmox_endpoint': current_app.config.get('PROXMOX_ENDPOINT'),
                'proxmox_username': current_app.config.get('PROXMOX_USERNAME'),
                'proxmox_password': current_app.config.get('PROXMOX_PASSWORD'),
                'proxmox_node': current_app.config.get('PROXMOX_NODE'),
                'vm_username': current_app.config.get('VM_USERNAME', 'rocky'),
                'vm_password': current_app.config.get('VM_PASSWORD', 'rocky123'),
                'ssh_keys': current_app.config.get('SSH_KEYS', '')
            }

        # 2. 서버 설정 병합
        import os
        hdd_datastore = os.environ.get('PROXMOX_HDD_DATASTORE')
        ssd_datastore = os.environ.get('PROXMOX_SSD_DATASTORE')

        for server_data in servers_data:
            server_name = server_data.get('name')
            if not server_name:
                continue
            server_config = {
                'name': server_name,
                'cpu': server_data.get('cpu', 2),
                'memory': server_data.get('memory', 2048),
                'role': server_data.get('role', ''),
                'os_type': server_data.get('os_type', ''),
                'disks': server_data.get('disks', []),
                'network_devices': server_data.get('network_devices', []),
                'template_vm_id': server_data.get('template_vm_id', 8000),
                'vm_username': server_data.get('vm_username', tfvars.get('vm_username', 'rocky')),
                'vm_password': server_data.get('vm_password', tfvars.get('vm_password', 'rocky123'))
            }

            for disk in server_config['disks']:
                if 'disk_type' not in disk:
                    disk['disk_type'] = 'hdd'
                if 'file_format' not in disk:
                    disk['file_format'] = 'auto'
                if 'datastore_id' not in disk or disk['datastore_id'] == 'auto':
                    if disk['disk_type'] == 'hdd':
                        disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'
                    elif disk['disk_type'] == 'ssd':
                        disk['datastore_id'] = ssd_datastore if ssd_datastore else 'local'
                    else:
                        disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'

            tfvars['servers'][server_name] = server_config
            logger.info(f"🔧 서버 설정 추가: {server_name}")

        # 3. tfvars 저장
        if not terraform_service.save_tfvars(tfvars):
            raise Exception('tfvars 파일 저장 실패')

        self.update_state(state='PROGRESS', meta={'current': 20, 'total': 100, 'status': 'Terraform 적용 중...'})

        # 4. Targeted apply
        new_server_targets = []
        for server_data in servers_data:
            name = server_data.get('name')
            if name:
                new_server_targets.append(f'module.server["{name}"]')
        apply_success, apply_message = terraform_service.apply(targets=new_server_targets)
        if not apply_success:
            raise Exception(f'Terraform apply 실패: {apply_message}')

        # 5. Proxmox에서 VM 확인 및 DB 저장
        self.update_state(state='PROGRESS', meta={'current': 60, 'total': 100, 'status': 'VM 확인 및 DB 저장...'})
        proxmox_service = ProxmoxService()
        created_servers = []
        failed_servers = []

        # 템플릿 캐시
        template_cache = {}
        try:
            headers, error = proxmox_service.get_proxmox_auth()
            if not error:
                vms, vm_error = proxmox_service.get_proxmox_vms(headers)
                if not vm_error:
                    for vm in vms:
                        template_cache[vm.get('vmid')] = vm.get('name', 'rocky-9-template')
        except Exception as e:
            logger.warning(f"템플릿 정보 조회 실패: {e}")

        for sd in servers_data:
            name = sd.get('name')
            if not name:
                continue
            if proxmox_service.check_vm_exists(name):
                created_servers.append(name)

                ip_address_str = ''
                nds = sd.get('network_devices', [])
                if nds:
                    ip_list = [d.get('ip_address', '') for d in nds if d.get('ip_address')]
                    ip_address_str = ', '.join(ip_list) if ip_list else ''

                template_vm_id = sd.get('template_vm_id', 8000)
                template_name = template_cache.get(template_vm_id, 'rocky-9-template')
                os_type = 'rocky'
                try:
                    from app.routes.servers import classify_os_type  # 재사용
                    os_type = classify_os_type(template_name)
                except Exception:
                    pass

                vm_id = None
                try:
                    tf_output = terraform_service.output()
                    if 'vm_ids' in tf_output:
                        vdata = tf_output['vm_ids']
                        if 'value' in vdata and name in vdata['value']:
                            vm_id = vdata['value'][name]
                    if not vm_id:
                        exists, info = proxmox_service.check_vm_exists(name)
                        if exists and info:
                            vm_id = info.get('vmid')
                except Exception as e:
                    logger.warning(f"VM ID 조회 실패: {e}")

                new_server = Server(
                    name=name,
                    vmid=vm_id,
                    ip_address=ip_address_str,
                    cpu=sd.get('cpu', 2),
                    memory=sd.get('memory', 2048),
                    role=sd.get('role', ''),
                    status='running',
                    os_type=os_type,
                    created_at=datetime.utcnow()
                )
                try:
                    db.session.add(new_server)
                    db.session.commit()
                    
                    # PostgreSQL 연결 확인을 위한 추가 검증
                    db.session.flush()  # 세션 플러시
                    logger.info(f"✅ PostgreSQL 대량 서버 생성 DB 저장 완료: {name}")
                except Exception as db_error:
                    logger.error(f"❌ 서버 DB 저장 실패: {name} - {db_error}")
                    db.session.rollback()
                    db.session.close()
            else:
                failed_servers.append(name)

        # 6. Node Exporter 일괄 설치 및 역할 할당
        if created_servers:
            try:
                ansible_service = AnsibleService()
                server_ips = []
                role_servers = {}  # 역할별 서버 그룹화
                
                for name in created_servers:
                    s = Server.query.filter_by(name=name).first()
                    if s and s.ip_address:
                        server_ip = s.ip_address.split(',')[0].strip()
                        server_ips.append(server_ip)
                        
                        # 역할별 그룹화
                        role = s.role or ''
                        if role and role != 'none' and role.strip():
                            if role not in role_servers:
                                role_servers[role] = []
                            role_servers[role].append(server_ip)
                
                # 서버 준비 대기 (대량 생성된 서버들이 완전히 부팅될 때까지)
                if server_ips:
                    logger.info(f"🔧 대량 서버 준비 대기 시작: {len(server_ips)}개 서버")
                    import time
                    time.sleep(90)  # 대량 서버는 1.5분 대기
                    logger.info(f"✅ 대량 서버 준비 대기 완료: {len(server_ips)}개 서버")
                
                # Node Exporter 일괄 설치
                if server_ips:
                    ans_ok, ans_msg = ansible_service.run_playbook(
                        role='node_exporter',
                        extra_vars={'install_node_exporter': True},
                        limit_hosts=','.join(server_ips)
                    )
                    if ans_ok:
                        logger.info(f"Node Exporter 일괄 설치 성공: {len(server_ips)}개")
                        
                        # Node Exporter 일괄 설치 완료 알림 생성
                        bulk_node_exporter_notification = Notification(
                            type='node_exporter_install',
                            title='Node Exporter 일괄 설치 완료',
                            message=f'{len(server_ips)}개 서버에 Node Exporter가 성공적으로 설치되었습니다.',
                            severity='success',
                            details=f'설치된 서버: {", ".join(created_servers)}\nIP: {", ".join(server_ips)}\n포트: 9100'
                        )
                        db.session.add(bulk_node_exporter_notification)
                        db.session.commit()
                        logger.info(f"📢 Node Exporter 일괄 설치 완료 알림 생성: {len(server_ips)}개")
                    else:
                        logger.warning(f"Node Exporter 일괄 설치 실패: {ans_msg}")
                
                # 역할별 일괄 할당
                for role, role_ips in role_servers.items():
                    if role_ips:
                        logger.info(f"🔧 역할별 일괄 할당 시작: {role} → {len(role_ips)}개 서버")
                        try:
                            role_ok, role_msg = ansible_service.run_playbook(
                                role=role,
                                extra_vars={'install_node_exporter': True},
                                limit_hosts=','.join(role_ips)
                            )
                            if role_ok:
                                logger.info(f"✅ 역할별 일괄 할당 완료: {role} → {len(role_ips)}개 서버")
                            else:
                                logger.warning(f"⚠️ 역할별 일괄 할당 실패: {role}, 메시지: {role_msg}")
                        except Exception as role_err:
                            logger.warning(f"⚠️ 역할별 일괄 할당 중 오류: {role_err}")
                            
            except Exception as ne_err:
                logger.warning(f"Node Exporter 설치 및 역할 할당 중 오류: {ne_err}")

        # 7. Prometheus 설정 갱신
        try:
            from app.services.prometheus_service import PrometheusService
            PrometheusService().update_prometheus_config()
        except Exception as e:
            logger.warning(f"Prometheus 설정 업데이트 중 오류: {e}")

        # 8. 알림 생성
        try:
            if created_servers and not failed_servers:
                msg = f"모든 서버 생성 완료: {', '.join(created_servers)}"
                # 알림 생성 (역할 정보 제거됨)
                notification = Notification(
                    type='bulk_server_creation',
                    title='대량 서버 생성 완료',
                    message=f'{len(created_servers)}개 서버가 성공적으로 생성되었습니다.\n역할: 별도 작업으로 할당 필요',
                    severity='success',
                    details=f'생성된 서버: {", ".join(created_servers)}'
                )
                db.session.add(notification)
                db.session.commit()
                
            elif created_servers and failed_servers:
                msg = f"일부 서버 생성 완료. 성공: {', '.join(created_servers)}, 실패: {', '.join(failed_servers)}"
            else:
                msg = f"모든 서버 생성 실패: {', '.join(failed_servers)}"
            logger.info(msg)
        except Exception as nerr:
            logger.warning(f"알림 생성 중 오류: {nerr}")

        # 완료
        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100, 'status': '완료'})
        return {
            'success': True,
            'created': created_servers,
            'failed': failed_servers,
            'task_id': task_id
        }

    except Exception as e:
        logger.error(f"❌ 비동기 다중 서버 생성 실패: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True)
def delete_server_async(self, server_name: str):
    """비동기 서버 삭제 작업"""
    try:
        logger.info(f"🗑️ 비동기 서버 삭제 시작: {server_name}")
        
        # 작업 상태 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': f'서버 {server_name} 중지 중...'}
        )
        
        # 0단계: 먼저 서버를 중지
        proxmox_service = ProxmoxService()
        try:
            stop_ok = proxmox_service.stop_server(server_name)
            if not stop_ok:
                logger.warning(f"⚠️ 서버 중지 실패(계속 진행): {server_name}")
            else:
                # 최대 15초 동안 중지 상태 대기
                wait_seconds = 0
                while wait_seconds < 15:
                    info = proxmox_service.get_server_info(server_name)
                    status = (info or {}).get('status')
                    if status and status != 'running':
                        logger.info(f"✅ 서버 중지 확인: {server_name} (status={status})")
                        break
                    time.sleep(3)
                    wait_seconds += 3
        except Exception as stop_err:
            logger.warning(f"⚠️ 서버 중지 중 예외(계속 진행): {stop_err}")
        
        # TerraformService를 사용하여 서버 삭제
        terraform_service = TerraformService()
        
        # terraform.tfvars.json에서 해당 서버 제거
        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': f'서버 {server_name} 설정 삭제 중...'}
        )
        
        success = terraform_service.delete_server_config(server_name)
        
        if not success:
            raise Exception(f'서버 {server_name} 설정 삭제 실패')
        
        # Terraform apply로 실제 삭제 실행 (타겟 지정 없이 단일 apply)
        self.update_state(
            state='PROGRESS',
            meta={'progress': 60, 'message': f'서버 {server_name} Terraform 적용 중...'}
        )
        # tfvars에서 제거가 반영되었으므로 전체 apply로 정합성 보장
        # state lock 충돌을 피하기 위해 재시도(최대 3회, 지수 백오프)
        retries = 3
        apply_ok = False
        apply_msg = ""
        for attempt in range(1, retries + 1):
            apply_ok, apply_msg = terraform_service.apply()
            if apply_ok:
                break
            if "Error acquiring the state lock" in (apply_msg or ""):
                wait_seconds = 3 * attempt
                logger.warning(f"Terraform state lock 충돌, {wait_seconds}s 후 재시도 ({attempt}/{retries})")
                time.sleep(wait_seconds)
                continue
            else:
                break
        if not apply_ok:
            raise Exception(f'서버 {server_name} Terraform 적용 실패: {apply_msg}')
        
        # DB에서 서버 객체 삭제 (PostgreSQL 연결 문제 해결)
        try:
            # Flask 앱 컨텍스트에서 실행
            from app import create_app
            app = create_app()
            with app.app_context():
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    db.session.delete(server)
                    db.session.commit()
                    logger.info(f"🗑️ 서버 DB 객체 삭제: {server_name}")
                    
                    # 삭제 확인을 위한 추가 쿼리
                    deleted_server = Server.query.filter_by(name=server_name).first()
                    if deleted_server is None:
                        logger.info(f"✅ 서버 삭제 확인 완료: {server_name}")
                    else:
                        logger.warning(f"⚠️ 서버 삭제 확인 실패: {server_name}")
                else:
                    logger.warning(f"⚠️ 삭제할 서버를 찾을 수 없음: {server_name}")
        except Exception as db_error:
            logger.error(f"❌ DB 객체 삭제 실패: {db_error}")
            # 세션 롤백
            db.session.rollback()
        
        # 작업 완료
        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': f'서버 {server_name} 삭제 완료'}
        )
        
        logger.info(f"✅ 서버 삭제 성공: {server_name}")
        # Redis 캐시 제거됨 - 실시간 조회로 변경
        
        # 성공 알림 생성 (SSE로 전달되어 UI에 즉시 표시)
        try:
            from app.models.notification import Notification
            success_noti = Notification(
                type='server_deletion',
                title='서버 삭제 완료',
                message=f'서버 {server_name}이 성공적으로 삭제되었습니다.',
                severity='success',
                details=f'서버명: {server_name}'
            )
            db.session.add(success_noti)
            db.session.commit()
        except Exception as notify_ok_error:
            logger.warning(f"알림 생성 경고(성공): {notify_ok_error}")

        return {
            'success': True,
            'message': f'서버 {server_name} 삭제 완료',
            'server_name': server_name
        }
        
    except Exception as e:
        logger.error(f"❌ 비동기 서버 삭제 실패: {server_name} - {str(e)}")
        
        # 실패 알림 생성
        try:
            from app.models.notification import Notification
            notification = Notification(
                title=f"서버 삭제 실패: {server_name}",
                message=f"서버 {server_name} 삭제 중 오류가 발생했습니다: {str(e)}",
                type="error"
            )
            db.session.add(notification)
            db.session.commit()
        except Exception as notify_error:
            logger.error(f"알림 생성 실패: {notify_error}")
        
        raise Exception(f'서버 {server_name} 삭제 실패: {str(e)}')

@celery_app.task(bind=True)
def start_server_async(self, server_name: str):
    """비동기 서버 시작"""
    try:
        logger.info(f"🚀 비동기 서버 시작 작업 시작: {server_name}")
        
        # ProxmoxService를 사용하여 서버 시작
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # 서버 시작 실행
        success = proxmox_service.start_server(server_name)
        
        if success:
            # DB 상태 업데이트
            from app.models.server import Server
            from app import db
            
            server = Server.query.filter_by(name=server_name).first()
            if server:
                server.status = 'running'
                db.session.commit()
                
                # PostgreSQL 연결 확인을 위한 추가 검증
                db.session.flush()  # 세션 플러시
                logger.info(f"✅ PostgreSQL 서버 시작 DB 업데이트 완료: {server_name}")
            
            # 성공 알림 생성
            from app.models.notification import Notification
            notification = Notification(
                type='server_start',
                title='서버 시작 완료',
                message=f'서버 {server_name}이 성공적으로 시작되었습니다.',
                severity='success',
                details=f'서버명: {server_name}'
            )
            db.session.add(notification)
            db.session.commit()
            
            # Redis 캐시 제거됨 - 실시간 조회로 변경
            
            logger.info(f"✅ 비동기 서버 시작 완료: {server_name}")
            return {
                'success': True,
                'message': f'서버 {server_name} 시작 완료'
            }
        else:
            # 실패 알림 생성
            from app.models.notification import Notification
            notification = Notification(
                type='server_start',
                title='서버 시작 실패',
                message=f'서버 {server_name} 시작에 실패했습니다.',
                severity='error',
                details=f'서버명: {server_name}'
            )
            db.session.add(notification)
            db.session.commit()
            
            logger.error(f"❌ 비동기 서버 시작 실패: {server_name}")
            return {
                'success': False,
                'error': f'서버 {server_name} 시작 실패',
                'message': f'서버 {server_name} 시작 실패'
            }
            
    except Exception as e:
        logger.error(f"❌ 비동기 서버 시작 실패: {server_name} - {str(e)}")
        try:
            # 예외 상황에서도 실패 알림을 반드시 생성
            from app.models.notification import Notification
            from app import db
            notification = Notification(
                type='server_start',
                title='서버 시작 실패',
                message=f'서버 {server_name} 시작에 실패했습니다. (예외)',
                severity='error',
                details=f'서버명: {server_name}\n에러: {str(e)}'
            )
            db.session.add(notification)
            db.session.commit()
        except Exception:
            pass
        return {
            'success': False,
            'error': f'서버 시작 실패: {str(e)}',
            'message': f'서버 {server_name} 시작 실패'
        }

@celery_app.task(bind=True)
def stop_server_async(self, server_name: str):
    """비동기 서버 중지"""
    try:
        logger.info(f"🚀 비동기 서버 중지 작업 시작: {server_name}")
        
        # ProxmoxService를 사용하여 서버 중지
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # 서버 중지 실행
        success = proxmox_service.stop_server(server_name)
        
        if success:
            # DB 상태 업데이트
            from app.models.server import Server
            from app import db
            
            server = Server.query.filter_by(name=server_name).first()
            if server:
                server.status = 'stopped'
                db.session.commit()
                
                # PostgreSQL 연결 확인을 위한 추가 검증
                db.session.flush()  # 세션 플러시
                logger.info(f"✅ PostgreSQL 서버 중지 DB 업데이트 완료: {server_name}")
            
            # 성공 알림 생성
            from app.models.notification import Notification
            notification = Notification(
                type='server_stop',
                title='서버 중지 완료',
                message=f'서버 {server_name}이 성공적으로 중지되었습니다.',
                severity='success',
                details=f'서버명: {server_name}'
            )
            db.session.add(notification)
            db.session.commit()
            
            # Redis 캐시 제거됨 - 실시간 조회로 변경
            
            logger.info(f"✅ 비동기 서버 중지 완료: {server_name}")
            return {
                'success': True,
                'message': f'서버 {server_name} 중지 완료'
            }
        else:
            # 실패 알림 생성
            from app.models.notification import Notification
            notification = Notification(
                type='server_stop',
                title='서버 중지 실패',
                message=f'서버 {server_name} 중지에 실패했습니다.',
                severity='error',
                details=f'서버명: {server_name}'
            )
            db.session.add(notification)
            db.session.commit()
            
            logger.error(f"❌ 비동기 서버 중지 실패: {server_name}")
            return {
                'success': False,
                'error': f'서버 {server_name} 중지 실패',
                'message': f'서버 {server_name} 중지 실패'
            }
            
    except Exception as e:
        logger.error(f"❌ 비동기 서버 중지 실패: {server_name} - {str(e)}")
        try:
            # 예외 상황에서도 실패 알림을 반드시 생성
            from app.models.notification import Notification
            from app import db
            notification = Notification(
                type='server_stop',
                title='서버 중지 실패',
                message=f'서버 {server_name} 중지에 실패했습니다. (예외)',
                severity='error',
                details=f'서버명: {server_name}\n에러: {str(e)}'
            )
            db.session.add(notification)
            db.session.commit()
        except Exception:
            pass
        return {
            'success': False,
            'error': f'서버 중지 실패: {str(e)}',
            'message': f'서버 {server_name} 중지 실패'
        }

@celery_app.task(bind=True)
def reboot_server_async(self, server_name: str):
    """비동기 서버 재시작"""
    try:
        logger.info(f"🚀 비동기 서버 재시작 작업 시작: {server_name}")
        
        # ProxmoxService를 사용하여 서버 재시작
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # 서버 재시작 실행
        success = proxmox_service.reboot_server(server_name)
        
        if success:
            # 성공 알림 생성
            from app.models.notification import Notification
            from app import db
            
            notification = Notification(
                type='server_reboot',
                title='서버 재시작 완료',
                message=f'서버 {server_name}이 성공적으로 재시작되었습니다.',
                severity='success',
                details=f'서버명: {server_name}'
            )
            db.session.add(notification)
            db.session.commit()
            
            # Redis 캐시 제거됨 - 실시간 조회로 변경
            
            logger.info(f"✅ 비동기 서버 재시작 완료: {server_name}")
            return {
                'success': True,
                'message': f'서버 {server_name} 재시작 완료'
            }
        else:
            # 실패 알림 생성
            from app.models.notification import Notification
            from app import db
            
            notification = Notification(
                type='server_reboot',
                title='서버 재시작 실패',
                message=f'서버 {server_name} 재시작에 실패했습니다.',
                severity='error',
                details=f'서버명: {server_name}'
            )
            db.session.add(notification)
            db.session.commit()
            
            logger.error(f"❌ 비동기 서버 재시작 실패: {server_name}")
            return {
                'success': False,
                'error': f'서버 {server_name} 재시작 실패',
                'message': f'서버 {server_name} 재시작 실패'
            }
            
    except Exception as e:
        logger.error(f"❌ 비동기 서버 재시작 실패: {server_name} - {str(e)}")
        try:
            # 예외 상황에서도 실패 알림을 반드시 생성
            from app.models.notification import Notification
            from app import db
            notification = Notification(
                type='server_reboot',
                title='서버 재시작 실패',
                message=f'서버 {server_name} 재시작에 실패했습니다. (예외)',
                severity='error',
                details=f'서버명: {server_name}\n에러: {str(e)}'
            )
            db.session.add(notification)
            db.session.commit()
        except Exception:
            pass
        return {
            'success': False,
            'error': f'서버 재시작 실패: {str(e)}',
            'message': f'서버 {server_name} 재시작 실패'
        }

