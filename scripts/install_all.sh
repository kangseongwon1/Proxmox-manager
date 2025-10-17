#!/bin/bash

# ========================================
# Proxmox 서버 자동 생성 시스템 통합 설치 스크립트
# ========================================
# 이 스크립트는 .env 파일의 변수를 참조하여 모든 구성 요소를 설치합니다.
# 절대 민감한 정보가 하드코딩되지 않습니다.

set -e  # 오류 발생 시 스크립트 중단

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

# .env 파일 확인
check_env_file() {
    if [ ! -f ".env" ]; then
        log_error ".env 파일이 없습니다!"
        log_info "env_template.txt를 .env로 복사한 후 설정하세요:"
        log_info "cp env_template.txt .env"
        log_info "nano .env"
        exit 1
    fi
    
    log_success ".env 파일 확인 완료"
}

# .env 파일 로드
load_env() {
    log_info ".env 파일 로드 중..."
    
    # .env 파일에서 변수 로드 (주석과 빈 줄 제외)
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    
    # 필수 변수 확인
    required_vars=(
        "PROXMOX_ENDPOINT"
        "PROXMOX_USERNAME"
        "PROXMOX_PASSWORD"
        "PROXMOX_NODE"
        "VM_USERNAME"
        "VM_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "필수 환경변수 $var가 설정되지 않았습니다!"
            exit 1
        fi
    done
    
    log_success "환경변수 로드 완료"
}

# 시스템 업데이트
update_system() {
    log_info "시스템 업데이트 중..."
    
    if command -v apt &> /dev/null; then
        sudo apt update && sudo apt upgrade -y
    elif command -v dnf &> /dev/null; then
        sudo dnf update -y
    elif command -v yum &> /dev/null; then
        sudo yum update -y
    else
        log_warning "지원되지 않는 패키지 매니저입니다."
    fi
    
    log_success "시스템 업데이트 완료"
}

# Python 및 pip 설치
install_python() {
    log_info "Python 및 pip 설치 중..."
    
    if command -v python3 &> /dev/null; then
        log_info "Python3 이미 설치됨"
    else
        if command -v apt &> /dev/null; then
            sudo apt install -y python3 python3-pip python3-venv
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3 python3-pip python3-venv
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip
        fi
    fi
    
    log_success "Python 설치 완료"
}

# Node.js 설치 (Grafana용)
install_nodejs() {
    log_info "Node.js 설치 중..."
    
    if command -v node &> /dev/null; then
        log_info "Node.js 이미 설치됨"
    else
        if command -v apt &> /dev/null; then
            curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
            sudo apt install -y nodejs
        elif command -v dnf &> /dev/null; then
            curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
            sudo dnf install -y nodejs
        elif command -v yum &> /dev/null; then
            curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
            sudo yum install -y nodejs
        fi
    fi
    
    log_success "Node.js 설치 완료"
}

# Docker 설치
install_docker() {
    log_info "Docker 설치 중..."
    
    if command -v docker &> /dev/null; then
        log_info "Docker 이미 설치됨"
    else
        if command -v apt &> /dev/null; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y docker
            sudo systemctl enable docker
            sudo systemctl start docker
            sudo usermod -aG docker $USER
        elif command -v yum &> /dev/null; then
            sudo yum install -y docker
            sudo systemctl enable docker
            sudo systemctl start docker
            sudo usermod -aG docker $USER
        fi
    fi
    
    log_success "Docker 설치 완료"
}

# Terraform 설치
install_terraform() {
    log_info "Terraform 설치 중..."
    
    if command -v terraform &> /dev/null; then
        log_info "Terraform 이미 설치됨"
    else
        if command -v apt &> /dev/null; then
            wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
            echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
            sudo apt update && sudo apt install -y terraform
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y dnf-plugins-core
            sudo dnf config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo
            sudo dnf install -y terraform
        elif command -v yum &> /dev/null; then
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo
            sudo yum install -y terraform
        fi
    fi
    
    log_success "Terraform 설치 완료"
}

# Ansible 설치
install_ansible() {
    log_info "Ansible 설치 중..."
    
    if command -v ansible &> /dev/null; then
        log_info "Ansible 이미 설치됨"
    else
        if command -v apt &> /dev/null; then
            sudo apt update
            sudo apt install -y software-properties-common
            sudo apt-add-repository --yes --update ppa:ansible/ansible
            sudo apt install -y ansible
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y ansible
        elif command -v yum &> /dev/null; then
            sudo yum install -y ansible
        fi
    fi
    
    log_success "Ansible 설치 완료"
}

# Vault 설치 (Docker 기반)
install_vault() {
    log_info "HashiCorp Vault Docker 설치 중..."
    
    if command -v docker &> /dev/null; then
        log_info "Docker가 설치되어 있습니다. Vault는 Docker로 실행됩니다."
    else
        log_error "Docker가 설치되지 않았습니다. Vault는 Docker로 실행됩니다."
        exit 1
    fi
    
    log_success "Vault Docker 설치 준비 완료"
}

# Python 가상환경 설정
setup_python_venv() {
    log_info "Python 가상환경 설정 중..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log_success "Python 가상환경 설정 완료"
}

# Vault 설정
setup_vault() {
    log_info "Vault 설정 중..."
    
    # Vault 서버 시작 (백그라운드)
    if [ "${USE_VAULT:-false}" = "true" ]; then
        log_info "Vault 서버 시작 중..."
        
        # 기존 Vault 프로세스 종료
        if [ -f "vault.pid" ]; then
            kill $(cat vault.pid) 2>/dev/null || true
            rm -f vault.pid
        fi
        
        # Vault 서버 시작
        vault server -dev -dev-root-token-id="${VAULT_TOKEN:-root}" &
        VAULT_PID=$!
        echo $VAULT_PID > vault.pid
        
        # Vault 초기화 대기
        sleep 5
        
        # 환경변수 설정
        export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
        export VAULT_TOKEN="${VAULT_TOKEN:-root}"
        
        # KV v2 엔진 활성화
        vault secrets enable -path=secret kv-v2
        
        # 자격증명 저장
        log_info "Vault에 자격증명 저장 중..."
        
        vault kv put secret/proxmox \
            username="${PROXMOX_USERNAME}" \
            password="${PROXMOX_PASSWORD}"
        
        vault kv put secret/vm \
            username="${VM_USERNAME}" \
            password="${VM_PASSWORD}"
        
        if [ -n "${MYSQL_ROOT_PASSWORD:-}" ]; then
            vault kv put secret/mysql \
                root_password="${MYSQL_ROOT_PASSWORD}" \
                user_password="${MYSQL_USER_PASSWORD:-$(openssl rand -base64 24)}"
        fi
        
        if [ -n "${FTP_PASSWORD:-}" ]; then
            vault kv put secret/ftp \
                password="${FTP_PASSWORD}"
        fi
        
        if [ -n "${GRAFANA_PASSWORD:-}" ]; then
            vault kv put secret/grafana \
                username="${GRAFANA_USERNAME:-admin}" \
                password="${GRAFANA_PASSWORD}"
        fi
        
        if [ -n "${PROMETHEUS_PASSWORD:-}" ]; then
            vault kv put secret/prometheus \
                username="${PROMETHEUS_USERNAME:-}" \
                password="${PROMETHEUS_PASSWORD}"
        fi
        
        log_success "Vault 설정 완료"
    else
        log_info "Vault 사용 비활성화됨 (USE_VAULT=false)"
    fi
}

# Grafana 설치 및 설정
setup_grafana() {
    log_info "Grafana 설치 및 설정 중..."
    
    # Grafana 설치
    if ! command -v grafana-server &> /dev/null; then
        sudo apt install -y software-properties-common
        sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
        wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
        sudo apt update
        sudo apt install -y grafana
    fi
    
    # Grafana 서비스 시작
    sudo systemctl enable grafana-server
    sudo systemctl start grafana-server
    
    # Grafana 설정 대기
    sleep 10
    
    # Grafana 데이터소스 설정
    if [ -n "${GRAFANA_URL:-}" ] && [ -n "${PROMETHEUS_URL:-}" ]; then
        log_info "Grafana 데이터소스 설정 중..."
        
        # Prometheus 데이터소스 추가
        curl -X POST \
            -H "Content-Type: application/json" \
            -u "${GRAFANA_USERNAME:-admin}:${GRAFANA_PASSWORD:-admin}" \
            -d "{
                \"name\": \"Prometheus\",
                \"type\": \"prometheus\",
                \"url\": \"${PROMETHEUS_URL}\",
                \"access\": \"proxy\",
                \"isDefault\": true
            }" \
            "${GRAFANA_URL}/api/datasources" || log_warning "Grafana 데이터소스 설정 실패"
    fi
    
    log_success "Grafana 설정 완료"
}

