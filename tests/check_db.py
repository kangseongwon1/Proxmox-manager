#!/usr/bin/env python3
"""
데이터베이스 확인 스크립트
"""

import sqlite3
import os

def check_database():
    """데이터베이스 상태 확인"""
    db_path = 'instance/proxmox_manager.db'
    
    print(f"🔍 데이터베이스 파일 확인: {db_path}")
    print(f"📁 파일 존재: {os.path.exists(db_path)}")
    
    if os.path.exists(db_path):
        print(f"📊 파일 크기: {os.path.getsize(db_path)} bytes")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 목록 조회
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n📋 테이블 목록:")
        if tables:
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("  ❌ 테이블이 없습니다!")
        
        # 각 테이블의 레코드 수 확인
        if tables:
            print(f"\n📊 테이블별 레코드 수:")
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    print(f"  - {table_name}: {count}개 레코드")
                except Exception as e:
                    print(f"  - {table_name}: 조회 실패 - {e}")
        
        # servers 테이블 상세 확인
        print(f"\n🖥️ servers 테이블 상세:")
        try:
            cursor.execute("PRAGMA table_info(servers)")
            columns = cursor.fetchall()
            if columns:
                print("  📋 컬럼 정보:")
                for col in columns:
                    print(f"    - {col[1]} ({col[2]})")
                
                cursor.execute("SELECT * FROM servers LIMIT 5")
                rows = cursor.fetchall()
                if rows:
                    print("  📄 데이터 샘플:")
                    for row in rows:
                        print(f"    - {row}")
                else:
                    print("  📄 데이터 없음")
            else:
                print("  ❌ servers 테이블이 존재하지 않습니다!")
        except Exception as e:
            print(f"  ❌ servers 테이블 조회 실패: {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")

if __name__ == "__main__":
    check_database() 