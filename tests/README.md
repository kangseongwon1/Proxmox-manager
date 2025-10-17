# 테스트 스크립트 모음

이 디렉토리는 Proxmox Manager의 다양한 기능을 테스트하는 스크립트들을 포함합니다.

## 📁 테스트 파일 목록

### 🔧 **기본 기능 테스트**
- `test_celery_simple.py` - 간단한 Celery 비동기 작업 테스트
- `test_celery_integration.py` - Celery 통합 테스트 (Redis + Celery + Flask)
- `test_datastore_api.py` - Datastore API 테스트
- `test_redis_celery.py` - Redis 및 Celery 연결 테스트

### 🗄️ **데이터베이스 테스트**
- `check_db_structure.py` - 데이터베이스 구조 확인
- `check_servers_data.py` - 서버 데이터 확인
- `sync_vm_data.py` - VM 데이터 동기화 테스트

### 🔄 **백업 테스트**
- `test_backup_api.py` - 백업 API 테스트
- `test_node_backups.py` - 노드 백업 테스트
- `check_backup_files.py` - 백업 파일 확인

### 🧪 **통합 테스트**
- `integration_test_suite.py` - 전체 시스템 통합 테스트
- `functional_test_suite.py` - 기능별 테스트 스위트
- `run_tests.py` - 모든 테스트 실행

## 🚀 **사용 방법**

### **개별 테스트 실행**
```bash
# Celery 통합 테스트
python tests/test_celery_integration.py

# Datastore API 테스트
python tests/test_datastore_api.py

# Redis 연결 테스트
python tests/test_redis_celery.py
```

### **모든 테스트 실행**
```bash
# 전체 테스트 스위트 실행
python tests/run_tests.py
```

## 📋 **테스트 전 준비사항**

1. **Flask 앱 실행**
   ```bash
   python run.py
   ```

2. **Redis + Celery 실행** (Docker)
   ```bash
   cd redis
   docker-compose up -d
   ```

3. **환경 변수 설정**
   - `.env` 파일에 필요한 설정들이 있는지 확인
   - `REDIS_ENABLED=true` 설정 확인

## 🔍 **테스트 결과 해석**

### ✅ **성공 케이스**
- 모든 API 응답이 200 상태코드
- Celery 작업이 SUCCESS 상태로 완료
- Redis 캐시가 정상 작동

### ❌ **실패 케이스**
- 401/403: 인증/권한 문제
- 500: 서버 내부 오류
- PENDING: Celery 워커가 실행되지 않음
- Redis 연결 실패

## 🛠️ **문제 해결**

### **Celery 작업이 PENDING 상태**
```bash
# Celery 워커 확인
docker ps | grep celery

# Celery 워커 로그 확인
docker logs proxmox-celery-worker
```

### **Redis 연결 실패**
```bash
# Redis 컨테이너 확인
docker ps | grep redis

# Redis 연결 테스트
docker exec proxmox-redis redis-cli ping
```

### **Flask 앱 연결 실패**
```bash
# Flask 앱 실행 확인
ps aux | grep python

# 포트 확인
netstat -tlnp | grep 5000
```

## 📊 **테스트 커버리지**

- ✅ 사용자 인증
- ✅ Datastore API
- ✅ 비동기 서버 생성
- ✅ Celery 작업 상태 폴링
- ✅ Redis 캐시 기능
- ✅ 데이터베이스 연동
- ✅ 백업 기능
- ✅ 모니터링 연동

## 🔄 **지속적 통합**

이 테스트들은 CI/CD 파이프라인에서 자동으로 실행되어 시스템의 안정성을 보장합니다.