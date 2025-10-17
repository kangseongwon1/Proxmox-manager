#!/bin/bash

# 🚀 모니터링 시스템 설치 후 자동 설정 스크립트
# Grafana 데이터 소스 추가, 대시보드 생성, 알림 설정

set -e

echo "🔧 모니터링 시스템 후처리 설정 시작..."

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Grafana API 설정
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASS="admin123"

# 대기 함수
wait_for_grafana() {
    log_info "Grafana 서비스 시작 대기 중..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "${GRAFANA_URL}/api/health" > /dev/null 2>&1; then
            log_success "Grafana 서비스 준비 완료"
            return 0
        fi
        
        log_info "시도 $attempt/$max_attempts - Grafana 대기 중..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    log_warning "Grafana 서비스 시작 시간 초과. 수동으로 확인해주세요."
    return 1
}

# Prometheus 데이터 소스 추가
add_prometheus_datasource() {
    log_info "Prometheus 데이터 소스 추가 중..."
    
    local datasource_config='{
        "name": "Prometheus",
        "type": "prometheus",
        "url": "http://localhost:9090",
        "access": "proxy",
        "isDefault": true,
        "jsonData": {
            "timeInterval": "15s"
        }
    }'
    
    local response=$(curl -s -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -u "${GRAFANA_USER}:${GRAFANA_PASS}" \
        -d "$datasource_config" \
        "${GRAFANA_URL}/api/datasources")
    
    local http_code="${response: -3}"
    local response_body="${response%???}"
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "409" ]; then
        log_success "Prometheus 데이터 소스 추가 완료"
    else
        log_warning "데이터 소스 추가 실패: $http_code - $response_body"
    fi
}

# 기본 대시보드 생성
create_basic_dashboard() {
    log_info "기본 모니터링 대시보드 생성 중..."
    
    local dashboard_config='{
        "dashboard": {
            "id": null,
            "title": "서버 모니터링 대시보드",
            "tags": ["monitoring", "servers"],
            "timezone": "browser",
            "panels": [
                {
                    "id": 1,
                    "title": "CPU 사용률",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
                            "legendFormat": "{{instance}}"
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                    "yAxes": [
                        {"unit": "percent", "min": 0, "max": 100}
                    ]
                },
                {
                    "id": 2,
                    "title": "메모리 사용률",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "100 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100)",
                            "legendFormat": "{{instance}}"
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                    "yAxes": [
                        {"unit": "percent", "min": 0, "max": 100}
                    ]
                },
                {
                    "id": 3,
                    "title": "디스크 사용률",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "100 - (node_filesystem_avail_bytes{fstype!=\"tmpfs\"} / node_filesystem_size_bytes{fstype!=\"tmpfs\"} * 100)",
                            "legendFormat": "{{instance}} - {{mountpoint}}"
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                    "yAxes": [
                        {"unit": "percent", "min": 0, "max": 100}
                    ]
                },
                {
                    "id": 4,
                    "title": "네트워크 트래픽",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "irate(node_network_receive_bytes_total[5m])",
                            "legendFormat": "{{instance}} - {{device}} (수신)"
                        },
                        {
                            "expr": "irate(node_network_transmit_bytes_total[5m])",
                            "legendFormat": "{{instance}} - {{device}} (송신)"
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                    "yAxes": [
                        {"unit": "bytes", "min": 0}
                    ]
                }
            ],
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "refresh": "30s"
        },
        "overwrite": true
    }'
    
    local response=$(curl -s -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -u "${GRAFANA_USER}:${GRAFANA_PASS}" \
        -d "$dashboard_config" \
        "${GRAFANA_URL}/api/dashboards/db")
    
    local http_code="${response: -3}"
    local response_body="${response%???}"
    
    if [ "$http_code" = "200" ]; then
        log_success "기본 대시보드 생성 완료"
    else
        log_warning "대시보드 생성 실패: $http_code - $response_body"
    fi
}

# 알림 채널 설정
setup_alerting() {
    log_info "알림 채널 설정 중..."
    
    # 이메일 알림 채널 (선택사항)
    log_info "이메일 알림 채널을 설정하려면 Grafana 웹 UI에서 수동으로 설정해주세요."
    log_info "경로: Alerting > Notification channels > Add channel"
    
    # 기본 알림 규칙 생성
    create_alert_rules
}

# 기본 알림 규칙 생성
create_alert_rules() {
    log_info "기본 알림 규칙 생성 중..."
    
    # CPU 사용률 알림
    local cpu_alert='{
        "name": "High CPU Usage",
        "query": "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100) > 80",
        "duration": "5m",
        "severity": "warning"
    }'
    
    # 메모리 사용률 알림
    local memory_alert='{
        "name": "High Memory Usage",
        "query": "100 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100) > 85",
        "duration": "5m",
        "severity": "warning"
    }'
    
    log_success "알림 규칙 템플릿 생성 완료"
    log_info "Grafana 웹 UI에서 Alerting > Alert rules에서 실제 규칙을 생성해주세요."
}

# 서비스 상태 확인
check_services() {
    log_info "모니터링 서비스 상태 확인 중..."
    
    local services=("prometheus" "grafana-server" "node_exporter")
    local all_healthy=true
    
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service"; then
            log_success "$service: 실행 중"
        else
            log_warning "$service: 중지됨"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = true ]; then
        log_success "모든 서비스가 정상 실행 중입니다."
    else
        log_warning "일부 서비스에 문제가 있습니다. 수동으로 확인해주세요."
    fi
}

# 접속 정보 출력
show_access_info() {
    echo ""
    echo "🎉 모니터링 시스템 설정 완료!"
    echo "=" * 60
    echo ""
    echo "📊 접속 정보:"
    echo "  - Grafana: http://$(hostname -I | awk '{print $1}'):3000"
    echo "  - Prometheus: http://$(hostname -I | awk '{print $1}'):9090"
    echo "  - Node Exporter (로컬): http://$(hostname -I | awk '{print $1}'):9100"
    echo ""
    echo "🔑 Grafana 계정:"
    echo "  - 사용자: admin"
    echo "  - 비밀번호: admin123"
    echo ""
    echo "📋 다음 단계:"
    echo "  1. Grafana에 로그인하여 대시보드 확인"
    echo "  2. 다른 서버들에 Node Exporter 설치:"
    echo "     ansible-playbook -i /etc/ansible/hosts ansible/install_node_exporter.yml"
    echo "  3. 필요에 따라 추가 대시보드 및 알림 설정"
    echo ""
    echo "💡 유용한 명령어:"
    echo "  - 서비스 상태: sudo systemctl status prometheus grafana-server node_exporter"
    echo "  - 로그 확인: sudo journalctl -u prometheus -f"
    echo "  - 포트 확인: sudo netstat -tlnp | grep -E ':(9090|3000|9100)'"
    echo ""
}

# 메인 실행
main() {
    echo "🚀 모니터링 시스템 후처리 설정 시작..."
    echo "⏰ 시작 시간: $(date)"
    echo ""
    
    # Grafana 서비스 대기
    if ! wait_for_grafana; then
        log_warning "Grafana 서비스가 준비되지 않았습니다. 수동으로 확인해주세요."
        return 1
    fi
    
    # 데이터 소스 추가
    add_prometheus_datasource
    
    # 기본 대시보드 생성
    create_basic_dashboard
    
    # 알림 설정
    setup_alerting
    
    # 서비스 상태 확인
    check_services
    
    # 접속 정보 출력
    show_access_info
    
    echo "✅ 후처리 설정 완료! $(date)"
}

# 스크립트 실행
main "$@"

