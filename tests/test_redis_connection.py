#!/usr/bin/env python3
"""
Redis 연결 테스트 스크립트
Flask와 Celery가 같은 Redis를 보고 있는지 확인
"""

import redis
import os
import sys

def test_redis_connection():
    """Redis 연결 테스트"""
    print("🧪 Redis 연결 테스트 시작")
    print("=" * 50)
    
    # 환경 변수에서 Redis 설정 가져오기
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_db = int(os.getenv('REDIS_DB', 0))
    redis_password = os.getenv('REDIS_PASSWORD')
    
    print(f"📋 Redis 설정:")
    print(f"   호스트: {redis_host}")
    print(f"   포트: {redis_port}")
    print(f"   DB: {redis_db}")
    print(f"   비밀번호: {'설정됨' if redis_password else '없음'}")
    
    # Redis 연결 테스트
    print(f"\n1️⃣ Redis 연결 테스트...")
    try:
        if redis_password:
            r = redis.Redis(host=redis_host, port=redis_port, db=redis_db, password=redis_password)
        else:
            r = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
        
        # 연결 테스트
        r.ping()
        print("✅ Redis 연결 성공")
        
        # Redis 정보 확인
        info = r.info()
        print(f"   Redis 버전: {info.get('redis_version', 'N/A')}")
        print(f"   연결된 클라이언트: {info.get('connected_clients', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Redis 연결 실패: {e}")
        return
    
    # Celery 큐 확인
    print(f"\n2️⃣ Celery 큐 확인...")
    try:
        # Celery 큐 키 패턴 확인
        queue_keys = r.keys('celery*')
        print(f"   Celery 관련 키 개수: {len(queue_keys)}")
        
        if queue_keys:
            print("   발견된 큐 키들:")
            for key in queue_keys[:10]:  # 최대 10개만 표시
                key_type = r.type(key).decode()
                key_ttl = r.ttl(key)
                print(f"     {key.decode()}: {key_type} (TTL: {key_ttl})")
        
        # 특정 큐 내용 확인
        celery_queue = 'celery'
        queue_length = r.llen(celery_queue)
        print(f"   '{celery_queue}' 큐 길이: {queue_length}")
        
        if queue_length > 0:
            print("   큐 내용 (최대 3개):")
            for i in range(min(3, queue_length)):
                item = r.lindex(celery_queue, i)
                if item:
                    try:
                        import json
                        data = json.loads(item)
                        print(f"     {i+1}: {data.get('id', 'N/A')} - {data.get('task', 'N/A')}")
                    except:
                        print(f"     {i+1}: {item[:100]}...")
        
    except Exception as e:
        print(f"❌ Celery 큐 확인 실패: {e}")
    
    # 테스트 메시지 전송
    print(f"\n3️⃣ 테스트 메시지 전송...")
    try:
        test_message = {
            'id': 'test-123',
            'task': 'test_task',
            'args': ['test'],
            'kwargs': {},
            'eta': None,
            'expires': None
        }
        
        import json
        r.lpush('celery', json.dumps(test_message))
        print("✅ 테스트 메시지 전송 완료")
        
        # 큐 길이 재확인
        new_length = r.llen('celery')
        print(f"   큐 길이: {queue_length} → {new_length}")
        
    except Exception as e:
        print(f"❌ 테스트 메시지 전송 실패: {e}")
    
    print("\n" + "=" * 50)
    print("🧪 Redis 테스트 완료")

if __name__ == "__main__":
    test_redis_connection()
