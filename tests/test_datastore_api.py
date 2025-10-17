#!/usr/bin/env python3
"""
Datastore API 테스트 스크립트
"""
import requests
import json

def test_datastore_api():
    """Datastore API 테스트"""
    base_url = "http://localhost:5000"
    
    print("🔍 Datastore API 테스트 시작...")
    
    try:
        # 1. 로그인
        print("\n1. 로그인 테스트...")
        login_data = {
            'username': 'admin',
            'password': 'admin123'
        }
        
        session = requests.Session()
        login_response = session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
        
        print(f"📊 로그인 응답 상태: {login_response.status_code}")
        print(f"📊 로그인 응답 헤더: {dict(login_response.headers)}")
        
        if login_response.status_code in [200, 302]:
            print("✅ 로그인 성공")
        else:
            print(f"❌ 로그인 실패: {login_response.status_code}")
            print(f"📊 로그인 응답 내용: {login_response.text[:500]}")
            return False
        
        # 2. Datastore API 테스트
        print("\n2. Datastore API 테스트...")
        datastore_response = session.get(f"{base_url}/api/datastores")
        
        print(f"📊 응답 상태: {datastore_response.status_code}")
        print(f"📊 응답 헤더: {dict(datastore_response.headers)}")
        
        if datastore_response.status_code == 200:
            try:
                data = datastore_response.json()
                print(f"✅ Datastore API 성공")
                print(f"📊 응답 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 데이터 구조 확인
                if 'datastores' in data:
                    print(f"📊 Datastore 개수: {len(data['datastores'])}")
                    for i, ds in enumerate(data['datastores']):
                        print(f"  {i+1}. {ds}")
                else:
                    print("⚠️ 'datastores' 키가 없습니다")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print(f"📊 원본 응답: {datastore_response.text}")
        else:
            print(f"❌ Datastore API 실패: {datastore_response.status_code}")
            print(f"📊 오류 응답: {datastore_response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: Flask 앱이 실행되지 않았습니다")
        return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_datastore_api()
