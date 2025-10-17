# 📊 모니터링 가이드

## 📋 개요

이 문서는 Proxmox 서버 자동 생성 및 관리 시스템의 모니터링 설정과 운영 방법을 설명합니다.

## 🎯 모니터링 아키텍처

### 전체 구조
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   웹 콘솔       │    │   Grafana       │    │   Prometheus    │
│   (Flask)       │◄──►│   (시각화)      │◄──►│   (수집/저장)   │
│                 │    │                 │    │                 │
│ - 요약 정보     │    │ - 대시보드      │    │ - 메트릭 저장   │
│ - 알림 표시     │    │ - 알림          │    │ - 쿼리 처리     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                    ┌─────────────────┐
                    │   Node Exporter │
                    │   (메트릭 수집) │
                    │                 │
                    │ - 시스템 메트릭 │
                    │ - 네트워크 정보 │
                    │ - 프로세스 정보 │
                    └─────────────────┘
```

### 모니터링 범위
1. **시스템 리소스**: CPU, 메모리, 디스크, 네트워크
2. **애플리케이션**: Flask 웹 서버, 데이터베이스
3. **인프라**: Proxmox VE, VM 상태
4. **비즈니스**: 서버 생성/삭제, 백업 상태

## 🚀 모니터링 스택 설치

### 1. Prometheus 설치

#### Docker를 사용한 설치
```bash
# Prometheus 설정 파일 생성
mkdir -p /opt/prometheus
cat > /opt/prometheus/prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'proxmox-manager'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
EOF

# Prometheus 실행
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v /opt/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

#### 바이너리 설치
```bash
# Prometheus 다운로드
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvf prometheus-2.45.0.linux-amd64.tar.gz
cd prometheus-2.45.0

# 설정 파일 생성
cat > prometheus.yml <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
EOF

# Prometheus 실행
./prometheus --config.file=prometheus.yml
```

### 2. Node Exporter 설치

#### Docker를 사용한 설치
```bash
# Node Exporter 실행
docker run -d \
  --name node-exporter \
  -p 9100:9100 \
  -v "/proc:/host/proc:ro" \
  -v "/sys:/host/sys:ro" \
  -v "/:/rootfs:ro" \
  prom/node-exporter \
  --path.procfs /host/proc \
  --path.sysfs /host/sys \
  --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
```

#### 바이너리 설치
```bash
# Node Exporter 다운로드
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar xvf node_exporter-1.6.1.linux-amd64.tar.gz
cd node_exporter-1.6.1

# Node Exporter 실행
./node_exporter
```

### 3. Grafana 설치

#### Docker를 사용한 설치
```bash
# Grafana 실행
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -e "GF_SECURITY_ADMIN_PASSWORD=admin123!" \
  grafana/grafana
```

#### 바이너리 설치
```bash
# Grafana 설치 (Ubuntu)
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install grafana

# Grafana 시작
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

## ⚙️ 모니터링 설정

### 1. Flask 애플리케이션 메트릭

#### Prometheus 클라이언트 설치
```bash
pip install prometheus_client
```

#### 메트릭 엔드포인트 추가
```python
# app/__init__.py
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

# 메트릭 정의
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

def create_app():
    app = Flask(__name__)
    
    # 메트릭 엔드포인트
    @app.route('/metrics')
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    
    # 요청 카운터 미들웨어
    @app.before_request
    def before_request():
        request.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.endpoint,
            status=response.status_code
        ).inc()
        
        REQUEST_LATENCY.observe(time.time() - request.start_time)
        return response
    
    return app
```

#### 비즈니스 메트릭 추가
```python
# app/services/monitoring_service.py
from prometheus_client import Gauge, Counter

# 서버 관련 메트릭
ACTIVE_SERVERS = Gauge('active_servers_total', 'Number of active servers')
SERVER_CREATION_COUNTER = Counter('server_creation_total', 'Total server creations')
BACKUP_COUNT = Gauge('backup_count_total', 'Number of backups')

class MonitoringService:
    @staticmethod
    def update_server_metrics():
        """서버 메트릭 업데이트"""
        try:
            from app.models.server import Server
            active_count = Server.query.filter_by(status='running').count()
            ACTIVE_SERVERS.set(active_count)
        except Exception as e:
            logger.error(f"서버 메트릭 업데이트 실패: {e}")
    
    @staticmethod
    def increment_server_creation():
        """서버 생성 카운터 증가"""
        SERVER_CREATION_COUNTER.inc()
    
    @staticmethod
    def update_backup_metrics():
        """백업 메트릭 업데이트"""
        try:
            # 백업 개수 계산 로직
            backup_count = 0  # 실제 백업 개수 계산
            BACKUP_COUNT.set(backup_count)
        except Exception as e:
            logger.error(f"백업 메트릭 업데이트 실패: {e}")
