"""
백업 관리 관련 라우트
"""
from flask import Blueprint, request, jsonify, current_app
import logging
from flask_login import login_required
from functools import wraps
import threading
import time
import uuid
from datetime import datetime
from app.routes.auth import permission_required
from app.models.notification import Notification
from app import db

# 안전한 DB 커밋 함수
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
                import time
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
    try:
        db.session.add(obj)
        return True
    except Exception as e:
        logger.error(f"❌ DB 추가 실패: {e}")
        return False


# 로거 설정
logger = logging.getLogger(__name__)

bp = Blueprint('backup', __name__)

# 백업 상태 관리 시스템 (간소화)
backup_status = {}  # 백업 중인 서버들의 상태 추적

def start_backup_monitoring(server_name, backup_config):
    """백업 모니터링 시작"""
    backup_id = str(uuid.uuid4())
    backup_status[server_name] = {
        'backup_id': backup_id,
        'status': 'running',
        'started_at': time.time(),
        'config': backup_config,
        'message': f'서버 {server_name} 백업이 진행 중입니다.',
        'last_check': time.time()
    }
    logger.info(f"🔧 백업 모니터링 시작: {server_name} (ID: {backup_id})")
    logger.info(f"🔧 backup_status에 추가됨: {backup_status}")
    return backup_id

def update_backup_status(server_name, status, message=None):
    """백업 상태 업데이트"""
    logger.info(f"🔧 백업 상태 업데이트 시도: {server_name} - {status} - {message}")
    logger.info(f"🔧 현재 backup_status: {backup_status}")
    
    if server_name in backup_status:
        backup_status[server_name]['status'] = status
        if message:
            backup_status[server_name]['message'] = message
        backup_status[server_name]['last_update'] = time.time()
        logger.info(f"백업 상태 업데이트 성공: {server_name} - {status} - {message}")
        logger.info(f"업데이트 후 backup_status: {backup_status}")
    else:
        logger.error(f"백업 상태를 찾을 수 없음: {server_name}")
        logger.error(f"현재 backup_status 키들: {list(backup_status.keys())}")

def is_server_backing_up(server_name):
    """서버가 백업 중인지 확인"""
    return server_name in backup_status and backup_status[server_name]['status'] == 'running'

def get_backup_status(server_name):
    """서버의 백업 상태 조회"""
    return backup_status.get(server_name, None)

