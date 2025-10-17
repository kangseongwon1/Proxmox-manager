"""
역할 할당 관련 Celery 태스크
"""
import logging
import time
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
def assign_role_async(self, server_name: str, role: str):
    """비동기 역할 할당"""
    try:
        logger.info(f"🔧 비동기 역할 할당 시작: {server_name} → {role}")
        
        # 상태 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': f'서버 {server_name}에 역할 {role} 할당 중...'}
        )
        
        from app.services import AnsibleService
        from app.models import Server
        from app.models.notification import Notification
        
        # 서버 정보 조회
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            raise Exception(f'서버 {server_name}을 찾을 수 없습니다.')
        
        # IP 주소 확인
        if not server.ip_address or not server.ip_address.strip():
            raise Exception(f'서버 {server_name}의 IP 주소가 없습니다.')
        
        # 첫 번째 IP 주소 사용
        first_ip = server.ip_address.split(',')[0].strip()
        if not first_ip:
            raise Exception(f'서버 {server_name}의 유효한 IP 주소가 없습니다.')
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': f'Ansible 실행 중...'}
        )
        
        # Ansible 실행
        ansible_service = AnsibleService()
        success, message = ansible_service.assign_role_to_server(server_name, role)
        
        if success:
            # DB 업데이트
            server.role = role
            db.session.commit()
            db.session.flush()  # PostgreSQL 연결 확인을 위한 추가 검증
            logger.info(f"✅ PostgreSQL 서버 역할 DB 업데이트 완료: {server_name} → {role}")
            
            # 성공 알림 (직접 DB 저장으로 즉시 SSE 감지)
            notification = Notification(
                type='ansible_role',
                title=f'서버 {server_name} 역할 할당 완료',
                message=f'역할 "{role}"이 성공적으로 적용되었습니다.',
                severity='success',
                details=message
            )
            db.session.add(notification)
            db.session.commit()
            logger.info(f"📢 서버 역할 할당 완료 알림 생성: {server_name} → {role}")
            
            # Redis 캐시 제거됨 - 실시간 조회로 변경
            
            logger.info(f"✅ 비동기 역할 할당 완료: {server_name} → {role}")
            return {
                'success': True,
                'message': f'서버 {server_name}에 역할 {role} 할당 완료',
                'server_name': server_name,
                'role': role
            }
        else:
            # 실패 알림 (직접 DB 저장으로 즉시 SSE 감지)
            notification = Notification(
                type='ansible_role',
                title=f'서버 {server_name} 역할 할당 실패',
                message=f'역할 "{role}" 할당 중 오류가 발생했습니다.',
                severity='error',
                details=message
            )
            db.session.add(notification)
            db.session.commit()
            logger.info(f"📢 서버 역할 할당 실패 알림 생성: {server_name} → {role}")
            
            raise Exception(f'Ansible 실행 실패: {message}')
            
    except Exception as e:
        logger.error(f"❌ 비동기 역할 할당 실패: {str(e)}")
        
        # 실패 알림 (직접 DB 저장으로 즉시 SSE 감지)
        try:
            from app.models.notification import Notification
            notification = Notification(
                type='ansible_role',
                title=f'서버 {server_name} 역할 할당 실패',
                message=f'역할 "{role}" 할당 중 오류가 발생했습니다: {str(e)}',
                severity='error'
            )
            db.session.add(notification)
            db.session.commit()
            logger.info(f"📢 서버 역할 할당 실패 알림 생성: {server_name} → {role}")
        except Exception:
            pass
        
        return {
            'success': False,
            'error': f'역할 할당 실패: {str(e)}',
            'message': f'서버 {server_name} 역할 할당 실패'
        }

