# 운영 가이드

## 📋 개요

이 문서는 Terraform Proxmox Manager의 일상적인 운영 및 관리 방법을 설명합니다. 서버 생성부터 모니터링, 백업, 문제 해결까지 모든 운영 작업을 다룹니다.

## 🔄 서비스 재시작 가이드

### Celery 워커 재시작이 필요한 경우

#### 1. 코드 변경 시 (항상 필요)
```bash
# Python 코드 수정 후
sudo systemctl restart proxmox-manager

# Docker 기반 Celery 워커 재시작
cd redis
docker-compose restart celery-worker

# 또는 전체 재시작
docker-compose down
docker-compose up -d
```

**재시작이 필요한 파일들:**
- `app/` 디렉토리 내 모든 Python 파일
- `app/celery_app.py` (Celery 설정)
- `app/tasks/` (Celery 작업)
- `app/routes/` (API 엔드포인트)
- `app/services/` (비즈니스 로직)
- `requirements.txt` (의존성 변경)

#### 2. 환경 설정 변경 시
```bash
# .env 파일 수정 후
sudo systemctl restart proxmox-manager

# Docker 기반 Celery 워커 재시작
cd redis
docker-compose restart celery-worker
```

**재시작이 필요한 설정:**
- Vault 설정 (VAULT_ADDR, VAULT_TOKEN)
- Redis 설정 (REDIS_HOST, REDIS_PASSWORD)
- Proxmox 설정 (PROXMOX_ENDPOINT, PROXMOX_USERNAME)

#### 3. 시스템 재시작 시
```bash
# 서버 재부팅 후 자동으로 시작됨
sudo systemctl status proxmox-manager

# Docker 서비스 확인
ps -aux | grep celery
docker ps | grep redis
docker ps | grep postgres
```

### 서비스 상태 확인
```bash
# 모든 서비스 상태 확인
sudo systemctl status proxmox-manager
sudo systemctl status celery-worker
sudo systemctl status redis

# Celery 워커 프로세스 확인
ps aux | grep celery

# Redis 연결 확인
redis-cli ping
```

### 로그 확인
```bash
# Flask 애플리케이션 로그
sudo journalctl -u proxmox-manager -f

# Celery 워커 로그
tail -f celery_worker.log

# Redis 로그
docker logs proxmox-redis
```

## 🖥️ 웹 인터페이스 사용법

### 1. 대시보드

웹 인터페이스에 접속하면 다음과 같은 대시보드를 볼 수 있습니다:

- **서버 목록**: 현재 생성된 모든 서버의 상태
- **리소스 사용량**: 전체 시스템 리소스 사용 현황
- **최근 알림**: 시스템 이벤트 및 상태 변경 알림
- **모니터링 차트**: 실시간 메트릭 그래프

### 2. 서버 관리

#### 서버 생성
1. **"서버 생성"** 버튼 클릭
2. 서버 정보 입력:
   - 서버 이름
   - 역할 (web, was, db)
   - CPU 코어 수
   - 메모리 크기
   - 디스크 크기
   - 네트워크 설정
3. **"생성"** 버튼 클릭

#### 대량 서버 생성
1. **"대량 생성"** 탭 선택
2. 서버 템플릿 설정
3. 생성할 서버 수 입력
4. IP 범위 설정
5. **"대량 생성"** 버튼 클릭

#### 서버 삭제
1. 삭제할 서버 선택
2. **"삭제"** 버튼 클릭
3. 확인 대화상자에서 **"확인"** 클릭

## 🔧 명령줄 도구 사용법

### 1. 기본 명령어

```bash
# 서비스 상태 확인
sudo systemctl status proxmox-manager

# 서비스 시작/중지/재시작
sudo systemctl start proxmox-manager
sudo systemctl stop proxmox-manager
sudo systemctl restart proxmox-manager

# 로그 확인
sudo journalctl -u proxmox-manager -f
```

### 2. 모니터링 시스템 관리

```bash
# 모니터링 시스템 시작
cd monitoring
docker-compose up -d

# 모니터링 시스템 중지
docker-compose down

# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### 3. Vault 관리

```bash
# Vault 상태 확인
docker exec vault-dev vault status

# Vault 언실
./scripts/vault.sh unseal

# 비밀 정보 조회
docker exec vault-dev vault kv get secret/ssh

# 비밀 정보 저장
docker exec vault-dev vault kv put secret/ssh \
  private_key="$(cat ~/.ssh/id_rsa)" \
  public_key="$(cat ~/.ssh/id_rsa.pub)"
```

## 📊 모니터링 및 알림

### 1. Grafana 대시보드

**접속**: `http://your-server-ip:3000`

