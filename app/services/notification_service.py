"""
알림 서비스
"""
import logging
from typing import Dict, List, Any, Optional
from flask import current_app
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger(__name__)

class NotificationService:
    """알림 서비스"""
    
    @staticmethod
    def create_notification(type: str, title: str, message: str, 
                          details: str = None, severity: str = 'info', 
                          user_id: int = None) -> Notification:
        """새 알림 생성"""
        try:
            notification = Notification.create_notification(
                type=type,
                title=title,
                message=message,
                details=details,
                severity=severity,
                user_id=user_id
            )
            
            logger.info(f"알림 생성 성공: {title}")
            return notification
            
        except Exception as e:
            logger.error(f"알림 생성 실패: {e}")
            raise
    
    @staticmethod
    def get_notifications_for_user(user_id: int, limit: int = 20) -> List[Notification]:
        """사용자별 알림 목록 조회"""
        try:
            return Notification.get_for_user(user_id, limit)
        except Exception as e:
            logger.error(f"사용자 {user_id} 알림 목록 조회 실패: {e}")
            return []
    
    @staticmethod
    def get_unread_count(user_id: int = None) -> int:
        """읽지 않은 알림 수"""
        try:
            return Notification.get_unread_count(user_id)
        except Exception as e:
            logger.error(f"읽지 않은 알림 수 조회 실패: {e}")
            return 0
    
    @staticmethod
    def mark_as_read(notification_id: int) -> bool:
        """알림을 읽음으로 표시"""
        try:
            notification = Notification.query.get(notification_id)
            if notification:
                notification.mark_as_read()
                return True
            return False
        except Exception as e:
            logger.error(f"알림 읽음 표시 실패: {e}")
            return False
    
    @staticmethod
    def clear_all_notifications(user_id: int = None) -> int:
        """모든 알림 삭제"""
        try:
            if user_id:
                count = Notification.query.filter_by(user_id=user_id).delete()
            else:
                count = Notification.query.delete()
            
            from app import db
            db.session.commit()
            return count
        except Exception as e:
            logger.error(f"모든 알림 삭제 실패: {e}")
            from app import db
            db.session.rollback()
            return 0
    
    @staticmethod
    def create_server_notification(server_name: str, action: str, 
                                 status: str, details: str = None) -> Notification:
        """서버 관련 알림 생성"""
        notification_map = {
            'create': {
                'success': {
                    'title': f'서버 생성 완료',
                    'message': f'서버 {server_name}이(가) 성공적으로 생성되었습니다.',
                    'severity': 'success'
                },
                'error': {
                    'title': f'서버 생성 실패',
                    'message': f'서버 {server_name} 생성 중 오류가 발생했습니다.',
                    'severity': 'error'
                }
            },
            'delete': {
                'success': {
                    'title': f'서버 삭제 완료',
                    'message': f'서버 {server_name}이(가) 성공적으로 삭제되었습니다.',
                    'severity': 'success'
                },
                'error': {
                    'title': f'서버 삭제 실패',
                    'message': f'서버 {server_name} 삭제 중 오류가 발생했습니다.',
                    'severity': 'error'
                }
            },
            'start': {
                'success': {
                    'title': f'서버 시작 완료',
                    'message': f'서버 {server_name}이(가) 시작되었습니다.',
                    'severity': 'success'
                },
                'error': {
                    'title': f'서버 시작 실패',
                    'message': f'서버 {server_name} 시작 중 오류가 발생했습니다.',
                    'severity': 'error'
                }
            },
            'stop': {
                'success': {
                    'title': f'서버 중지 완료',
                    'message': f'서버 {server_name}이(가) 중지되었습니다.',
                    'severity': 'warning'
                },
                'error': {
                    'title': f'서버 중지 실패',
                    'message': f'서버 {server_name} 중지 중 오류가 발생했습니다.',
                    'severity': 'error'
                }
            },
            'reboot': {
                'success': {
                    'title': f'서버 재부팅 완료',
                    'message': f'서버 {server_name}이(가) 재부팅되었습니다.',
                    'severity': 'info'
                },
                'error': {
                    'title': f'서버 재부팅 실패',
                    'message': f'서버 {server_name} 재부팅 중 오류가 발생했습니다.',
                    'severity': 'error'
                }
            }
        }
        
        if action in notification_map and status in notification_map[action]:
            notification_info = notification_map[action][status]
            return NotificationService.create_notification(
                type=f'server_{action}',
                title=notification_info['title'],
                message=notification_info['message'],
                details=details,
                severity=notification_info['severity']
            )
        else:
            # 기본 알림
            return NotificationService.create_notification(
                type=f'server_{action}',
                title=f'서버 {action}',
                message=f'서버 {server_name}에 대한 {action} 작업이 {status} 상태입니다.',
                details=details,
                severity='info' if status == 'success' else 'error'
            )
    
    @staticmethod
    def create_system_notification(title: str, message: str, 
                                 severity: str = 'info', details: str = None) -> Notification:
        """시스템 알림 생성"""
        return NotificationService.create_notification(
            type='system',
            title=title,
            message=message,
            details=details,
            severity=severity
        )
    
    @staticmethod
    def create_user_notification(user_id: int, title: str, message: str,
                               severity: str = 'info', details: str = None) -> Notification:
        """사용자별 알림 생성"""
        return NotificationService.create_notification(
            type='user',
            title=title,
            message=message,
            details=details,
            severity=severity,
            user_id=user_id
        ) 