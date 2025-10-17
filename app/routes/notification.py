"""
알림 관련 라우트
"""
from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
from app.models import Notification
from app.routes.auth import permission_required
from app import db
import logging
import json
import time
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

bp = Blueprint('notification', __name__)

# SSE 연결 관리
sse_connections = defaultdict(list)

@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """알림 목록 조회"""
    try:
        # user_id가 None인 알림도 포함 (시스템 알림)
        notifications = Notification.query.filter(
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None))
        ).order_by(Notification.created_at.desc()).all()
        
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'details': notification.details,
                'severity': notification.severity,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None
            })
        
        resp = jsonify({'notifications': notification_data})
        # 캐시 방지 헤더 추가 (즉시 최신 알림 반영)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        logger.error(f"알림 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/latest', methods=['GET'])
@login_required
def get_latest_notification():
    """특정 서버/타입에 대한 최신 알림 1건 조회 (경량)

    Query params:
      - server: 서버 이름(제목/메시지 내 포함 여부로 필터)
      - type: 알림 타입 필터(옵션)
      - since_ts: Unix epoch seconds 이후의 알림만 반환(옵션)
    """
    try:
        server = request.args.get('server', type=str)
        ntype = request.args.get('type', type=str)
        since_ts = request.args.get('since_ts', type=float)

        if not server:
            return jsonify({'success': True, 'notification': None})

        query = Notification.query
        if ntype:
            query = query.filter(Notification.type == ntype)
        if since_ts:
            from datetime import datetime
            since_dt = datetime.fromtimestamp(since_ts)
            query = query.filter(Notification.created_at >= since_dt)

        # 제목/메시지 내 정확한 서버명 매칭(부분 일치에 의한 교차 매칭 방지)
        from sqlalchemy import or_
        token_a = f"서버 {server} "           # 예: 서버 test 
        token_b = f"서버 {server}\n"          # 줄바꿈 케이스
        token_c = f"'{server}'"               # 따옴표로 감싼 서버명
        token_d = f"\"{server}\""           # 쌍따옴표로 감싼 서버명
        token_e = f" {server} "               # 공백으로 구분된 서버명
        server_filter = or_(
            Notification.title.contains(token_a),
            Notification.title.contains(token_b),
            Notification.title.contains(token_c),
            Notification.title.contains(token_d),
            Notification.message.contains(token_a),
            Notification.message.contains(token_b),
            Notification.message.contains(token_c),
            Notification.message.contains(token_d),
            Notification.title == server,
            Notification.message == server,
        )
        query = query.filter(server_filter).order_by(Notification.created_at.desc())

        latest = query.first()
        data = None
        if latest:
            data = {
                'id': latest.id,
                'title': latest.title,
                'message': latest.message,
                'details': latest.details,
                'severity': latest.severity,
                'created_at': latest.created_at.isoformat() if latest.created_at else None
            }

        resp = jsonify({'success': True, 'notification': data})
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        logger.error(f"최신 알림 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/stream', methods=['GET'])
def notification_stream():
    """Server-Sent Events를 통한 실시간 알림 스트림"""
    from flask import stream_with_context
    
    def event_stream():
        # 로그인하지 않은 경우 기본 사용자 ID 사용
        user_id = current_user.id if current_user.is_authenticated else 0
        connection_id = f"{user_id}_{int(time.time() * 1000)}"
        last_id = 0
        
        # 연결 등록
        sse_connections[user_id].append(connection_id)
        
        try:
            # 즉시 연결 확인 메시지 전송(두 번 전송하여 즉시 인지율 향상)
            logger.info(f"SSE 연결 수립: {connection_id}")
            yield ': ping\n\n'
            yield f"data: {json.dumps({'type': 'connected', 'connection_id': connection_id})}\n\n"
            yield ': ping\n\n'
            
            # 하트비트 (15초마다)
            last_heartbeat = time.time()
            while True:
                try:
                    current_time = time.time()
                    
                    # 새로운 알림이 있는지 확인 (전체 사용자 공통 알림)
                    # 새 트랜잭션에서 읽도록 세션을 주기적으로 갱신
                    try:
                        db.session.expire_all()
                    except Exception:
                        pass
                    
                    # SQLite 락 오류 방지를 위한 재시도 로직
                    max_retries = 3
                    retry_count = 0
                    notifications = []
                    
                    while retry_count < max_retries:
                        try:
                            notifications = Notification.query.filter(
                                Notification.id > last_id
                            ).order_by(Notification.id.asc()).limit(20).all()
                            break
                        except Exception as db_error:
                            retry_count += 1
                            if "database is locked" in str(db_error) and retry_count < max_retries:
                                logger.warning(f"⚠️ DB 락 오류, {retry_count}초 후 재시도: {db_error}")
                                time.sleep(retry_count)
                                # 세션 갱신
                                try:
                                    db.session.rollback()
                                    db.session.close()
                                    db.session = db.create_scoped_session()
                                except Exception:
                                    pass
                            else:
                                logger.error(f"❌ DB 조회 실패: {db_error}")
                                break
                    
                    if notifications:
                        logger.info(f"🔔 SSE에서 {len(notifications)}개 새 알림 감지 (last_id: {last_id})")
                        for notification in notifications:
                            event_data = {
                                'id': notification.id,
                                'type': notification.type or 'notification',  # DB의 type 필드 사용
                                'severity': notification.severity,
                                'title': notification.title,
                                'message': notification.message,
                                'details': notification.details,
                                'created_at': notification.created_at.isoformat()
                            }
                            
                            logger.info(f"📤 SSE로 알림 전송: {notification.title}")
                            yield f"data: {json.dumps(event_data)}\n\n"
                            last_id = notification.id
                    
                    # 주기적 하트비트 전송 (더 자주)
                    if current_time - last_heartbeat >= 10:
                        yield ': ping\n\n'
                        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': current_time})}\n\n"
                        last_heartbeat = current_time
                    
                    time.sleep(1)  # 안정적인 간격으로 체크
                except Exception as loop_error:
                    logger.exception(f"SSE 루프 오류: {loop_error}")
                    # 잠시 대기 후 루프 계속 (연결 유지)
                    yield ': error\n\n'
                    time.sleep(2)
                
        except GeneratorExit:
            # 연결 종료 시 정리
            if user_id in sse_connections and connection_id in sse_connections[user_id]:
                sse_connections[user_id].remove(connection_id)
                if not sse_connections[user_id]:
                    del sse_connections[user_id]
            logger.info(f"SSE 연결 종료: {connection_id}")
    
    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',  # Nginx 버퍼링 방지
        'X-Accel-Cache': 'no',       # Nginx 캐시 방지
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Cache-Control',
        'Keep-Alive': 'timeout=60, max=1000'  # 연결 유지 설정
    }
    
    return Response(stream_with_context(event_stream()), headers=headers)

