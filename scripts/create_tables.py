import sqlite3

def create_tables():
    """instance/proxmox_manager.db에 필요한 테이블들을 생성합니다."""
    try:
        # instance 디렉토리가 없으면 생성
        import os
        instance_dir = 'instance'
        if not os.path.exists(instance_dir):
            os.makedirs(instance_dir)
            print(f"📁 {instance_dir} 디렉토리 생성됨")
        
        db_path = os.path.join(instance_dir, 'proxmox_manager.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 사용자 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                email TEXT,
                role TEXT DEFAULT 'developer',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 알림 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                severity TEXT DEFAULT 'info',
                user_id TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 서버 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                vmid INTEGER,
                status TEXT,
                ip_address TEXT,
                role TEXT,
                firewall_group TEXT,
                os_type TEXT,
                cpu INTEGER,
                memory INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 프로젝트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("✅ 테이블 생성 완료!")
        
        # 생성된 테이블 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📋 생성된 테이블: {[table[0] for table in tables]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")

if __name__ == "__main__":
    create_tables() 