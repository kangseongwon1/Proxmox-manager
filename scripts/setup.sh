#!/bin/bash

# ========================================
# Proxmox 서버 자동 생성 시스템 설치 스크립트 (보안 강화 버전)
# ========================================
# 이 스크립트는 .env 파일의 변수를 참조하여 설치합니다.
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
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
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

# SSH 키 설정
setup_ssh_keys() {
    log_info "SSH 키 설정 중..."
    
    if [ ! -f ~/.ssh/id_rsa ]; then
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -C "proxmox-manager"
        log_info "SSH 키가 생성되었습니다."
        log_info "공개키를 Proxmox에 등록하세요:"
        log_info "cat ~/.ssh/id_rsa.pub"
        log_info ""
        log_info "Proxmox 웹 UI에서:"
        log_info "   # Proxmox 웹 UI → Datacenter → SSH Keys"
        log_info "   # 공개키 내용을 복사하여 등록"
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
    echo ""
    
    log_info "다음 단계:"
    echo "  1. Flask 애플리케이션 시작: python run.py"
    echo "  2. 웹 브라우저에서 http://localhost:5000 접속"
    echo "  3. .env 파일에서 추가 설정 조정"
    echo ""
    
    log_info "추가 설치 옵션:"
    echo "  - 모니터링 시스템: ./install_all.sh (Grafana, Prometheus 포함)"
    echo "  - Vault만 설정: ./vault_setup.sh"
    echo ""
    
    log_warning "SSH 키를 Proxmox에 등록하는 것을 잊지 마세요!"
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
    install_terraform
    install_ansible
    
    # 설정
    setup_python_venv
    setup_ssh_keys
    
    # 초기화
    init_database
    init_terraform
    
    # 완료 메시지
    show_completion_message
}

# 스크립트 실행
main "$@"