#### 주요 대시보드
- **System Overview**: 전체 시스템 상태
- **Server Metrics**: 서버별 상세 메트릭
- **Network Traffic**: 네트워크 트래픽 분석
- **Disk Usage**: 디스크 사용량 모니터링

#### 대시보드 사용법
1. 왼쪽 메뉴에서 **"Dashboards"** 클릭
2. 원하는 대시보드 선택
3. 시간 범위 설정 (우상단)
4. 새로고침 주기 설정

### 2. Prometheus 메트릭

**접속**: `http://your-server-ip:9090`

#### 주요 메트릭
```promql
# 서버 가동 상태
up

# CPU 사용률
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 메모리 사용률
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# 디스크 사용률
100 - ((node_filesystem_avail_bytes * 100) / node_filesystem_size_bytes)
```

### 3. 알림 설정

#### 웹 인터페이스 알림
- 실시간 알림은 웹 인터페이스에서 자동으로 표시
- 알림 타입: 성공, 경고, 오류
- 알림 내용: 서버 생성/삭제, 상태 변경, 오류 발생

#### 이메일 알림 (향후 지원)
```yaml
# Grafana 알림 규칙 예시
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - "alert_rules.yml"
```

## 💾 백업 및 복원

### 1. 자동 백업

시스템은 다음 스케줄로 자동 백업을 수행합니다:

```bash
# 백업 스케줄 확인
crontab -l | grep backup

# 백업 로그 확인
tail -f /var/log/backup.log
```

### 2. 수동 백업

```bash
# 특정 서버 백업
curl -X POST http://localhost:5000/api/backups/create \
  -H "Content-Type: application/json" \
  -d '{"server_id": 1, "backup_type": "full"}'

# 전체 서버 백업
./scripts/backup_all.sh
```

### 3. 백업 복원

```bash
# 백업 목록 확인
curl http://localhost:5000/api/backups

# 특정 백업 복원
curl -X POST http://localhost:5000/api/backups/backup_12345/restore \
  -H "Content-Type: application/json" \
  -d '{"target_server_id": 2, "overwrite": true}'
```

### 4. 백업 정책 관리

```bash
# 백업 보존 정책 설정
vim config/backup_policy.yml

# 백업 정책 적용
./scripts/apply_backup_policy.sh
```

## 🔐 보안 관리

### 1. 사용자 관리

```bash
# 새 사용자 생성
sudo useradd -m -s /bin/bash newuser
sudo usermod -aG wheel newuser

# SSH 키 설정
sudo mkdir -p /home/newuser/.ssh
sudo cp ~/.ssh/authorized_keys /home/newuser/.ssh/
sudo chown -R newuser:newuser /home/newuser/.ssh
```

### 2. 방화벽 관리

```bash
# 방화벽 상태 확인
sudo firewall-cmd --list-all

# 포트 열기
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# 포트 닫기
sudo firewall-cmd --permanent --remove-port=8080/tcp
sudo firewall-cmd --reload
```

### 3. SSL/TLS 설정

```bash
# Let's Encrypt 인증서 발급
sudo certbot --nginx -d your-domain.com

# 인증서 자동 갱신 설정
sudo crontab -e
# 다음 라인 추가:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔄 유지보수

### 1. 정기 점검

#### 일일 점검
```bash
# 서비스 상태 확인
sudo systemctl status proxmox-manager docker

# 디스크 사용량 확인
df -h

# 로그 확인
tail -f logs/proxmox_manager.log
```

#### 주간 점검
```bash
# 시스템 업데이트
sudo dnf update -y

# 백업 상태 확인
./scripts/check_backup_status.sh

# 보안 스캔
sudo lynis audit system
```

#### 월간 점검
```bash
# 로그 로테이션
sudo logrotate -f /etc/logrotate.conf

# 데이터베이스 최적화
sqlite3 instance/proxmox_manager.db "VACUUM;"

# 모니터링 데이터 정리
docker exec prometheus promtool tsdb clean --retention.time=30d
```

### 2. 성능 최적화

#### 데이터베이스 최적화
```bash
# 인덱스 생성
sqlite3 instance/proxmox_manager.db "
CREATE INDEX IF NOT EXISTS idx_servers_status ON servers(status);
CREATE INDEX IF NOT EXISTS idx_servers_created_at ON servers(created_at);
"

# 통계 업데이트
sqlite3 instance/proxmox_manager.db "ANALYZE;"
```

#### 메모리 최적화
```bash
# 메모리 사용량 확인
free -h
ps aux --sort=-%mem | head -10

# 캐시 정리
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

### 3. 로그 관리

#### 로그 로테이션 설정
```bash
# logrotate 설정
sudo tee /etc/logrotate.d/proxmox-manager > /dev/null <<EOF
/data/terraform-proxmox/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF
```

