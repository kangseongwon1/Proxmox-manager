# 문제 해결 가이드

## 📋 개요

이 문서는 Terraform Proxmox Manager 사용 중 발생할 수 있는 일반적인 문제들과 해결 방법을 제공합니다. 문제가 발생했을 때 이 가이드를 참조하여 빠르게 해결할 수 있습니다.

## 🚨 긴급 문제 해결

### 1. 웹 인터페이스 접속 불가

#### 증상
- 브라우저에서 `http://your-server-ip:5000` 접속 시 연결 실패
- "Connection refused" 또는 "This site can't be reached" 오류

#### 해결 방법

**1단계: 서비스 상태 확인**
```bash
sudo systemctl status proxmox-manager
```

**2단계: 포트 확인**
```bash
sudo netstat -tlnp | grep :5000
```

**3단계: 방화벽 확인**
```bash
sudo firewall-cmd --list-ports
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

**4단계: 서비스 재시작**
```bash
sudo systemctl restart proxmox-manager
```

### 2. 서버 생성 실패

#### 증상
- 서버 생성 시 "Terraform 실행 실패" 오류
- Proxmox에서 VM 생성되지 않음

#### 해결 방법

**1단계: Terraform 상태 확인**
```bash
cd terraform
terraform show
terraform plan
```

**2단계: Proxmox 연결 확인**
```bash
curl -k https://your-proxmox-server:8006/api2/json/version
```

**3단계: 인증 정보 확인**
```bash
docker exec vault-dev vault kv get secret/proxmox
```

**4단계: 로그 확인**
```bash
tail -f logs/proxmox_manager.log | grep -i terraform
```

### 3. 모니터링 시스템 오류

#### 증상
- Grafana 대시보드에 데이터가 표시되지 않음
- Prometheus에서 메트릭을 수집하지 못함

#### 해결 방법

**1단계: 컨테이너 상태 확인**
```bash
cd monitoring
docker-compose ps
```

**2단계: Prometheus 설정 확인**
```bash
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

**3단계: Node Exporter 연결 확인**
```bash
curl http://server-ip:9100/metrics
```

**4단계: 컨테이너 재시작**
```bash
docker-compose restart
```

## 🔧 일반적인 문제 해결

### 1. 권한 관련 문제

#### 증상
- "Permission denied" 오류
- 파일 생성/수정 불가

#### 해결 방법

**파일 권한 수정**
```bash
sudo chown -R $USER:$USER /data/terraform-proxmox
sudo chmod -R 755 /data/terraform-proxmox
```

**데이터베이스 권한 수정**
```bash
sudo chown $USER:$USER instance/proxmox_manager.db
sudo chmod 664 instance/proxmox_manager.db
```

**로그 디렉토리 권한 수정**
```bash
sudo chown -R $USER:$USER logs/
sudo chmod -R 755 logs/
```

### 2. 데이터베이스 문제

#### 증상
- "unable to open database file" 오류
- 데이터베이스 연결 실패

#### 해결 방법

**1단계: 데이터베이스 파일 확인**
```bash
ls -la instance/proxmox_manager.db
```

**2단계: 디렉토리 생성**
```bash
mkdir -p instance
chmod 755 instance
```

**3단계: 데이터베이스 초기화**
```bash
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Database initialized successfully')
"
```

**4단계: 데이터베이스 복구**
```bash
sqlite3 instance/proxmox_manager.db ".recover" | sqlite3 instance/proxmox_manager_recovered.db
mv instance/proxmox_manager_recovered.db instance/proxmox_manager.db
```

### 3. Docker 관련 문제

#### 증상
- Docker 컨테이너 시작 실패
- "Cannot connect to the Docker daemon" 오류

#### 해결 방법

**1단계: Docker 서비스 확인**
```bash
sudo systemctl status docker
sudo systemctl start docker
```

**2단계: Docker 권한 확인**
```bash
sudo usermod -aG docker $USER
# 로그아웃 후 재로그인 필요
```

**3단계: 컨테이너 정리**
```bash
docker system prune -a
docker volume prune
```

