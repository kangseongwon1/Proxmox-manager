# 설치 가이드

## 📋 개요

이 문서는 Terraform Proxmox Manager의 설치 및 초기 설정 방법을 상세히 설명합니다. 자동 설치 스크립트를 사용하여 모든 구성 요소를 한 번에 설치할 수 있습니다.

## 🛠️ 시스템 요구사항

### 최소 요구사항
- **OS**: Rocky Linux 8+ / CentOS 8+ / RHEL 8+
- **CPU**: 4 Core
- **Memory**: 8GB RAM
- **Storage**: 50GB 여유 공간
- **Network**: 인터넷 연결

### 권장 요구사항
- **OS**: Rocky Linux 9+ / CentOS Stream 9+
- **CPU**: 8 Core
- **Memory**: 16GB RAM
- **Storage**: 100GB SSD
- **Network**: 1Gbps 연결

## 🚀 자동 설치 (권장)

### 1. 저장소 클론

```bash
# 저장소 클론
git clone https://github.com/your-org/terraform-proxmox.git
cd terraform-proxmox

# 실행 권한 부여
chmod +x install_complete_system.sh
```

### 2. 자동 설치 실행

```bash
# 루트 권한으로 설치 실행
sudo ./install_complete_system.sh
```

**설치 과정에서 수행되는 작업**:
- ✅ 시스템 패키지 업데이트
- ✅ Python 3.8+ 설치
- ✅ Docker & Docker Compose 설치
- ✅ Terraform 설치
- ✅ Ansible 설치
- ✅ Git 설치
- ✅ 가상환경 생성 및 의존성 설치
- ✅ Vault 초기화 및 설정
- ✅ 모니터링 시스템 (Prometheus + Grafana) 설정
- ✅ **Redis & Celery 워커 설정**
- ✅ **PostgreSQL 데이터베이스 설정**
- ✅ **SSE 실시간 알림 시스템 설정**
- ✅ 시스템 서비스 등록
- ✅ 데이터베이스 초기화

### 3. 설치 완료 확인

```bash
# 서비스 상태 확인
sudo systemctl status proxmox-manager

# 웹 UI 접속 확인
curl http://localhost:5000

# 모니터링 시스템 확인
curl http://localhost:9090  # Prometheus
curl http://localhost:3000  # Grafana

# Redis & Celery 상태 확인
docker ps | grep redis
ps -aux|grep celery
curl http://localhost:5555  # Celery Flower

# PostgreSQL 상태 확인
docker ps | grep postgres
```

## 🔧 수동 설치

자동 설치가 실패하거나 특정 구성 요소만 설치하려는 경우 수동 설치를 진행할 수 있습니다.

### 1. 시스템 패키지 설치

```bash
# 시스템 업데이트
sudo dnf update -y

# 필수 패키지 설치
sudo dnf install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    unzip \
    jq \
    htop \
    vim \
    net-tools
```

### 2. Docker 설치

```bash
# Docker 저장소 추가
sudo dnf config-manager --add-repo \
    https://download.docker.com/linux/centos/docker-ce.repo

# Docker 설치
sudo dnf install -y docker-ce docker-ce-cli containerd.io

# Docker 서비스 시작 및 자동 시작 설정
sudo systemctl start docker
sudo systemctl enable docker

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
```

### 3. Docker Compose 설치

```bash
# Docker Compose 다운로드
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose

# 실행 권한 부여
sudo chmod +x /usr/local/bin/docker-compose

# 버전 확인
docker-compose --version
```

### 4. Terraform 설치

```bash
# Terraform 다운로드
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip

# 압축 해제
unzip terraform_1.6.0_linux_amd64.zip

# 실행 파일 이동
sudo mv terraform /usr/local/bin/

# 버전 확인
terraform --version
```

### 5. Ansible 설치

```bash
# EPEL 저장소 활성화
sudo dnf install -y epel-release

# Ansible 설치
sudo dnf install -y ansible

# 버전 확인
ansible --version
```

### 6. Python 가상환경 설정

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 의존성 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 7. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# 환경 변수 편집
vim .env
```

**필수 환경 변수**:
```bash
# Flask 설정
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# 데이터베이스 설정 (PostgreSQL)
DATABASE_URL=postgresql://proxmox:your_postgres_password@localhost:5432/proxmox_manager

# Redis & Celery 설정
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
CELERY_BROKER_URL=redis://:your_redis_password@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:your_redis_password@localhost:6379/0

# Proxmox 설정
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=your-username
PROXMOX_PASSWORD=your-password

# Vault 설정
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=your-vault-token
```

### 8. Vault 설정

```bash
# Vault 컨테이너 시작
docker-compose -f docker-compose.vault.yaml up -d

# Vault 초기화
./scripts/vault.sh init

# Vault 언실
./scripts/vault.sh unseal
```

### 9. 모니터링 시스템 설정

```bash
# 모니터링 디렉토리로 이동
cd monitoring

