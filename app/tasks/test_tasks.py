"""
간단한 Celery 테스트 태스크
"""
from app.celery_app import celery_app
import time
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def simple_test_task(self, message="Hello Celery"):
    """간단한 테스트 태스크"""
    try:
        task_id = self.request.id
        logger.info(f"🧪 테스트 태스크 시작: {message} (Task ID: {task_id})")
        
        # 작업 상태 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '테스트 진행 중...'}
        )
        
        # 1초 대기
        time.sleep(1)
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 50, 'total': 100, 'status': '테스트 중간 단계...'}
        )
        
        # 1초 더 대기
        time.sleep(1)
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 100, 'total': 100, 'status': '테스트 완료!'}
        )
        
        logger.info(f"✅ 테스트 태스크 완료: {message}")
        
        return {
            'success': True,
            'message': f'테스트 완료: {message}',
            'task_id': task_id
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ 테스트 태스크 실패: {error_msg}")
        
        # 간단한 실패 상태 업데이트
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'status': '테스트 실패'
            }
        )
        
        return {
            'success': False,
            'error': error_msg,
            'message': f'테스트 실패: {message}'
        }

@celery_app.task(bind=True)
def error_test_task(self, should_fail=True):
    """의도적으로 오류를 발생시키는 테스트 태스크"""
    task_id = self.request.id
    logger.info(f"🧪 오류 테스트 태스크 시작 (Task ID: {task_id})")
    
    if should_fail:
        # 예외를 발생시키지 않고 로그만 남기고 실패 결과 반환
        error_msg = "의도적인 테스트 오류"
        logger.error(f"❌ 오류 테스트 태스크 실패: {error_msg}")
        
        return {
            'success': False,
            'error': error_msg,
            'message': '오류 테스트 실패'
        }
    else:
        return {
            'success': True,
            'message': '오류 테스트 성공',
            'task_id': task_id
        }
