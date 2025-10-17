"""
메인 애플리케이션 진입점
"""
from app import create_app, db
from app.models import User, Server, Notification, Project
from flask_login import LoginManager
import os

app = create_app()

# 로그인 매니저 설정 (app/__init__.py에서 이미 설정됨)
from app import login_manager

@login_manager.user_loader
def load_user(user_id):
    """사용자 로더"""
    return User.query.get(int(user_id))

if __name__ == '__main__':
    # 데이터베이스 테이블 생성
    with app.app_context():
        db.create_all()
        
        # 기본 관리자 사용자 생성
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin_user.set_password('admin123!')
            db.session.add(admin_user)
            db.session.commit()
            print("✅ 기본 관리자 계정이 생성되었습니다: admin / admin123!")
    
    print("🚀 Proxmox Manager 시작 중...")
    print("🌐 웹 인터페이스: http://localhost:5000")
    print("🔑 기본 로그인: admin / admin123!")
    
    # 개발 서버 실행
    app.run(debug=True, host='0.0.0.0', port=5000) 