#!/usr/bin/env python3
"""
Celery 통합 테스트 스크립트
Redis + Celery + Flask 앱의 전체적인 동작을 테스트합니다.
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

def test_celery_integration():
    """Celery 통합 테스트"""
    base_url = "http://localhost:5000"
    
    print("🔍 Celery 통합 테스트 시작...")
    print("=" * 50)
    
    try:
        # 1. 로그인 테스트
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
        
        # 2. Datastore API 테스트
        print("\n2. Datastore API 테스트...")
        datastore_response = session.get(f"{base_url}/api/datastores")
        print(f"📊 Datastore 응답: {datastore_response.status_code}")
        
        if datastore_response.status_code == 200:
            datastore_data = datastore_response.json()
            print(f"✅ Datastore API 성공: {len(datastore_data.get('datastores', []))}개 datastore")
        else:
            print(f"❌ Datastore API 실패: {datastore_response.text}")
            return False
        
        # 3. 비동기 서버 생성 테스트
        print("\n3. 비동기 서버 생성 테스트...")
        server_data = {
            'name': 'test-celery-integration',
            'cpu': 2,
            'memory': 4,
            'disk': 20,
            'os_type': 'ubuntu'
        }
        
        async_response = session.post(f"{base_url}/api/servers/async", json=server_data)
        print(f"📊 비동기 응답: {async_response.status_code}")
        
        if async_response.status_code == 200:
            result = async_response.json()
            print(f"✅ 비동기 작업 시작: {result}")
            
            if 'task_id' in result:
                task_id = result['task_id']
                print(f"📋 작업 ID: {task_id}")
                
                # 4. 작업 상태 폴링
                print("\n4. 작업 상태 폴링...")
                for i in range(15):  # 최대 15번 폴링 (30초)
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
                                print("🎉 Celery 통합 테스트 성공!")
                                return True
                            else:
                                print(f"❌ 작업 실패: {status_data}")
                                return False
                            break
                    else:
                        print(f"❌ 상태 조회 실패: {status_response.status_code}")
                        print(f"📊 응답: {status_response.text}")
                    
                    time.sleep(2)  # 2초 대기
                
                print("⏰ 작업 타임아웃 (30초)")
                return False
            else:
                print("❌ task_id가 없습니다")
                return False
        else:
            print(f"❌ 비동기 작업 시작 실패: {async_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_redis_connection():
    """Redis 연결 테스트"""
    print("\n5. Redis 연결 테스트...")
    try:
        from app.utils.redis_utils import redis_utils
        
        if redis_utils.is_available():
            print("✅ Redis 연결 성공")
            
            # 간단한 캐시 테스트
            test_key = "test:celery:integration"
            test_value = {"test": "data", "timestamp": time.time()}
            
            if redis_utils.set_cache(test_key, test_value, expire=60):
                cached_data = redis_utils.get_cache(test_key)
                if cached_data and cached_data.get("test") == "data":
                    print("✅ Redis 캐시 테스트 성공")
                    redis_utils.delete_cache(test_key)
                    return True
                else:
                    print("❌ Redis 캐시 테스트 실패")
                    return False
            else:
                print("❌ Redis 캐시 설정 실패")
                return False
        else:
            print("❌ Redis 연결 실패")
            return False
    except Exception as e:
        print(f"❌ Redis 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 Celery 통합 테스트 시작")
    print("=" * 50)
    
    # Redis 연결 테스트
    redis_ok = test_redis_connection()
    
    # Celery 통합 테스트
    celery_ok = test_celery_integration()
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과:")
    print(f"  Redis 연결: {'✅ 성공' if redis_ok else '❌ 실패'}")
    print(f"  Celery 통합: {'✅ 성공' if celery_ok else '❌ 실패'}")
    
    if redis_ok and celery_ok:
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print("\n❌ 일부 테스트 실패")
        return 1

if __name__ == "__main__":
    exit(main())
