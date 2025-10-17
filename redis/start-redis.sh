#!/bin/bash
# Proxmox Manager Redis + Celery 시작 스크립트
set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info(){ echo -e "${BLUE}[INFO]${NC} $1"; }
log_success(){ echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn(){ echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error(){ echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# .env에서 Redis 설정 로드 (없으면 기본값)
export REDIS_HOST=${REDIS_HOST:-localhost}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_PASSWORD=${REDIS_PASSWORD:-}

if [ -z "$REDIS_PASSWORD" ]; then
  log_warn "REDIS_PASSWORD가 설정되지 않았습니다. 보안을 위해 설정을 권장합니다 (.env)."
fi

log_info "Redis Docker 스택 시작: 포트=${REDIS_PORT}"
docker-compose up -d

log_info "Redis 상태 확인 중..."
ATTEMPTS=20
SLEEP_SECS=2
for i in $(seq 1 $ATTEMPTS); do
  if docker-compose ps | grep -q "proxmox-redis"; then
    if [ -n "$REDIS_PASSWORD" ]; then
      if docker exec proxmox-redis redis-cli -a "$REDIS_PASSWORD" PING 2>/dev/null | grep -q PONG; then
        log_success "Redis 컨테이너 실행 및 응답 확인 (PONG)"
        exit 0
      fi
    else
      if docker exec proxmox-redis redis-cli PING 2>/dev/null | grep -q PONG; then
        log_success "Redis 컨테이너 실행 및 응답 확인 (PONG)"
        exit 0
      fi
    fi
  fi
  sleep $SLEEP_SECS
done

log_error "Redis 컨테이너 응답 확인 실패"
docker-compose logs --no-color | tail -n 100 || true
exit 1


