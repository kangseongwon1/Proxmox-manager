# Celery & Redis 아키텍처 가이드

## 📋 개요

Terraform Proxmox Manager는 Celery와 Redis를 사용하여 비동기 작업 처리와 실시간 알림 시스템을 구현합니다.

## 🏗️ 아키텍처 구성

### 핵심 컴포넌트
- **Flask 앱**: 웹 인터페이스 및 API 제공
- **Redis**: Celery 브로커, 캐싱, 세션 저장
- **Celery 워커**: 비동기 작업 처리
- **PostgreSQL**: 메인 데이터베이스
- **SSE**: 실시간 알림 시스템

## 🔄 작업 처리 흐름

### 1. 서버 생성 작업
```
1. 사용자 요청 → Flask API
2. Celery 태스크 큐에 작업 추가
3. Redis를 통해 Celery 워커에 전달
4. Celery 워커가 Terraform 실행
5. DB에 결과 저장
6. SSE로 실시간 알림 전송
7. UI 즉시 업데이트
```

### 2. 실시간 알림 시스템
```
1. Celery 워커 작업 완료
2. DB에 Notification 레코드 생성
3. SSE 스트림이 새 알림 감지
4. 웹 브라우저에 실시간 전송
5. UI 자동 업데이트 (새로고침 불필요)
```

## 🐳 Docker 구성

### docker-compose.yml
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: proxmox-redis
    ports:
      - "6379:6379"
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile.celery
    container_name: proxmox-celery-worker
    volumes:
      - ../:/app
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2

  celery-flower:
    image: mher/flower:latest
    container_name: proxmox-celery-flower
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    container_name: proxmox-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=proxmox_manager
      - POSTGRES_USER=proxmox
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U proxmox"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  redis_data:
  postgres_data:
```

## 🔧 Celery 설정

### app/celery_app.py
```python
from celery import Celery
from app import create_app

def make_celery(app=None):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

flask_app = create_app()
celery_app = make_celery(flask_app)
```

### 환경 변수 설정
```bash
# .env 파일
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
CELERY_BROKER_URL=redis://:your_redis_password@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:your_redis_password@localhost:6379/0

# PostgreSQL 설정
POSTGRES_PASSWORD=your_postgres_password
DATABASE_URL=postgresql://proxmox:your_postgres_password@localhost:5432/proxmox_manager
```

## 📊 모니터링 및 관리

### 1. Celery Flower
- **URL**: http://localhost:5555
- **기능**: 
  - 워커 상태 모니터링
  - 태스크 실행 현황
  - 실패한 태스크 확인
  - 워커 성능 통계

### 2. Redis 모니터링
```bash
# Redis CLI 접속
docker exec -it proxmox-redis redis-cli -a your_password

# 큐 상태 확인
LLEN celery

# 모든 키 확인
KEYS *

# Celery 관련 키만 확인
KEYS celery*
```

### 3. PostgreSQL 모니터링
```bash
# PostgreSQL 접속
docker exec -it proxmox-postgres psql -U proxmox -d proxmox_manager

# 테이블 확인
\dt

# 알림 테이블 확인
SELECT * FROM notifications ORDER BY created_at DESC LIMIT 10;
```

## 🚀 배포 및 실행

### 1. 전체 시스템 시작
```bash
# 1. Redis & Celery 시작
cd redis
docker-compose up -d

# 2. Flask 앱 시작
python run.py

# 3. 모니터링 스택 시작 (선택사항)
cd monitoring
docker-compose up -d
```

### 2. 서비스 확인
```bash
# Redis 상태 확인
docker exec proxmox-redis redis-cli -a your_password ping

# Celery 워커 상태 확인
docker logs proxmox-celery-worker

# PostgreSQL 상태 확인
docker exec proxmox-postgres pg_isready -U proxmox
```

## 🔧 개발 및 디버깅

### 1. Celery 워커 로그 확인
```bash
# 실시간 로그 확인
docker logs -f proxmox-celery-worker

# 특정 태스크 로그 확인
docker logs proxmox-celery-worker | grep "서버 생성"
```

### 2. Redis 디버깅
```bash
# Redis CLI 접속
docker exec -it proxmox-redis redis-cli -a your_password

