#!/usr/bin/env python3
"""
SQLite에서 PostgreSQL로 데이터 마이그레이션 스크립트
"""
import os
import sys
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime

# 프로젝트 루트 디렉토리 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_sqlite_data():
    """SQLite에서 데이터 추출"""
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'proxmox_manager.db')
    
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite 데이터베이스 파일을 찾을 수 없습니다: {sqlite_path}")
        return None
    
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 테이블 목록 조회
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    data = {}
    for table in tables:
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        data[table] = [dict(row) for row in rows]
        print(f"📊 {table}: {len(rows)}개 레코드")
    
    conn.close()
    return data

def migrate_to_postgres(data):
    """PostgreSQL로 데이터 마이그레이션"""
    # PostgreSQL 연결
    postgres_url = os.environ.get('DATABASE_URL', 'postgresql://proxmox:proxmox123@localhost:5432/proxmox_manager')
    
    print(f"🔗 PostgreSQL 연결: {postgres_url}")
    
    try:
        conn = psycopg2.connect(postgres_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 테이블별 데이터 삽입
        for table_name, records in data.items():
            if not records:
                continue
                
            print(f"🔄 {table_name} 테이블 마이그레이션 중...")
            
            for record in records:
                try:
                    # 컬럼과 값 분리
                    columns = list(record.keys())
                    values = list(record.values())
                    
                    # SQL 생성
                    placeholders = ', '.join(['%s'] * len(values))
                    columns_str = ', '.join(columns)
                    
                    sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                    cursor.execute(sql, values)
                    
                except Exception as e:
                    print(f"⚠️ 레코드 삽입 실패: {e}")
                    continue
            
            conn.commit()
            print(f"✅ {table_name}: {len(records)}개 레코드 마이그레이션 완료")
        
        cursor.close()
        conn.close()
        print("🎉 PostgreSQL 마이그레이션 완료!")
        
    except Exception as e:
        print(f"❌ PostgreSQL 마이그레이션 실패: {e}")
        return False
    
    return True

def main():
    """메인 함수"""
    print("🚀 SQLite → PostgreSQL 마이그레이션 시작")
    
    # 1. SQLite 데이터 추출
    print("📊 SQLite 데이터 추출 중...")
    data = get_sqlite_data()
    if not data:
        return False
    
    # 2. PostgreSQL로 마이그레이션
    print("🔄 PostgreSQL로 마이그레이션 중...")
    success = migrate_to_postgres(data)
    
    if success:
        print("✅ 마이그레이션 완료!")
        print("📝 다음 단계:")
        print("1. .env 파일에 DATABASE_URL 설정")
        print("2. docker-compose.postgres.yml 실행")
        print("3. 애플리케이션 재시작")
    else:
        print("❌ 마이그레이션 실패")
    
    return success

if __name__ == '__main__':
    main()