**4단계: 네트워크 재설정**
```bash
docker network prune
docker-compose down
docker-compose up -d
```

### 4. Vault 관련 문제

#### 증상
- Vault 초기화 실패
- "Vault is sealed" 오류

#### 해결 방법

**1단계: Vault 상태 확인**
```bash
docker exec vault-dev vault status
```

**2단계: Vault 언실**
```bash
./scripts/vault.sh unseal
```

**3단계: Vault 재초기화**
```bash
docker-compose -f docker-compose.vault.yaml down
docker volume rm terraform-proxmox_vault_data
docker-compose -f docker-compose.vault.yaml up -d
./scripts/vault.sh init
```

**4단계: 토큰 확인**
```bash
docker exec vault-dev vault auth -method=token token=your-token
```

### 5. Ansible 관련 문제

#### 증상
- Ansible 플레이북 실행 실패
- SSH 연결 오류

#### 해결 방법

**1단계: SSH 연결 테스트**
```bash
ssh -o StrictHostKeyChecking=no rocky@server-ip
```

**2단계: Ansible 설정 확인**
```bash
ansible-config dump --only-changed
```

**3단계: 인벤토리 확인**
```bash
ansible-inventory --list
```

**4단계: 플레이북 테스트**
```bash
ansible-playbook --check --diff ansible/role_playbook.yml
```

### 6. 네트워크 관련 문제

#### 증상
- 서버 간 통신 실패
- 포트 연결 불가

#### 해결 방법

**1단계: 네트워크 연결 확인**
```bash
ping -c 4 target-server-ip
telnet target-server-ip port
```

**2단계: 방화벽 확인**
```bash
sudo firewall-cmd --list-all
sudo firewall-cmd --permanent --add-port=port/tcp
sudo firewall-cmd --reload
```

**3단계: 라우팅 확인**
```bash
ip route show
traceroute target-server-ip
```

**4단계: DNS 확인**
```bash
nslookup target-server-ip
dig target-server-ip
```

## 🔍 진단 도구

### 1. 시스템 상태 진단

```bash
# 전체 시스템 상태 확인
./scripts/system_health_check.sh

# 리소스 사용량 확인
./scripts/resource_monitor.sh

# 서비스 상태 확인
./scripts/service_status.sh
```

### 2. 로그 분석

```bash
# 오류 로그 분석
grep -i error logs/proxmox_manager.log | tail -20

# 성능 로그 분석
grep -i "slow\|timeout" logs/proxmox_manager.log

# 접속 로그 분석
grep "GET\|POST" logs/proxmox_manager.log | awk '{print $1}' | sort | uniq -c
```

### 3. 네트워크 진단

```bash
# 포트 스캔
nmap -p 5000,3000,9090,8200 localhost

# 연결 상태 확인
ss -tuln | grep -E ":(5000|3000|9090|8200)"

# 네트워크 인터페이스 확인
ip addr show
```

## 📊 성능 문제 해결

### 1. 느린 응답 시간

#### 원인 분석
- 높은 CPU 사용률
- 메모리 부족
- 디스크 I/O 병목
- 네트워크 지연

#### 해결 방법

**CPU 사용률 최적화**
```bash
# CPU 사용률 확인
top -bn1 | grep "Cpu(s)"

# 프로세스별 CPU 사용률
ps aux --sort=-%cpu | head -10

# 불필요한 프로세스 종료
sudo kill -9 process_id
```

**메모리 최적화**
```bash
# 메모리 사용률 확인
free -h

# 메모리 사용량이 높은 프로세스
ps aux --sort=-%mem | head -10

# 캐시 정리
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

**디스크 I/O 최적화**
```bash
# 디스크 I/O 확인
iostat -x 1

# 디스크 사용률 확인
df -h

# 로그 파일 정리
sudo find /var/log -name "*.log" -type f -mtime +30 -delete
```

### 2. 메모리 부족

#### 증상
- "Out of memory" 오류
- 시스템 응답 지연
- 프로세스 강제 종료

#### 해결 방법

**1단계: 메모리 사용량 확인**
```bash
free -h
cat /proc/meminfo
```

**2단계: 스왑 메모리 확인**
```bash
swapon -s
cat /proc/swaps
```

**3단계: 스왑 메모리 생성**
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**4단계: 스왑 메모리 영구 설정**
```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. 디스크 공간 부족