# 큐 길이 확인
LLEN celery

# 특정 큐 내용 확인
LRANGE celery 0 -1

# 모든 키 확인
KEYS *
```

### 3. 태스크 상태 확인
```python
# Python에서 태스크 상태 확인
from app.celery_app import celery_app

# 태스크 ID로 상태 확인
result = celery_app.AsyncResult('task-id')
print(result.state)  # PENDING, SUCCESS, FAILURE
print(result.result)  # 결과 데이터
```

## 🛠️ 문제 해결

### 1. Celery 워커가 작업을 처리하지 않는 경우
```bash
# 워커 재시작
docker-compose restart celery-worker

# 워커 로그 확인
docker logs proxmox-celery-worker

# Redis 연결 확인
docker exec proxmox-redis redis-cli -a your_password ping
```

### 2. 태스크가 PENDING 상태에서 멈춘 경우
```bash
# Redis 큐 확인
docker exec -it proxmox-redis redis-cli -a your_password
LLEN celery

# 큐 초기화 (주의: 모든 대기 중인 작업이 삭제됨)
FLUSHDB
```

### 3. SSE 알림이 오지 않는 경우
```bash
# PostgreSQL 연결 확인
docker exec proxmox-postgres pg_isready -U proxmox

# 알림 테이블 확인
docker exec -it proxmox-postgres psql -U proxmox -d proxmox_manager
SELECT * FROM notifications ORDER BY created_at DESC LIMIT 5;
```

## 📈 성능 최적화

### 1. Celery 워커 설정
```python
# app/celery_app.py
celery_app.conf.update(
    worker_concurrency=2,  # CPU 코어 수에 맞게 조정
    worker_prefetch_multiplier=1,  # 메모리 사용량 최적화
    task_acks_late=True,  # 작업 완료 후 ACK
    worker_disable_rate_limits=True,  # 속도 제한 비활성화
)
```

### 2. Redis 최적화
```bash
# Redis 설정 확인
docker exec proxmox-redis redis-cli -a your_password CONFIG GET "*"

# 메모리 사용량 확인
docker exec proxmox-redis redis-cli -a your_password INFO memory
```

### 3. PostgreSQL 최적화
```sql
-- 인덱스 확인
SELECT schemaname, tablename, indexname, indexdef 
FROM pg_indexes 
WHERE schemaname = 'public';

-- 테이블 크기 확인
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public';
```

## 🔄 마이그레이션 가이드

### SQLite에서 PostgreSQL로 마이그레이션
```bash
# 1. 데이터 백업
python scripts/migrate_sqlite_to_postgres.py

# 2. PostgreSQL 컨테이너 시작
docker-compose up -d postgres

# 3. 데이터 복원
python scripts/restore_postgres_data.py
```

## 📝 개발 가이드

### 새로운 비동기 작업 추가
```python
# app/tasks/new_task.py
from app.celery_app import celery_app

@celery_app.task(bind=True)
def new_async_task(self, param1, param2):
    """새로운 비동기 작업"""
    try:
        # 작업 로직
        result = do_something(param1, param2)
        
        # DB 업데이트
        # ...
        
        # 알림 생성
        notification = Notification(
            type='new_task',
            title='새 작업 완료',
            message=f'작업이 완료되었습니다.',
            severity='success'
        )
        db.session.add(notification)
        db.session.commit()
        
        return {'success': True, 'result': result}
    except Exception as e:
        logger.error(f"작업 실패: {e}")
        raise
```

### API 엔드포인트 추가
```python
# app/routes/new_async.py
@bp.route('/api/new_task/async', methods=['POST'])
@login_required
def new_task_async():
    """새로운 비동기 작업 API"""
    try:
        data = request.get_json()
        
        # Celery 태스크 실행
        task = new_async_task.delay(
            param1=data['param1'],
            param2=data['param2']
        )
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': '작업이 시작되었습니다.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

**최종 업데이트**: 2025-10-16  
**버전**: 2.0.0  
**주요 변경사항**: Celery/Redis 도입, PostgreSQL 마이그레이션, SSE 실시간 알림 시스템
