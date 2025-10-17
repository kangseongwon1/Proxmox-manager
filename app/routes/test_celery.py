"""
Celery 테스트 API 엔드포인트
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required
import logging

logger = logging.getLogger(__name__)
test_bp = Blueprint('test_celery', __name__)

@test_bp.route('/api/test/simple', methods=['POST'])
@login_required
def test_simple_task():
    """간단한 Celery 테스트"""
    try:
        # 지연 import로 순환 import 방지
        from app.tasks.test_tasks import simple_test_task
        
        data = request.get_json() or {}
        message = data.get('message', 'Hello Celery')
        
        # 간단한 테스트 태스크 실행
        task = simple_test_task.delay(message)
        
        return jsonify({
            'success': True,
            'message': '간단한 테스트 작업이 시작되었습니다.',
            'task_id': task.id,
            'status': 'queued'
        })
        
    except Exception as e:
        logger.error(f"간단한 테스트 작업 시작 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '간단한 테스트 작업 시작 실패'
        }), 500

@test_bp.route('/api/test/error', methods=['POST'])
@login_required
def test_error_task():
    """오류 테스트 Celery 태스크"""
    try:
        # 지연 import로 순환 import 방지
        from app.tasks.test_tasks import error_test_task
        
        data = request.get_json() or {}
        should_fail = data.get('should_fail', True)
        
        # 오류 테스트 태스크 실행
        task = error_test_task.delay(should_fail)
        
        return jsonify({
            'success': True,
            'message': '오류 테스트 작업이 시작되었습니다.',
            'task_id': task.id,
            'status': 'queued'
        })
        
    except Exception as e:
        logger.error(f"오류 테스트 작업 시작 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '오류 테스트 작업 시작 실패'
        }), 500
