#!/usr/bin/env python3
"""
PostgreSQL 스키마 초기화 스크립트
기존 SQLite 스키마와 동일한 구조로 PostgreSQL 테이블 생성
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def init_postgres_schema():
    """PostgreSQL 스키마 초기화"""
    
    # 환경 변수에서 데이터베이스 URL 가져오기
    database_url = os.environ.get('DATABASE_URL', 'postgresql://proxmox:proxmox123@localhost:5432/proxmox_manager')
    
    print("🚀 PostgreSQL 스키마 초기화 시작")
    print(f"📊 데이터베이스 URL: {database_url}")
    
    try:
        # PostgreSQL 연결
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("✅ PostgreSQL 연결 성공")
        
        # 기존 테이블 삭제 (재초기화 시)
        print("🗑️ 기존 테이블 정리 중...")
        cursor.execute("DROP TABLE IF EXISTS user_permissions CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS notifications CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS servers CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS projects CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS datastores CASCADE;")
        
        # 시퀀스 삭제
        cursor.execute("DROP SEQUENCE IF EXISTS users_id_seq CASCADE;")
        cursor.execute("DROP SEQUENCE IF EXISTS servers_id_seq CASCADE;")
        cursor.execute("DROP SEQUENCE IF EXISTS projects_id_seq CASCADE;")
        cursor.execute("DROP SEQUENCE IF EXISTS notifications_id_seq CASCADE;")
        cursor.execute("DROP SEQUENCE IF EXISTS user_permissions_id_seq CASCADE;")
        cursor.execute("DROP SEQUENCE IF EXISTS datastores_id_seq CASCADE;")
        
        print("✅ 기존 테이블 정리 완료")
        
        # 1. users 테이블 생성
        print("👤 users 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password_hash VARCHAR(120) NOT NULL,
                name VARCHAR(100),
                email VARCHAR(120),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 2. servers 테이블 생성
        print("🖥️ servers 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE servers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                vmid INTEGER,
                status VARCHAR(20),
                ip_address TEXT,
                role VARCHAR(50),
                firewall_group VARCHAR(100),
                os_type VARCHAR(50),
                cpu INTEGER,
                memory INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 3. projects 테이블 생성
        print("📁 projects 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE projects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 4. notifications 테이블 생성
        print("🔔 notifications 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE notifications (
                id SERIAL PRIMARY KEY,
                type VARCHAR(50),
                title VARCHAR(200),
                message TEXT,
                details TEXT,
                severity VARCHAR(20),
                user_id INTEGER,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        
        # 5. user_permissions 테이블 생성
        print("🔐 user_permissions 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE user_permissions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                permission VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, permission)
            );
        """)
        
        # 6. datastores 테이블 생성
        print("💾 datastores 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE datastores (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                type VARCHAR(50),
                size BIGINT,
                used BIGINT,
                available BIGINT,
                content TEXT,
                enabled BOOLEAN DEFAULT TRUE,
                shared BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 인덱스 생성
        print("📊 인덱스 생성 중...")
        cursor.execute("CREATE INDEX idx_servers_name ON servers(name);")
        cursor.execute("CREATE INDEX idx_servers_vmid ON servers(vmid);")
        cursor.execute("CREATE INDEX idx_servers_status ON servers(status);")
        cursor.execute("CREATE INDEX idx_notifications_user_id ON notifications(user_id);")
        cursor.execute("CREATE INDEX idx_notifications_created_at ON notifications(created_at);")
        cursor.execute("CREATE INDEX idx_user_permissions_user_id ON user_permissions(user_id);")
        cursor.execute("CREATE INDEX idx_datastores_name ON datastores(name);")
        
        print("✅ 인덱스 생성 완료")
        
        # 기본 관리자 사용자 생성
        print("👤 기본 관리자 사용자 생성 중...")
        cursor.execute("""
            INSERT INTO users (username, password_hash, name, email, is_active)
            VALUES ('admin', 'scrypt:32768:8:1$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4QbQjQjQjQ', '시스템 관리자', 'admin@dmcmedia.co.kr', TRUE)
            ON CONFLICT (username) DO NOTHING;
        """)
        
        # 기본 권한 생성
        print("🔐 기본 권한 생성 중...")
        admin_user_id = cursor.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if admin_user_id:
            admin_id = admin_user_id[0]
            permissions = [
                'server_create', 'server_delete', 'server_start', 'server_stop', 'server_reboot',
                'server_configure', 'server_backup', 'server_restore', 'server_monitor',
                'user_manage', 'role_assign', 'firewall_manage', 'datastore_manage',
                'system_admin', 'monitoring_view', 'logs_view'
            ]
            
            for permission in permissions:
                cursor.execute("""
                    INSERT INTO user_permissions (user_id, permission)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, permission) DO NOTHING;
                """, (admin_id, permission))
        
        print("✅ 기본 권한 생성 완료")
        
        # 테이블 생성 확인
        print("🔍 테이블 생성 확인 중...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print("📋 생성된 테이블:")
        for table in tables:
            print(f"  ✅ {table[0]}")
        
        # 테이블별 레코드 수 확인
        print("📊 테이블별 레코드 수:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"  📈 {table_name}: {count}개 레코드")
        
        conn.close()
        print("🎉 PostgreSQL 스키마 초기화 완료!")
        
    except Exception as e:
        print(f"❌ PostgreSQL 스키마 초기화 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_postgres_schema()
