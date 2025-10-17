"""
서버 비동기 작업 관련 엔드포인트
"""
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.routes.auth import permission_required
from app.routes.server_utils import validate_server_config, format_server_response, handle_server_error
from app.models.server import Server

logger = logging.getLogger(__name__)

# 비동기 작업용 별도 Blueprint 생성
async_bp = Blueprint('servers_async', __name__)


@async_bp.route('/api/servers/async', methods=['POST'])
@permission_required('create_server')
def create_server_async_endpoint():
    """비동기 서버 생성"""
    try:
        # 지연 임포트로 순환 참조 방지
        from app.tasks.server_tasks import create_server_async
        
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 4)
        os_type = data.get('os_type', 'rocky')
        role = data.get('role', '')
        firewall_group = data.get('firewall_group', '')
        disks = data.get('disks', [])
        
        if not server_name:
            return jsonify({'error': '서버 이름이 필요합니다.'}), 400
        
        # disks 필드 검증
        if not disks or not isinstance(disks, list) or len(disks) == 0:
            return jsonify({'error': 'disks 배열이 필요합니다.'}), 400
        
        # 서버 설정 검증
        is_valid, error_msg, config = validate_server_config(data)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # 서버 설정 구성
        server_config = {
            'name': server_name,
            'cpu': cpu,
            'memory': memory,
            'os_type': os_type,
            'role': role,
            'firewall_group': firewall_group,
            # disks 배열만 사용 (disk 필드 제거)
            'disks': disks,
            'network_devices': data.get('network_devices', []),
            'template_vm_id': data.get('template_vm_id', 8000),
            'vm_username': data.get('vm_username', 'rocky'),
            'vm_password': data.get('vm_password', 'rocky123')
        }
        
        # Celery 작업 실행
        task = create_server_async.delay(server_config)
        
        logger.info(f"🚀 비동기 서버 생성 작업 시작: {server_name} (Task ID: {task.id})")

        # 시작 알림 생성 (SSE로 즉시 표시)
        try:
            from app.models.notification import Notification
            from app import db
            start_noti = Notification(
                type='server_creation',
                title='서버 생성 시작',
                message=f'서버 {server_name} 생성이 시작되었습니다.',
                severity='info',
                details=f'Task ID: {task.id}'
            )
            db.session.add(start_noti)
            db.session.commit()
        except Exception as notify_err:
            logger.warning(f"시작 알림 생성 실패: {notify_err}")
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'서버 {server_name} 생성 작업이 시작되었습니다.',
            'status': 'queued'
        })
        
    except Exception as e:
        return jsonify(handle_server_error(e, "비동기 서버 생성")), 500


