"""
Proxmox Manager 실행 파일
"""
import os
import sys
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Terraform 변수 자동 매핑
try:
    # config 디렉토리를 Python 경로에 추가
    config_dir = os.path.join(project_root, 'config')
    if config_dir not in sys.path:
        sys.path.insert(0, config_dir)
    
    from config import TerraformConfig
except ImportError as e:
    print(f"❌ config/config.py import 실패: {e}")
    print(f"현재 작업 디렉토리: {os.getcwd()}")
    print(f"프로젝트 루트: {project_root}")
    print(f"Python 경로: {sys.path}")
    
    # 대안 방법 시도
    try:
        import importlib.util
        config_path = os.path.join(project_root, 'config', 'config.py')
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        TerraformConfig = config_module.TerraformConfig
        print("✅ 대안 방법으로 config.py 로드 성공")
    except Exception as e2:
        print(f"❌ 대안 방법도 실패: {e2}")
        sys.exit(1)
TerraformConfig.setup_terraform_vars()

# Terraform 변수 검증
if not TerraformConfig.validate_terraform_vars():
    print("⚠️ 일부 Terraform 변수가 누락되었습니다. .env 파일을 확인하세요.")
    TerraformConfig.debug_terraform_vars()

from app.main import app, db
from app.models import User, Server, Notification, Project
from flask_login import login_required
from flask import render_template
import logging

if __name__ == '__main__':
    # 데이터베이스 테이블 생성
    with app.app_context():
        db.create_all()
        
        # 기본 관리자 계정 생성 (없는 경우)
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                name='시스템 관리자',
                email='admin@dmcmedia.co.kr',
                role='admin',
                is_active=True
            )
            admin_user.set_password('admin123!')
            db.session.add(admin_user)
            
            # 관리자에게 모든 권한 부여
            admin_permissions = [
                'view_all', 'create_server', 'start_server', 'stop_server', 
                'reboot_server', 'delete_server', 'assign_roles', 'remove_roles', 
                'manage_users', 'view_logs', 'manage_roles', 'manage_storage', 
                'manage_network', 'assign_firewall_group', 'remove_firewall_group'
            ]
            
            for permission in admin_permissions:
                admin_user.add_permission(permission)
            
            db.session.commit()
            print("기본 관리자 계정이 생성되었습니다.")
            print("사용자명: admin")
            print("비밀번호: admin123!")
            print("⚠️  보안을 위해 비밀번호를 변경하세요!")
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 개발 서버 실행
    print("🚀 Proxmox Manager 시작 중...")
    print("📱 웹 인터페이스: http://localhost:5000")
    print("🔑 기본 로그인: admin / admin123!")
    
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=5000,
        use_reloader=True
    ) 