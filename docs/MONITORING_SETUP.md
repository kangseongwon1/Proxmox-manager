# 모니터링 시스템 설정 가이드

## 📋 개요

이 모니터링 시스템은 **config 파일 기반**으로 동작하며, 사용자가 코드 수정 없이 설정을 변경할 수 있습니다.

## 🚀 빠른 시작

### 1. 설정 파일 생성

프로젝트 루트에 `monitoring_config.conf` 파일이 자동으로 생성됩니다.

### 2. 기본 설정 확인

```bash
# 설정 파일 확인
cat monitoring_config.conf
```

### 3. 설정 수정

`monitoring_config.conf` 파일을 편집하여 원하는 설정으로 변경하세요.

## ⚙️ 설정 섹션별 설명

### [GRAFANA] 섹션

```ini
[GRAFANA]
# Grafana 서버 설정
grafana_url = http://localhost:3000
grafana_username = admin
grafana_password = admin
org_id = 1

# 대시보드 설정
dashboard_uid = system_monitoring
dashboard_id = 2
dashboard_url = /d/system_monitoring/system-monitoring-dashboard-10-servers

# 임베딩 설정
allow_embedding = true
anonymous_access = false
kiosk_mode = true
auto_refresh = 5s
```

**설정 항목:**
- `grafana_url`: Grafana 서버 URL
- `grafana_username`: Grafana 로그인 사용자명
- `grafana_password`: Grafana 로그인 비밀번호
- `org_id`: Grafana 조직 ID
- `dashboard_uid`: 대시보드 UID
- `anonymous_access`: 익명 접근 허용 여부
- `auto_refresh`: 자동 새로고침 간격

### [PROMETHEUS] 섹션

```ini
[PROMETHEUS]
# Prometheus 서버 설정
prometheus_url = http://localhost:9090
prometheus_username = 
prometheus_password = 
```

**설정 항목:**
- `prometheus_url`: Prometheus 서버 URL
- `prometheus_username`: Prometheus 인증 사용자명 (선택사항)
- `prometheus_password`: Prometheus 인증 비밀번호 (선택사항)

### [MONITORING] 섹션

```ini
[MONITORING]
# 모니터링 설정
default_time_range = 1h
default_refresh_interval = 5s
max_data_points = 1000

# 서버 상태 확인 설정
ping_timeout = 5s
ssh_timeout = 10s
health_check_interval = 30s

# Node Exporter 자동 설치 설정
auto_install_node_exporter = true
node_exporter_port = 9100
node_exporter_version = 1.6.1
```

**설정 항목:**
- `default_time_range`: 기본 시간 범위 (1h, 6h, 24h, 7d)
- `default_refresh_interval`: 기본 새로고침 간격
- `health_check_interval`: 서버 상태 확인 간격
- `auto_install_node_exporter`: 서버 생성 시 Node Exporter 자동 설치 여부
- `node_exporter_port`: Node Exporter 포트 (기본: 9100)
- `node_exporter_version`: Node Exporter 버전 (기본: 1.6.1)

### [ALERTS] 섹션

```ini
[ALERTS]
# 알림 설정
enable_alerts = true
alert_email = admin@example.com
alert_webhook = 

# 알림 임계값
cpu_warning_threshold = 80
cpu_critical_threshold = 95
memory_warning_threshold = 85
memory_critical_threshold = 95
disk_warning_threshold = 85
disk_critical_threshold = 95
```

**설정 항목:**
- `enable_alerts`: 알림 활성화 여부
- `alert_email`: 알림 이메일 주소
- `cpu_warning_threshold`: CPU 경고 임계값 (%)
- `cpu_critical_threshold`: CPU 위험 임계값 (%)

### [SECURITY] 섹션

```ini
[SECURITY]
# 보안 설정
enable_https = false
ssl_cert_path = 
ssl_key_path = 
allowed_origins = *

# 인증 설정
enable_auth = true
session_timeout = 3600
max_login_attempts = 5
```

## 🔧 설정 방법

### 방법 1: 파일 직접 편집

1. `monitoring_config.conf` 파일을 텍스트 에디터로 열기
2. 원하는 설정 값 변경
3. 파일 저장
4. 웹 애플리케이션 재시작

### 방법 2: 웹 UI 사용

1. 웹 애플리케이션 실행
2. 모니터링 설정 페이지 접속: `/monitoring/config-page`
3. 설정 값 변경
4. "설정 저장" 버튼 클릭

## 📝 설정 예시

### 로컬 개발 환경

```ini
[GRAFANA]
grafana_url = http://localhost:3000
grafana_username = admin
grafana_password = admin
anonymous_access = false

[PROMETHEUS]
prometheus_url = http://localhost:9090
```

### 프로덕션 환경

```ini
[GRAFANA]
grafana_url = https://grafana.yourcompany.com
grafana_username = monitoring_user
grafana_password = secure_password
anonymous_access = true

[PROMETHEUS]
prometheus_url = https://prometheus.yourcompany.com
prometheus_username = prometheus_user
prometheus_password = secure_password
```

### 익명 접근 허용 환경

```ini
[GRAFANA]
grafana_url = http://localhost:3000
anonymous_access = true
kiosk_mode = true
```

## 🔍 설정 확인

### API를 통한 설정 조회

```bash
# 설정 조회
curl -X GET http://localhost:5000/monitoring/config

# 특정 설정 확인
curl -X GET http://localhost:5000/monitoring/config | jq '.data.grafana'
```

### 로그를 통한 설정 확인

웹 애플리케이션 로그에서 다음 메시지 확인:
```
✅ 설정 파일 로드 완료: monitoring_config.conf
```

## 🚨 주의사항

1. **비밀번호 보안**: `grafana_password`와 `prometheus_password`는 민감한 정보입니다.
2. **파일 권한**: `monitoring_config.conf` 파일의 권한을 적절히 설정하세요.
3. **백업**: 설정 파일을 정기적으로 백업하세요.
4. **재시작**: 설정 변경 후 웹 애플리케이션을 재시작해야 합니다.

## 🆘 문제 해결

### 설정이 적용되지 않는 경우

1. 설정 파일 문법 확인
2. 웹 애플리케이션 재시작
3. 로그 파일 확인

### Grafana 연결 실패

1. `grafana_url` 확인
2. `grafana_username`과 `grafana_password` 확인
3. Grafana 서버 상태 확인

### Prometheus 연결 실패

1. `prometheus_url` 확인
2. Prometheus 서버 상태 확인
3. 방화벽 설정 확인

## 📞 지원

문제가 발생하면 다음을 확인하세요:

1. 설정 파일 문법
2. 웹 애플리케이션 로그
3. Grafana/Prometheus 서버 상태
4. 네트워크 연결 상태
