"""
서버 관련 공통 유틸리티 함수들
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from flask import jsonify, request
from app.models import Server, Notification
from app import db
from app.utils.redis_utils import redis_utils
from datetime import datetime

logger = logging.getLogger(__name__)

# 전역 작업 상태 dict
tasks = {}


def create_task(status: str, task_type: str, message: str) -> str:
    """작업 생성"""
    import uuid
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': status,
        'type': task_type,
        'message': message,
        'created_at': datetime.now()
    }
    return task_id


def update_task(task_id: str, status: str, message: str = None):
    """작업 상태 업데이트"""
    if task_id in tasks:
        tasks[task_id]['status'] = status
        if message:
            tasks[task_id]['message'] = message
        tasks[task_id]['updated_at'] = datetime.now()


def create_notification(notification_type: str, title: str, message: str, 
                       details: str = "", severity: str = "info", user_id: int = None) -> Notification:
    """알림 생성 헬퍼 함수"""
    notification = Notification(
        type=notification_type,
        title=title,
        message=message,
        details=details,
        severity=severity,
        user_id=user_id
    )
    db.session.add(notification)
    return notification


def get_server_by_name(server_name: str) -> Optional[Server]:
    """서버 이름으로 서버 조회"""
    return Server.query.filter_by(name=server_name).first()


def validate_server_config(data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """서버 설정 검증"""
    required_fields = ['name', 'cpu', 'memory', 'disks']
    
    for field in required_fields:
        if field not in data:
            return False, f"필수 필드가 누락되었습니다: {field}", {}
    
    # disks 배열 검증
    disks = data.get('disks', [])
    if not disks or not isinstance(disks, list) or len(disks) == 0:
        return False, "disks 배열이 필요합니다.", {}
    
    # 서버 이름 중복 확인
    existing_server = get_server_by_name(data['name'])
    if existing_server:
        return False, "이미 존재하는 서버 이름입니다.", {}
    
    return True, "", data


def format_server_response(success: bool, message: str = "", data: Any = None, 
                         error: str = None) -> Dict[str, Any]:
    """서버 API 응답 포맷팅"""
    response = {
        'success': success,
        'message': message
    }
    
    if data is not None:
        response['data'] = data
    
    if error:
        response['error'] = error
        
    return response


def get_cached_server_status():
    """Redis 캐시에서 서버 상태 조회"""
    cache_key = "servers:all_status"
    cached_data = redis_utils.get_cache(cache_key)
    if cached_data:
        logger.info("📦 Redis 캐시에서 서버 상태 데이터 로드")
        return cached_data
    return None


def set_cached_server_status(data: Dict[str, Any], expire: int = 120):
    """서버 상태를 Redis에 캐시 저장"""
    cache_key = "servers:all_status"
    redis_utils.set_cache(cache_key, data, expire=expire)
    logger.info("💾 서버 상태 데이터를 Redis에 캐시 저장")


def merge_db_server_info(servers: Dict[str, Any]) -> Dict[str, Any]:
    """Proxmox 서버 데이터에 DB 정보 병합"""
    db_servers = Server.query.all()
    db_server_map = {s.name: s for s in db_servers}
    
    logger.info(f"🔧 DB에서 조회된 서버 수: {len(db_servers)}")
    for db_server in db_servers:
        logger.info(f"🔧 DB 서버: {db_server.name} → role={db_server.role}")
    
    for vm_key, server_data in servers.items():
        server_name = server_data.get('name')
        if server_name and server_name in db_server_map:
            db_server = db_server_map[server_name]
            server_data['role'] = db_server.role
            server_data['firewall_group'] = db_server.firewall_group
            server_data['os_type'] = db_server.os_type
            logger.info(f"🔧 서버 '{server_name}' DB 정보 병합: role={db_server.role}, firewall_group={db_server.firewall_group}")
        else:
            logger.warning(f"⚠️ DB에서 서버 '{server_name}' 정보를 찾을 수 없음")
    
    return servers


def handle_server_error(error: Exception, operation: str = "서버 작업") -> Dict[str, Any]:
    """서버 에러 처리 공통 함수"""
    error_msg = str(error)
    logger.error(f"{operation} 실패: {error_msg}")
    return format_server_response(False, f"{operation} 중 오류가 발생했습니다.", error=error_msg)
