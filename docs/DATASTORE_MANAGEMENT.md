# Datastore 관리 시스템

## 개요

Proxmox Manager의 Datastore 관리 시스템은 Proxmox 스토리지를 자동으로 감지하고, DB에 캐싱하여 빠른 접근을 제공합니다. 기본 HDD/SSD datastore 설정을 DB에서 관리하여 유연성을 제공합니다.

## 주요 기능

- **자동 감지**: Proxmox에서 datastore 목록을 자동으로 가져와서 DB에 저장
- **DB 캐싱**: 매번 Proxmox API 호출 없이 DB에서 빠르게 조회
- **기본 설정 관리**: DB에서 기본 HDD/SSD datastore 설정 관리
- **Fallback 지원**: DB 조회 실패 시 `.env` 파일에서 fallback
- **새로고침**: Proxmox에서 최신 정보를 가져와서 DB 업데이트

## 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │    │   Flask API     │    │   Proxmox API   │
│                 │    │                 │    │                 │
│ - 스토리지 선택  │◄──►│ - /api/datastores│◄──►│ - /storage      │
│ - 기본 설정 변경 │    │ - DB 캐싱      │    │ - datastore 정보│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   SQLite DB     │
                       │                 │
                       │ - datastores    │
                       │ - 기본 설정     │
                       └─────────────────┘
