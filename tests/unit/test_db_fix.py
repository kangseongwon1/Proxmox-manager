#!/usr/bin/env python3
"""
데이터베이스 수정 확인 테스트
"""

import requests
import json

def test_database_fix():
    """데이터베이스 수정 확인"""
    base_url = "http://localhost:5000"
    
    print("🔍 데이터베이스 수정 확인 테스트")
    
    # 1. 로그인 테스트
    print("\n1️⃣ 로그인 테스트")
    login_data = {
        'username': 'admin',
        'password': 'admin123!'
    }
    
    try:
        response = requests.post(f"{base_url}/auth/login", data=login_data)
        print(f"📡 로그인 응답: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 로그인 성공")
            
            # 세션 쿠키 저장
            cookies = response.cookies
            
            # 2. 서버 목록 조회 테스트
            print("\n2️⃣ 서버 목록 조회 테스트")
            response = requests.get(f"{base_url}/api/servers", cookies=cookies)
            print(f"📡 서버 목록 응답: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ 서버 목록 조회 성공")
                print(f"📋 서버 수: {len(data.get('servers', []))}")
                
                # 3. 대시보드 콘텐츠 테스트
                print("\n3️⃣ 대시보드 콘텐츠 테스트")
                response = requests.get(f"{base_url}/dashboard/content", cookies=cookies)
                print(f"📡 대시보드 응답: {response.status_code}")
                
                if response.status_code == 200:
                    print("✅ 대시보드 조회 성공")
                else:
                    print(f"❌ 대시보드 조회 실패: {response.text}")
            else:
                print(f"❌ 서버 목록 조회 실패: {response.text}")
        else:
            print(f"❌ 로그인 실패: {response.text}")
            
    except Exception as e:
        print(f"💥 테스트 실패: {e}")

if __name__ == "__main__":
    test_database_fix() 