# Prometheus 설치 및 설정
setup_prometheus() {
    log_info "Prometheus 설치 및 설정 중..."
    
    # Prometheus 사용자 생성
    sudo useradd --no-create-home --shell /bin/false prometheus || true
    
    # Prometheus 디렉토리 생성
    sudo mkdir -p /etc/prometheus
    sudo mkdir -p /var/lib/prometheus
    
    # Prometheus 다운로드 및 설치
    if ! command -v prometheus &> /dev/null; then
        wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
        tar xvf prometheus-2.45.0.linux-amd64.tar.gz
        sudo cp prometheus-2.45.0.linux-amd64/prometheus /usr/local/bin/
        sudo cp prometheus-2.45.0.linux-amd64/promtool /usr/local/bin/
        sudo cp -r prometheus-2.45.0.linux-amd64/consoles /etc/prometheus
        sudo cp -r prometheus-2.45.0.linux-amd64/console_libraries /etc/prometheus
        rm -rf prometheus-2.45.0.linux-amd64*
    fi
    
    # Prometheus 설정 파일 생성
    sudo tee /etc/prometheus/prometheus.yml > /dev/null <<EOF
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
    
    # Prometheus 서비스 파일 생성
    sudo tee /etc/systemd/system/prometheus.service > /dev/null <<EOF
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \\
    --config.file /etc/prometheus/prometheus.yml \\
    --storage.tsdb.path /var/lib/prometheus/ \\
    --web.console.templates=/etc/prometheus/consoles \\
    --web.console.libraries=/etc/prometheus/console_libraries \\
    --web.listen-address=0.0.0.0:9090

[Install]
WantedBy=multi-user.target
EOF
    
    # Prometheus 서비스 시작
    sudo chown -R prometheus:prometheus /etc/prometheus
    sudo chown -R prometheus:prometheus /var/lib/prometheus
    sudo systemctl daemon-reload
    sudo systemctl enable prometheus
    sudo systemctl start prometheus
    
    log_success "Prometheus 설정 완료"
}

