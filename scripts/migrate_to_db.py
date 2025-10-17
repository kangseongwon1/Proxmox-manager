#!/usr/bin/env python3
"""
기존 JSON 파일 데이터를 SQLite DB로 마이그레이션
"""

import json
import os
from database import db

def migrate_users():
    """사용자 데이터 마이그레이션"""
    print("사용자 데이터 마이그레이션 시작...")
    
    try:
        if os.path.exists('users.json'):
            with open('users.json', 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            
            migrated_count = 0
            for username, user_data in users_data.items():
                try:
                    # 이미 존재하는지 확인
                    existing_user = db.get_user_by_username(username)
                    if not existing_user:
                        db.create_user(
                            username=username,
                            password='temp_password_123',  # 임시 비밀번호
                            name=user_data.get('name', username),
                            email=user_data.get('email', ''),
                            role=user_data.get('role', 'developer')
                        )
                        migrated_count += 1
                        print(f"  ✓ 사용자 '{username}' 마이그레이션 완료")
                    else:
                        print(f"  - 사용자 '{username}' 이미 존재함")
                except Exception as e:
                    print(f"  ✗ 사용자 '{username}' 마이그레이션 실패: {e}")
            
            print(f"사용자 마이그레이션 완료: {migrated_count}개")
        else:
            print("users.json 파일이 없습니다. 기본 관리자 계정만 생성됩니다.")
    
    except Exception as e:
        print(f"사용자 마이그레이션 오류: {e}")

def migrate_notifications():
    """알림 데이터 마이그레이션"""
    print("알림 데이터 마이그레이션 시작...")
    
    try:
        if os.path.exists('notifications.json'):
            with open('notifications.json', 'r', encoding='utf-8') as f:
                notifications_data = json.load(f)
            
            migrated_count = 0
            for notification in notifications_data.get('notifications', []):
                try:
                    db.add_notification(
                        type=notification.get('type', 'info'),
                        title=notification.get('title', ''),
                        message=notification.get('message', ''),
                        details=notification.get('details'),
                        severity=notification.get('severity', 'info'),
                        user_id=notification.get('user_id')
                    )
                    migrated_count += 1
                except Exception as e:
                    print(f"  ✗ 알림 마이그레이션 실패: {e}")
            
            print(f"알림 마이그레이션 완료: {migrated_count}개")
        else:
            print("notifications.json 파일이 없습니다.")
    
    except Exception as e:
        print(f"알림 마이그레이션 오류: {e}")

def backup_json_files():
    """기존 JSON 파일 백업"""
    print("기존 JSON 파일 백업...")
    
    backup_dir = 'backup_json'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    json_files = ['users.json', 'notifications.json']
    for file_name in json_files:
        if os.path.exists(file_name):
            import shutil
            backup_path = os.path.join(backup_dir, f"{file_name}.backup")
            shutil.copy2(file_name, backup_path)
            print(f"  ✓ {file_name} → {backup_path}")

def main():
    """메인 마이그레이션 함수"""
    print("=" * 50)
    print("JSON → SQLite 마이그레이션 시작")
    print("=" * 50)
    
    # 백업
    backup_json_files()
    
    # 마이그레이션
    migrate_users()
    migrate_notifications()
    
    print("=" * 50)
    print("마이그레이션 완료!")
    print("=" * 50)
    print("다음 단계:")
    print("1. 애플리케이션을 재시작하세요")
    print("2. admin 계정으로 로그인하세요")
    print("3. 비밀번호를 변경하세요 (임시 비밀번호: temp_password_123)")
    print("4. 다른 사용자들의 비밀번호도 변경하세요")
    print("5. 백업된 JSON 파일은 backup_json/ 디렉토리에 있습니다")

if __name__ == '__main__':
    main() 