#### 로그 분석
```bash
# 오류 로그 분석
grep "ERROR" logs/proxmox_manager.log | tail -20

# 성능 로그 분석
grep "slow" logs/proxmox_manager.log | wc -l

# 접속 로그 분석
grep "GET /api" logs/proxmox_manager.log | awk '{print $1}' | sort | uniq -c
```

## 🚨 장애 대응

### 1. 서비스 장애

#### Flask 애플리케이션 장애
```bash
# 프로세스 확인
ps aux | grep python

# 포트 확인
sudo netstat -tlnp | grep :5000

# 서비스 재시작
sudo systemctl restart proxmox-manager

# 로그 확인
sudo journalctl -u proxmox-manager -f
```

#### 데이터베이스 장애
```bash
# 데이터베이스 파일 확인
ls -la instance/proxmox_manager.db

# 권한 확인
ls -la instance/

# 권한 수정
sudo chown $USER:$USER instance/proxmox_manager.db
sudo chmod 664 instance/proxmox_manager.db
```

### 2. 모니터링 시스템 장애

#### Prometheus 장애
```bash
# 컨테이너 상태 확인
docker ps | grep prometheus

# 컨테이너 재시작
docker-compose -f monitoring/docker-compose.yml restart prometheus

# 설정 확인
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

#### Grafana 장애
```bash
# 컨테이너 상태 확인
docker ps | grep grafana

# 컨테이너 재시작
docker-compose -f monitoring/docker-compose.yml restart grafana

# 로그 확인
docker-compose -f monitoring/docker-compose.yml logs grafana
```

### 3. 네트워크 장애

#### 연결 문제 진단
```bash
# 네트워크 연결 확인
ping -c 4 8.8.8.8

# DNS 확인
nslookup google.com

# 포트 연결 확인
telnet your-server-ip 5000
```

#### 방화벽 문제
```bash
# 방화벽 상태 확인
sudo firewall-cmd --list-all

# 방화벽 비활성화 (임시)
sudo systemctl stop firewalld

# 방화벽 재시작
sudo systemctl start firewalld
```

## 📈 성능 모니터링

### 1. 시스템 리소스 모니터링

```bash
# CPU 사용률
top -bn1 | grep "Cpu(s)"

# 메모리 사용률
free -h

# 디스크 I/O
iostat -x 1

# 네트워크 트래픽
iftop
```

### 2. 애플리케이션 성능 모니터링

```bash
# 응답 시간 측정
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:5000/api/servers

# 동시 연결 수 확인
netstat -an | grep :5000 | wc -l

# 메모리 사용량 확인
ps aux | grep python | awk '{sum+=$6} END {print sum/1024 " MB"}'
```

### 3. 데이터베이스 성능 모니터링

```bash
# 데이터베이스 크기 확인
ls -lh instance/proxmox_manager.db

# 테이블 크기 확인
sqlite3 instance/proxmox_manager.db "
SELECT name, 
       (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as row_count
FROM sqlite_master m WHERE type='table';
"
```

## 🔧 설정 관리

### 1. 환경 변수 관리

```bash
# 환경 변수 확인
cat .env

# 환경 변수 수정
vim .env

# 변경사항 적용
sudo systemctl restart proxmox-manager
```

### 2. Ansible 설정 관리

```bash
# Ansible 설정 확인
ansible-config dump --only-changed

# 인벤토리 확인
ansible-inventory --list

# 플레이북 테스트
ansible-playbook --check ansible/role_playbook.yml
```

### 3. Terraform 설정 관리

```bash
# Terraform 상태 확인
terraform show

# 계획 확인
terraform plan

# 설정 검증
terraform validate
```

## 📞 지원 및 문의

### 1. 로그 수집

문제 발생 시 다음 로그를 수집하여 지원팀에 전달하세요:

```bash
# 시스템 정보 수집
./scripts/collect_logs.sh

# 로그 파일 위치
- 애플리케이션 로그: logs/proxmox_manager.log
- 시스템 로그: /var/log/messages
- 서비스 로그: journalctl -u proxmox-manager
```

### 2. 문제 보고

GitHub Issues를 통해 문제를 보고하세요:

1. [GitHub Issues](https://github.com/your-org/terraform-proxmox/issues) 접속
2. **"New Issue"** 클릭
3. 문제 유형 선택 및 상세 정보 입력
4. 로그 파일 첨부

### 3. 커뮤니티 지원

- **GitHub Discussions**: [토론 및 질문](https://github.com/your-org/terraform-proxmox/discussions)
- **Wiki**: [상세 문서](https://github.com/your-org/terraform-proxmox/wiki)
- **Discord**: [실시간 채팅](https://discord.gg/your-discord)

---

더 자세한 문제 해결 방법은 [문제 해결 가이드](TROUBLESHOOTING.md)를 참조하세요.
