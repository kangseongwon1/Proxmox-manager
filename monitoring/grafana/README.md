# Grafana Provisioning 설정

이 디렉토리는 Grafana의 자동 설정(Provisioning)을 위한 파일들을 포함합니다.

## 📁 디렉토리 구조

```
grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml          # Prometheus 데이터소스 설정
│   └── dashboards/
│       ├── dashboard.yml           # 대시보드 provisioning 설정
│       └── system-monitoring.json  # 시스템 모니터링 대시보드
└── README.md
```

## 🔧 파일 설명

### 1. 데이터소스 설정 (`datasources/prometheus.yml`)
- Prometheus 데이터소스를 자동으로 추가
- 기본 데이터소스로 설정
- 60초 쿼리 타임아웃 설정

### 2. 대시보드 설정 (`dashboards/dashboard.yml`)
- 대시보드 파일 기반 provisioning 활성화
- 10초마다 대시보드 업데이트 확인
- UI에서 대시보드 수정 허용

### 3. 시스템 모니터링 대시보드 (`dashboards/system-monitoring.json`)
- **CPU 사용률**: 실시간 CPU 사용률 표시 (임계값: 80% 경고, 95% 위험)
- **메모리 사용률**: 메모리 사용률 표시 (임계값: 85% 경고, 95% 위험)
- **디스크 사용률**: 디스크 사용률 표시 (임계값: 85% 경고, 95% 위험)
- **네트워크 트래픽**: 네트워크 수신/송신 트래픽 그래프
- **CPU 사용률 시간별**: CPU 사용률 시간별 추이 그래프

## 🚀 설치 과정

`install_complete_system.sh` 실행 시:

1. **Grafana 설치** 후 provisioning 디렉토리 생성
2. **파일 복사**: 이 디렉토리의 파일들을 `/etc/grafana/provisioning/`로 복사
3. **권한 설정**: grafana 사용자 소유권 설정
4. **서비스 재시작**: provisioning 적용을 위해 Grafana 재시작

## 📊 대시보드 접근

설치 완료 후 다음 URL로 접근 가능:

- **일반 모드**: http://localhost:3000/d/system-monitoring-dashboard
- **키오스크 모드**: http://localhost:3000/d/system-monitoring-dashboard?kiosk=tv
- **익명 접근**: 로그인 없이 바로 접근 가능

## 🔄 대시보드 수정

### 방법 1: UI에서 수정
1. Grafana 웹 인터페이스 접속
2. 대시보드 편집 모드로 진입
3. 원하는 대시보드 수정
4. 저장 (자동으로 JSON 파일에 반영됨)

### 방법 2: JSON 파일 직접 수정
1. `system-monitoring.json` 파일 편집
2. Grafana 서비스 재시작: `sudo systemctl restart grafana-server`
3. 변경사항 자동 적용

## 📈 추가 패널 추가

새로운 모니터링 패널을 추가하려면:

1. `system-monitoring.json` 파일의 `panels` 배열에 새 패널 추가
2. 패널 설정:
   - `id`: 고유 ID (기존 ID와 중복되지 않도록)
   - `title`: 패널 제목
   - `type`: 패널 타입 (stat, timeseries, graph 등)
   - `targets`: Prometheus 쿼리 설정
   - `gridPos`: 위치 및 크기 설정
3. Grafana 서비스 재시작

## 🎯 Prometheus 쿼리 예시

### CPU 사용률
```promql
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

### 메모리 사용률
```promql
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
```

### 디스크 사용률
```promql
(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100
```

### 네트워크 트래픽
```promql
rate(node_network_receive_bytes_total[5m])  # 수신
rate(node_network_transmit_bytes_total[5m]) # 송신
```

## 🔧 문제 해결

### 대시보드가 표시되지 않는 경우
1. Grafana 서비스 상태 확인: `sudo systemctl status grafana-server`
2. 로그 확인: `sudo journalctl -u grafana-server -n 50`
3. 파일 권한 확인: `ls -la /etc/grafana/provisioning/`
4. 서비스 재시작: `sudo systemctl restart grafana-server`

### 데이터가 표시되지 않는 경우
1. Prometheus 연결 확인: http://localhost:9090
2. Node Exporter 상태 확인: http://localhost:9100/metrics
3. 데이터소스 설정 확인: Grafana > Configuration > Data Sources

## 📝 참고사항

- 모든 설정은 파일 기반으로 관리되므로 버전 관리 가능
- 서비스 재시작 시에도 설정이 유지됨
- 대시보드 수정 시 자동으로 JSON 파일에 반영됨
- 익명 접근이 활성화되어 있어 로그인 없이 모니터링 가능
