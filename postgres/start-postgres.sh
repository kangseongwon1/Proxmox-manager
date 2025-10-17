#!/bin/bash
# PostgreSQL 시작 스크립트

echo "🐘 PostgreSQL 시작 중..."

# 환경 변수 설정
export POSTGRES_USER=${POSTGRES_USER:-proxmox}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-proxmox123}
export POSTGRES_DB=${POSTGRES_DB:-proxmox_manager}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}

# PostgreSQL 컨테이너 시작
docker-compose up -d

# 연결 대기
echo "⏳ PostgreSQL 연결 대기 중..."
sleep 10

# 연결 테스트
docker exec proxmox-postgres pg_isready -U $POSTGRES_USER -d $POSTGRES_DB

if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL 시작 완료!"
    echo "📊 연결 정보:"
    echo "  - 호스트: localhost"
    echo "  - 포트: $POSTGRES_PORT"
    echo "  - 데이터베이스: $POSTGRES_DB"
    echo "  - 사용자: $POSTGRES_USER"
    echo "  - URL: postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB"
else
    echo "❌ PostgreSQL 시작 실패"
    exit 1
fi