```

### 2. Grafana 대시보드 설정

#### 데이터 소스 추가
1. Grafana 접속 (http://localhost:3000)
2. 관리자 계정으로 로그인 (admin/admin123!)
3. Configuration > Data Sources > Add data source
4. Prometheus 선택 및 설정:
   - URL: http://localhost:9090
   - Access: Server (default)

#### 대시보드 생성

##### 시스템 대시보드
```json
{
  "dashboard": {
    "title": "System Overview",
    "panels": [
      {
        "title": "CPU Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "CPU Usage %"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100",
            "legendFormat": "Memory Usage %"
          }
        ]
      },
      {
        "title": "Disk Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100",
            "legendFormat": "Disk Usage %"
          }
        ]
      }
    ]
  }
}
```

##### 애플리케이션 대시보드
```json
{
  "dashboard": {
    "title": "Application Metrics",
    "panels": [
      {
        "title": "HTTP Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Active Servers",
        "type": "stat",
        "targets": [
          {
            "expr": "active_servers_total",
            "legendFormat": "Active Servers"
          }
        ]
      },
      {
        "title": "Server Creation Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(server_creation_total[5m])",
            "legendFormat": "Server Creations/min"
          }
        ]
      }
    ]
  }
}
```

### 3. 알림 설정

#### Prometheus 알림 규칙
```yaml
# /opt/prometheus/alerts.yml
groups:
  - name: proxmox-manager
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is above 80% for 5 minutes"

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage detected"
          description: "Memory usage is above 85% for 5 minutes"

      - alert: HighDiskUsage
        expr: (node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100 > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High disk usage detected"
          description: "Disk usage is above 90% for 5 minutes"

      - alert: ApplicationDown
        expr: up{job="proxmox-manager"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Application is down"
          description: "Proxmox Manager application is not responding"

      - alert: NoActiveServers
        expr: active_servers_total == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "No active servers"
          description: "No servers are currently running"
```

#### Grafana 알림 설정
1. 대시보드에서 패널 편집
2. Alert 탭에서 알림 규칙 생성
3. 알림 채널 설정 (이메일, Slack 등)

## 📊 모니터링 메트릭

### 1. 시스템 메트릭

#### CPU 메트릭
```promql
# CPU 사용률
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# CPU 코어별 사용률
100 - (avg by (cpu, instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# CPU 로드 평균
node_load1
node_load5
node_load15
```

#### 메모리 메트릭
```promql
# 메모리 사용률
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# 메모리 사용량 (GB)
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1024 / 1024 / 1024

# 스왑 사용률
(node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes) / node_memory_SwapTotal_bytes * 100
```

#### 디스크 메트릭
```promql
# 디스크 사용률
(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100

# 디스크 I/O
rate(node_disk_io_time_seconds_total[5m])

# 디스크 읽기/쓰기 바이트
rate(node_disk_read_bytes_total[5m])
rate(node_disk_written_bytes_total[5m])
```

#### 네트워크 메트릭
```promql
# 네트워크 트래픽
rate(node_network_receive_bytes_total[5m])
rate(node_network_transmit_bytes_total[5m])

# 네트워크 패킷
rate(node_network_receive_packets_total[5m])
rate(node_network_transmit_packets_total[5m])
```

### 2. 애플리케이션 메트릭

#### HTTP 메트릭
```promql
# 요청률
rate(http_requests_total[5m])

# 응답 시간
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 에러율
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100
```

#### 비즈니스 메트릭
```promql
# 활성 서버 수
active_servers_total

# 서버 생성률
rate(server_creation_total[5m])

# 백업 개수
backup_count_total
```

### 3. 인프라 메트릭

#### Proxmox 메트릭
```promql
# VM 상태
proxmox_vm_status

# 스토리지 사용량
proxmox_storage_usage

# 노드 상태
proxmox_node_status
```

## 🔔 알림 시스템

### 1. 이메일 알림 설정

#### SMTP 설정
```yaml
# Grafana 설정 파일 (/etc/grafana/grafana.ini)
[smtp]
enabled = true
host = smtp.gmail.com:587
user = your-email@gmail.com
password = your-app-password
from_address = your-email@gmail.com
from_name = Proxmox Manager Alert
```

#### 알림 채널 생성
1. Grafana > Alerting > Notification channels
2. Add channel > Email
3. 설정:
   - Name: Email Alerts
   - Email addresses: admin@your-domain.com
   - Include image: Yes

### 2. Slack 알림 설정

#### Slack 웹훅 설정
1. Slack 워크스페이스에서 앱 추가
2. Incoming Webhooks 활성화
3. 웹훅 URL 생성

#### Grafana에서 Slack 채널 설정
1. Grafana > Alerting > Notification channels
2. Add channel > Slack
3. 설정:
   - Name: Slack Alerts
   - Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL

### 3. 커스텀 알림 스크립트

#### 웹훅 알림
```python
# app/services/notification_service.py
import requests
import json

class NotificationService:
    def __init__(self):
        self.webhook_url = os.getenv('WEBHOOK_URL')
    
    def send_alert(self, title, message, severity='info'):
        """알림 전송"""
        payload = {
            'title': title,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"알림 전송 실패: {e}")
```

## 📈 대시보드 예제

### 1. 시스템 개요 대시보드

#### 패널 구성
1. **CPU 사용률**: 실시간 CPU 사용률 그래프
2. **메모리 사용률**: 메모리 사용률 및 사용 가능한 메모리
3. **디스크 사용률**: 각 마운트 포인트별 디스크 사용률
4. **네트워크 트래픽**: 인바운드/아웃바운드 트래픽
5. **시스템 로드**: 1분, 5분, 15분 로드 평균

#### 쿼리 예제
```promql
# CPU 사용률
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 메모리 사용률
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# 디스크 사용률
(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100
```

### 2. 애플리케이션 대시보드

#### 패널 구성
1. **요청률**: HTTP 요청 수/초
2. **응답 시간**: 95th percentile 응답 시간
3. **에러율**: HTTP 5xx 에러 비율
4. **활성 서버**: 현재 실행 중인 서버 수
5. **백업 상태**: 백업 개수 및 상태

#### 쿼리 예제
```promql
# 요청률
rate(http_requests_total[5m])

# 응답 시간
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 에러율
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100
```

### 3. 비즈니스 대시보드

#### 패널 구성
1. **서버 생성/삭제**: 일별 서버 생성/삭제 수
2. **백업 상태**: 백업 성공/실패율
3. **사용자 활동**: 활성 사용자 수
4. **리소스 사용량**: VM별 리소스 사용량

## 🛠️ 운영 및 유지보수

### 1. 정기적인 점검

#### 일일 점검
```bash
# Prometheus 상태 확인
curl http://localhost:9090/-/healthy

# Grafana 상태 확인
curl http://localhost:3000/api/health

# 메트릭 수집 확인
curl http://localhost:9100/metrics | grep -c "node_"
```

#### 주간 점검
```bash
# 데이터 보존 정책 확인
# 알림 규칙 검토
# 대시보드 성능 최적화
```

### 2. 백업 및 복구

#### 설정 백업
```bash
# Prometheus 설정 백업
cp /opt/prometheus/prometheus.yml /backup/prometheus.yml

# Grafana 설정 백업
cp /etc/grafana/grafana.ini /backup/grafana.ini

# 대시보드 백업
curl -s http://admin:admin123!@localhost:3000/api/dashboards/db/system-overview | jq '.' > /backup/dashboard-system-overview.json
```

#### 데이터 백업
```bash
# Prometheus 데이터 백업
tar -czf /backup/prometheus-data-$(date +%Y%m%d).tar.gz /opt/prometheus/data/

# Grafana 데이터베이스 백업
sqlite3 /var/lib/grafana/grafana.db ".backup '/backup/grafana-$(date +%Y%m%d).db'"
```

### 3. 성능 최적화

#### Prometheus 최적화
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'proxmox-manager'

storage:
  tsdb:
    retention.time: 30d
    retention.size: 10GB

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 15s

  - job_name: 'proxmox-manager'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

#### Grafana 최적화
```ini
# grafana.ini
[server]
http_port = 3000
root_url = http://localhost:3000/

[database]
type = sqlite3
path = /var/lib/grafana/grafana.db

[security]
admin_user = admin
admin_password = admin123!

[users]
allow_sign_up = false

[log]
mode = file
level = info
```

## 📚 추가 리소스

### 1. 공식 문서
- [Prometheus 공식 문서](https://prometheus.io/docs/)
- [Grafana 공식 문서](https://grafana.com/docs/)
- [Node Exporter 문서](https://github.com/prometheus/node_exporter)

### 2. 커뮤니티 리소스
- [Prometheus 커뮤니티](https://prometheus.io/community/)
- [Grafana 커뮤니티](https://community.grafana.com/)
- [대시보드 갤러리](https://grafana.com/grafana/dashboards/)

### 3. 도구 및 유틸리티
- [Prometheus Query Builder](https://prometheus.io/docs/prometheus/latest/querying/examples/)
- [Grafana Dashboard Builder](https://grafana.com/docs/grafana/latest/dashboards/)
- [Alert Manager](https://prometheus.io/docs/alerting/latest/alertmanager/)

---

이 문서는 모니터링 시스템의 설정과 운영 방법을 설명합니다. 추가 질문이 있으면 팀에 문의하세요.


