#!/bin/bash
# Proxmox Manager Redis + Celery Docker Compose 시작 스크립트

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

# .env 파일 확인
if [ ! -f "../.env" ]; then
    log_error ".env 파일을 찾을 수 없습니다. 프로젝트 루트에 .env 파일을 생성하세요."
    exit 1
fi

# .env에서 Redis 설정 로드
export REDIS_HOST=${REDIS_HOST:-localhost}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_PASSWORD=${REDIS_PASSWORD:-proxmox123}

log_info "Redis + Celery Docker Compose 시작 중..."
log_info "Redis Host: $REDIS_HOST"
log_info "Redis Port: $REDIS_PORT"
log_info "Redis Password: ${REDIS_PASSWORD:0:3}***"

# Docker 설치 확인
if ! command -v docker &> /dev/null; then
    log_error "Docker가 설치되지 않았습니다."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose가 설치되지 않았습니다."
    exit 1
fi

# 기존 컨테이너 정리
log_info "기존 컨테이너 정리 중..."
docker-compose down 2>/dev/null || true

# Docker Compose 실행
log_info "Redis + Celery 서비스 시작 중..."
if docker-compose up -d; then
    log_success "Redis + Celery 서비스 시작 완료"
    
    # 서비스 상태 확인
    log_info "서비스 상태 확인 중..."
    sleep 5
    
    # Redis 연결 테스트
    if docker exec proxmox-redis redis-cli -a "$REDIS_PASSWORD" ping > /dev/null 2>&1; then
        log_success "Redis: redis://localhost:$REDIS_PORT"
    else
        log_warn "Redis 연결 실패"
    fi
    
    # Celery 워커 상태 확인
    if docker ps | grep -q "proxmox-celery-worker.*Up"; then
        log_success "Celery Worker: 실행 중"
    else
        log_warn "Celery Worker 실행 실패"
    fi
    
    # Flower 상태 확인
    if docker ps | grep -q "proxmox-celery-flower.*Up"; then
        log_success "Celery Flower: http://localhost:5555"
    else
        log_warn "Celery Flower 실행 실패"
    fi
    
    log_success "Redis + Celery 시스템 설정 완료!"
    log_info "Flower 대시보드: http://localhost:5555"
    log_info "Redis: redis://localhost:$REDIS_PORT"
    
else
    log_error "Redis + Celery 서비스 시작 실패"
    docker-compose logs
    exit 1
fi
