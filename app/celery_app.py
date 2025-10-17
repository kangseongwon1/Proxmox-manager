from celery import Celery
import os
from app import create_app  # 앱 팩토리 불러오기

# .env 파일 로드
try:
    from dotenv import load_dotenv
    load_dotenv('.env')
    print("✅ .env 파일 로드 완료")
except ImportError:
    print("⚠️ python-dotenv가 설치되지 않았습니다. 환경 변수를 수동으로 설정하세요.")
except Exception as e:
    print(f"⚠️ .env 파일 로드 실패: {e}")

def create_celery_app():
    flask_app = create_app()  # Flask 앱 생성

    # Redis 브로커 설정 (비밀번호 지원)
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = os.getenv('REDIS_PORT', 6379)
    redis_db = os.getenv('REDIS_DB', 0)
    redis_password = os.getenv('REDIS_PASSWORD')

    if redis_password:
        broker_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        broker_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

    # 백엔드 URL 설정 (환경 변수 우선)
    backend_url = os.getenv('CELERY_RESULT_BACKEND', broker_url)
    
    celery = Celery(
        'proxmox_manager',
        broker=broker_url,
        backend=backend_url,  # 환경 변수 또는 브로커 URL 사용
        include=['app.tasks.server_tasks', 'app.tasks.role_tasks', 'app.tasks.backup_tasks']
    )

    # 간단하고 안전한 Celery 설정 (예외 직렬화 문제 방지)
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Seoul',
        enable_utc=True,
        task_time_limit=1800,
        task_soft_time_limit=1500,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_disable_rate_limits=True,
        result_expires=3600,
        # 결과 저장 단순화 (예외 직렬화 문제 방지)
        task_ignore_result=False,
        task_store_eager_result=False,
        task_always_eager=False,
        # Redis 연결 설정
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=10,
        # 태스크 추적 활성화
        task_track_started=True,
        task_send_sent_event=True,
        # 예외 직렬화 문제 방지를 위한 설정
        task_store_errors_even_if_ignored=False,
        task_ignore_result_on_task_failure=False
    )

    # Flask 컨텍스트 자동 주입
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery_app = create_celery_app()