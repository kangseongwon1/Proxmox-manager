"""
역할 할당 관련 API 라우트
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.routes.auth import permission_required
from app.models import Server
from app import db
import logging

logger = logging.getLogger(__name__)

# 역할 할당 전용 Blueprint
role_bp = Blueprint('role', __name__, url_prefix='/api')

@role_bp.route('/assign_role/<server_name>', methods=['POST'])
@login_required
@permission_required('assign_roles')
def assign_role_to_server(server_name):
    """서버에 역할 할당 (비동기)"""
    try:
        logger.info(f"🔧 역할 할당 요청: {server_name}")
        
        data = request.get_json()
        role = data.get('role')
        logger.info(f"🔧 할당할 역할: {role}")
        
        # 빈 문자열도 허용 (역할 제거)
        if role is None:
            return jsonify({'error': '역할(role)을 지정해야 합니다.'}), 400
        
        # 비동기 Celery 태스크 실행
        from app.tasks.role_tasks import assign_role_async
        from app.models.notification import Notification
        
        task = assign_role_async.delay(server_name, role)
        
        # 시작 알림 생성
        notification = Notification(
            type='ansible_role',
            title=f'서버 {server_name} 역할 할당 시작',
            message=f'역할 "{role}" 할당 작업이 시작되었습니다.',
            severity='info',
            details=f'Task ID: {task.id}'
        )
        db.session.add(notification)
        db.session.commit()
        
        # PostgreSQL 연결 확인을 위한 추가 검증
        db.session.flush()
        logger.info(f"✅ PostgreSQL 역할 할당 알림 저장 완료: {server_name} → {role}")
        
        logger.info(f"🚀 비동기 역할 할당 작업 시작: {server_name} → {role} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'message': f'서버 {server_name}에 역할 {role} 할당 작업이 시작되었습니다.',
            'task_id': task.id
        })
            
    except Exception as e:
        logger.error(f"역할 할당 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@role_bp.route('/remove_role/<server_name>', methods=['POST'])
@permission_required('remove_role')
def remove_role(server_name):
    """서버에서 역할 제거"""
    try:
        logger.info(f"🔧 역할 제거 요청: {server_name}")
        
        # DB에서 역할 제거
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.role = None
        db.session.commit()
        
        logger.info(f"✅ 역할 제거 완료: {server_name}")
        return jsonify({
            'success': True,
            'message': f'서버 {server_name}에서 역할이 제거되었습니다.'
        })
        
    except Exception as e:
        logger.error(f"역할 제거 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@role_bp.route('/roles/assign_bulk', methods=['POST'])
@permission_required('assign_roles')
def assign_role_bulk():
    """다중 서버에 역할 할당 (비동기)"""
    try:
        logger.info(f"🔧 다중 서버 역할 할당 요청")
        
        data = request.get_json()
        server_names = data.get('server_names', [])
        role = data.get('role')
        
        logger.info(f"🔧 대상 서버들: {server_names}")
        logger.info(f"🔧 할당할 역할: {role}")
        
        if not server_names:
            return jsonify({'error': '서버 목록을 지정해야 합니다.'}), 400
        
        if not role or role == '':
            return jsonify({'error': '역할(role)을 지정해야 합니다.'}), 400
        
        # "none" 값을 역할 해제로 처리
        if role == 'none':
            logger.info(f"🔧 역할 해제 요청으로 변환: none → None")
            role = None
        
        # 비동기 Celery 태스크 실행
        from app.tasks.role_tasks import assign_role_bulk_async
        from app.models.notification import Notification
        
        task = assign_role_bulk_async.delay(server_names, role)
        
        # 시작 알림 생성
        notification = Notification(
            type='ansible_role',
            title=f'일괄 역할 할당 시작',
            message=f'{len(server_names)}개 서버에 역할 "{role}" 할당 작업이 시작되었습니다.',
            severity='info',
            details=f'Task ID: {task.id}'
        )
        db.session.add(notification)
        db.session.commit()
        
        # PostgreSQL 연결 확인을 위한 추가 검증
        db.session.flush()
        logger.info(f"✅ PostgreSQL 역할 할당 알림 저장 완료: {len(server_names)}개 서버 → {role}")
        
        logger.info(f"🚀 비동기 일괄 역할 할당 작업 시작: {len(server_names)}개 서버 → {role} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'message': f'{len(server_names)}개 서버에 역할 {role} 할당 작업이 시작되었습니다.',
            'task_id': task.id
        })

    except Exception as e:
        logger.error(f"일괄 역할 할당 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500
