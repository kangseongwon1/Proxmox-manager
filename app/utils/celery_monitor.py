"""
Celery 작업 모니터링 유틸리티
"""
import logging
from celery import current_app
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

class CeleryMonitor:
    """Celery 작업 모니터링 클래스"""
    
    @staticmethod
    def get_active_tasks():
        """현재 활성 작업 목록 조회"""
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            return active_tasks or {}
        except Exception as e:
            logger.error(f"활성 작업 조회 실패: {e}")
            return {}
    
    @staticmethod
    def get_scheduled_tasks():
        """예약된 작업 목록 조회"""
        try:
            inspect = celery_app.control.inspect()
            scheduled_tasks = inspect.scheduled()
            return scheduled_tasks or {}
        except Exception as e:
            logger.error(f"예약 작업 조회 실패: {e}")
            return {}
    
    @staticmethod
    def get_worker_stats():
        """워커 통계 조회"""
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            return stats or {}
        except Exception as e:
            logger.error(f"워커 통계 조회 실패: {e}")
            return {}
    
    @staticmethod
    def get_task_info(task_id):
        """특정 작업 정보 조회"""
        try:
            result = celery_app.AsyncResult(task_id)
            return {
                'task_id': task_id,
                'status': result.status,
                'result': result.result,
                'traceback': result.traceback
            }
        except Exception as e:
            logger.error(f"작업 정보 조회 실패: {e}")
            return None
    
    @staticmethod
    def cancel_task(task_id):
        """작업 취소"""
        try:
            celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"작업 취소됨: {task_id}")
            return True
        except Exception as e:
            logger.error(f"작업 취소 실패: {e}")
            return False
    
    @staticmethod
    def get_queue_length():
        """큐 길이 조회"""
        try:
            inspect = celery_app.control.inspect()
            reserved_tasks = inspect.reserved()
            active_tasks = inspect.active()
            
            total_tasks = 0
            if reserved_tasks:
                total_tasks += sum(len(tasks) for tasks in reserved_tasks.values())
            if active_tasks:
                total_tasks += sum(len(tasks) for tasks in active_tasks.values())
            
            return total_tasks
        except Exception as e:
            logger.error(f"큐 길이 조회 실패: {e}")
            return 0

# 전역 인스턴스
celery_monitor = CeleryMonitor()