def start_file_monitoring(server_name):
    """파일 기반 백업 완료 감지 시작"""
    def monitor_backup_files():
        from app.main import app
        with app.app_context():
            try:
                from app.services.proxmox_service import ProxmoxService
                proxmox_service = ProxmoxService()
                
                start_time = backup_status[server_name]['started_at']
                logger.info(f"🔍 백업 파일 감지 시작: {server_name} (시작: {datetime.fromtimestamp(start_time).strftime('%H:%M:%S')})")
                logger.info(f"🔍 현재 시간: {datetime.now().strftime('%H:%M:%S')}")
                logger.info(f"🔍 백업 시작 시간: {start_time}")
                
                check_count = 0
                
                # 30초마다 파일 체크
                while is_server_backing_up(server_name):
                    check_count += 1
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    
                    logger.info(f"🔍 파일 감지 체크 #{check_count}: {server_name} (경과: {elapsed_time:.1f}초)")
                    
                    try:
                        # 백업 타임아웃 체크 (30분)
                        if elapsed_time > 1800:  # 30분
                            logger.info(f"⏰ 백업 타임아웃: {server_name} (30분 초과)")
                            update_backup_status(server_name, 'failed', f'서버 {server_name} 백업이 타임아웃되었습니다. (30분 초과)')
                            break
                        
                        # 백업 파일 목록 확인
                        logger.info(f"🔍 백업 파일 목록 조회 시작: {server_name}")
                        backup_files = proxmox_service.get_server_backups(server_name)
                        logger.info(f"🔍 백업 파일 목록 응답: {backup_files}")
                        
                        if backup_files.get('success') and backup_files.get('data'):
                            backup_data = backup_files['data']
                            all_backups = backup_data.get('backups', [])
                            logger.info(f"🔍 전체 백업 파일 수: {len(all_backups)}")
                            
                            logger.info(f"🔍 백업 시작 시간: {start_time} ({datetime.fromtimestamp(start_time)})")
                            logger.info(f"🔍 현재 시간: {time.time()} ({datetime.now()})")

                            recent_backups = []
                            for b in all_backups:
                                file_ctime = b.get('ctime', 0)
                                file_name = b.get('name', '')
                                
                                logger.info(f"�� 파일: {file_name}")
                                logger.info(f"�� 파일 ctime: {file_ctime}")
                                logger.info(f"�� 파일 ctime (datetime): {datetime.fromtimestamp(file_ctime) if file_ctime else 'N/A'}")
                                logger.info(f"�� 시간 차이: {file_ctime - start_time:.1f}초")
                                logger.info(f"�� 조건 체크: {file_ctime} > {start_time} = {file_ctime > start_time}")
                                
                                if file_ctime > (start_time - 5):
                                    recent_backups.append(b)
                                    logger.info(f"최근 백업 파일로 인식")
                                else:
                                    logger.error(f"오래된 백업 파일로 제외")

                            logger.info(f"🔍 백업 시작 후 생성된 파일 수: {len(recent_backups)}")
                            
                            if recent_backups:
                                # 최근 백업 파일의 정보 확인
                                latest_backup = max(recent_backups, key=lambda x: x.get('ctime', 0))
                                backup_age = current_time - latest_backup.get('ctime', 0)
                                
                                logger.info(f"📁 백업 파일 발견: {latest_backup.get('name', 'unknown')}")
                                logger.info(f"📁 백업 파일 정보: {latest_backup}")
                                logger.info(f"📁 백업 파일 나이: {backup_age:.1f}초")
                                logger.info(f"📁 백업 파일 크기: {latest_backup.get('size_gb', 0)}GB")
                                
                                # 백업 파일이 최근에 생성되었고 (5분 이내), 파일 크기가 0이 아니면 완료로 간주
                                if backup_age < 300 and latest_backup.get('size_gb', 0) > 0:
                                    logger.info(f"백업 완료 조건 충족: {server_name}")
                                    update_backup_status(server_name, 'completed', f'서버 {server_name} 백업이 완료되었습니다.')
                                    logger.info(f"백업 완료 감지: {server_name} (파일: {latest_backup.get('name', 'unknown')})")
                                    
                                    # 완료 후 5분 후 상태 정리
                                    def cleanup_backup_status():
                                        time.sleep(300)  # 5분 후 정리
                                        if server_name in backup_status and backup_status[server_name]['status'] == 'completed':
                                            del backup_status[server_name]
                                            logger.info(f"🧹 완료된 백업 상태 정리: {server_name}")
                                    cleanup_thread = threading.Thread(target=cleanup_backup_status)
                                    cleanup_thread.daemon = True
                                    cleanup_thread.start()
                                    break
                                else:
                                    logger.info(f"⏳ 백업 파일 발견했지만 완료 조건 불충족: {server_name}")
                                    logger.info(f"⏳ 나이 조건: {backup_age:.1f}초 < 300초 = {backup_age < 300}")
                                    logger.info(f"⏳ 크기 조건: {latest_backup.get('size_gb', 0)}GB > 0 = {latest_backup.get('size_gb', 0) > 0}")
                            else:
                                logger.info(f"⏳ 백업 시작 후 생성된 백업 파일 없음: {server_name}")
                                logger.info(f"⏳ 전체 백업 파일들: {[b.get('name', 'unknown') for b in all_backups]}")
                        else:
                            logger.warning(f"백업 파일 목록 조회 실패: {server_name}")
                            logger.warning(f"응답: {backup_files}")
                            
                    except Exception as e:
                        logger.warning(f"백업 파일 확인 중 오류: {str(e)}")
                        import traceback
                        logger.warning(f"오류 상세: {traceback.format_exc()}")
                    
                    logger.info(f"⏳ 30초 대기 시작: {server_name}")
                    time.sleep(30)
                    logger.info(f"⏳ 30초 대기 완료: {server_name}")
                    
            except Exception as e:
                logger.error(f"백업 파일 감지 실패: {str(e)}")
                import traceback
                logger.error(f"오류 상세: {traceback.format_exc()}")
                update_backup_status(server_name, 'failed', f'백업 파일 감지 중 오류 발생: {str(e)}')
    
    logger.info(f"🔧 파일 감지 스레드 시작: {server_name}")
    # 백그라운드 스레드로 파일 감지 시작
    monitor_thread = threading.Thread(target=monitor_backup_files)
    monitor_thread.daemon = True
    monitor_thread.start()
    logger.info(f"🔧 파일 감지 스레드 시작 완료: {server_name}")



