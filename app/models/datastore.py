"""
Datastore 모델
"""
from datetime import datetime
from app import db

class Datastore(db.Model):
    """Datastore 정보 모델"""
    __tablename__ = 'datastores'
    
    id = db.Column(db.String(100), primary_key=True)  # datastore ID
    name = db.Column(db.String(100), nullable=False)  # datastore 이름
    type = db.Column(db.String(50), nullable=False)   # datastore 타입 (lvm, dir, nfs 등)
    size = db.Column(db.BigInteger, default=0)       # 총 크기 (bytes)
    used = db.Column(db.BigInteger, default=0)       # 사용된 크기 (bytes)
    available = db.Column(db.BigInteger, default=0)   # 사용 가능한 크기 (bytes)
    content = db.Column(db.Text)                     # 지원하는 콘텐츠 타입
    enabled = db.Column(db.Boolean, default=True)    # 활성화 상태
    is_default_hdd = db.Column(db.Boolean, default=False)  # 기본 HDD datastore 여부
    is_default_ssd = db.Column(db.Boolean, default=False)  # 기본 SSD datastore 여부
    is_system_default = db.Column(db.Boolean, default=False)  # 시스템 기본 datastore 여부
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'size': self.size,
            'used': self.used,
            'available': self.available,
            'content': self.content,
            'enabled': self.enabled,
            'is_default_hdd': self.is_default_hdd,
            'is_default_ssd': self.is_default_ssd,
            'is_system_default': self.is_system_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Datastore {self.id}>'