def broadcast_notification(user_id: int, notification_data: dict):
    """특정 사용자에게 알림 브로드캐스트"""
    if user_id in sse_connections:
        for connection_id in sse_connections[user_id].copy():
            try:
                # 실제로는 연결된 클라이언트에게 전송
                # 여기서는 로그만 출력 (실제 구현에서는 WebSocket이나 SSE 큐 사용)
                logger.info(f"알림 브로드캐스트: {user_id} -> {connection_id}: {notification_data}")
            except Exception as e:
                logger.error(f"알림 브로드캐스트 실패: {e}")
                # 연결 제거
                sse_connections[user_id].remove(connection_id)

@bp.route('/notifications/<int:notification_id>', methods=['GET'])
@login_required
def get_notification_by_id(notification_id: int):
    """알림 1건 조회 (상세 로그 포함)"""
    try:
        n = Notification.query.filter_by(id=notification_id).first()
        if not n:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        return jsonify({
            'success': True,
            'notification': {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'details': n.details,
                'severity': n.severity,
                'created_at': n.created_at.isoformat() if n.created_at else None
            }
        })
    except Exception as e:
        logger.error(f"알림 단건 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """알림 읽음 표시"""
    try:
        notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
        
        if not notification:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        notification.is_read = True
        db.session.commit()
        
        # PostgreSQL 연결 확인을 위한 추가 검증
        db.session.flush()
        logger.info(f"✅ PostgreSQL 알림 읽음 표시 완료: {notification_id}")
        
        return jsonify({'success': True, 'message': '알림이 읽음으로 표시되었습니다.'})
    except Exception as e:
        logger.error(f"알림 읽음 표시 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """읽지 않은 알림 개수"""
    try:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        logger.error(f"읽지 않은 알림 개수 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """개별 알림 삭제"""
    try:
        # user_id가 None인 시스템 알림도 삭제 가능하도록 수정
        notification = Notification.query.filter(
            (Notification.id == notification_id) & 
            ((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))
        ).first()
        
        if not notification:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '알림이 삭제되었습니다.'
        })
        
    except Exception as e:
        logger.error(f"개별 알림 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """모든 알림 삭제"""
    try:
        # user_id가 None인 시스템 알림도 삭제 가능하도록 수정
        Notification.query.filter(
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None))
        ).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '모든 알림이 삭제되었습니다.'
        })
        
    except Exception as e:
        logger.error(f"모든 알림 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500 