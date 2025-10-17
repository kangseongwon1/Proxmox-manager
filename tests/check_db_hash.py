#!/usr/bin/env python3
"""
데이터베이스 비밀번호 해시 확인 스크립트
"""

import sqlite3

def check_password_hashes():
    """데이터베이스의 비밀번호 해시 확인"""
    db_path = 'instance/proxmox_manager.db'
    
    print(f"🔍 데이터베이스 확인: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 사용자 테이블 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("❌ users 테이블이 없습니다.")
            return
        
        # 사용자 정보 조회
        cursor.execute("SELECT id, username, password_hash FROM users")
        users = cursor.fetchall()
        
        print(f"📋 사용자 수: {len(users)}")
        
        for user_id, username, password_hash in users:
            print(f"🔍 사용자: {username} (ID: {user_id})")
            print(f"  해시: {password_hash}")
            
            if password_hash:
                if 'scrypt:' in password_hash:
                    print(f"  ⚠️ scrypt 해시 발견!")
                elif 'pbkdf2:' in password_hash:
                    print(f"  ✅ pbkdf2 해시 (정상)")
                else:
                    print(f"  ❓ 알 수 없는 해시 형식")
            else:
                print(f"  ❌ 비밀번호 해시가 없음")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 데이터베이스 확인 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_password_hashes() 