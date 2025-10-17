"""
백업 관련 Celery 태스크
"""
import logging
import time
import uuid
from app.celery_app import celery_app
from app import db

logger = logging.getLogger(__name__)

def safe_db_commit():
    """DB 락 오류 방지를 위한 안전한 커밋"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            db.session.commit()
            return True
        except Exception as e:
            retry_count += 1
            if "database is locked" in str(e) and retry_count < max_retries:
                logger.warning(f"⚠️ DB 락 오류, {retry_count}초 후 재시도: {e}")
                time.sleep(retry_count)
                try:
                    db.session.rollback()
                except Exception:
                    pass
            else:
                logger.error(f"❌ DB 커밋 실패: {e}")
                return False
    return False

def safe_db_add(obj):
    """DB 락 오류 방지를 위한 안전한 추가"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            db.session.add(obj)
            return True
        except Exception as e:
            retry_count += 1
            if "database is locked" in str(e) and retry_count < max_retries:
                logger.warning(f"⚠️ DB 락 오류, {retry_count}초 후 재시도: {e}")
                time.sleep(retry_count)
                try:
                    db.session.rollback()
                except Exception:
                    pass
            else:
                logger.error(f"❌ DB 추가 실패: {e}")
                return False
    return False

@celery_app.task(bind=True)
def create_server_backup_async(self, server_name: str, backup_config: dict):
    """비동기 서버 백업 생성"""
    try:
        logger.info(f"💾 비동기 서버 백업 시작: {server_name}")
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': f'서버 {server_name} 백업 준비 중...'}
        )
        
        # ProxmoxService를 사용하여 백업 생성
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': f'Proxmox 백업 API 호출 중...'}
        )
        
        result = proxmox_service.create_server_backup(server_name, backup_config)
        
        if result['success']:
            self.update_state(
                state='PROGRESS',
                meta={'progress': 60, 'message': f'백업 작업 시작됨, 파일 감지 중...'}
            )
            
            # 백업 파일 감지 시작
            backup_id = str(uuid.uuid4())
            start_file_monitoring_async.delay(server_name, backup_id)
            
            # 성공 알림
            from app.models.notification import Notification
            notification = Notification(
                type='backup',
                title=f'서버 {server_name} 백업 시작',
                message=f'백업 작업이 성공적으로 시작되었습니다.',
                severity='info',
                details=f'백업 ID: {backup_id}'
            )
            if safe_db_add(notification):
                safe_db_commit()
            
            logger.info(f"✅ 비동기 서버 백업 시작 완료: {server_name}")
            return {
                'success': True,
                'message': f'서버 {server_name} 백업이 시작되었습니다.',
                'server_name': server_name,
                'backup_id': backup_id
            }
        else:
            # 실패 알림
            notification = Notification(
                type='backup',
                title=f'서버 {server_name} 백업 실패',
                message=f'백업 시작에 실패했습니다: {result.get("message", "알 수 없는 오류")}',
                severity='error',
                details=result.get('message', '알 수 없는 오류')
            )
            if safe_db_add(notification):
                safe_db_commit()
            
            raise Exception(f'백업 시작 실패: {result.get("message", "알 수 없는 오류")}')
            
    except Exception as e:
        logger.error(f"❌ 비동기 서버 백업 실패: {str(e)}")
        
        # 실패 알림
        try:
            from app.models.notification import Notification
            notification = Notification(
                type='backup',
                title=f'서버 {server_name} 백업 실패',
                message=f'백업 중 오류가 발생했습니다: {str(e)}',
                severity='error'
            )
            if safe_db_add(notification):
                safe_db_commit()
        except Exception:
            pass
        
        return {
            'success': False,
            'error': f'백업 실패: {str(e)}',
            'message': f'서버 {server_name} 백업 실패'
        }

