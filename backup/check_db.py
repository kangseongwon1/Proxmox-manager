import sqlite3

def check_database():
    try:
        conn = sqlite3.connect('proxmox.db')
        cursor = conn.cursor()
        
        # 테이블 목록 조회
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("Tables:", tables)
        
        # 각 테이블의 구조 확인
        for table in tables:
            table_name = table[0]
            print(f"\n=== Table: {table_name} ===")
            
            # 테이블 스키마 조회
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print("Columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
            
            # 데이터 조회
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
            rows = cursor.fetchall()
            print(f"Data (first 5 rows): {rows}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_database() 