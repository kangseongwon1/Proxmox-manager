import sqlite3
import json

def check_db_structure():
    """DB 구조 확인"""
    conn = sqlite3.connect('instance/proxmox_manager.db')
    cursor = conn.cursor()
    
    # 테이블 목록 조회
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("📋 데이터베이스 테이블 목록:")
    print("=" * 50)
    for table in tables:
        table_name = table[0]
        print(f"\n🔍 테이블: {table_name}")
        
        # 테이블 스키마 조회
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        print("  컬럼:")
        for col in columns:
            col_id, col_name, col_type, not_null, default_val, pk = col
            print(f"    - {col_name} ({col_type})")
        
        # 데이터 개수 조회
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  레코드 수: {count}")
        
        # 샘플 데이터 조회 (최대 3개)
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_data = cursor.fetchall()
            print("  샘플 데이터:")
            for i, row in enumerate(sample_data, 1):
                print(f"    {i}. {row}")
    
    conn.close()

if __name__ == "__main__":
    check_db_structure() 