@celery_app.task(bind=True)
def start_file_monitoring_async(self, server_name: str, backup_id: str):
    """비동기 백업 파일 감지"""
    try:
        logger.info(f"🔍 백업 파일 감지 시작: {server_name} (ID: {backup_id})")
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': f'백업 파일 감지 중...'}
        )
        
        # 백업 상태 관리 (기존 로직 활용)
        from app.routes.backup import backup_status, update_backup_status
        
        # 백업 상태 초기화
        backup_status[server_name] = {
            'backup_id': backup_id,
            'status': 'running',
            'started_at': time.time(),
            'message': f'서버 {server_name} 백업이 진행 중입니다.',
            'last_check': time.time()
        }
        
        # 파일 감지 로직 (기존 코드 활용)
        max_wait_time = 300  # 5분
        check_interval = 10  # 10초마다 체크
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                from app.services.proxmox_service import ProxmoxService
                proxmox_service = ProxmoxService()
                
                # 백업 파일 목록 조회
                backup_result = proxmox_service.get_server_backups(server_name)
                logger.info(f"🔍 백업 파일 조회 결과: {backup_result}")
                
                if backup_result.get('success') and backup_result.get('data', {}).get('backups'):
                    backup_files = backup_result['data']['backups']
                    if len(backup_files) > 0:
                        # 백업 완료 감지
                        latest_backup = backup_files[0]  # 가장 최신 백업
                        
                        update_backup_status(server_name, 'completed', f'백업 완료: {latest_backup.get("name", "알 수 없음")}')
                        
                        # 완료 알림
                        from app.models.notification import Notification
                        notification = Notification(
                            type='backup',
                            title=f'서버 {server_name} 백업 완료',
                            message=f'백업이 성공적으로 완료되었습니다.',
                            severity='success',
                            details=f'파일: {latest_backup.get("name", "알 수 없음")}'
                        )
                        if safe_db_add(notification):
                            safe_db_commit()
                        
                        logger.info(f"✅ 백업 파일 감지 완료: {server_name}")
                        return {
                            'success': True,
                            'message': f'서버 {server_name} 백업 완료',
                            'server_name': server_name,
                            'backup_file': latest_backup.get('name', '알 수 없음')
                        }
                    else:
                        logger.info(f"🔍 백업 파일이 아직 없음: {server_name}")
                else:
                    logger.info(f"🔍 백업 파일 조회 실패 또는 빈 결과: {backup_result}")
                
                # 진행 상태 업데이트
                progress = min(90, 10 + (elapsed_time / max_wait_time) * 80)
                self.update_state(
                    state='PROGRESS',
                    meta={'progress': progress, 'message': f'백업 파일 감지 중... ({elapsed_time}초 경과)'}
                )
                
                time.sleep(check_interval)
                elapsed_time += check_interval
                
            except Exception as check_error:
                logger.warning(f"⚠️ 백업 파일 체크 중 오류: {check_error}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        # 타임아웃
        update_backup_status(server_name, 'timeout', '백업 파일 감지 타임아웃')
        
        notification = Notification(
            type='backup',
            title=f'서버 {server_name} 백업 타임아웃',
            message=f'백업 파일 감지가 타임아웃되었습니다.',
            severity='warning'
        )
        if safe_db_add(notification):
            safe_db_commit()
        
        logger.warning(f"⚠️ 백업 파일 감지 타임아웃: {server_name}")
        return {
            'success': False,
            'message': f'서버 {server_name} 백업 파일 감지 타임아웃',
            'server_name': server_name
        }
        
    except Exception as e:
        logger.error(f"❌ 백업 파일 감지 실패: {str(e)}")
        
        # 실패 알림
        try:
            from app.models.notification import Notification
            notification = Notification(
                type='backup',
                title=f'서버 {server_name} 백업 감지 실패',
                message=f'백업 파일 감지 중 오류가 발생했습니다: {str(e)}',
                severity='error'
            )
            if safe_db_add(notification):
                safe_db_commit()
        except Exception:
            pass
        
        return {
            'success': False,
            'error': f'백업 파일 감지 실패: {str(e)}',
            'message': f'서버 {server_name} 백업 감지 실패'
        }
