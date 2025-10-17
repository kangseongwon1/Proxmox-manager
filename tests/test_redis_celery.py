#!/usr/bin/env python3
"""
Redis & Celery 테스트 스크립트
"""
import os
import sys
import time
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_redis_connection():
    """Redis 연결 테스트"""
    print("🔍 Redis 연결 테스트 시작...")
    
    try:
        from app.utils.redis_utils import redis_utils
        
        if redis_utils.is_available():
            print("✅ Redis 연결 성공!")
            
            # 캐시 테스트
            test_data = {"message": "Hello Redis!", "timestamp": time.time()}
            cache_key = "test:connection"
            
            # 캐시 저장
            if redis_utils.set_cache(cache_key, test_data, expire=60):
                print("✅ Redis 캐시 저장 성공!")
                
                # 캐시 조회
                cached_data = redis_utils.get_cache(cache_key)
                if cached_data:
                    print(f"✅ Redis 캐시 조회 성공: {cached_data}")
                else:
                    print("❌ Redis 캐시 조회 실패")
            else:
                print("❌ Redis 캐시 저장 실패")
                
        else:
            print("❌ Redis 연결 실패 - Redis가 실행되지 않았거나 설정이 잘못되었습니다.")
            print("💡 Redis를 시작하려면: redis-server")
            return False
            
    except Exception as e:
        print(f"❌ Redis 테스트 실패: {e}")
        return False
    
    return True

def test_celery_connection():
    """Celery 연결 테스트"""
    print("\n🔍 Celery 연결 테스트 시작...")
    
    try:
        from app.celery_app import celery_app
        
        # Celery 상태 확인
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            print("✅ Celery Worker 연결 성공!")
            print(f"📊 활성 Worker 수: {len(stats)}")
            
            # 간단한 작업 테스트
            from app.tasks.server_tasks import create_server_async
            
            test_config = {
                'name': 'test-server',
                'cpu': 2,
                'memory': 4,
                'disk': 20,
                'os_type': 'ubuntu'
            }
            
            print("🚀 테스트 작업 실행 중...")
            result = create_server_async.delay(test_config)
            print(f"✅ 작업 ID: {result.id}")
            
            # 작업 상태 확인
            for i in range(5):
                status = result.status
                print(f"📊 작업 상태: {status}")
                if status in ['SUCCESS', 'FAILURE']:
                    break
                time.sleep(1)
            
            return True
        else:
            print("❌ Celery Worker가 실행되지 않았습니다.")
            print("💡 Celery Worker를 시작하려면: celery -A app.celery_app worker --loglevel=info")
            return False
            
    except Exception as e:
        print(f"❌ Celery 테스트 실패: {e}")
        return False

def test_cache_performance():
    """캐시 성능 테스트"""
    print("\n🔍 캐시 성능 테스트 시작...")
    
    try:
        from app.utils.redis_utils import redis_utils
        
        if not redis_utils.is_available():
            print("❌ Redis가 사용 불가능합니다.")
            return False
        
        # 대용량 데이터 캐시 테스트
        large_data = {
            "servers": {f"server-{i}": {
                "name": f"server-{i}",
                "cpu": 2,
                "memory": 4,
                "status": "running"
            } for i in range(100)},
            "stats": {
                "total_servers": 100,
                "running_servers": 100,
                "cpu_usage": 45.5
            }
        }
        
        cache_key = "test:performance"
        
        # 캐시 저장 시간 측정
        start_time = time.time()
        redis_utils.set_cache(cache_key, large_data, expire=300)
        save_time = time.time() - start_time
        
        # 캐시 조회 시간 측정
        start_time = time.time()
        cached_data = redis_utils.get_cache(cache_key)
        load_time = time.time() - start_time
        
        print(f"✅ 캐시 저장 시간: {save_time:.4f}초")
        print(f"✅ 캐시 조회 시간: {load_time:.4f}초")
        print(f"✅ 데이터 크기: {len(json.dumps(large_data))} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ 캐시 성능 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 Redis & Celery 통합 테스트 시작")
    print("=" * 50)
    
    # Redis 테스트
    redis_success = test_redis_connection()
    
    # Celery 테스트
    celery_success = test_celery_connection()
    
    # 캐시 성능 테스트
    if redis_success:
        cache_success = test_cache_performance()
    else:
        cache_success = False
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약:")
    print(f"Redis 연결: {'✅ 성공' if redis_success else '❌ 실패'}")
    print(f"Celery 연결: {'✅ 성공' if celery_success else '❌ 실패'}")
    print(f"캐시 성능: {'✅ 성공' if cache_success else '❌ 실패'}")
    
    if redis_success and celery_success:
        print("\n🎉 모든 테스트 통과! Redis & Celery 통합이 성공적으로 완료되었습니다.")
    else:
        print("\n⚠️ 일부 테스트 실패. 설정을 확인해주세요.")
        
        if not redis_success:
            print("💡 Redis 시작 방법: redis-server")
        if not celery_success:
            print("💡 Celery Worker 시작 방법: celery -A app.celery_app worker --loglevel=info")

if __name__ == "__main__":
    main()