@async_bp.route('/api/servers/bulk_action', methods=['POST'])
@permission_required('manage_server')
def bulk_server_action_endpoint():
    """비동기 대량 서버 작업 (즉시 실행)"""
    try:
        from app.services import ProxmoxService
        from app.models import Server
        from app import db
        
        data = request.get_json()
        action = data.get('action')
        server_names = data.get('server_names', [])
        
        if not action or not server_names:
            return jsonify({'error': '작업 유형과 서버 목록이 필요합니다.'}), 400
        
        proxmox_service = ProxmoxService()
        success_servers = []
        failed_servers = []
        
        for server_name in server_names:
            try:
                if action == 'start':
                    if proxmox_service.start_server(server_name):
                        # DB 상태 업데이트
                        server = Server.query.filter_by(name=server_name).first()
                        if server:
                            server.status = 'running'
                            db.session.commit()
                        # 성공 알림 생성 (SSE로 전달)
                        try:
                            from app.models.notification import Notification
                            from app import db
                            notification = Notification(
                                type='server_start',
                                title='서버 시작 완료',
                                message=f'서버 {server_name}이 성공적으로 시작되었습니다.',
                                severity='success',
                                details=f'서버명: {server_name}'
                            )
                            db.session.add(notification)
                            db.session.commit()
                            logger.info(f"📢 서버 시작 완료 알림 생성: {server_name}")
                        except Exception as nerr:
                            logger.warning(f"알림 생성 실패(start): {server_name} - {nerr}")
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'stop':
                    if proxmox_service.stop_server(server_name):
                        # DB 상태 업데이트
                        server = Server.query.filter_by(name=server_name).first()
                        if server:
                            server.status = 'stopped'
                            db.session.commit()
                        # 성공 알림 생성 (SSE로 전달)
                        try:
                            from app.models.notification import Notification
                            from app import db
                            notification = Notification(
                                type='server_stop',
                                title='서버 중지 완료',
                                message=f'서버 {server_name}이 성공적으로 중지되었습니다.',
                                severity='success',
                                details=f'서버명: {server_name}'
                            )
                            db.session.add(notification)
                            db.session.commit()
                            logger.info(f"📢 서버 중지 완료 알림 생성: {server_name}")
                        except Exception as nerr:
                            logger.warning(f"알림 생성 실패(stop): {server_name} - {nerr}")
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'reboot':
                    if proxmox_service.reboot_server(server_name):
                        # 성공 알림 생성 (SSE로 전달)
                        try:
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
                            logger.info(f"📢 서버 재시작 완료 알림 생성: {server_name}")
                        except Exception as nerr:
                            logger.warning(f"알림 생성 실패(reboot): {server_name} - {nerr}")
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'delete':
                    # 삭제는 비동기로 처리
                    from app.tasks.server_tasks import delete_server_async
                    task = delete_server_async.delay(server_name)
                    success_servers.append(server_name)
                    
            except Exception as e:
                logger.error(f"서버 {server_name} {action} 실패: {str(e)}")
                failed_servers.append(server_name)
        
        # 결과에 따른 응답
        if success_servers and not failed_servers:
            return jsonify({
                'success': True,
                'message': f'모든 서버 {action} 완료: {", ".join(success_servers)}',
                'success_servers': success_servers,
                'failed_servers': failed_servers
            })
        elif success_servers and failed_servers:
            return jsonify({
                'success': True,
                'message': f'일부 서버 {action} 완료. 성공: {len(success_servers)}개, 실패: {len(failed_servers)}개',
                'success_servers': success_servers,
                'failed_servers': failed_servers
            })
        else:
            return jsonify({
                'success': False,
                'error': f'모든 서버 {action} 실패: {len(failed_servers)}개',
                'success_servers': success_servers,
                'failed_servers': failed_servers
            }), 500
        
    except Exception as e:
        return jsonify(handle_server_error(e, "대량 서버 작업")), 500


@async_bp.route('/api/tasks/<task_id>/status', methods=['GET'])
@login_required
def get_task_status(task_id):
    """작업 상태 조회"""
    try:
        from app.celery_app import celery_app
        
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'status': 'pending',
                'message': '작업 대기 중...',
                'progress': 0
            }
        elif task.state == 'PROGRESS':
            response = {
                'status': 'running',
                'message': task.info.get('message', '작업 진행 중...'),
                'progress': task.info.get('progress', 0)
            }
        elif task.state == 'SUCCESS':
            response = {
                'status': 'completed',
                'message': '작업 완료',
                'progress': 100,
                'result': task.result
            }
        else:  # FAILURE
            response = {
                'status': 'failed',
                'message': '작업 실패',
                'progress': 0,
                'error': str(task.info)
            }
        
        response['task_id'] = task_id
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"작업 상태 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '작업 상태 조회 실패',
            'error': str(e)
        }), 500


@async_bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@permission_required('delete_server')
def delete_server_endpoint(server_name):
    """비동기 서버 삭제"""
    try:
        # 서버 존재 확인
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        logger.info(f"🚀 비동기 서버 삭제 시작: {server_name}")
        
        # Celery 작업 시작
        from app.tasks.server_tasks import delete_server_async
        task = delete_server_async.delay(server_name)
        
        logger.info(f"✅ 서버 삭제 작업 시작: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'message': f'서버 {server_name} 삭제 작업이 시작되었습니다.',
            'status': 'queued',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"비동기 서버 삭제 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'서버 삭제 실패: {str(e)}'
        }), 500