```

## 데이터베이스 모델

### Datastore 테이블

```sql
CREATE TABLE datastores (
    id VARCHAR(100) PRIMARY KEY,           -- datastore ID
    name VARCHAR(100) NOT NULL,           -- datastore 이름
    type VARCHAR(50) NOT NULL,            -- 타입 (lvm, dir, nfs 등)
    size BIGINT DEFAULT 0,                -- 총 크기 (bytes)
    used BIGINT DEFAULT 0,                -- 사용된 크기 (bytes)
    available BIGINT DEFAULT 0,           -- 사용 가능한 크기 (bytes)
    content TEXT,                         -- 지원하는 콘텐츠 타입
    enabled BOOLEAN DEFAULT TRUE,         -- 활성화 상태
    is_default_hdd BOOLEAN DEFAULT FALSE, -- 기본 HDD datastore 여부
    is_default_ssd BOOLEAN DEFAULT FALSE, -- 기본 SSD datastore 여부
    is_system_default BOOLEAN DEFAULT FALSE, -- 시스템 기본 datastore 여부
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## API 엔드포인트

### 1. Datastore 목록 조회

```http
GET /api/datastores
```

**응답:**
```json
{
  "success": true,
  "datastores": [
    {
      "id": "local-lvm",
      "name": "local-lvm",
      "type": "lvm",
      "size": 1073741824000,
      "used": 536870912000,
      "available": 536870912000,
      "is_default_hdd": true,
      "is_default_ssd": false
    }
  ],
  "default_hdd": "local-lvm",
  "default_ssd": "local"
}
```

### 2. Datastore 새로고침

```http
POST /api/datastores/refresh
```

**기능:**
- 기존 datastore 정보 삭제
- Proxmox에서 최신 정보 가져오기
- DB에 새로 저장

**응답:**
```json
{
  "success": true,
  "message": "3개 datastore 정보를 새로고침했습니다.",
  "count": 3
}
```

### 3. 기본 Datastore 설정 변경

```http
POST /api/datastores/default
Content-Type: application/json

{
  "hdd_datastore_id": "HDD-Storage",
  "ssd_datastore_id": "local"
}
```

**응답:**
```json
{
  "success": true,
  "message": "기본 datastore 설정이 변경되었습니다.",
  "hdd_datastore": "HDD-Storage",
  "ssd_datastore": "local"
}
```

## 동작 방식

### 1. 초기 설정

1. **첫 번째 API 호출**: DB에 datastore 정보가 없음
2. **Proxmox API 호출**: `/storage` 엔드포인트에서 datastore 목록 가져오기
3. **환경변수 읽기**: `.env` 파일에서 `PROXMOX_HDD_DATASTORE`, `PROXMOX_SSD_DATASTORE` 설정
4. **DB 저장**: Proxmox datastore 정보를 DB에 저장
5. **응답**: DB에서 가져온 정보를 포맷팅하여 반환

### 2. 이후 호출

1. **DB 조회**: `Datastore.query.filter_by(enabled=True).all()`
2. **기본 설정 조회**: DB에서 `is_default_hdd=True`, `is_default_ssd=True`인 datastore 조회
3. **응답**: DB에서 가져온 정보를 포맷팅하여 반환

### 3. Fallback 메커니즘

DB 조회 실패 시:
1. **환경변수 읽기**: `.env` 파일에서 기본 설정 가져오기
2. **기본값 사용**: `local-lvm` (HDD), `local` (SSD)

## 환경변수 설정

### .env 파일

```bash
# Datastore 설정 (초기 기본값, 이후 DB에서 관리)
PROXMOX_HDD_DATASTORE=local-lvm
PROXMOX_SSD_DATASTORE=local
```

### env_template 업데이트

```bash
# Datastore 설정 (초기 기본값, 이후 DB에서 관리)
PROXMOX_HDD_DATASTORE=local-lvm
PROXMOX_SSD_DATASTORE=local
```

## 설치 스크립트 통합

### install_complete_system.sh

```bash
# 데이터베이스 초기화 (필요한 경우)
echo "🗄️ 데이터베이스 초기화 확인 중..."
if [ ! -f "instance/proxmox_manager.db" ]; then
    echo "📝 데이터베이스 초기화 중..."
    ./venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from app import create_app, db
from app.models.datastore import Datastore
app = create_app()
with app.app_context():
    db.create_all()
    print('✅ 데이터베이스 초기화 완료')
    print('✅ Datastore 모델 포함됨')
" 2>/dev/null || echo "⚠️ 데이터베이스 초기화 실패 (서비스 시작 시 자동 생성됨)"
else
    echo "✅ 데이터베이스 파일이 이미 존재합니다"
    echo "🔄 기존 DB에 새로운 테이블 추가 확인 중..."
    ./venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from app import create_app, db
from app.models.datastore import Datastore
app = create_app()
with app.app_context():
    try:
        db.create_all()
        print('✅ 기존 DB에 새로운 테이블 추가 완료')
    except Exception as e:
        print(f'⚠️ DB 업데이트 중 오류: {e}')
" 2>/dev/null || echo "⚠️ DB 업데이트 실패 (서비스 시작 시 자동 처리됨)"
fi
```

## 성능 최적화

### 1. DB 캐싱
- **첫 번째 호출**: Proxmox API 호출 (느림)
- **두 번째 호출부터**: DB 조회 (빠름)

### 2. 새로고침 전략
- **자동 새로고침**: 필요시에만 `/api/datastores/refresh` 호출
- **수동 새로고침**: 관리자가 직접 새로고침

### 3. Fallback 지원
- **DB 실패 시**: `.env` 파일에서 기본값 사용
- **네트워크 실패 시**: 기존 DB 데이터 사용

## 트러블슈팅

### 1. Datastore 목록이 비어있음

**원인**: Proxmox API 연결 실패
**해결**: 
1. Proxmox 연결 확인
2. `/api/datastores/refresh` 호출

### 2. 기본 설정이 적용되지 않음

**원인**: DB에 기본 설정이 없음
**해결**:
1. `/api/datastores/default` API로 설정 변경
2. 또는 `.env` 파일에서 기본값 설정

### 3. 성능 문제

**원인**: 매번 Proxmox API 호출
**해결**: DB 캐싱 시스템 사용

## 향후 개선 계획

1. **관리자 UI**: 웹 인터페이스에서 기본 설정 변경
2. **자동 새로고침**: 주기적으로 Proxmox에서 최신 정보 가져오기
3. **모니터링**: Datastore 사용량 모니터링
4. **알림**: Datastore 용량 부족 시 알림