# 개별 서버 백업 관련 API 엔드포인트
@bp.route('/api/server/backup/<server_name>', methods=['POST'])
@permission_required('backup_management')
def create_server_backup(server_name):
    """개별 서버 백업 생성 (비동기)"""
    try:
        data = request.get_json()
        
        # 이미 백업 중인지 확인
        if is_server_backing_up(server_name):
            return jsonify({
                'error': f'서버 {server_name}은(는) 이미 백업 중입니다.'
            }), 400
        
        logger.info(f"🚀 비동기 서버 백업 시작: {server_name}")
        
        # Celery 비동기 태스크 실행
        from app.tasks.backup_tasks import create_server_backup_async
        task = create_server_backup_async.delay(server_name, data)
        
        # 시작 알림은 태스크에서 생성됨 (중복 방지)
        
        logger.info(f"✅ 비동기 백업 작업 시작: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'message': f'서버 {server_name} 백업 작업이 시작되었습니다.',
            'task_id': task.id,
            'status': 'queued'
        })
            
    except Exception as e:
        logger.error(f"백업 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/backups/<server_name>', methods=['GET'])
@permission_required('backup_management')
def get_server_backups(server_name):
    """개별 서버 백업 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_backups(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '백업 목록 조회 실패')}), 500
            
    except Exception as e:
        logger.error(f"백업 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/backup/status/<server_name>', methods=['GET'])
@permission_required('backup_management')
def get_server_backup_status(server_name):
    """서버 백업 상태 조회"""
    try:
        status = get_backup_status(server_name)
        logger.info(f"🔍 백업 상태 조회: {server_name} - {status}")
        logger.info(f"🔍 현재 backup_status 딕셔너리: {backup_status}")
        
        if status:
            logger.info(f"백업 상태 반환: {server_name} - {status['status']}")
            return jsonify({
                'success': True,
                'backup_status': status
            })
        else:
            logger.error(f"백업 상태 없음: {server_name}")
            return jsonify({
                'success': True,
                'backup_status': None
            })
    except Exception as e:
        logger.error(f"백업 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/backup/status', methods=['GET'])
@permission_required('backup_management')
def get_all_backup_status():
    """모든 서버의 백업 상태 조회"""
    try:
        logger.info(f"🔍 전체 백업 상태 조회 - 현재 backup_status: {backup_status}")
        return jsonify({
            'success': True,
            'backup_status': backup_status
        })
    except Exception as e:
        logger.error(f"전체 백업 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 백업 관리 관련 API 엔드포인트 (전체 백업 관리)
@bp.route('/api/backups/nodes', methods=['GET'])
@permission_required('backup_management')
def get_all_node_backups():
    """모든 노드의 백업 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_node_backups()
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('error', '백업 목록 조회 실패')}), 500
            
    except Exception as e:
        logger.error(f"백업 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/backups/nodes/<node_name>', methods=['GET'])
@permission_required('backup_management')
def get_node_backups(node_name):
    """특정 노드의 백업 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_node_backups(node_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('error', '백업 목록 조회 실패')}), 500
            
    except Exception as e:
        logger.error(f"백업 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/backups/restore', methods=['POST'])
@permission_required('backup_management')
def restore_backup():
    """백업 복원"""
    try:
        data = request.get_json()
        node = data.get('node')
        vm_id = data.get('vm_id')
        filename = data.get('filename')
        
        if not all([node, vm_id, filename]):
            return jsonify({'error': 'node, vm_id, filename이 모두 필요합니다.'}), 400
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.restore_backup(node, vm_id, filename)
        if result['success']:
            # 복원 성공 알림 생성
            notification = Notification(
                type='backup',
                title=f'백업 복원 완료',
                message=f'백업 파일 {filename}이 성공적으로 복원되었습니다.',
                severity='success',
                details=f'Node: {node}, VM ID: {vm_id}'
            )
            
            # 안전한 DB 커밋
            if safe_db_add(notification):
                if safe_db_commit():
                    logger.info(f"✅ 백업 복원 완료 알림 생성: {filename} (Node: {node}, VM ID: {vm_id})")
                else:
                    logger.error(f"❌ 백업 복원 완료 알림 커밋 실패: {filename}")
            else:
                logger.error(f"❌ 백업 복원 완료 알림 추가 실패: {filename}")
            
            logger.info(f"✅ 백업 복원 완료: {filename} (Node: {node}, VM ID: {vm_id})")
            return jsonify(result)
        else:
            # 복원 실패 알림 생성
            notification = Notification(
                type='backup',
                title=f'백업 복원 실패',
                message=f'백업 파일 {filename} 복원에 실패했습니다.',
                severity='error',
                details=result.get('message', '알 수 없는 오류')
            )
            
            # 안전한 DB 커밋
            if safe_db_add(notification):
                if safe_db_commit():
                    logger.info(f"✅ 백업 복원 실패 알림 생성: {filename}")
                else:
                    logger.error(f"❌ 백업 복원 실패 알림 커밋 실패: {filename}")
            else:
                logger.error(f"❌ 백업 복원 실패 알림 추가 실패: {filename}")
            
            return jsonify({'error': result.get('message', '백업 복원 실패')}), 500
            
    except Exception as e:
        logger.error(f"백업 복원 실패: {str(e)}")
        
        # 예외 발생 시 실패 알림 생성
        try:
            notification = Notification(
                type='backup',
                title=f'백업 복원 실패',
                message=f'백업 복원 중 오류가 발생했습니다: {str(e)}',
                severity='error'
            )
            
            # 안전한 DB 커밋
            if safe_db_add(notification):
                if safe_db_commit():
                    logger.info(f"✅ 백업 복원 예외 알림 생성: {str(e)}")
                else:
                    logger.error(f"❌ 백업 복원 예외 알림 커밋 실패: {str(e)}")
            else:
                logger.error(f"❌ 백업 복원 예외 알림 추가 실패: {str(e)}")
        except Exception as notify_error:
            logger.error(f"복원 실패 알림 생성 실패: {notify_error}")
        
        return jsonify({'error': str(e)}), 500

@bp.route('/api/test/notification', methods=['POST'])
@permission_required('backup_management')
def test_notification():
    """테스트 알림 생성"""
    try:
        # 테스트 알림 생성
        notification = Notification(
            type='backup',
            title='테스트 백업 알림',
            message='SSE 테스트를 위한 알림입니다.',
            severity='info',
            details='테스트 알림'
        )
        
        # 안전한 DB 커밋
        if safe_db_add(notification):
            if safe_db_commit():
                logger.info("✅ 테스트 알림 생성 성공")
                return jsonify({'success': True, 'message': '테스트 알림이 생성되었습니다.'})
            else:
                logger.error("❌ 테스트 알림 커밋 실패")
                return jsonify({'error': '테스트 알림 커밋 실패'}), 500
        else:
            logger.error("❌ 테스트 알림 추가 실패")
            return jsonify({'error': '테스트 알림 추가 실패'}), 500
            
    except Exception as e:
        logger.error(f"테스트 알림 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/backups/delete', methods=['POST'])
@permission_required('backup_management')
def delete_backup():
    """백업 삭제"""
    try:
        data = request.get_json()
        node = data.get('node')
        filename = data.get('filename')
        
        if not all([node, filename]):
            return jsonify({'error': 'node, filename이 모두 필요합니다.'}), 400
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.delete_backup(node, filename)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '백업 삭제 실패')}), 500
            
    except Exception as e:
        logger.error(f"백업 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/backup/<server_name>/status', methods=['GET'])
@permission_required('backup_management')
def get_backup_status(server_name):
    """서버 백업 상태 조회"""
    try:
        # 백업 상태 확인
        if is_server_backing_up(server_name):
            status_info = backup_status.get(server_name, {})
            return jsonify({
                'success': True,
                'is_backing_up': True,
                'status': status_info.get('status', 'unknown'),
                'backup_id': status_info.get('backup_id'),
                'message': status_info.get('message', '백업 진행 중'),
                'started_at': status_info.get('started_at'),
                'last_check': status_info.get('last_check')
            })
        else:
            return jsonify({
                'success': True,
                'is_backing_up': False,
                'status': 'idle',
                'message': '백업 중이 아닙니다.'
            })
            
    except Exception as e:
        logger.error(f"백업 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/tasks/<task_id>/status', methods=['GET'])
@permission_required('backup_management')
def get_backup_task_status(task_id):
    """백업 태스크 상태 조회"""
    try:
        from app.celery_app import celery_app
        
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            return jsonify({
                'success': True,
                'state': 'PENDING',
                'message': '작업 대기 중...'
            })
        elif task.state == 'PROGRESS':
            return jsonify({
                'success': True,
                'state': 'PROGRESS',
                'progress': task.info.get('progress', 0),
                'message': task.info.get('message', '작업 진행 중...')
            })
        elif task.state == 'SUCCESS':
            return jsonify({
                'success': True,
                'state': 'SUCCESS',
                'result': task.result,
                'message': '작업 완료'
            })
        else:
            return jsonify({
                'success': False,
                'state': task.state,
                'error': str(task.info) if task.info else '작업 실패'
            })
            
    except Exception as e:
        logger.error(f"태스크 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500 