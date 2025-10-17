#!/usr/bin/env python3
"""
로그인 테스트 스크립트
"""

import requests
import json

def test_login():
    """로그인 테스트"""
    base_url = "http://localhost:5000"
    
    print("🔐 로그인 테스트 시작")
    
    # 세션 생성
    session = requests.Session()
    
    try:
        # 로그인 시도
        login_data = {
            'username': 'admin',
            'password': 'admin123!'
        }
        
        print(f"📤 로그인 요청: {login_data}")
        
        response = session.post(f"{base_url}/auth/login", data=login_data)
        
        print(f"📥 응답 상태: {response.status_code}")
        print(f"📥 응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ 로그인 성공!")
            
            # 현재 사용자 정보 확인
            user_response = session.get(f"{base_url}/current-user")
            print(f"👤 사용자 정보 응답: {user_response.status_code}")
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                print(f"👤 사용자 정보: {user_data}")
            else:
                print(f"❌ 사용자 정보 조회 실패: {user_response.text}")
                
        else:
            print(f"❌ 로그인 실패: {response.text}")
            
            # HTML 응답인 경우 일부만 출력
            if len(response.text) > 500:
                print(f"📄 응답 내용 (처음 500자): {response.text[:500]}...")
            else:
                print(f"📄 응답 내용: {response.text}")
                
    except Exception as e:
        print(f"❌ 로그인 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_login() 