@celery_app.task(bind=True)
def assign_role_bulk_async(self, server_names: list, role: str):
    """비동기 일괄 역할 할당"""
    try:
        logger.info(f"🔧 비동기 일괄 역할 할당 시작: {len(server_names)}개 서버 → {role}")
        
        # 상태 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': f'{len(server_names)}개 서버에 역할 {role} 할당 중...'}
        )
        
        from app.services import AnsibleService
        from app.models import Server
        from app.models.notification import Notification
        
        # 서버 정보 조회 및 IP 주소 수집
        db_servers = Server.query.filter(Server.name.in_(server_names)).all()
        target_servers = []
        missing_servers = []
        
        for server in db_servers:
            if server.ip_address and server.ip_address.strip():
                first_ip = server.ip_address.split(',')[0].strip()
                if first_ip:
                    target_servers.append({'ip_address': first_ip, 'name': server.name})
                else:
                    missing_servers.append(server.name)
            else:
                missing_servers.append(server.name)
        
        if not target_servers:
            raise Exception('선택된 서버들에 유효한 IP가 없습니다.')
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': f'Ansible 일괄 실행 중...'}
        )
        
        # 역할 해제인 경우
        if not role or role == 'none':
            logger.info(f"🔧 역할 해제: DB에서만 역할 제거")
            updated_count = 0
            for server in db_servers:
                server.role = None
                updated_count += 1
            
            if not safe_db_commit():
                logger.error(f"❌ 일괄 역할 해제 커밋 실패")
            
            # 성공 알림
            notification = Notification(
                type='ansible_role',
                title=f'일괄 역할 해제 완료',
                message=f'{updated_count}개 서버에서 역할이 해제되었습니다.',
                severity='success'
            )
            if safe_db_add(notification):
                safe_db_commit()
            
            # Redis 캐시 무효화 (서버 상태 즉시 반영)
            try:
                from app.utils import redis_utils
                # 모든 서버 관련 캐시 무효화
                redis_utils.delete_cache("servers:all_status")
                redis_utils.delete_cache("servers:status")
                redis_utils.delete_cache("servers:list")
                logger.info("🧹 Redis 서버 상태 캐시 삭제: servers:all_status, servers:status, servers:list")
            except Exception as cache_err:
                logger.warning(f"⚠️ 서버 상태 캐시 삭제 실패: {cache_err}")
            
            return {
                'success': True,
                'message': f'{updated_count}개 서버에서 역할이 해제되었습니다.',
                'updated_count': updated_count,
                'missing_servers': missing_servers
            }
        
        # Ansible 일괄 실행
        ansible_service = AnsibleService()
        success, message = ansible_service.run_role_for_multiple_servers(target_servers, role)
        
        if success:
            # DB 업데이트
            updated_count = 0
            for server in db_servers:
                if server.ip_address and server.ip_address.strip():
                    first_ip = server.ip_address.split(',')[0].strip()
                    if first_ip and any(t['ip_address'] == first_ip for t in target_servers):
                        server.role = role
                        updated_count += 1
            
            # DB 커밋 (시작/중지와 동일한 방식)
            db.session.commit()
            db.session.flush()  # PostgreSQL 연결 확인을 위한 추가 검증
            logger.info(f"✅ PostgreSQL 일괄 역할 할당 DB 업데이트 완료: {updated_count}개 서버 → {role}")
            
            # 성공 알림 (직접 DB 저장으로 즉시 SSE 감지)
            notification = Notification(
                type='ansible_role',
                title=f'일괄 역할 할당 완료',
                message=f'{updated_count}개 서버에 역할 "{role}"이 할당되었습니다.',
                severity='success',
                details=message
            )
            db.session.add(notification)
            db.session.commit()
            logger.info(f"📢 일괄 역할 할당 완료 알림 생성: {updated_count}개 서버 → {role}")
            
            # Redis 캐시 무효화 (서버 상태 즉시 반영)
            try:
                from app.utils import redis_utils
                # 모든 서버 관련 캐시 무효화
                redis_utils.delete_cache("servers:all_status")
                redis_utils.delete_cache("servers:status")
                redis_utils.delete_cache("servers:list")
                logger.info("🧹 Redis 서버 상태 캐시 삭제: servers:all_status, servers:status, servers:list")
            except Exception as cache_err:
                logger.warning(f"⚠️ 서버 상태 캐시 삭제 실패: {cache_err}")
            
            logger.info(f"✅ 비동기 일괄 역할 할당 완료: {updated_count}개 서버 → {role}")
            return {
                'success': True,
                'message': f'{updated_count}개 서버에 역할 {role} 할당 완료',
                'updated_count': updated_count,
                'missing_servers': missing_servers
            }
        else:
            # 실패 알림 (직접 DB 저장으로 즉시 SSE 감지)
            notification = Notification(
                type='ansible_role',
                title=f'일괄 역할 할당 실패',
                message=f'역할 "{role}" 할당 중 오류가 발생했습니다.',
                severity='error',
                details=message
            )
            db.session.add(notification)
            db.session.commit()
            logger.info(f"📢 일괄 역할 할당 실패 알림 생성: {role}")
            
            raise Exception(f'Ansible 일괄 실행 실패: {message}')
            
    except Exception as e:
        logger.error(f"❌ 비동기 일괄 역할 할당 실패: {str(e)}")
        
        # 실패 알림
        try:
            from app.models.notification import Notification
            notification = Notification(
                type='ansible_role',
                title=f'일괄 역할 할당 실패',
                message=f'역할 "{role}" 할당 중 오류가 발생했습니다: {str(e)}',
                severity='error'
            )
            if safe_db_add(notification):
                safe_db_commit()
        except Exception:
            pass
        
        return {
            'success': False,
            'error': f'일괄 역할 할당 실패: {str(e)}',
            'message': f'일괄 역할 할당 실패'
        }
