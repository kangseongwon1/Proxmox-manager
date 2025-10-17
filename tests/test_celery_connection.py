#!/usr/bin/env python3
"""
Celery 연결 및 태스크 실행 테스트 스크립트
Flask와 Celery가 같은 브로커를 보고 있는지, 태스크가 정상 실행되는지 확인
"""

import os
import sys
import time
import json
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_celery_connection():
    """Celery 연결 및 태스크 테스트"""
    print("🧪 Celery 연결 테스트 시작")
    print("=" * 50)
    
    try:
        # 1. Flask 앱 생성 및 Celery 앱 가져오기
        print("1️⃣ Flask 앱 생성 중...")
        from app import create_app
        from app.celery_app import celery_app
        
        app = create_app()
        print("✅ Flask 앱 생성 완료")
        
        # 2. 브로커 설정 확인
        print("\n2️⃣ 브로커 설정 확인...")
        broker_url = celery_app.conf.broker_url
        backend_url = celery_app.conf.result_backend
        print(f"📨 브로커 URL: {broker_url}")
        print(f"📨 백엔드 URL: {backend_url}")
        
        # 3. 등록된 태스크 목록 확인
        print("\n3️⃣ 등록된 태스크 목록...")
        registered_tasks = list(celery_app.tasks.keys())
        target_tasks = [
            'app.tasks.server_tasks.start_server_async',
            'app.tasks.server_tasks.stop_server_async', 
            'app.tasks.server_tasks.reboot_server_async'
        ]
        
        for task in target_tasks:
            if task in registered_tasks:
                print(f"✅ {task}")
            else:
                print(f"❌ {task} - 등록되지 않음")
        
        # 4. Redis 연결 테스트
        print("\n4️⃣ Redis 연결 테스트...")
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            active_queues = inspect.active_queues()
            if active_queues:
                print("✅ Redis 연결 성공")
                for worker, queues in active_queues.items():
                    print(f"   워커: {worker}")
                    for queue in queues:
                        print(f"     큐: {queue['name']}")
            else:
                print("⚠️ 활성 워커가 없습니다")
        except Exception as e:
            print(f"❌ Redis 연결 실패: {e}")
        
        # 5. 간단한 태스크 실행 테스트
        print("\n5️⃣ 태스크 실행 테스트...")
        try:
            # 간단한 테스트 태스크 정의
            @celery_app.task
            def test_task(message):
                return f"테스트 완료: {message} at {datetime.now()}"
            
            # 태스크 실행
            print("📤 테스트 태스크 실행 중...")
            result = test_task.delay("Celery 연결 테스트")
            
            # 결과 대기 (최대 10초)
            print("⏳ 결과 대기 중...")
            for i in range(10):
                if result.ready():
                    print(f"✅ 태스크 완료: {result.result}")
                    break
                time.sleep(1)
                print(f"   대기 중... ({i+1}/10)")
            else:
                print("❌ 태스크 타임아웃 (10초)")
                print(f"   태스크 ID: {result.id}")
                print(f"   상태: {result.state}")
        
        except Exception as e:
            print(f"❌ 태스크 실행 실패: {e}")
        
        # 6. 서버 작업 태스크 직접 테스트
        print("\n6️⃣ 서버 작업 태스크 테스트...")
        try:
            from app.tasks.server_tasks import start_server_async, stop_server_async, reboot_server_async
            
            # 태스크 객체 확인
            print(f"📋 start_server_async: {start_server_async}")
            print(f"📋 stop_server_async: {stop_server_async}")
            print(f"📋 reboot_server_async: {reboot_server_async}")
            
            # 태스크 실행 (실제 서버가 없어도 실행 시도)
            print("📤 start_server_async 실행 시도...")
            result = start_server_async.delay("test-server")
            print(f"   태스크 ID: {result.id}")
            
            # 결과 확인
            for i in range(5):
                if result.ready():
                    print(f"✅ 태스크 완료: {result.result}")
                    break
                time.sleep(1)
                print(f"   대기 중... ({i+1}/5)")
            else:
                print("❌ 태스크 타임아웃 (5초)")
                print(f"   상태: {result.state}")
                if hasattr(result, 'traceback'):
                    print(f"   에러: {result.traceback}")
        
        except Exception as e:
            print(f"❌ 서버 작업 태스크 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
        
        # 7. 환경 변수 확인
        print("\n7️⃣ 환경 변수 확인...")
        env_vars = [
            'REDIS_HOST', 'REDIS_PORT', 'REDIS_DB', 'REDIS_PASSWORD',
            'CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND'
        ]
        for var in env_vars:
            value = os.getenv(var, '설정되지 않음')
            print(f"   {var}: {value}")
        
        print("\n" + "=" * 50)
        print("🧪 테스트 완료")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_celery_connection()
