#!/usr/bin/env python3
"""
Flask 앱의 데이터베이스 설정 확인
"""

import os
import sys
try:
    from config.config import Config
except ImportError:
    # 대안 방법으로 config 로드
    import importlib.util
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.py')
    spec = importlib.util.spec_from_file_location("config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    Config = config_module.Config, DevelopmentConfig

def check_flask_config():
    """Flask 설정 확인"""
    print("🔍 Flask 설정 확인")
    
    # 기본 설정
    config = Config()
    print(f"📋 기본 SQLALCHEMY_DATABASE_URI: {config.SQLALCHEMY_DATABASE_URI}")
    
    # 개발 설정
    dev_config = DevelopmentConfig()
    print(f"📋 개발 SQLALCHEMY_DATABASE_URI: {dev_config.SQLALCHEMY_DATABASE_URI}")
    
    # 환경 변수 확인
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        print(f"📋 환경 변수 DATABASE_URL: {database_url}")
    else:
        print("📋 환경 변수 DATABASE_URL: 설정되지 않음")
    
    # 실제 파일 경로 계산
    basedir = os.path.abspath(os.path.dirname(__file__))
    default_db_path = os.path.join(basedir, "instance", "proxmox_manager.db")
    print(f"📋 기본 데이터베이스 파일 경로: {default_db_path}")
    print(f"📁 파일 존재: {os.path.exists(default_db_path)}")
    
    if os.path.exists(default_db_path):
        print(f"📊 파일 크기: {os.path.getsize(default_db_path)} bytes")

def check_database_class():
    """Database 클래스 확인"""
    print("\n🔍 Database 클래스 확인")
    
    try:
        from database import Database
        db = Database()
        print(f"📋 Database 클래스 db_path: {db.db_path}")
        print(f"📁 파일 존재: {os.path.exists(db.db_path)}")
        
        if os.path.exists(db.db_path):
            print(f"📊 파일 크기: {os.path.getsize(db.db_path)} bytes")
            
            # 테이블 확인
            import sqlite3
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"📋 테이블 목록: {[table[0] for table in tables]}")
            conn.close()
            
    except Exception as e:
        print(f"❌ Database 클래스 확인 실패: {e}")

if __name__ == "__main__":
    check_flask_config()
    check_database_class() 