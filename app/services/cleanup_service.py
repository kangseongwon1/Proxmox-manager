"""
서버 생성 실패 시 자동 정리 서비스
"""
import logging
from app.models import Server, Notification
from app import db
from app.services import ProxmoxService, TerraformService

logger = logging.getLogger(__name__)

class CleanupService:
    """서버 생성 실패 시 자동 정리 서비스"""
    
    def __init__(self):
        self.proxmox_service = ProxmoxService()
        self.terraform_service = TerraformService()
    
    def cleanup_failed_server_creation(self, server_name, failure_stage=None, error_message=None):
        """
        서버 생성 실패 시 자동 정리
        
        Args:
            server_name (str): 서버명
            failure_stage (str): 실패 단계 ('validation', 'terraform', 'proxmox', 'db', 'notification')
            error_message (str): 오류 메시지
        """
        logger.info(f"🧹 서버 생성 실패 자동 정리 시작: {server_name}")
        logger.info(f"📋 실패 단계: {failure_stage}, 오류: {error_message}")
        
        cleanup_results = {
            'db_cleaned': False,
            'terraform_cleaned': False,
            'proxmox_cleaned': False,
            'notification_created': False,
            'errors': []
        }
        
        try:
            # 1. DB 정리 (가장 먼저)
            cleanup_results['db_cleaned'] = self._cleanup_database(server_name)
            
            # 2. Terraform 정리 (DB 정리 후)
            if failure_stage in [None, 'terraform', 'proxmox', 'db', 'notification']:
                cleanup_results['terraform_cleaned'] = self._cleanup_terraform(server_name)
            
            # 3. Proxmox 정리 (Terraform 정리 후)
            if failure_stage in [None, 'proxmox', 'db', 'notification']:
                cleanup_results['proxmox_cleaned'] = self._cleanup_proxmox(server_name)
            
            # 4. 실패 알림 생성 (마지막)
            cleanup_results['notification_created'] = self._create_failure_notification(
                server_name, failure_stage, error_message
            )
            
            logger.info(f"✅ 자동 정리 완료: {server_name}")
            logger.info(f"📊 정리 결과: {cleanup_results}")
            
        except Exception as e:
            logger.error(f"❌ 자동 정리 중 오류: {e}")
            cleanup_results['errors'].append(str(e))
        
        return cleanup_results
    
    def _cleanup_database(self, server_name):
        """DB에서 서버 객체 삭제"""
        try:
            server = Server.query.filter_by(name=server_name).first()
            if server:
                db.session.delete(server)
                db.session.commit()
                logger.info(f"🗑️ DB에서 서버 객체 삭제: {server_name}")
                return True
            else:
                logger.info(f"ℹ️ DB에 서버 객체 없음: {server_name}")
                return True
        except Exception as e:
            logger.error(f"❌ DB 정리 실패: {e}")
            return False
    
    def _cleanup_terraform(self, server_name):
        """Terraform에서 서버 설정 삭제"""
        try:
            # terraform.tfvars.json에서 해당 서버 제거
            success = self.terraform_service.delete_server_config(server_name)
            if success:
                logger.info(f"🗑️ Terraform 설정 삭제: {server_name}")
                return True
            else:
                logger.warning(f"⚠️ Terraform 설정 삭제 실패: {server_name}")
                return False
        except Exception as e:
            logger.error(f"❌ Terraform 정리 실패: {e}")
            return False
    
    def _cleanup_proxmox(self, server_name):
        """Proxmox에서 부분적으로 생성된 VM 삭제"""
        try:
            # VM이 존재하는지 확인
            server_info = self.proxmox_service.get_server_info(server_name)
            if server_info:
                # VM이 실행 중이면 먼저 중지
                if server_info.get('status') == 'running':
                    logger.info(f"⏹️ 실행 중인 VM 중지: {server_name}")
                    self.proxmox_service.stop_server(server_name)
                
                # VM 삭제
                delete_success = self.proxmox_service.delete_server(server_name)
                if delete_success:
                    logger.info(f"🗑️ Proxmox VM 삭제: {server_name}")
                    return True
                else:
                    logger.warning(f"⚠️ Proxmox VM 삭제 실패: {server_name}")
                    return False
            else:
                logger.info(f"ℹ️ Proxmox에 VM 없음: {server_name}")
                return True
        except Exception as e:
            logger.error(f"❌ Proxmox 정리 실패: {e}")
            return False
    
    def _create_failure_notification(self, server_name, failure_stage, error_message):
        """실패 알림 생성"""
        try:
            # 실패 단계별 메시지 생성
            stage_messages = {
                'validation': '입력 검증 실패',
                'terraform': '인프라 생성 실패', 
                'proxmox': '가상머신 생성 실패',
                'db': '데이터베이스 저장 실패',
                'notification': '알림 생성 실패'
            }
            
            stage_message = stage_messages.get(failure_stage, '알 수 없는 단계')
            
            notification = Notification(
                type='server_creation_failure',
                title='서버 생성 실패',
                message=f'서버 {server_name} 생성에 실패했습니다.',
                severity='error',
                details=f'실패 단계: {stage_message}\n오류: {error_message or "상세 정보 없음"}'
            )
            
            db.session.add(notification)
            db.session.commit()
            
            logger.info(f"📢 실패 알림 생성: {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 실패 알림 생성 실패: {e}")
            return False
    
    def get_cleanup_status(self, server_name):
        """정리 상태 확인"""
        status = {
            'db_exists': False,
            'terraform_exists': False,
            'proxmox_exists': False
        }
        
        try:
            # DB 확인
            server = Server.query.filter_by(name=server_name).first()
            status['db_exists'] = server is not None
            
            # Terraform 확인 (간접적으로)
            # terraform.tfvars.json 파일에서 해당 서버가 있는지 확인
            try:
                import json
                with open('terraform/terraform.tfvars.json', 'r') as f:
                    tfvars = json.load(f)
                    servers = tfvars.get('servers', {})
                    status['terraform_exists'] = server_name in servers
            except:
                status['terraform_exists'] = False
            
            # Proxmox 확인
            try:
                server_info = self.proxmox_service.get_server_info(server_name)
                status['proxmox_exists'] = server_info is not None
            except:
                status['proxmox_exists'] = False
                
        except Exception as e:
            logger.error(f"❌ 정리 상태 확인 실패: {e}")
        
        return status
