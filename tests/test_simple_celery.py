#!/usr/bin/env python3
"""
간단한 Celery 테스트 스크립트
"""
import requests
import json
import time
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def log(msg):
    print(msg, flush=True)

def test_simple_celery():
    """간단한 Celery 테스트"""
    base_url = "http://localhost:5000"
    
    print("🔍 간단한 Celery 테스트 시작...")
    print("=" * 50)
    
    try:
        # 1. 로그인
        print("\n1. 로그인 테스트...")
        session = requests.Session()
        
        login_data = {
            'username': 'admin',
            'password': 'admin123!'
        }
        
        login_response = session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
        print(f"📊 로그인 응답: {login_response.status_code}")
        
        if login_response.status_code not in [200, 302]:
            print("❌ 로그인 실패")
            return False
        
        print("✅ 로그인 성공")
        
        # 2. 간단한 테스트 태스크
        print("\n2. 간단한 테스트 태스크...")
        test_data = {
            'message': 'Hello Celery Test'
        }
        
        test_response = session.post(f"{base_url}/api/test/simple", json=test_data)
        print(f"📊 테스트 응답: {test_response.status_code}")
        
        if test_response.status_code == 200:
            result = test_response.json()
            print(f"✅ 테스트 태스크 시작: {result}")
            
            if 'task_id' in result:
                task_id = result['task_id']
                print(f"📋 작업 ID: {task_id}")
                
                # 3. 작업 상태 폴링
                print("\n3. 작업 상태 폴링...")
                for i in range(10):  # 최대 10번 폴링 (20초)
                    try:
                        status_response = session.get(f"{base_url}/api/tasks/{task_id}/status")
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            status = status_data.get('status', 'unknown')
                            message = status_data.get('message', '')
                            progress = status_data.get('progress', 0)
                            
                            print(f"📊 상태 {i+1}: {status} ({progress}%) - {message}")
                            
                            if status in ['SUCCESS', 'FAILURE']:
                                print(f"✅ 작업 완료: {status}")
                                if status == 'SUCCESS':
                                    print("🎉 간단한 Celery 테스트 성공!")
                                    return True
                                else:
                                    print(f"❌ 작업 실패: {status_data}")
                                    return False
                                break
                        else:
                            print(f"❌ 상태 조회 실패: {status_response.status_code}")
                            print(f"📊 응답: {status_response.text}")
                            
                    except Exception as e:
                        print(f"❌ 폴링 중 오류: {e}")
                    
                    time.sleep(2)  # 2초 대기
                
                print("⏰ 작업 타임아웃 (20초)")
                return False
            else:
                print("❌ task_id가 없습니다")
                return False
        else:
            print(f"❌ 테스트 태스크 시작 실패: {test_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_celery():
    """오류 테스트 Celery"""
    base_url = "http://localhost:5000"
    
    print("\n4. 오류 테스트 Celery...")
    
    try:
        session = requests.Session()
        
        # 로그인 (간단히)
        login_data = {'username': 'admin', 'password': 'admin123!'}
        session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
        
        # 오류 테스트 태스크
        error_data = {'should_fail': True}
        error_response = session.post(f"{base_url}/api/test/error", json=error_data)
        
        if error_response.status_code == 200:
            result = error_response.json()
            print(f"✅ 오류 테스트 태스크 시작: {result}")
            
            if 'task_id' in result:
                task_id = result['task_id']
                
                # 상태 폴링
                for i in range(5):
                    status_response = session.get(f"{base_url}/api/tasks/{task_id}/status")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get('status', 'unknown')
                        print(f"📊 오류 테스트 상태 {i+1}: {status}")
                        
                        if status in ['SUCCESS', 'FAILURE']:
                            print(f"✅ 오류 테스트 완료: {status}")
                            return True
                    
                    time.sleep(2)
                
                print("⏰ 오류 테스트 타임아웃")
                return False
        else:
            print(f"❌ 오류 테스트 시작 실패: {error_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 오류 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 간단한 Celery 테스트 시작")
    print("=" * 50)
    
    # 간단한 테스트
    simple_ok = test_simple_celery()
    
    # 오류 테스트
    error_ok = test_error_celery()
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과:")
    print(f"  간단한 테스트: {'✅ 성공' if simple_ok else '❌ 실패'}")
    print(f"  오류 테스트: {'✅ 성공' if error_ok else '❌ 실패'}")
    
    if simple_ok and error_ok:
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print("\n❌ 일부 테스트 실패")
        return 1

if __name__ == "__main__":
    exit(main())