@async_bp.route('/api/servers/<server_name>/start', methods=['POST'])
@permission_required('start_server')
def start_server_endpoint(server_name):
    """비동기 서버 시작"""
    try:
        # 서버 존재 확인
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        logger.info(f"🚀 비동기 서버 시작 시작: {server_name}")
        
        # Celery 작업 시작
        from app.tasks.server_tasks import start_server_async
        try:
            broker_url = getattr(getattr(start_server_async, 'app', None), 'conf', {}).broker_url  # type: ignore
            logger.info(f"📨 Celery 브로커(broker_url): {broker_url}")
        except Exception:
            pass
        task = start_server_async.delay(server_name)
        
        logger.info(f"✅ 서버 시작 작업 시작: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'message': f'서버 {server_name} 시작 작업이 시작되었습니다.',
            'status': 'queued',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"비동기 서버 시작 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'서버 시작 실패: {str(e)}'
        }), 500

@async_bp.route('/api/servers/<server_name>/stop', methods=['POST'])
@permission_required('stop_server')
def stop_server_endpoint(server_name):
    """비동기 서버 중지"""
    try:
        # 서버 존재 확인
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        logger.info(f"🚀 비동기 서버 중지 시작: {server_name}")
        
        # Celery 작업 시작
        from app.tasks.server_tasks import stop_server_async
        try:
            broker_url = getattr(getattr(stop_server_async, 'app', None), 'conf', {}).broker_url  # type: ignore
            logger.info(f"📨 Celery 브로커(broker_url): {broker_url}")
        except Exception:
            pass
        task = stop_server_async.delay(server_name)
        
        logger.info(f"✅ 서버 중지 작업 시작: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'message': f'서버 {server_name} 중지 작업이 시작되었습니다.',
            'status': 'queued',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"비동기 서버 중지 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'서버 중지 실패: {str(e)}'
        }), 500

@async_bp.route('/api/servers/<server_name>/reboot', methods=['POST'])
@permission_required('reboot_server')
def reboot_server_endpoint(server_name):
    """비동기 서버 재시작"""
    try:
        # 서버 존재 확인
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        logger.info(f"🚀 비동기 서버 재시작 시작: {server_name}")
        
        # Celery 작업 시작
        from app.tasks.server_tasks import reboot_server_async
        try:
            broker_url = getattr(getattr(reboot_server_async, 'app', None), 'conf', {}).broker_url  # type: ignore
            logger.info(f"📨 Celery 브로커(broker_url): {broker_url}")
        except Exception:
            pass
        task = reboot_server_async.delay(server_name)
        
        logger.info(f"✅ 서버 재시작 작업 시작: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'message': f'서버 {server_name} 재시작 작업이 시작되었습니다.',
            'status': 'queued',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"비동기 서버 재시작 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'서버 재시작 실패: {str(e)}'
        }), 500

@async_bp.route('/api/create_servers_bulk', methods=['POST'])
@permission_required('create_server')
def create_servers_bulk():
    """다중 서버 생성 - Celery 비동기 큐로 위임"""
    try:
        data = request.get_json()
        servers_data = data.get('servers', [])
        if not servers_data:
            return jsonify({'error': '서버 데이터가 필요합니다.'}), 400

        # 이름 중복 선검사
        from app.models import Server
        names = [s.get('name') for s in servers_data if s.get('name')]
        for name in names:
            if Server.query.filter_by(name=name).first():
                return jsonify({'error': f'이미 존재하는 서버 이름입니다: {name}'}), 400

        # Celery 태스크 큐에 넣기
        from app.tasks.server_tasks import create_servers_bulk_async
        async_result = create_servers_bulk_async.delay(servers_data)

        return jsonify({
            'success': True,
            'message': f'{len(servers_data)}개 서버 생성 작업이 큐에 등록되었습니다.',
            'task_id': async_result.id
        })
    except Exception as e:
        logger.error(f"다중 서버 생성 API 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500