# Docker Compose로 모니터링 시스템 시작
docker-compose up -d

# 상태 확인
docker-compose ps
```

### 10. 시스템 서비스 등록

```bash
# systemd 서비스 파일 생성
sudo tee /etc/systemd/system/proxmox-manager.service > /dev/null <<EOF
[Unit]
Description=Proxmox Manager Flask Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/data/terraform-proxmox
Environment=PATH=/data/terraform-proxmox/venv/bin
ExecStart=/data/terraform-proxmox/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable proxmox-manager
sudo systemctl start proxmox-manager
```

## 🔐 초기 보안 설정

### 1. 방화벽 설정

```bash
# 방화벽 활성화
sudo systemctl enable firewalld
sudo systemctl start firewalld

# 필요한 포트 열기
sudo firewall-cmd --permanent --add-port=5000/tcp  # Flask API
sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
sudo firewall-cmd --permanent --add-port=8200/tcp  # Vault
sudo firewall-cmd --reload
```

### 2. SSH 보안 설정

```bash
# SSH 설정 파일 편집
sudo vim /etc/ssh/sshd_config

# 다음 설정 추가/수정
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
```

### 3. 사용자 계정 설정

```bash
# 관리자 사용자 생성
sudo useradd -m -s /bin/bash admin
sudo usermod -aG wheel admin

# SSH 키 설정
sudo mkdir -p /home/admin/.ssh
sudo cp ~/.ssh/authorized_keys /home/admin/.ssh/
sudo chown -R admin:admin /home/admin/.ssh
sudo chmod 700 /home/admin/.ssh
sudo chmod 600 /home/admin/.ssh/authorized_keys
```

## 📊 설치 후 확인

### 1. 서비스 상태 확인

```bash
# 모든 서비스 상태 확인
sudo systemctl status proxmox-manager
sudo systemctl status docker
docker-compose -f docker-compose.vault.yaml ps
docker-compose -f monitoring/docker-compose.yml ps
```

### 2. 웹 인터페이스 접속

```bash
# 로컬에서 접속 테스트
curl http://localhost:5000

# 브라우저에서 접속
http://your-server-ip:5000
```

### 3. API 엔드포인트 테스트

```bash
# 서버 목록 조회
curl http://localhost:5000/api/servers

# 알림 목록 조회
curl http://localhost:5000/api/notifications

# 모니터링 상태 확인
curl http://localhost:5000/api/monitoring/status
```

### 4. 모니터링 시스템 확인

```bash
# Prometheus 메트릭 확인
curl http://localhost:9090/api/v1/query?query=up

# Grafana 대시보드 접속
# 브라우저에서 http://your-server-ip:3000 접속
```

## 🐛 문제 해결

### 자주 발생하는 문제

#### 1. 권한 오류
```bash
# 파일 권한 수정
sudo chown -R $USER:$USER /data/terraform-proxmox
sudo chmod -R 755 /data/terraform-proxmox
```

#### 2. 포트 충돌
```bash
# 포트 사용 확인
sudo netstat -tlnp | grep :5000
sudo netstat -tlnp | grep :3000
sudo netstat -tlnp | grep :9090

# 프로세스 종료
sudo kill -9 <PID>
```

#### 3. Docker 권한 오류
```bash
# 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 로그아웃 후 재로그인
```

#### 4. Vault 연결 오류
```bash
# Vault 컨테이너 재시작
docker-compose -f docker-compose.vault.yaml restart

# Vault 상태 확인
docker exec vault-dev vault status
```

## 📝 설치 로그

설치 과정에서 생성되는 로그 파일들:

```bash
# 설치 로그
/var/log/proxmox-manager-install.log

# 애플리케이션 로그
/data/terraform-proxmox/logs/proxmox_manager.log

# 시스템 로그
journalctl -u proxmox-manager -f
```

## 🔄 업그레이드

### 1. 백업 생성

```bash
# 데이터베이스 백업
cp instance/proxmox_manager.db instance/proxmox_manager.db.backup

# 설정 파일 백업
cp .env .env.backup
```

### 2. 새 버전 다운로드

```bash
# 현재 버전 백업
mv /data/terraform-proxmox /data/terraform-proxmox.backup

# 새 버전 클론
git clone https://github.com/your-org/terraform-proxmox.git /data/terraform-proxmox
```

### 3. 설정 복원

```bash
# 설정 파일 복원
cp /data/terraform-proxmox.backup/.env /data/terraform-proxmox/
cp /data/terraform-proxmox.backup/instance/proxmox_manager.db /data/terraform-proxmox/instance/
```

### 4. 서비스 재시작

```bash
# 서비스 재시작
sudo systemctl restart proxmox-manager
```

---

설치가 완료되면 [운영 가이드](OPERATION_GUIDE.md)를 참조하여 시스템을 운영하세요.
