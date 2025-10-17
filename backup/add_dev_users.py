#!/usr/bin/env python3
"""
dev1, dev2 사용자를 DB에 추가하는 스크립트
"""

from database import db
from werkzeug.security import generate_password_hash

def add_dev_users():
    """dev1, dev2 사용자 추가 (기존 해시값 사용)"""
    
    # dev1 사용자 추가 (기존 해시값 사용)
    try:
        dev1_id = db.create_user_with_hash(
            username='dev1',
            password_hash='scrypt:32768:8:1$DZwKGedKYTOM4jdg$84d7bd4a7e4e6b1f772aae62d79847586930a282e1abd3d252889b8db027536940629ab0883e4e6b8f85f555f9c53d6454659310ecbdca24ac582d62bc417e80',
            name='개발자 1',
            email='dev1@dmcmedia.co.kr',
            role='developer'
        )
        # dev1에게 view_all, create_server 권한 부여
        db.add_user_permissions(dev1_id, ['view_all', 'create_server'])
        print("✅ dev1 사용자 추가 완료 (view_all, create_server 권한)")
    except Exception as e:
        print(f"❌ dev1 사용자 추가 실패: {e}")
    
    # dev2 사용자 추가 (기존 해시값 사용)
    try:
        dev2_id = db.create_user_with_hash(
            username='dev2',
            password_hash='scrypt:32768:8:1$r8YD2qOdFcLlzpW8$6a262904d78cbfd9a8d700c2965555e99e16140148f8137a521499525b7fd92ac8443553eb0cf6b6d2c1ccbaee63a3d6b5bc022d9bcd60c021c09bd612601309',
            name='개발자 2',
            email='dev2@dmcmedia.co.kr',
            role='developer'
        )
        # dev2에게 view_all 권한만 부여
        db.add_user_permissions(dev2_id, ['view_all'])
        print("✅ dev2 사용자 추가 완료 (view_all 권한)")
    except Exception as e:
        print(f"❌ dev2 사용자 추가 실패: {e}")
    
    # 확인
    print("\n📋 현재 사용자 목록:")
    users = db.get_all_users()
    for user in users:
        permissions = db.get_user_permissions(user['id'])
        print(f"👤 {user['username']} ({user['role']}) - 권한: {permissions}")

if __name__ == "__main__":
    add_dev_users() 