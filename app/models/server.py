"""
서버 모델
"""
from datetime import datetime
from app import db

class Server(db.Model):
    """서버 모델"""
    __tablename__ = 'servers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    vmid = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    ip_address = db.Column(db.String(45))  # IPv6 지원
    role = db.Column(db.String(50))
    firewall_group = db.Column(db.String(50))
    os_type = db.Column(db.String(50))
    cpu = db.Column(db.Integer)
    memory = db.Column(db.Integer)  # MB 단위
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Server {self.name}>'
    
    @property
    def memory_gb(self):
        """메모리를 GB 단위로 반환"""
        return self.memory / 1024 if self.memory else 0
    
    @property
    def status_display(self):
        """상태 표시용 텍스트"""
        status_map = {
            'running': '실행 중',
            'stopped': '중지됨',
            'pending': '대기 중',
            'creating': '생성 중',
            'deleting': '삭제 중',
            'error': '오류'
        }
        return status_map.get(self.status, self.status)
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'name': self.name,
            'vmid': self.vmid,
            'status': self.status,
            'status_display': self.status_display,
            'ip_address': self.ip_address,
            'role': self.role,
            'firewall_group': self.firewall_group,
            'os_type': self.os_type,
            'cpu': self.cpu,
            'memory': self.memory,
            'memory_gb': self.memory_gb,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_by_name(cls, name):
        """이름으로 서버 조회"""
        return cls.query.filter_by(name=name).first()
    
    @classmethod
    def get_all_active(cls):
        """활성 서버 목록 조회"""
        return cls.query.filter(cls.status.in_(['running', 'pending'])).all()
    
    @classmethod
    def get_by_status(cls, status):
        """상태별 서버 목록 조회"""
        return cls.query.filter_by(status=status).all()
    
    def update_status(self, status):
        """상태 업데이트"""
        self.status = status
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def update_vm_info(self, vmid, ip_address=None):
        """VM 정보 업데이트"""
        self.vmid = vmid
        if ip_address:
            self.ip_address = ip_address
        self.updated_at = datetime.utcnow()
        db.session.commit() 