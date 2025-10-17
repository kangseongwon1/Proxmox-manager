import json
import redis
from app.config.redis_config import RedisConfig

class RedisUtils:
    """Redis 유틸리티 클래스"""
    
    def __init__(self):
        self.client = RedisConfig.get_redis_client()
        self.enabled = RedisConfig.REDIS_ENABLED
    
    def is_available(self):
        """Redis 사용 가능 여부 확인"""
        return self.enabled and self.client is not None
    
    def set_cache(self, key, value, expire=300):
        """캐시 설정"""
        if not self.is_available():
            return False
            
        try:
            if isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            self.client.setex(key, expire, value)
            return True
        except Exception as e:
            print(f"⚠️ Redis 캐시 설정 실패: {e}")
            return False
    
    def get_cache(self, key):
        """캐시 조회"""
        if not self.is_available():
            return None
            
        try:
            value = self.client.get(key)
            if value:
                # JSON 파싱 시도
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except Exception as e:
            print(f"⚠️ Redis 캐시 조회 실패: {e}")
            return None
    
    def delete_cache(self, key):
        """캐시 삭제"""
        if not self.is_available():
            return False
            
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"⚠️ Redis 캐시 삭제 실패: {e}")
            return False
    
    def clear_all_cache(self):
        """모든 캐시 삭제"""
        if not self.is_available():
            return False
            
        try:
            self.client.flushdb()
            return True
        except Exception as e:
            print(f"⚠️ Redis 전체 캐시 삭제 실패: {e}")
            return False

# 전역 인스턴스
redis_utils = RedisUtils()