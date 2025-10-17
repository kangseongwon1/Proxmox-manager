import os
import redis
from flask import current_app

class RedisConfig:
    """Redis 설정 클래스"""
    
    # Redis 연결 설정
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    
    # Redis 활성화 여부
    REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'false').lower() == 'true'
    
    @classmethod
    def get_redis_client(cls):
        """Redis 클라이언트 생성"""
        if not cls.REDIS_ENABLED:
            return None
            
        try:
            client = redis.Redis(
                host=cls.REDIS_HOST,
                port=cls.REDIS_PORT,
                db=cls.REDIS_DB,
                password=cls.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # 연결 테스트
            client.ping()
            return client
        except Exception as e:
            print(f"⚠️ Redis 연결 실패: {e}")
            return None