"""
프로젝트 모델
"""
from datetime import datetime
from app import db

class Project(db.Model):
    """프로젝트 모델"""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Project {self.name}>'
    
    @property
    def status_display(self):
        """상태 표시용 텍스트"""
        status_map = {
            'pending': '대기 중',
            'running': '실행 중',
            'completed': '완료',
            'failed': '실패',
            'cancelled': '취소됨'
        }
        return status_map.get(self.status, self.status)
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'status_display': self.status_display,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_by_name(cls, name):
        """이름으로 프로젝트 조회"""
        return cls.query.filter_by(name=name).first()
    
    @classmethod
    def get_by_status(cls, status):
        """상태별 프로젝트 목록 조회"""
        return cls.query.filter_by(status=status).all()
    
    def update_status(self, status):
        """상태 업데이트"""
        self.status = status
        self.updated_at = datetime.utcnow()
        db.session.commit() 