#### 증상
- "No space left on device" 오류
- 파일 생성 실패

#### 해결 방법

**1단계: 디스크 사용량 확인**
```bash
df -h
du -sh /* | sort -hr
```

**2단계: 대용량 파일 찾기**
```bash
find / -type f -size +100M 2>/dev/null | head -10
```

**3단계: 로그 파일 정리**
```bash
sudo find /var/log -name "*.log" -type f -mtime +7 -delete
sudo find /var/log -name "*.gz" -type f -mtime +30 -delete
```

**4단계: Docker 정리**
```bash
docker system prune -a
docker volume prune
```

## 🔐 보안 문제 해결

### 1. 인증 실패

#### 증상
- 로그인 실패
- "Invalid credentials" 오류

#### 해결 방법

**1단계: 사용자 계정 확인**
```bash
# 사용자 목록 확인
cut -d: -f1 /etc/passwd

# 사용자 그룹 확인
groups username
```

**2단계: 비밀번호 재설정**
```bash
sudo passwd username
```

**3단계: SSH 키 확인**
```bash
ls -la ~/.ssh/
cat ~/.ssh/authorized_keys
```

### 2. 방화벽 문제

#### 증상
- 특정 포트 접속 불가
- 서비스 간 통신 실패

#### 해결 방법

**1단계: 방화벽 상태 확인**
```bash
sudo firewall-cmd --state
sudo firewall-cmd --list-all
```

**2단계: 포트 열기**
```bash
sudo firewall-cmd --permanent --add-port=port/tcp
sudo firewall-cmd --reload
```

**3단계: 서비스 추가**
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 📞 지원 요청

### 1. 문제 보고 시 포함할 정보

- **시스템 정보**: OS 버전, 하드웨어 사양
- **오류 메시지**: 정확한 오류 메시지
- **재현 단계**: 문제를 재현하는 단계
- **로그 파일**: 관련 로그 파일
- **환경 정보**: 설정 파일, 환경 변수

### 2. 로그 수집

```bash
# 시스템 정보 수집
./scripts/collect_system_info.sh

# 로그 파일 수집
./scripts/collect_logs.sh

# 설정 파일 수집
./scripts/collect_configs.sh
```

### 3. 지원 채널

- **GitHub Issues**: [문제 보고](https://github.com/your-org/terraform-proxmox/issues)
- **GitHub Discussions**: [토론 및 질문](https://github.com/your-org/terraform-proxmox/discussions)
- **Discord**: [실시간 채팅](https://discord.gg/your-discord)

## 🔄 복구 절차

### 1. 완전 복구

```bash
# 1. 백업에서 복구
cp instance/proxmox_manager.db.backup instance/proxmox_manager.db

# 2. 설정 파일 복구
cp .env.backup .env

# 3. 서비스 재시작
sudo systemctl restart proxmox-manager

# 4. 상태 확인
curl http://localhost:5000/api/system/status
```

### 2. 부분 복구

```bash
# 1. 특정 서비스만 재시작
sudo systemctl restart proxmox-manager

# 2. 모니터링 시스템만 재시작
cd monitoring && docker-compose restart

# 3. Vault만 재시작
docker-compose -f docker-compose.vault.yaml restart
```

### 3. 재설치

```bash
# 1. 데이터 백업
cp -r instance instance.backup
cp .env .env.backup

# 2. 서비스 중지
sudo systemctl stop proxmox-manager

# 3. 재설치
sudo ./install_complete_system.sh

# 4. 데이터 복구
cp instance.backup/* instance/
cp .env.backup .env

# 5. 서비스 시작
sudo systemctl start proxmox-manager
```

---

문제가 지속되거나 해결되지 않는 경우 [운영 가이드](OPERATION_GUIDE.md)를 참조하거나 지원팀에 문의하세요.