# Node Exporter 설치
install_node_exporter() {
    log_info "Node Exporter 설치 중..."
    
    if ! command -v node_exporter &> /dev/null; then
        wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
        tar xvf node_exporter-1.6.1.linux-amd64.tar.gz
        sudo cp node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/
        rm -rf node_exporter-1.6.1.linux-amd64*
    fi
    
    # Node Exporter 서비스 파일 생성
    sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF
    
    # Node Exporter 서비스 시작
    sudo systemctl daemon-reload
    sudo systemctl enable node_exporter
    sudo systemctl start node_exporter
    
    log_success "Node Exporter 설치 완료"
}

# SSH 키 설정
setup_ssh_keys() {
    log_info "SSH 키 설정 중..."
    
    if [ ! -f ~/.ssh/id_rsa ]; then
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -C "proxmox-manager"
        log_info "SSH 키가 생성되었습니다."
        log_info "공개키를 Proxmox에 등록하세요:"
        log_info "cat ~/.ssh/id_rsa.pub"
    else
        log_info "SSH 키가 이미 존재합니다."
    fi
    
    log_success "SSH 키 설정 완료"
}

# 데이터베이스 초기화
init_database() {
    log_info "데이터베이스 초기화 중..."
    
    source venv/bin/activate
    python create_tables.py
    
    log_success "데이터베이스 초기화 완료"
}

# Terraform 초기화
init_terraform() {
    log_info "Terraform 초기화 중..."
    
    cd terraform
    terraform init
    cd ..
    
    log_success "Terraform 초기화 완료"
}

# 설치 완료 메시지
show_completion_message() {
    log_success "=========================================="
    log_success "설치가 완료되었습니다!"
    log_success "=========================================="
    
    echo ""
    log_info "설치된 구성 요소:"
    echo "  ✅ Python 및 Flask 애플리케이션"
    echo "  ✅ Terraform"
    echo "  ✅ Ansible"
    echo "  ✅ HashiCorp Vault"
    echo "  ✅ Grafana"
    echo "  ✅ Prometheus"
    echo "  ✅ Node Exporter"
    echo ""
    
    log_info "서비스 상태:"
    echo "  📊 Grafana: http://localhost:3000"
    echo "  📈 Prometheus: http://localhost:9090"
    echo "  🔒 Vault: ${VAULT_ADDR:-http://127.0.0.1:8200}"
    echo ""
    
    log_info "다음 단계:"
    echo "  1. Flask 애플리케이션 시작: python run.py"
    echo "  2. 웹 브라우저에서 http://localhost:5000 접속"
    echo "  3. .env 파일에서 추가 설정 조정"
    echo ""
    
    if [ "${USE_VAULT:-false}" = "true" ]; then
        log_warning "Vault가 개발 모드로 실행 중입니다."
        log_warning "프로덕션 환경에서는 적절한 Vault 설정이 필요합니다."
    fi
}

# 메인 실행 함수
main() {
    log_info "Proxmox 서버 자동 생성 시스템 설치 시작..."
    
    # 필수 확인
    check_env_file
    load_env
    
    # 시스템 업데이트
    update_system
    
    # 패키지 설치
    install_python
    install_nodejs
    install_docker
    install_terraform
    install_ansible
    install_vault
    
    # 설정
    setup_python_venv
    setup_vault
    setup_grafana
    setup_prometheus
    install_node_exporter
    setup_ssh_keys
    
    # 초기화
    init_database
    init_terraform
    
    # 완료 메시지
    show_completion_message
}

# 스크립트 실행
main "$@"
