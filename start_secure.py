#!/usr/bin/env python3
"""
보안 강화된 Proxmox Manager 시작 스크립트
"""

import os
import sys
import subprocess
from pathlib import Path

def check_environment():
    """환경 변수 및 보안 설정 검증"""
    print("🔒 보안 검증을 시작합니다...")
    
    # .env 파일 존재 확인
    if not Path('.env').exists():
        print("❌ .env 파일이 없습니다!")
        print("📝 다음 명령어로 .env 파일을 생성하세요:")
        print("   cp env_template.txt .env")
        print("   nano .env  # 실제 값으로 변경")
        return False
    
    # 필수 환경 변수 확인
    required_vars = [
        'SECRET_KEY', 'PROXMOX_ENDPOINT', 'PROXMOX_USERNAME', 
        'PROXMOX_PASSWORD', 'PROXMOX_NODE', 'PROXMOX_DATASTORE'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ 필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
        print("📝 .env 파일을 확인하고 모든 필수 변수를 설정하세요.")
        return False
    
    # SECRET_KEY 강도 확인
    secret_key = os.environ.get('SECRET_KEY', '')
    if len(secret_key) < 32:
        print("⚠️  SECRET_KEY가 너무 짧습니다. 최소 32자 이상으로 설정하세요.")
        return False
    
    if secret_key == 'your-super-secret-key-change-this':
        print("❌ SECRET_KEY가 기본값입니다. 반드시 변경하세요!")
        return False
    
    print("✅ 환경 변수 검증 완료")
    return True

def check_file_permissions():
    """파일 권한 검증"""
    print("🔐 파일 권한을 검증합니다...")
    
    sensitive_files = ['.env', 'config/config.py']
    for file_path in sensitive_files:
        if Path(file_path).exists():
            stat = Path(file_path).stat()
            # 소유자만 읽기/쓰기 가능한지 확인
            if stat.st_mode & 0o777 != 0o600:
                print(f"⚠️  {file_path}의 권한이 너무 개방적입니다.")
                print(f"   현재: {oct(stat.st_mode & 0o777)}")
                print(f"   권장: 0o600 (소유자만 읽기/쓰기)")
                print(f"   수정: chmod 600 {file_path}")
    
    print("✅ 파일 권한 검증 완료")
    return True

def check_ssl_certificate():
    """SSL 인증서 확인"""
    print("🔒 SSL 인증서를 확인합니다...")
    
    # HTTPS 사용 여부 확인
    if os.environ.get('FLASK_ENV') == 'production':
        if not os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true':
            print("⚠️  운영 환경에서 SESSION_COOKIE_SECURE가 False로 설정되어 있습니다.")
            print("   HTTPS를 사용하는 경우 True로 설정하세요.")
    
    print("✅ SSL 설정 확인 완료")
    return True

def main():
    """메인 함수"""
    print("🚀 Proxmox Manager 보안 시작 스크립트")
    print("=" * 50)
    
    # 환경 변수 로드
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("❌ python-dotenv가 설치되지 않았습니다.")
        print("   pip install python-dotenv")
        sys.exit(1)
    
    # 보안 검증
    if not check_environment():
        sys.exit(1)
    
    if not check_file_permissions():
        print("⚠️  파일 권한 문제가 있습니다. 수정 후 다시 시도하세요.")
    
    if not check_ssl_certificate():
        print("⚠️  SSL 설정 문제가 있습니다.")
    
    print("=" * 50)
    print("✅ 모든 보안 검증을 통과했습니다!")
    print("🚀 애플리케이션을 시작합니다...")
    
    # Flask 애플리케이션 시작
    try:
        from app import app
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=os.environ.get('DEBUG', 'False').lower() == 'true'
        )
    except Exception as e:
        print(f"❌ 애플리케이션 시작 실패: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 