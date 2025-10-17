"""
알림 모델
"""
from datetime import datetime
from app import db

class Notification(db.Model):
    """알림 모델"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)
    severity = db.Column(db.String(20), default='info')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
    
    @property
    def severity_class(self):
        """Bootstrap 클래스용 심각도"""
        severity_map = {
            'info': 'info',
            'success': 'success',
            'warning': 'warning',
            'error': 'danger'
        }
        return severity_map.get(self.severity, 'info')
    
    @property
    def created_at_display(self):
        """생성 시간 표시용"""
        if not self.created_at:
            return ''
        
        now = datetime.utcnow()
        diff = now - self.created_at
        
        if diff.days > 0:
            return f"{diff.days}일 전"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}시간 전"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}분 전"
        else:
            return "방금 전"
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'details': self.details,
            'severity': self.severity,
            'severity_class': self.severity_class,
            'user_id': self.user_id,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_at_display': self.created_at_display
        }
    
    @classmethod
    def get_unread_count(cls, user_id=None):
        """읽지 않은 알림 수"""
        query = cls.query.filter_by(is_read=False)
        if user_id:
            query = query.filter(
                (cls.user_id == user_id) | (cls.user_id.is_(None))
            )
        return query.count()
    
    @classmethod
    def get_for_user(cls, user_id, limit=20):
        """사용자별 알림 목록"""
        return cls.query.filter(
            (cls.user_id == user_id) | (cls.user_id.is_(None))
        ).order_by(cls.created_at.desc()).limit(limit).all()
    
    def mark_as_read(self):
        """읽음으로 표시"""
        self.is_read = True
        db.session.commit()
    
    @classmethod
    def create_notification(cls, type, title, message, details=None, 
                          severity='info', user_id=None):
        """새 알림 생성"""
        notification = cls(
            type=type,
            title=title,
            message=message,
            details=details,
            severity=severity,
            user_id=user_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification 