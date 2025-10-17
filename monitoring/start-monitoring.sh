#!/bin/bash
# Proxmox Manager 모니터링 시스템 시작 스크립트

# set -e 제거 (오류 시 즉시 종료 방지)

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Docker 설치 확인
check_docker() {
    log_info "Docker 설치 확인 중..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
        log_info "Docker 설치 후 다시 시도해주세요."
        return 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다."
        log_info "Docker Compose 설치 후 다시 시도해주세요."
        return 1
    fi
    
    # Docker 서비스 상태 확인
    if ! docker info &> /dev/null; then
        log_error "Docker 서비스가 실행되지 않았습니다."
        log_info "Docker 서비스를 시작한 후 다시 시도해주세요."
        return 1
    fi
    
    # 포트 충돌 확인 (Linux/Windows 호환)
    log_info "포트 충돌 확인 중..."
    
    # Linux에서 netstat 사용, Windows에서는 다른 방법 사용
    if command -v netstat &> /dev/null; then
        if netstat -tuln 2>/dev/null | grep -q ":9090 "; then
            log_warning "포트 9090이 이미 사용 중입니다. 기존 Prometheus 컨테이너를 중지합니다."
            docker stop prometheus 2>/dev/null || true
            docker rm prometheus 2>/dev/null || true
        fi
        
        if netstat -tuln 2>/dev/null | grep -q ":3000 "; then
            log_warning "포트 3000이 이미 사용 중입니다. 기존 Grafana 컨테이너를 중지합니다."
            docker stop grafana 2>/dev/null || true
            docker rm grafana 2>/dev/null || true
        fi
        
        if netstat -tuln 2>/dev/null | grep -q ":9100 "; then
            log_warning "포트 9100이 이미 사용 중입니다. 기존 Node Exporter 컨테이너를 중지합니다."
            docker stop node-exporter 2>/dev/null || true
            docker rm node-exporter 2>/dev/null || true
        fi
    else
        log_info "netstat 명령어를 사용할 수 없습니다. Docker 컨테이너로 포트 확인을 시도합니다."
        # Docker 컨테이너로 포트 확인
        if docker ps --format "table {{.Ports}}" | grep -q ":9090"; then
            log_warning "포트 9090이 이미 사용 중입니다. 기존 Prometheus 컨테이너를 중지합니다."
            docker stop prometheus 2>/dev/null || true
            docker rm prometheus 2>/dev/null || true
        fi
        
        if docker ps --format "table {{.Ports}}" | grep -q ":3000"; then
            log_warning "포트 3000이 이미 사용 중입니다. 기존 Grafana 컨테이너를 중지합니다."
            docker stop grafana 2>/dev/null || true
            docker rm grafana 2>/dev/null || true
        fi
        
        if docker ps --format "table {{.Ports}}" | grep -q ":9100"; then
            log_warning "포트 9100이 이미 사용 중입니다. 기존 Node Exporter 컨테이너를 중지합니다."
            docker stop node-exporter 2>/dev/null || true
            docker rm node-exporter 2>/dev/null || true
        fi
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
    return 0
}

# 디렉토리 생성
create_directories() {
    log_info "필요한 디렉토리 생성 중..."
    mkdir -p prometheus_data
    mkdir -p grafana_data
    mkdir -p grafana/provisioning/datasources
    mkdir -p grafana/provisioning/dashboards
    mkdir -p grafana/dashboards
    
    # 권한 설정 (Linux에서만)
    if command -v chmod &> /dev/null; then
        chmod 755 prometheus_data
        chmod 755 grafana_data
        chmod 755 grafana/provisioning/datasources
        chmod 755 grafana/provisioning/dashboards
        chmod 755 grafana/dashboards
    fi
    
    # 디렉토리 생성 확인
    log_info "생성된 디렉토리 확인:"
    ls -la
    
    log_success "디렉토리 생성 완료"
    return 0
}

# 기존 컨테이너 정리
cleanup_containers() {
    log_info "기존 모니터링 컨테이너 정리 중..."
    
    # 기존 컨테이너 중지 및 제거
    docker-compose down 2>/dev/null || true
    
    log_success "기존 컨테이너 정리 완료"
    return 0
}

# 모니터링 시스템 시작
start_monitoring() {
    log_info "모니터링 시스템 시작 중..."
    
    # 현재 디렉토리 확인
    log_info "현재 디렉토리: $(pwd)"
    log_info "Docker Compose 파일 확인: $(ls -la docker-compose.yml 2>/dev/null || echo 'docker-compose.yml 파일이 없습니다')"
    
    # Docker Compose 실행
    if [ -f "docker-compose.yml" ]; then
        log_info "Docker Compose 실행 중..."
        
        # Docker Compose 실행
        log_info "Docker Compose 명령어 실행: docker-compose up -d"
        if docker-compose up -d; then
            log_info "Docker Compose 실행 완료"
        else
            log_error "Docker Compose 실행 실패"
            log_info "컨테이너 로그 확인 중..."
            docker-compose logs
            log_info "Docker Compose 상태 확인:"
            docker-compose ps
            return 1
        fi
        
        # 컨테이너 상태 확인
        log_info "컨테이너 상태 확인 중..."
        sleep 10
        
        # 각 컨테이너별 상태 확인
        if docker-compose ps | grep -q "prometheus.*Up"; then
            log_success "Prometheus 컨테이너 실행 중"
        else
            log_warning "Prometheus 컨테이너 실행 실패"
        fi
        
        if docker-compose ps | grep -q "grafana.*Up"; then
            log_success "Grafana 컨테이너 실행 중"
        else
            log_warning "Grafana 컨테이너 실행 실패"
        fi
        
        if docker-compose ps | grep -q "node-exporter.*Up"; then
            log_success "Node Exporter 컨테이너 실행 중"
        else
            log_warning "Node Exporter 컨테이너 실행 실패"
        fi
        
        # 전체 상태 확인
        if docker-compose ps | grep -q "Up"; then
            log_success "모니터링 시스템 시작 완료"
            return 0
        else
            log_error "모니터링 시스템 시작 실패"
            log_info "컨테이너 로그 확인 중..."
            docker-compose logs
            return 1
        fi
    else
        log_error "docker-compose.yml 파일을 찾을 수 없습니다"
        log_info "현재 디렉토리 내용:"
        ls -la
        return 1
    fi
}

# 서비스 상태 확인
check_services() {
    log_info "서비스 상태 확인 중..."
    
    # Prometheus 확인
    log_info "Prometheus 상태 확인 중..."
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus: http://localhost:9090"
    else
        log_warning "Prometheus 연결 실패"
        log_info "Prometheus 컨테이너 로그:"
        docker logs prometheus 2>/dev/null || true
    fi
    
    # Grafana 확인
    log_info "Grafana 상태 확인 중..."
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        log_success "Grafana: http://localhost:3000 (admin/admin123)"
    else
        log_warning "Grafana 연결 실패"
        log_info "Grafana 컨테이너 로그:"
        docker logs grafana 2>/dev/null || true
    fi
    
    # Node Exporter 확인
    log_info "Node Exporter 상태 확인 중..."
    if curl -s http://localhost:9100/metrics > /dev/null 2>&1; then
        log_success "Node Exporter: http://localhost:9100"
    else
        log_warning "Node Exporter 연결 실패"
        log_info "Node Exporter 컨테이너 로그:"
        docker logs node-exporter 2>/dev/null || true
    fi
    
    return 0
}

# 메인 실행
main() {
    log_info "Proxmox Manager 모니터링 시스템 시작"
    
    # 각 단계별로 오류 처리
    if ! check_docker; then
        log_error "Docker 확인 실패"
        return 1
    fi
    
    if ! create_directories; then
        log_error "디렉토리 생성 실패"
        return 1
    fi
    
    if ! cleanup_containers; then
        log_error "컨테이너 정리 실패"
        return 1
    fi
    
    if ! start_monitoring; then
        log_error "모니터링 시스템 시작 실패"
        return 1
    fi
    
    if ! check_services; then
        log_warning "서비스 상태 확인 중 일부 문제가 발생했습니다"
    fi
    
    log_success "모니터링 시스템 설정 완료!"
    echo ""
    echo "📊 모니터링 대시보드:"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin123)"
    echo "  - Node Exporter: http://localhost:9100"
    echo ""
    echo "🔧 관리 명령어:"
    echo "  - 중지: docker-compose down"
    echo "  - 재시작: docker-compose restart"
    echo "  - 로그 확인: docker-compose logs"
    echo "  - 상태 확인: docker-compose ps"
    echo ""
    echo "🐛 문제 해결:"
    echo "  - 컨테이너 로그: docker-compose logs [서비스명]"
    echo "  - 컨테이너 재시작: docker-compose restart [서비스명]"
    echo "  - 완전 재시작: docker-compose down && docker-compose up -d"
    
    return 0
}

# 스크립트 실행
main "$@"