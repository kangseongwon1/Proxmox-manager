"""
사용자 모델
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db

class User(UserMixin, db.Model):
    """사용자 모델"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    role = db.Column(db.String(20), default='developer')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    permissions = db.relationship('UserPermission', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    @property
    def is_admin(self):
        """관리자 여부 확인"""
        return self.role == 'admin'
    
    def set_password(self, password):
        """비밀번호 설정"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """비밀번호 확인"""
        return check_password_hash(self.password_hash, password)
    
    def update_user_login(self):
        """사용자 마지막 로그인 시간 업데이트"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_permissions(self):
        """사용자 권한 목록 반환"""
        return [perm.permission for perm in self.permissions]
    
    def has_permission(self, permission):
        """특정 권한 보유 여부 확인"""
        return self.permissions.filter_by(permission=permission).first() is not None
    
    def add_permission(self, permission):
        """권한 추가"""
        if not self.has_permission(permission):
            user_perm = UserPermission(user_id=self.id, permission=permission)
            db.session.add(user_perm)
            db.session.commit()
    
    def remove_permission(self, permission):
        """권한 제거"""
        user_perm = self.permissions.filter_by(permission=permission).first()
        if user_perm:
            db.session.delete(user_perm)
            db.session.commit()
    
    def set_permissions(self, permissions):
        """사용자 권한을 완전히 교체"""
        # 기존 권한 모두 삭제
        self.permissions.delete()
        # 새 권한 추가
        for permission in permissions:
            user_perm = UserPermission(user_id=self.id, permission=permission)
            db.session.add(user_perm)
        db.session.commit()

class UserPermission(db.Model):
    """사용자 권한 모델"""
    __tablename__ = 'user_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    permission = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'permission'),)
    
    def __repr__(self):
        return f'<UserPermission {self.user_id}:{self.permission}>' 