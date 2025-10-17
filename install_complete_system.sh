#!/bin/bash

# ========================================
# Proxmox Manager 완전 통합 설치 스크립트
# ========================================
# 이 스크립트는 다음을 모두 자동으로 설치하고 설정합니다:
# - Python, pip, Node.js
# - Docker, Docker Compose
# - Terraform, Ansible
# - Vault (Docker)
# - Grafana, Prometheus, Node Exporter
# - Flask 애플리케이션
# - 모든 환경변수 설정
# - 데이터베이스 초기화
# - 보안 설정

set -e  # 오류 발생 시 스크립트 중단

# 스크립트 위치 기반으로 작업 디렉토리 설정 (환경 독립적)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 작업 디렉토리 확인 로그
echo "🔧 작업 디렉토리 설정: $(pwd)"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 로그 함수들
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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# ========================================
# 0. 사전 검증
# ========================================

pre_validation() {
    log_step "0. 사전 검증 중..."
    
    # 필수 파일 확인
    REQUIRED_FILES=(
        "requirements.txt"
        "scripts/vault.sh"
        "docker-compose.vault.yaml"
        "config/vault-dev.hcl"
        "scripts/create_tables.py"
        "monitoring/update_prometheus_targets.py"
    )
    
    MISSING_FILES=()
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            MISSING_FILES+=("$file")
        fi
    done
    
    if [ ${#MISSING_FILES[@]} -gt 0 ]; then
        log_error "❌ 필수 파일이 누락되었습니다:"
        for file in "${MISSING_FILES[@]}"; do
            log_error "   - $file"
        done
        log_error ""
        log_error "모든 필수 파일이 있는지 확인하고 다시 실행하세요."
        exit 1
    fi
    
    # .env 파일이 이미 존재하는 경우 검증
    if [ -f ".env" ]; then
        log_info "기존 .env 파일 발견. 내용을 검증합니다..."
        source .env
        
        # 필수 변수 확인
        if [ -z "$PROXMOX_ENDPOINT" ] || [ -z "$PROXMOX_USERNAME" ] || [ -z "$PROXMOX_PASSWORD" ] || \
           [ "$PROXMOX_ENDPOINT" = "your_proxmox_endpoint" ] || \
           [ "$PROXMOX_USERNAME" = "your_proxmox_username" ] || \
           [ "$PROXMOX_PASSWORD" = "your_proxmox_password" ]; then
            log_warning "⚠️  .env 파일에 기본값이 있습니다. 대화형으로 설정하시겠습니까? (y/n)"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                log_info "기존 .env 파일을 백업합니다..."
                cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
                rm .env
            else
                log_error "❌ .env 파일의 필수 정보를 수정한 후 다시 실행하세요."
                exit 1
            fi
        else
            log_success "기존 .env 파일이 올바르게 설정되어 있습니다."
        fi
    fi
    
    log_success "사전 검증 완료"
}

# ========================================
# 1. 시스템 정보 확인 및 준비
# ========================================

check_system() {
    log_step "1. 시스템 정보 확인 중..."
    
    # OS 확인
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
        log_info "OS: $OS $VERSION"
    else
        log_error "OS 정보를 확인할 수 없습니다"
        exit 1
    fi
    
    # 패키지 매니저 확인
    if command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
    elif command -v apt &> /dev/null; then
        PKG_MANAGER="apt"
    else
        log_error "지원되지 않는 패키지 매니저입니다"
        exit 1
    fi
    
    log_info "패키지 매니저: $PKG_MANAGER"
    
    # sudo 권한 확인
    if ! sudo -n true 2>/dev/null; then
        log_warning "sudo 권한이 필요합니다. 설치 중에 비밀번호를 입력해주세요."
    fi
    
    log_success "시스템 정보 확인 완료"
}

# ========================================
# 2. 필수 패키지 설치
# ========================================

install_essential_packages() {
    log_step "2. 필수 패키지 설치 중..."
    
    # 공통 필수 패키지
    ESSENTIAL_PACKAGES="curl wget git unzip tar gcc gcc-c++ make"
    
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        # RedHat 계열 (Rocky, CentOS, RHEL)
        log_info "RedHat 계열 패키지 설치 중..."
        sudo $PKG_MANAGER update -y
        sudo $PKG_MANAGER groupinstall -y "Development Tools"
        sudo $PKG_MANAGER install -y $ESSENTIAL_PACKAGES python3 python3-pip python3-devel openssl-devel libffi-devel
    elif [ "$PKG_MANAGER" = "apt" ]; then
        # Debian 계열 (Ubuntu, Debian)
        log_info "Debian 계열 패키지 설치 중..."
        sudo apt update
        sudo apt install -y build-essential $ESSENTIAL_PACKAGES python3 python3-pip python3-dev libssl-dev libffi-dev
    fi
    
    log_success "필수 패키지 설치 완료"
}

# ========================================
# 3. Python 환경 설정
# ========================================

setup_python() {
    log_step "3. Python 3.12 설치 및 환경 설정 중..."
    
    # 현재 Python 버전 확인
    CURRENT_PYTHON=$(python3 --version 2>&1 | awk '{print $2}')
    log_info "현재 Python 버전: $CURRENT_PYTHON"
    
    # Python 3.12 설치 확인
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_info "Python 3.12 이미 설치됨: $PYTHON312_VERSION"
    else
        log_info "Python 3.12 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
    # RedHat 계열에서 Python 3.12 설치 (소스 빌드 방식)
    log_info "RedHat 계열에서 Python 3.12 소스 빌드 설치 중..."
    
    # 사용자 계정으로 설치 시도
    log_info "사용자 계정으로 Python 3.12 설치 시도 중..."
    install_python312_from_source
    
    # 설치 실패 시 sudo 권한으로 재시도
    if [ $? -ne 0 ]; then
        log_warning "사용자 계정 설치 실패, sudo 권한으로 재시도..."
        install_python312_from_source_sudo
    fi
            
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # Debian 계열에서 Python 3.12 설치
            log_info "Debian 계열에서 Python 3.12 설치 중..."
            
            # deadsnakes PPA 추가 (Ubuntu)
            sudo apt update
            sudo apt install -y software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa
            sudo apt update
            sudo apt install -y python3.12 python3.12-pip python3.12-venv python3.12-dev
            
            if [ $? -eq 0 ]; then
                log_success "Python 3.12 설치 완료"
            else
                log_warning "패키지 매니저로 Python 3.12 설치 실패, 소스에서 빌드 시도..."
                install_python312_from_source
            fi
        fi
    fi
    
    # Python 3.12 확인
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_success "Python 3.12 사용 가능: $PYTHON312_VERSION"
    else
        log_error "Python 3.12 설치 실패"
        exit 1
    fi
    
    # 가상환경 생성 (Python 3.12 사용)
    # 재설치 시에도 문제없이 작동하도록 기존 가상환경 정리
    if [ -d "venv" ]; then
        log_info "기존 가상환경 정리 중..."
        rm -rf venv
    fi
    
    log_info "Python 3.12로 가상환경 생성 중..."
    
    # Python 경로 확인 (python 명령어 우선, 없으면 python3.12)
    if command -v python &> /dev/null; then
        PYTHON_PATH=$(which python)
        PYTHON_VERSION=$(python --version 2>&1)
        log_info "Python 경로: $PYTHON_PATH"
        log_info "Python 버전: $PYTHON_VERSION"
        
        # Python 3.12인지 확인
        if [[ "$PYTHON_VERSION" == *"3.12"* ]]; then
            python -m venv venv
        else
            log_warning "python 명령어가 Python 3.12가 아닙니다: $PYTHON_VERSION"
            if command -v python3.12 &> /dev/null; then
                PYTHON_PATH=$(which python3.12)
                log_info "Python 3.12 경로로 재시도: $PYTHON_PATH"
                python3.12 -m venv venv
            else
                log_error "Python 3.12를 찾을 수 없습니다"
                exit 1
            fi
        fi
    elif command -v python3.12 &> /dev/null; then
        PYTHON_PATH=$(which python3.12)
        log_info "Python 3.12 경로: $PYTHON_PATH"
        python3.12 -m venv venv
    else
        log_error "Python을 찾을 수 없습니다"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        log_success "가상환경 생성 완료"
        
        # 가상환경 생성 후 권한 확인 및 수정
        log_info "가상환경 파일 권한 확인 중..."
        if [ -f "venv/bin/python" ]; then
            # Python 실행 파일 권한 확인
            CURRENT_PERMS=$(ls -l venv/bin/python | awk '{print $1}')
            log_info "Python 파일 권한: $CURRENT_PERMS"
            
            if [[ ! "$CURRENT_PERMS" =~ x ]]; then
                log_info "실행 권한이 없습니다. 권한 설정 중..."
                chmod +x venv/bin/python
                if [ $? -eq 0 ]; then
                    log_success "Python 파일 실행 권한 설정 완료"
                else
                    log_warning "Python 파일 권한 설정 실패"
                fi
            else
                log_success "Python 파일에 이미 실행 권한이 있습니다"
            fi
            
            # pip 실행 파일 권한도 확인
            if [ -f "venv/bin/pip" ]; then
                chmod +x venv/bin/pip 2>/dev/null || log_warning "pip 권한 설정 실패"
            fi
        else
            log_error "가상환경 Python 파일을 찾을 수 없습니다"
            exit 1
        fi
    else
        log_error "가상환경 생성 실패"
        exit 1
    fi
    
    # 가상환경 활성화
    log_info "가상환경 활성화 중..."
    source venv/bin/activate
    
    # 가상환경에서 Python 버전 확인
    if command -v python &> /dev/null; then
        VENV_PYTHON_VERSION=$(python --version 2>&1)
        log_info "가상환경 Python 버전: $VENV_PYTHON_VERSION"
        
        if [[ "$VENV_PYTHON_VERSION" == *"3.12"* ]]; then
            log_success "가상환경이 Python 3.12를 사용합니다"
        else
            log_warning "가상환경이 Python 3.12가 아닙니다: $VENV_PYTHON_VERSION"
        fi
    else
        log_error "가상환경에서 python 명령어를 찾을 수 없습니다"
        exit 1
    fi
    
    # pip 업그레이드
    log_info "pip 업그레이드 중..."
    
    # 가상환경에서 Python 명령어 확인
    if command -v python &> /dev/null; then
        python -m pip install --upgrade pip
    elif command -v python3 &> /dev/null; then
        python3 -m pip install --upgrade pip
    elif command -v python3.12 &> /dev/null; then
        python3.12 -m pip install --upgrade pip
    else
        log_error "Python 명령어를 찾을 수 없습니다"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        log_success "pip 업그레이드 완료"
    else
        log_warning "pip 업그레이드 실패 (계속 진행)"
    fi
    
    # 가상환경 활성화 및 Python 패키지 설치
    log_info "가상환경 활성화 중..."
    source venv/bin/activate
    
    # 가상환경 활성화 확인
    if [[ "$VIRTUAL_ENV" != *"venv"* ]]; then
        log_error "가상환경 활성화 실패"
        exit 1
    fi
    
    log_info "가상환경 활성화 완료: $VIRTUAL_ENV"
    log_info "Python 경로: $(which python)"
    log_info "pip 경로: $(which pip)"
    
    # Python 패키지 설치
    log_info "Python 패키지 설치 중..."
    
    # 작업 디렉토리 재확인 및 설정 (전역 SCRIPT_DIR 사용)
    cd "$SCRIPT_DIR"
    log_info "작업 디렉토리 재설정: $(pwd)"
    log_info "requirements.txt 파일 확인: $(ls -la requirements.txt 2>/dev/null || echo '파일 없음')"
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        log_success "Python 패키지 설치 완료"
        
        # 설치된 패키지 확인
        log_info "설치된 패키지 확인 중..."
        pip list | grep -E "(dotenv|flask|requests)" || log_warning "일부 패키지가 설치되지 않았을 수 있습니다"
        
        # 필수 패키지 개별 확인
        log_info "필수 패키지 개별 확인 중..."
        python -c "import dotenv; print('✅ python-dotenv 설치됨')" 2>/dev/null || log_warning "❌ python-dotenv 누락"
        python -c "import flask; print('✅ flask 설치됨')" 2>/dev/null || log_warning "❌ flask 누락"
        python -c "import requests; print('✅ requests 설치됨')" 2>/dev/null || log_warning "❌ requests 누락"
    else
        log_error "Python 패키지 설치 실패"
        log_info "수동으로 필수 패키지를 설치합니다..."
        
        # 필수 패키지 수동 설치
        pip install python-dotenv flask flask-sqlalchemy flask-login requests pyyaml cryptography hvac
        
        if [ $? -eq 0 ]; then
            log_success "필수 패키지 수동 설치 완료"
        else
            log_error "필수 패키지 설치 실패"
            exit 1
        fi
    fi
    
    log_success "Python 3.12 환경 설정 완료"
}

install_python312_from_source() {
    log_info "소스에서 Python 3.12 빌드 중..."
    
    # 빌드 도구 설치
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        log_info "빌드 도구 설치 중..."
        sudo $PKG_MANAGER groupinstall -y "Development Tools"
        sudo $PKG_MANAGER install -y openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel wget gcc gcc-c++ make
    elif [ "$PKG_MANAGER" = "apt" ]; then
        sudo apt install -y build-essential libssl-dev libbz2-dev libffi-dev zlib1g-dev libreadline-dev libsqlite3-dev wget
    fi
    
    # 사용자 홈 디렉토리에 Python 설치
    PYTHON_INSTALL_DIR="$HOME/python3.12"
    PYTHON_BUILD_DIR="$HOME/python-build"
    
    log_info "Python 3.12.7 다운로드 중..."
    mkdir -p "$PYTHON_BUILD_DIR"
    cd "$PYTHON_BUILD_DIR"
    
    if [ ! -f "Python-3.12.7.tgz" ]; then
        wget https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz
        
        if [ $? -eq 0 ]; then
            log_success "Python 3.12.7 다운로드 완료"
        else
            log_error "Python 3.12.7 다운로드 실패"
            exit 1
        fi
    else
        log_info "Python 3.12.7 이미 다운로드됨"
    fi
    
    log_info "압축 해제 중..."
    tar xzf Python-3.12.7.tgz
    cd Python-3.12.7
    
    log_info "컨피규어 실행 중..."
    # Rocky 9에서 Python 3.12 빌드 시 발생하는 경고 해결
    export CFLAGS="-Wno-stringop-overflow"
    export CPPFLAGS="-Wno-stringop-overflow"
    ./configure --enable-optimizations --prefix="$PYTHON_INSTALL_DIR"
    
    if [ $? -eq 0 ]; then
        log_success "컨피규어 완료"
    else
        log_error "컨피규어 실패"
        exit 1
    fi
    
    log_info "컴파일 중... (시간이 걸릴 수 있습니다)"
    make -j $(nproc)
    
    if [ $? -eq 0 ]; then
        log_success "컴파일 완료"
    else
        log_error "컴파일 실패"
        exit 1
    fi
    
    log_info "설치 중..."
    make install
    
    if [ $? -eq 0 ]; then
        log_success "Python 3.12 소스 빌드 및 설치 완료"
    else
        log_error "Python 3.12 설치 실패"
        exit 1
    fi
    
    # PATH에 Python 3.12 추가
    log_info "PATH 설정 중..."
    echo "export PATH=\"$PYTHON_INSTALL_DIR/bin:\$PATH\"" >> ~/.bashrc
    export PATH="$PYTHON_INSTALL_DIR/bin:$PATH"
    
    # python 심볼릭 링크 생성 (python3.12 -> python)
    log_info "python 심볼릭 링크 생성 중..."
    ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python"
    ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python3"
    
    # 정리 (권한 문제 해결)
    log_info "빌드 파일 정리 중..."
    cd "$HOME"
    rm -rf "$PYTHON_BUILD_DIR"
    
    log_info "Python 3.12 설치 확인 중..."
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_success "Python 3.12 설치 확인: $PYTHON312_VERSION"
        log_info "Python 3.12 경로: $(which python3.12)"
        
        # python 명령어 확인
        if command -v python &> /dev/null; then
            log_success "python 명령어 사용 가능: $(which python)"
        else
            log_warning "python 명령어를 찾을 수 없습니다"
        fi
    else
        log_error "Python 3.12 설치 확인 실패"
        exit 1
    fi
}

install_python312_from_source_sudo() {
    log_info "sudo 권한으로 Python 3.12 소스 빌드 중..."
    
    # 빌드 도구 설치
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        log_info "빌드 도구 설치 중..."
        sudo $PKG_MANAGER groupinstall -y "Development Tools"
        sudo $PKG_MANAGER install -y openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel wget gcc gcc-c++ make
    elif [ "$PKG_MANAGER" = "apt" ]; then
        sudo apt install -y build-essential libssl-dev libbz2-dev libffi-dev zlib1g-dev libreadline-dev libsqlite3-dev wget
    fi
    
    # /tmp 대신 사용자 홈 디렉토리 사용
    PYTHON_BUILD_DIR="$HOME/python-build"
    PYTHON_INSTALL_DIR="/usr/local"
    
    log_info "Python 3.12.7 다운로드 중..."
    mkdir -p "$PYTHON_BUILD_DIR"
    cd "$PYTHON_BUILD_DIR"
    
    if [ ! -f "Python-3.12.7.tgz" ]; then
        wget https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz
        
        if [ $? -eq 0 ]; then
            log_success "Python 3.12.7 다운로드 완료"
        else
            log_error "Python 3.12.7 다운로드 실패"
            exit 1
        fi
    else
        log_info "Python 3.12.7 이미 다운로드됨"
    fi
    
    log_info "압축 해제 중..."
    tar xzf Python-3.12.7.tgz
    cd Python-3.12.7
    
    log_info "컨피규어 실행 중..."
    # Rocky 9에서 Python 3.12 빌드 시 발생하는 경고 해결
    export CFLAGS="-Wno-stringop-overflow"
    export CPPFLAGS="-Wno-stringop-overflow"
    ./configure --enable-optimizations --prefix="$PYTHON_INSTALL_DIR"
    
    if [ $? -eq 0 ]; then
        log_success "컨피규어 완료"
    else
        log_error "컨피규어 실패"
        exit 1
    fi
    
    log_info "컴파일 중... (시간이 걸릴 수 있습니다)"
    make -j $(nproc)
    
    if [ $? -eq 0 ]; then
        log_success "컴파일 완료"
    else
        log_error "컴파일 실패"
        exit 1
    fi
    
    log_info "설치 중..."
    sudo make altinstall
    
    if [ $? -eq 0 ]; then
        log_success "Python 3.12 소스 빌드 및 설치 완료"
    else
        log_error "Python 3.12 설치 실패"
        exit 1
    fi
    
    # python 심볼릭 링크 생성 (python3.12 -> python)
    log_info "python 심볼릭 링크 생성 중..."
    sudo ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python"
    sudo ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python3"
    
    # 정리 (권한 문제 해결)
    log_info "빌드 파일 정리 중..."
    cd "$HOME"
    sudo rm -rf "$PYTHON_BUILD_DIR"
    
    log_info "Python 3.12 설치 확인 중..."
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_success "Python 3.12 설치 확인: $PYTHON312_VERSION"
        log_info "Python 3.12 경로: $(which python3.12)"
        
        # python 명령어 확인
        if command -v python &> /dev/null; then
            log_success "python 명령어 사용 가능: $(which python)"
        else
            log_warning "python 명령어를 찾을 수 없습니다"
        fi
    else
        log_error "Python 3.12 설치 확인 실패"
        exit 1
    fi
}

# ========================================
# 4. Node.js 설치
# ========================================

install_nodejs() {
    log_step "4. Node.js 설치 중..."
    
    # Node.js 설치 확인 및 재설치 지원
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        NODE_MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'.' -f1 | sed 's/v//')
        
        # Node.js 18 이하인 경우 재설치 (20+ 권장)
        if [ "$NODE_MAJOR_VERSION" -lt 20 ]; then
            log_info "Node.js $NODE_VERSION 감지, 20 LTS로 업그레이드 중..."
        else
            log_info "Node.js 이미 설치됨: $NODE_VERSION"
        fi
    else
        log_info "Node.js 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo $PKG_MANAGER install -y nodejs
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt install -y nodejs
        fi
    fi
    
    # Node.js 18 이하인 경우 재설치
    if [ "$NODE_MAJOR_VERSION" -lt 20 ]; then
        log_info "Node.js 20 LTS로 재설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # 기존 Node.js 제거
            sudo $PKG_MANAGER remove -y nodejs npm
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo $PKG_MANAGER install -y nodejs
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # 기존 Node.js 제거
            sudo apt remove -y nodejs npm
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt install -y nodejs
        fi
        
        NODE_VERSION=$(node --version)
        log_info "Node.js 설치 완료: $NODE_VERSION"
    fi
    
    # npm 버전 확인 및 업그레이드
    NPM_VERSION=$(npm --version)
    log_info "현재 npm 버전: $NPM_VERSION"
    
    # Node.js 버전에 따른 npm 업그레이드
    NODE_MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'.' -f1 | sed 's/v//')
    
    if [ "$NODE_MAJOR_VERSION" -ge 20 ]; then
        log_info "Node.js 20+ 감지, npm 최신 버전으로 업그레이드 중..."
        sudo npm install -g npm@latest
    else
        log_info "Node.js 18 감지, 호환되는 npm 버전으로 업그레이드 중..."
        sudo npm install -g npm@10
    fi
    
    # 업그레이드 후 npm 버전 확인
    NEW_NPM_VERSION=$(npm --version)
    log_info "업그레이드된 npm 버전: $NEW_NPM_VERSION"
    
    log_success "Node.js 설치 완료"
}

# ========================================
# 5. Docker 설치
# ========================================

install_docker() {
    log_step "5. Docker 설치 중..."
    
    # Docker 설치 확인
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        log_info "Docker 이미 설치됨: $DOCKER_VERSION"
    else
        log_info "Docker 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # Docker 저장소 추가
            sudo $PKG_MANAGER config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo $PKG_MANAGER install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # Docker 저장소 추가
            sudo apt update
            sudo apt install -y ca-certificates curl gnupg lsb-release
            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt update
            sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        fi
        
        # Docker 서비스 시작 및 활성화
        sudo systemctl start docker
        sudo systemctl enable docker
        
        # 현재 사용자를 docker 그룹에 추가
        sudo usermod -aG docker $USER
        
        DOCKER_VERSION=$(docker --version)
        log_info "Docker 설치 완료: $DOCKER_VERSION"
        
        # Docker 권한 확인 및 수정
        log_info "Docker 권한 확인 중..."
        if ! docker ps &> /dev/null; then
            log_warning "Docker 권한 문제 감지. Docker 소켓 권한 수정 중..."
            
            # Docker 소켓 소유자 변경
            sudo chown $USER:docker /var/run/docker.sock
            sudo chmod 660 /var/run/docker.sock
            
            # 현재 사용자를 docker 그룹에 추가
            sudo usermod -aG docker $USER
            
            log_warning "⚠️  Docker 그룹 권한이 변경되었습니다."
            log_warning "⚠️  다음 중 하나를 선택하세요:"
            log_warning "   1. 새 터미널 세션을 시작하거나"
            log_warning "   2. 'newgrp docker' 명령어를 실행하거나"
            log_warning "   3. 로그아웃 후 다시 로그인하세요"
            log_warning ""
            log_warning "그 후 다시 이 스크립트를 실행하세요."
            
            # newgrp docker 실행 시도
            log_info "newgrp docker 실행 중..."
            newgrp docker << 'EOF'
echo "Docker 그룹 권한이 적용되었습니다."
docker ps
EOF
            
            # 권한 재확인
            if docker ps &> /dev/null; then
                log_success "Docker 권한 문제 해결됨"
            else
                log_warning "Docker 권한 문제가 지속됩니다."
                log_warning "설치 완료 후 다음 중 하나를 실행하세요:"
                log_warning "  1. 새 터미널 세션 시작"
                log_warning "  2. 또는 'newgrp docker' 실행"
                log_warning "  3. 또는 로그아웃 후 재로그인"
            fi
        else
            log_success "Docker 권한 확인 완료"
        fi
    fi
    
    # Docker Compose 설치 및 확인
    log_info "Docker Compose 설치 확인 중..."
    
    # docker-compose 명령어 확인
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version)
        log_info "Docker Compose 이미 설치됨: $COMPOSE_VERSION"
    else
        log_info "Docker Compose 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # Rocky 8에서 Docker Compose 설치
            log_info "Rocky 8에서 Docker Compose 바이너리 직접 설치 중..."
            
            # EPEL 설치 (다른 패키지용)
            sudo $PKG_MANAGER install -y epel-release
            
            # 바이너리 직접 설치 (Rocky 8에서 권장 방법)
            log_info "최신 Docker Compose 바이너리 다운로드 중..."
            
            # 최신 Docker Compose 다운로드
            COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)
            COMPOSE_VERSION=${COMPOSE_VERSION#v}  # v 제거
            
            log_info "Docker Compose 버전: $COMPOSE_VERSION"
            
            # 아키텍처 확인
            ARCH=$(uname -m)
            case $ARCH in
                x86_64) ARCH="x86_64" ;;
                aarch64) ARCH="aarch64" ;;
                *) log_error "지원되지 않는 아키텍처: $ARCH"; exit 1 ;;
            esac
            
            # 바이너리 다운로드 및 설치
            sudo curl -L "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-$(uname -s)-${ARCH}" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            
            log_success "Docker Compose 바이너리 설치 완료"
            
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # Ubuntu/Debian에서 Docker Compose 설치
            sudo apt install -y docker-compose
        fi
        
        # 설치 확인
        if command -v docker-compose &> /dev/null; then
            COMPOSE_VERSION=$(docker-compose --version)
            log_success "Docker Compose 설치 완료: $COMPOSE_VERSION"
        else
            log_error "Docker Compose 설치 실패"
            log_info "수동 설치 방법:"
            log_info "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
            log_info "  sudo chmod +x /usr/local/bin/docker-compose"
        fi
    fi
    
    log_success "Docker 설치 완료"
}

# ========================================
# 6. Terraform 설치
# ========================================

install_terraform() {
    log_step "6. Terraform 설치 중..."
    
    # Terraform 설치 확인 및 재설치 지원
    if command -v terraform &> /dev/null; then
        TERRAFORM_VERSION=$(terraform --version | head -n1)
        log_info "Terraform 이미 설치됨: $TERRAFORM_VERSION"
        log_info "Terraform 재설치를 위해 기존 설치 제거 중..."
        
        # 기존 Terraform 제거
        sudo rm -f /usr/local/bin/terraform
    fi
    
    log_info "Terraform 설치 중..."
    
    # 최신 버전 다운로드
    TERRAFORM_VERSION=$(curl -s https://api.github.com/repos/hashicorp/terraform/releases/latest | grep tag_name | cut -d '"' -f 4)
    TERRAFORM_VERSION=${TERRAFORM_VERSION#v}  # v 제거
    
    # 아키텍처 확인
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) ARCH="amd64" ;;
        aarch64) ARCH="arm64" ;;
        *) log_error "지원되지 않는 아키텍처: $ARCH"; exit 1 ;;
    esac
    
    # 임시 디렉토리에서 다운로드 및 설치
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # 다운로드
    wget -O terraform.zip "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip"
    
    # 압축 해제
    log_info "Terraform 압축 해제 중..."
    unzip -o terraform.zip
    
    # 원래 디렉토리로 돌아가기
    cd - > /dev/null
    
    # 설치
    if [ -f "$TEMP_DIR/terraform" ]; then
        sudo mv "$TEMP_DIR/terraform" /usr/local/bin/
        sudo chmod +x /usr/local/bin/terraform
        log_success "Terraform 바이너리 설치 완료"
    else
        log_error "Terraform 바이너리를 찾을 수 없습니다"
        exit 1
    fi
    
    # 임시 디렉토리 정리
    rm -rf "$TEMP_DIR"
    
    TERRAFORM_VERSION=$(terraform --version | head -n1)
    log_info "Terraform 설치 완료: $TERRAFORM_VERSION"
    
    log_success "Terraform 설치 완료"
}

# ========================================
# 7. Ansible 설치
# ========================================

install_ansible() {
    log_step "7. Ansible 설치 중..."
    
    # Ansible 설치 확인
    if command -v ansible &> /dev/null; then
        ANSIBLE_VERSION=$(ansible --version | head -n1)
        log_info "Ansible 이미 설치됨: $ANSIBLE_VERSION"
    else
        log_info "Ansible 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # EPEL 저장소 추가
            sudo $PKG_MANAGER install -y epel-release
            sudo $PKG_MANAGER install -y ansible
        elif [ "$PKG_MANAGER" = "apt" ]; then
            sudo apt update
            sudo apt install -y ansible
        fi
        
        ANSIBLE_VERSION=$(ansible --version | head -n1)
        log_info "Ansible 설치 완료: $ANSIBLE_VERSION"
    fi
    
    log_success "Ansible 설치 완료"
}

# ========================================
# 8. 환경변수 파일 설정 및 검증
# ========================================

setup_environment() {
    log_step "8. 환경변수 파일 설정 및 검증 중..."
    
    # SSH 공개키를 Vault에 저장
    log_info "SSH 공개키를 Vault에 저장 중..."
    SSH_PUBLIC_KEY_PATH=""
    
    # SSH 공개키 파일 찾기 (여러 가능한 위치 확인)
    for ssh_path in "$HOME/.ssh/id_rsa.pub" "$HOME/.ssh/id_ed25519.pub" "/root/.ssh/id_rsa.pub" "/root/.ssh/id_ed25519.pub"; do
        if [ -f "$ssh_path" ]; then
            SSH_PUBLIC_KEY_PATH="$ssh_path"
            log_success "SSH 공개키 발견: $SSH_PUBLIC_KEY_PATH"
            break
        fi
    done
    
    if [ -z "$SSH_PUBLIC_KEY_PATH" ]; then
        log_warning "SSH 공개키를 찾을 수 없습니다. SSH 키를 생성합니다..."
        mkdir -p "$HOME/.ssh"
        ssh-keygen -t rsa -b 4096 -f "$HOME/.ssh/id_rsa" -N "" -C "$(whoami)@$(hostname)"
        SSH_PUBLIC_KEY_PATH="$HOME/.ssh/id_rsa.pub"
        log_success "SSH 키 생성 완료: $SSH_PUBLIC_KEY_PATH"
    fi
    
    # SSH 공개키 내용을 Vault에 저장
    SSH_PUBLIC_KEY_CONTENT=$(cat "$SSH_PUBLIC_KEY_PATH")
    if command -v vault >/dev/null 2>&1; then
        vault kv put secret/ssh public_key="$SSH_PUBLIC_KEY_CONTENT" key_path="$SSH_PUBLIC_KEY_PATH"
        log_success "SSH 공개키를 Vault에 저장 완료"
    else
        log_warning "Vault CLI가 설치되지 않았습니다. 나중에 수동으로 저장하세요"
    fi
    
    # .env 파일 확인
    if [ ! -f ".env" ]; then
        log_info ".env 파일 생성 중..."
        # .env 파일이 없으면 기본 템플릿 생성
        cat > .env << EOF
# Proxmox Manager 환경 변수 설정
# 이 파일을 편집하여 실제 값으로 변경하세요

# 환경 설정
ENVIRONMENT=development

# Proxmox 설정
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=your-username
PROXMOX_PASSWORD=your-password
PROXMOX_NODE=your-node-name

# SSH 설정은 Vault에서 관리됩니다

# Vault 설정
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=your-vault-token

# 데이터베이스 설정 (PostgreSQL)
DATABASE_URL=postgresql://proxmox:proxmox123@localhost:5432/proxmox_manager

# Flask 설정
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
EOF
        
        log_warning "⚠️  .env 파일을 생성했습니다. 필수 정보를 입력해주세요:"
        echo ""
        
        # 필수 정보 입력
        read -p "Proxmox 서버 주소를 입력하세요 (예: https://example.proxmox.co.kr:8006): " PROXMOX_ENDPOINT
        read -p "Proxmox 사용자명을 입력하세요 (예: root@pam): " PROXMOX_USERNAME
        read -s -p "Proxmox 비밀번호를 입력하세요: " PROXMOX_PASSWORD
        echo
        
        # 입력값 검증
        if [ -z "$PROXMOX_ENDPOINT" ] || [ -z "$PROXMOX_USERNAME" ] || [ -z "$PROXMOX_PASSWORD" ]; then
            log_error "❌ 필수 정보가 누락되었습니다. 설치를 중단합니다."
            log_error "   - PROXMOX_ENDPOINT: $([ -z "$PROXMOX_ENDPOINT" ] && echo "누락" || echo "입력됨")"
            log_error "   - PROXMOX_USERNAME: $([ -z "$PROXMOX_USERNAME" ] && echo "누락" || echo "입력됨")"
            log_error "   - PROXMOX_PASSWORD: $([ -z "$PROXMOX_PASSWORD" ] && echo "누락" || echo "입력됨")"
            exit 1
        fi
        
        # .env 파일 업데이트
        sed -i "s|PROXMOX_ENDPOINT=.*|PROXMOX_ENDPOINT=$PROXMOX_ENDPOINT|" .env
        sed -i "s|PROXMOX_USERNAME=.*|PROXMOX_USERNAME=$PROXMOX_USERNAME|" .env
        sed -i "s|PROXMOX_PASSWORD=.*|PROXMOX_PASSWORD=$PROXMOX_PASSWORD|" .env
        
    # SSH 키 파일 경로 확인 및 생성
    log_info "SSH 키 파일 경로 확인 중..."
    SSH_PUBLIC_KEY_PATH_FULL=$(eval echo ${SSH_PUBLIC_KEY_PATH})
    SSH_PRIVATE_KEY_PATH_FULL=$(eval echo ${SSH_PRIVATE_KEY_PATH})
    
    if [ ! -f "$SSH_PUBLIC_KEY_PATH_FULL" ]; then
        log_warning "SSH 공개키 파일이 없습니다: $SSH_PUBLIC_KEY_PATH_FULL"
        log_info "SSH 키 쌍을 생성합니다..."
        ssh-keygen -t rsa -b 4096 -f "$SSH_PRIVATE_KEY_PATH_FULL" -N "" -C "proxmox-manager@$(hostname)"
        log_success "SSH 키 쌍 생성 완료"
    else
        log_success "SSH 공개키 파일 확인됨: $SSH_PUBLIC_KEY_PATH_FULL"
    fi
    
    # Terraform 변수들을 .env 파일에 추가
    log_info "Terraform 변수를 .env 파일에 추가 중..."
    cat >> .env << EOF

# Terraform 변수 (자동 매핑용)
TF_VAR_vault_token=${VAULT_TOKEN}
TF_VAR_vault_address=${VAULT_ADDR}
TF_VAR_proxmox_endpoint=${PROXMOX_ENDPOINT}
TF_VAR_proxmox_username=${PROXMOX_USERNAME}
TF_VAR_proxmox_password=${PROXMOX_PASSWORD}
TF_VAR_proxmox_node=${PROXMOX_NODE}
TF_VAR_vm_username=${SSH_USER}
TF_VAR_ssh_keys=${SSH_PUBLIC_KEY_PATH_FULL}
EOF
        
        log_success ".env 파일 설정 완료"
    else
        log_info ".env 파일이 이미 존재합니다"
        
        # SSH 키 파일 경로 확인 및 생성
        log_info "SSH 키 파일 경로 확인 중..."
        SSH_PUBLIC_KEY_PATH_FULL=$(eval echo ${SSH_PUBLIC_KEY_PATH})
        SSH_PRIVATE_KEY_PATH_FULL=$(eval echo ${SSH_PRIVATE_KEY_PATH})
        
        if [ ! -f "$SSH_PUBLIC_KEY_PATH_FULL" ]; then
            log_warning "SSH 공개키 파일이 없습니다: $SSH_PUBLIC_KEY_PATH_FULL"
            log_info "SSH 키 쌍을 생성합니다..."
            ssh-keygen -t rsa -b 4096 -f "$SSH_PRIVATE_KEY_PATH_FULL" -N "" -C "proxmox-manager@$(hostname)"
            log_success "SSH 키 쌍 생성 완료"
        else
            log_success "SSH 공개키 파일 확인됨: $SSH_PUBLIC_KEY_PATH_FULL"
        fi
        
        # 기존 .env 파일에 Terraform 변수가 있는지 확인
        if ! grep -q "TF_VAR_vault_token" .env; then
            log_info "기존 .env 파일에 Terraform 변수를 추가 중..."
            cat >> .env << EOF

# Terraform 변수 (자동 매핑용)
TF_VAR_vault_token=${VAULT_TOKEN}
TF_VAR_vault_address=${VAULT_ADDR}
TF_VAR_proxmox_endpoint=${PROXMOX_ENDPOINT}
TF_VAR_proxmox_username=${PROXMOX_USERNAME}
TF_VAR_proxmox_password=${PROXMOX_PASSWORD}
TF_VAR_proxmox_node=${PROXMOX_NODE}
TF_VAR_vm_username=${SSH_USER}
TF_VAR_ssh_keys=${SSH_PUBLIC_KEY_PATH_FULL}
EOF
            log_success "기존 .env 파일에 Terraform 변수 추가 완료"
        else
            log_info "Terraform 변수가 이미 .env 파일에 존재합니다"
        fi
    fi
    
    # .env 파일 로드
    source .env
    
    # terraform.tfvars.json 파일 생성 (Git에 없으므로 설치 시 생성)
    log_info "terraform.tfvars.json 파일 생성 중..."
    if [ ! -f "terraform/terraform.tfvars.json" ]; then
        cat > terraform/terraform.tfvars.json << EOF
{
  "proxmox_endpoint": "${PROXMOX_ENDPOINT:-https://localhost:8006}",
  "proxmox_username": "${PROXMOX_USERNAME:-root@pam}",
  "proxmox_node": "${PROXMOX_NODE:-prox}",
  "vm_username": "${SSH_USER:-rocky}",
  "environment": "${ENVIRONMENT:-development}",
  "proxmox_hdd_datastore": "${PROXMOX_HDD_DATASTORE:-local-lvm}",
  "proxmox_ssd_datastore": "${PROXMOX_SSD_DATASTORE:-local}",
  "servers": {}
}
EOF
        log_success "terraform.tfvars.json 파일 생성 완료"
    else
        log_info "terraform.tfvars.json 파일이 이미 존재합니다"
    fi
    
    # 필수 환경변수 검증
    log_info "필수 환경변수 검증 중..."
    
    REQUIRED_VARS=(
        "PROXMOX_ENDPOINT"
        "PROXMOX_USERNAME" 
        "PROXMOX_PASSWORD"
    )
    
    MISSING_VARS=()
    
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ] || [ "${!var}" = "your_proxmox_endpoint" ] || [ "${!var}" = "your_proxmox_username" ] || [ "${!var}" = "your_proxmox_password" ]; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        log_error "❌ 필수 환경변수가 설정되지 않았습니다:"
        for var in "${MISSING_VARS[@]}"; do
            log_error "   - $var: ${!var:-'설정되지 않음'}"
        done
        log_error ""
        log_error "다음 중 하나를 선택하세요:"
        log_error "1. .env 파일을 수정하여 필수 정보를 설정한 후 다시 실행"
        log_error "2. 이 스크립트를 다시 실행하여 대화형으로 설정"
        log_error ""
        log_error "설치를 중단합니다."
        exit 1
    fi
    
    log_success "모든 필수 환경변수가 설정되었습니다"
    
    # Terraform 변수 설정
    log_info "Terraform 변수 설정 중..."
    export TF_VAR_proxmox_endpoint="$PROXMOX_ENDPOINT"
    export TF_VAR_proxmox_username="$PROXMOX_USERNAME"
    export TF_VAR_proxmox_password="$PROXMOX_PASSWORD"
    export TF_VAR_proxmox_node="$PROXMOX_NODE"
    export TF_VAR_vm_username="$VM_USERNAME"
    export TF_VAR_vm_password="$VM_PASSWORD"
    export TF_VAR_vault_address="$VAULT_ADDR"
    export TF_VAR_vault_token="$VAULT_TOKEN"
    
    # SSH 공개키 설정 (파일이 존재하는 경우)
    if [ -f "$SSH_PUBLIC_KEY_PATH" ]; then
        export TF_VAR_ssh_keys="$(cat $SSH_PUBLIC_KEY_PATH)"
    fi
    
    log_success "Terraform 변수 설정 완료"
    log_success "환경변수 설정 완료"
}

# ========================================
# 9. Vault 설정
# ========================================

setup_vault() {
    log_step "9. Vault 설정 중..."
    
    # Vault 관련 환경변수 검증
    log_info "Vault 설정을 위한 환경변수 검증 중..."
    
    VAULT_REQUIRED_VARS=(
        "PROXMOX_PASSWORD"
    )
    
    VAULT_MISSING_VARS=()
    
    for var in "${VAULT_REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ] || [ "${!var}" = "your_proxmox_password" ]; then
            VAULT_MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#VAULT_MISSING_VARS[@]} -gt 0 ]; then
        log_error "❌ Vault 설정을 위한 필수 환경변수가 누락되었습니다:"
        for var in "${VAULT_MISSING_VARS[@]}"; do
            log_error "   - $var: ${!var:-'설정되지 않음'}"
        done
        log_error ""
        log_error "Vault는 Proxmox 비밀번호를 안전하게 저장하기 위해 필요합니다."
        log_error "설치를 중단합니다."
        exit 1
    fi
    
    # Vault 스크립트 실행
    if [ -f "scripts/vault.sh" ]; then
        log_info "Vault 설정 스크립트 실행 중..."
        chmod +x scripts/vault.sh
        ./scripts/vault.sh
        
        if [ $? -eq 0 ]; then
            log_success "Vault 설정 완료"
        else
            log_error "Vault 설정 실패"
            exit 1
        fi
    else
        log_error "scripts/vault.sh 파일을 찾을 수 없습니다"
        exit 1
    fi
    
    # Vault 수동 초기화 스크립트 생성
    log_info "Vault 수동 초기화 스크립트 생성 중..."
    cat > vault-init.sh << 'EOF'
#!/bin/bash
# Vault 수동 초기화 스크립트

echo "🔐 Vault 수동 초기화 스크립트"
echo "================================"

# Vault 컨테이너 상태 확인
if ! docker ps | grep -q vault-dev; then
    echo "❌ Vault 컨테이너가 실행되지 않았습니다."
    echo "먼저 다음 명령어로 Vault를 시작하세요:"
    echo "docker-compose -f docker-compose.vault.yaml up -d"
    exit 1
fi

# Vault 상태 확인
echo "🔍 Vault 상태 확인 중..."
VAULT_STATUS=$(docker exec vault-dev vault status 2>/dev/null)

if echo "$VAULT_STATUS" | grep -q "Initialized.*true"; then
    echo "⚠️ Vault가 이미 초기화되어 있습니다."
    echo ""
    echo "현재 상태:"
    echo "$VAULT_STATUS"
    echo ""
    
    read -p "Vault를 재초기화하시겠습니까? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "취소되었습니다."
        exit 0
    fi
    
    echo "⚠️ 주의: Vault 재초기화 시 기존 데이터가 모두 삭제됩니다!"
    read -p "정말로 재초기화하시겠습니까? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "취소되었습니다."
        exit 0
    fi
fi

echo ""
echo "🔐 Vault 초기화를 위한 정보를 입력해주세요:"
echo ""

# Proxmox 비밀번호 입력
read -p "Proxmox root 비밀번호를 입력하세요: " -s PROXMOX_PASSWORD
echo ""

# VM 비밀번호 입력
read -p "VM 기본 비밀번호를 입력하세요: " -s VM_PASSWORD
echo ""

# Vault 볼륨 권한 설정 (권한 문제 해결)
echo "🔧 Vault 볼륨 권한 설정 중..."
docker exec vault-dev sh -c "mkdir -p /vault/data && chmod 755 /vault/data" 2>/dev/null || true

# Vault 초기화 실행
echo "🚀 Vault 초기화 실행 중..."
VAULT_INIT_OUTPUT=$(docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 2>/dev/null)

if [ $? -eq 0 ]; then
    VAULT_TOKEN=$(echo "$VAULT_INIT_OUTPUT" | grep "Initial Root Token:" | awk '{print $4}')
    UNSEAL_KEY=$(echo "$VAULT_INIT_OUTPUT" | grep "Unseal Key 1:" | awk '{print $4}')
    
    # 토큰과 Unseal 키를 파일에 저장
    echo "$VAULT_TOKEN" > vault_token.txt
    echo "$UNSEAL_KEY" > vault_unseal_keys.txt
    chmod 600 vault_token.txt
    chmod 600 vault_unseal_keys.txt
    
    echo "✅ Vault 초기화 완료 및 키 저장"
    
    # 환경변수에 토큰 설정
    export VAULT_TOKEN="$VAULT_TOKEN"
    export TF_VAR_vault_token="$VAULT_TOKEN"
    
    # .env 파일에 토큰 업데이트
    if [ -f ".env" ]; then
        sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
        sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
        echo "✅ .env 파일에 토큰 업데이트 완료"
    fi
    
    # Vault 시크릿 설정 (Base64 암호화)
    echo "🔐 Vault 시크릿 설정 중 (Base64 암호화)..."
    
    # Proxmox 비밀번호 Base64 암호화
    PROXMOX_PASSWORD_B64=$(echo -n "$PROXMOX_PASSWORD" | base64)
    VM_PASSWORD_B64=$(echo -n "$VM_PASSWORD" | base64)
    
    # Vault에 시크릿 저장
    docker exec vault-dev vault kv put secret/proxmox username=root@pam password="$PROXMOX_PASSWORD_B64" password_plain="$PROXMOX_PASSWORD"
    docker exec vault-dev vault kv put secret/vm username=rocky password="$VM_PASSWORD_B64" password_plain="$VM_PASSWORD"
    
    echo "✅ Vault 시크릿 설정 완료 (Base64 암호화)"
    
    # 중요 정보 출력
    echo ""
    echo "================================"
    echo "📋 Vault 초기화 완료 정보:"
    echo "================================"
    echo "  Vault Token: $VAULT_TOKEN"
    echo "  Unseal Key: $UNSEAL_KEY"
    echo "  Proxmox Password (Base64): $PROXMOX_PASSWORD_B64"
    echo "  VM Password (Base64): $VM_PASSWORD_B64"
    echo ""
    echo "📁 저장된 파일:"
    echo "  vault_token.txt"
    echo "  vault_unseal_keys.txt"
    echo ""
    echo "⚠️  중요: 이 정보들을 안전한 곳에 보관하세요!"
    echo ""
    
    # Vault 상태 확인
    echo "🔍 Vault 최종 상태:"
    docker exec vault-dev vault status
    
else
    echo "❌ Vault 초기화 실패"
    exit 1
fi
EOF
    
    chmod +x vault-init.sh
    log_success "Vault 수동 초기화 스크립트 생성 완료"
}

# ========================================
# 10. 모니터링 시스템 설치
# ========================================

install_monitoring() {
    log_step "10. 모니터링 시스템 설치 중..."
    
    # Docker 모니터링 시스템 설치 (권장)
    log_info "Docker 모니터링 시스템 설치 중..."
    
    # Docker 설치 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
        log_info "Docker 설치 후 다시 시도해주세요."
        log_info "설치 명령어: curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다."
        log_info "Docker Compose 설치 후 다시 시도해주세요."
        log_info "설치 명령어: sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose"
        exit 1
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
    
    # 로그 디렉토리 생성
    log_info "로그 디렉토리 생성 중..."
    mkdir -p logs
    chmod 755 logs
    
    # 모니터링 디렉토리 생성
    log_info "모니터링 디렉토리 생성 중..."
    mkdir -p monitoring/grafana/provisioning/datasources
    mkdir -p monitoring/grafana/provisioning/dashboards
    mkdir -p monitoring/grafana/dashboards
    mkdir -p monitoring/prometheus_data
    mkdir -p monitoring/grafana_data
    
    # 권한 설정
    chmod 755 monitoring/prometheus_data
    chmod 755 monitoring/grafana_data
    chmod 755 monitoring/grafana/provisioning/datasources
    chmod 755 monitoring/grafana/provisioning/dashboards
    chmod 755 monitoring/grafana/dashboards
    
    # Docker 모니터링 시스템은 아래에서 별도로 시작됩니다
    log_info "모니터링 디렉토리 구조 준비 완료"
    
    # Prometheus 타겟 업데이트 스크립트 권한 설정
    if [ -f "monitoring/update_prometheus_targets.py" ]; then
        log_info "Prometheus 타겟 업데이트 스크립트 설정 중..."
        chmod +x monitoring/update_prometheus_targets.py
        
        # PyYAML 설치 확인 (스크립트 실행에 필요)
        source venv/bin/activate
        pip install PyYAML requests
        
        log_success "Prometheus 타겟 업데이트 스크립트 설정 완료"
    fi
    
    # Ansible Dynamic Inventory 스크립트 권한 설정
    if [ -f "ansible/dynamic_inventory.py" ]; then
        log_info "Ansible Dynamic Inventory 스크립트 권한 설정 중..."
        chmod +x ansible/dynamic_inventory.py
        log_success "Dynamic Inventory 스크립트 권한 설정 완료"
    fi
    
    # 방화벽 설정 (Docker 포트)
    if command -v firewall-cmd &> /dev/null; then
        log_info "방화벽 설정 중..."
        sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
        sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
        sudo firewall-cmd --permanent --add-port=9100/tcp  # Node Exporter
        sudo firewall-cmd --reload
        log_success "방화벽 설정 완료"
    fi
    
    # Docker 네트워크 Trust Zone 등록
    if command -v firewall-cmd &> /dev/null; then
        log_info "Docker 네트워크 Trust Zone 등록 중..."
        
        # Docker 네트워크 확인 및 Trust Zone 등록
        if docker network ls | grep -q "monitoring_monitoring"; then
            # monitoring_monitoring 네트워크가 이미 존재하는 경우
            NETWORK_SUBNET=$(docker network inspect monitoring_monitoring --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "")
            if [ -n "$NETWORK_SUBNET" ]; then
                log_info "Docker 네트워크 Trust Zone 등록: $NETWORK_SUBNET"
                sudo firewall-cmd --permanent --add-source="$NETWORK_SUBNET" --zone=trusted
                sudo firewall-cmd --reload
                log_success "Docker 네트워크 Trust Zone 등록 완료: $NETWORK_SUBNET"
            else
                log_warning "Docker 네트워크 서브넷 정보를 가져올 수 없습니다"
            fi
        else
            log_info "Docker 네트워크가 아직 생성되지 않았습니다 (모니터링 시작 후 자동 등록됨)"
        fi
    fi
    
    log_success "모니터링 시스템 설치 완료"
    
    # 모니터링 시스템 준비 완료 (실제 시작은 아래에서)
    log_success "모니터링 시스템 준비 완료"

        # Docker 기반 모니터링 시스템 시작
    log_info "Docker 기반 모니터링 시스템 시작 중..."
    
    # 모니터링 디렉토리로 이동하여 Docker Compose 실행
    if [ -f "monitoring/start-monitoring.sh" ]; then
        chmod +x monitoring/start-monitoring.sh
        cd monitoring
        ./start-monitoring.sh
        cd ..
        log_success "Docker 기반 모니터링 시스템 시작 완료"
    else
        log_warning "monitoring/start-monitoring.sh 파일을 찾을 수 없습니다"
        log_info "수동으로 Docker Compose 실행: cd monitoring && docker-compose up -d"
    fi
    
    # 정리 (Docker 사용으로 불필요한 파일들 제거)
    # rm -rf prometheus_temp prometheus.tar.gz  # Docker 사용으로 불필요
    
    log_success "Prometheus Docker 설정 완료"
    log_info "프로메테우스는 http://localhost:9090 에서 접근 가능합니다"
    
    # Grafana는 Docker Compose에서 함께 실행되므로 별도 설치 불필요
    log_info "Grafana는 Docker Compose에서 Prometheus와 함께 실행됩니다"
    
    # Docker 네트워크 Trust Zone 등록 (모니터링 시작 후)
    if command -v firewall-cmd &> /dev/null; then
        log_info "Docker 네트워크 Trust Zone 등록 (모니터링 시작 후)..."
        
        # 잠시 대기 후 네트워크 생성 확인
        sleep 5
        
        if docker network ls | grep -q "monitoring_monitoring"; then
            NETWORK_SUBNET=$(docker network inspect monitoring_monitoring --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "")
            if [ -n "$NETWORK_SUBNET" ]; then
                log_info "Docker 네트워크 Trust Zone 등록: $NETWORK_SUBNET"
                sudo firewall-cmd --permanent --add-source="$NETWORK_SUBNET" --zone=trusted
                sudo firewall-cmd --reload
                log_success "Docker 네트워크 Trust Zone 등록 완료: $NETWORK_SUBNET"
            else
                log_warning "Docker 네트워크 서브넷 정보를 가져올 수 없습니다"
            fi
        else
            log_warning "monitoring_monitoring 네트워크를 찾을 수 없습니다"
        fi
    fi
    
    # Docker 컨테이너 상태 확인
    log_info "Docker 컨테이너 상태 확인 중..."
    if command -v docker &> /dev/null; then
        if docker ps | grep -q "grafana"; then
            log_success "Grafana Docker 컨테이너가 실행 중입니다"
        else
            log_warning "Grafana Docker 컨테이너가 실행되지 않았습니다"
            log_info "Docker Compose를 다시 실행해주세요: cd monitoring && docker-compose up -d"
        fi
    else
        log_warning "Docker가 설치되지 않았습니다"
    fi
    
    log_success "Grafana Docker 설정 완료"
    log_info "Grafana는 http://localhost:3000 에서 접근 가능합니다 (admin/admin)"
    
    # Grafana Provisioning은 Docker 볼륨 마운트로 자동 설정됨
    log_info "Grafana Provisioning 확인 중..."
    
    # Provisioning 파일들이 올바른 위치에 있는지 확인
    if [ -f "monitoring/grafana/provisioning/datasources/prometheus.yml" ]; then
        log_success "Prometheus 데이터소스 provisioning 파일 확인 완료"
    else
        log_warning "Prometheus 데이터소스 provisioning 파일을 찾을 수 없습니다"
    fi
    
    if [ -f "monitoring/grafana/provisioning/dashboards/dashboard.yml" ]; then
        log_success "대시보드 provisioning 설정 파일 확인 완료"
    else
        log_warning "대시보드 provisioning 설정 파일을 찾을 수 없습니다"
    fi
    
    if [ -f "monitoring/grafana/dashboards/system-monitoring.json" ]; then
        log_success "시스템 모니터링 대시보드 JSON 파일 확인 완료"
    else
        log_warning "시스템 모니터링 대시보드 JSON 파일을 찾을 수 없습니다"
    fi
    
    # Docker 컨테이너 재시작으로 provisioning 적용
    log_info "Docker 컨테이너 재시작으로 provisioning 적용 중..."
    if command -v docker-compose &> /dev/null; then
        cd monitoring
        docker-compose restart grafana
        cd ..
        log_success "Grafana Docker 컨테이너 재시작 완료"
        
        # 데이터소스 연결 확인
        log_info "Prometheus 데이터소스 연결 확인 중..."
        sleep 10  # Grafana가 완전히 시작될 때까지 대기
        
        # 데이터소스 연결 테스트
        if curl -s -f http://admin:admin@localhost:3000/api/datasources/prometheus > /dev/null 2>&1; then
            log_success "Prometheus 데이터소스 연결 확인 완료"
        else
            log_warning "Prometheus 데이터소스 연결에 문제가 있을 수 있습니다"
            log_info "Grafana 웹 인터페이스에서 데이터소스 설정을 확인해주세요: http://localhost:3000/datasources"
        fi
    else
        log_warning "docker-compose가 설치되지 않았습니다"
    fi
    
    # Grafana 설정 완료
    log_success "Grafana Docker Provisioning 설정 완료"
    log_info "익명 접근 및 iframe 임베딩이 설정되었습니다"
    log_info "Prometheus 데이터소스가 자동으로 추가됩니다"
    log_info "시스템 모니터링 대시보드가 자동으로 생성됩니다"
    log_info "대시보드 URL: http://localhost:3000/d/system-monitoring-dashboard?kiosk=tv"
    
    # Ansible Dynamic Inventory 스크립트 권한 설정
    if [ -f "ansible/dynamic_inventory.py" ]; then
        log_info "Ansible Dynamic Inventory 스크립트 권한 설정 중..."
        chmod +x ansible/dynamic_inventory.py
        log_success "Dynamic Inventory 스크립트 권한 설정 완료"
    fi
    
    # Prometheus 타겟 업데이트 스크립트 권한 설정
    if [ -f "monitoring/update_prometheus_targets.py" ]; then
        log_info "Prometheus 타겟 업데이트 스크립트 설정 중..."
        chmod +x monitoring/update_prometheus_targets.py
        
        # PyYAML 설치 확인 (스크립트 실행에 필요)
        source venv/bin/activate
        pip install PyYAML requests
        
        log_success "Prometheus 타겟 업데이트 스크립트 설정 완료"
    fi
    
    # Docker 모니터링 시스템 설정
    log_info "Docker 모니터링 시스템 설정 중..."
    if [ -f "monitoring/start-monitoring.sh" ]; then
        chmod +x monitoring/start-monitoring.sh
        log_success "Docker 모니터링 스크립트 권한 설정 완료"
        
        # Docker 설치 확인
        if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
            log_info "Docker 모니터링 시스템 시작 중..."
            cd monitoring
            ./start-monitoring.sh
            cd ..
            log_success "Docker 모니터링 시스템 시작 완료"
        else
            log_warning "Docker가 설치되지 않아 모니터링 시스템을 시작할 수 없습니다."
            log_info "Docker 설치 후 'monitoring/start-monitoring.sh'를 실행하세요."
        fi
    else
        log_warning "Docker 모니터링 스크립트를 찾을 수 없습니다."
    fi
    
    log_success "모니터링 시스템 설치 완료"
}

# ========================================
# 10.5. Redis 설치 (백엔드 큐/캐시용)
# ========================================

install_redis() {
    log_step "10.5. Redis + Celery (Docker) 설치 중..."

    # Docker 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 필요합니다. Docker 설치 단계를 먼저 완료하세요."
        exit 1
    fi
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 필요합니다. 설치를 먼저 완료하세요."
        exit 1
    fi

    # 디렉토리 준비
    mkdir -p redis
    chmod 755 redis

    # 파일 존재 확인
    if [ ! -f "redis/docker-compose.yml" ]; then
        log_error "redis/docker-compose.yml 파일이 없습니다. 리포지토리를 최신화하세요."
        exit 1
    fi
    if [ -f "redis/start-redis.sh" ]; then
        chmod +x redis/start-redis.sh
    fi
    if [ -f "redis/start-redis-celery.sh" ]; then
        chmod +x redis/start-redis-celery.sh
    fi

    # 방화벽 개방 (선택)
    if command -v firewall-cmd &> /dev/null; then
        log_info "방화벽에 Redis + Celery 포트 개방 중..."
        sudo firewall-cmd --permanent --add-port=6379/tcp || true  # Redis
        sudo firewall-cmd --permanent --add-port=5555/tcp || true  # Celery Flower
        sudo firewall-cmd --reload || true
        log_success "방화벽 포트 개방 완료: Redis(6379), Flower(5555)"
    fi

    # 환경 변수 기본값 안내 (비밀번호는 .env로 설정)
    if [ ! -f ".env" ]; then
        log_warning "⚠️  .env 파일이 없어 REDIS_PASSWORD가 설정되지 않을 수 있습니다. 보안을 위해 설정을 권장합니다."
    fi

    # Redis + Celery 스택 시작
    log_info "Redis + Celery Docker 스택 시작 중..."
    (cd redis && docker-compose up -d)

    # 헬스체크 대기 및 확인
    log_info "Redis + Celery 헬스체크 대기 중..."
    sleep 5
    ATTEMPTS=20
    for i in $(seq 1 $ATTEMPTS); do
        if (cd redis && docker-compose ps) | grep -q "proxmox-redis"; then
            # 비밀번호 설정 여부에 따라 ping 시도
            if [ -n "${REDIS_PASSWORD}" ]; then
                if docker exec proxmox-redis redis-cli -a "${REDIS_PASSWORD}" PING 2>/dev/null | grep -q PONG; then
                    log_success "Redis 컨테이너 정상 동작 확인 (PONG)"
                    break
                fi
            else
                if docker exec proxmox-redis redis-cli PING 2>/dev/null | grep -q PONG; then
                    log_success "Redis 컨테이너 정상 동작 확인 (PONG)"
                    break
                fi
            fi
        fi
        sleep 2
    done

    # Celery 워커는 로컬에서 실행되므로 Docker 컨테이너 확인 제거
    log_info "Celery 워커는 로컬에서 실행됩니다 (Docker 컨테이너 아님)"

    # Flower 확인
    log_info "Celery Flower 상태 확인 중..."
    if (cd redis && docker-compose ps) | grep -q "proxmox-celery-flower"; then
        log_success "Celery Flower 컨테이너 실행 중 (http://localhost:5555)"
    else
        log_warning "Celery Flower 컨테이너 실행 실패"
    fi

    # 최종 확인
    if ! docker exec proxmox-redis redis-cli ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} PING 2>/dev/null | grep -q PONG; then
        log_warning "Redis 컨테이너 응답 확인 실패. 로그를 확인하세요."
        (cd redis && docker-compose logs --no-color | tail -n 100) || true
    fi

    log_success "Redis + Celery (Docker) 설치 및 시작 완료"
}

# ========================================
# 10.6. PostgreSQL 설치 (Docker)
# ========================================

install_postgresql() {
    log_step "10.6. PostgreSQL (Docker) 설치 중..."

    # Docker 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 필요합니다. Docker 설치 단계를 먼저 완료하세요."
        exit 1
    fi
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 필요합니다. 설치를 먼저 완료하세요."
        exit 1
    fi

    # 디렉토리 준비
    mkdir -p postgres
    chmod 755 postgres

    # PostgreSQL Docker Compose 파일 생성
    if [ ! -f "postgres/docker-compose.yml" ]; then
        log_info "PostgreSQL Docker Compose 파일 생성 중..."
        cat > postgres/docker-compose.yml << 'EOF'
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    container_name: proxmox-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: proxmox_manager
      POSTGRES_USER: ${POSTGRES_USER:-proxmox}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-proxmox123}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --locale=C"
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-postgres.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-proxmox} -d proxmox_manager"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - proxmox_network

networks:
  proxmox_network:
    driver: bridge

volumes:
  postgres-data:
    driver: local
EOF
        log_success "PostgreSQL Docker Compose 파일 생성 완료"
    fi

    # PostgreSQL 초기화 스크립트 생성
    if [ ! -f "postgres/init-postgres.sql" ]; then
        log_info "PostgreSQL 초기화 스크립트 생성 중..."
        cat > postgres/init-postgres.sql << 'EOF'
-- PostgreSQL 초기화 스크립트
-- Proxmox Manager 데이터베이스 설정

-- 연결 풀 설정
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- 인덱스 최적화 설정
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;

-- 로그 설정
ALTER SYSTEM SET log_statement = 'none';
ALTER SYSTEM SET log_min_duration_statement = 1000;

-- 설정 적용
SELECT pg_reload_conf();

-- 확장 설치
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 사용자 권한 설정
GRANT ALL PRIVILEGES ON DATABASE proxmox_manager TO proxmox;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO proxmox;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO proxmox;
EOF
        log_success "PostgreSQL 초기화 스크립트 생성 완료"
    fi

    # 환경 변수 파일 생성
    if [ ! -f "postgres/.env" ]; then
        log_info "PostgreSQL 환경 변수 파일 생성 중..."
        cat > postgres/.env << 'EOF'
# PostgreSQL 설정
POSTGRES_USER=proxmox
POSTGRES_PASSWORD=proxmox123
POSTGRES_DB=proxmox_manager
POSTGRES_PORT=5432

# 애플리케이션용 DATABASE_URL
DATABASE_URL=postgresql://proxmox:proxmox123@localhost:5432/proxmox_manager
EOF
        log_success "PostgreSQL 환경 변수 파일 생성 완료"
    fi

    # PostgreSQL 시작 스크립트 생성
    if [ ! -f "postgres/start-postgres.sh" ]; then
        log_info "PostgreSQL 시작 스크립트 생성 중..."
        cat > postgres/start-postgres.sh << 'EOF'
#!/bin/bash
# PostgreSQL 시작 스크립트

echo "🐘 PostgreSQL 시작 중..."

# 환경 변수 설정
export POSTGRES_USER=${POSTGRES_USER:-proxmox}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-proxmox123}
export POSTGRES_DB=${POSTGRES_DB:-proxmox_manager}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}

# PostgreSQL 컨테이너 시작
docker-compose up -d

# 연결 대기
echo "⏳ PostgreSQL 연결 대기 중..."
sleep 10

# 연결 테스트
docker exec proxmox-postgres pg_isready -U $POSTGRES_USER -d $POSTGRES_DB

if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL 시작 완료!"
    echo "📊 연결 정보:"
    echo "  - 호스트: localhost"
    echo "  - 포트: $POSTGRES_PORT"
    echo "  - 데이터베이스: $POSTGRES_DB"
    echo "  - 사용자: $POSTGRES_USER"
    echo "  - URL: postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB"
else
    echo "❌ PostgreSQL 시작 실패"
    exit 1
fi
EOF
        chmod +x postgres/start-postgres.sh
        log_success "PostgreSQL 시작 스크립트 생성 완료"
    fi

    # 방화벽 개방
    if command -v firewall-cmd &> /dev/null; then
        log_info "방화벽에 PostgreSQL 포트 개방 중..."
        sudo firewall-cmd --permanent --add-port=5432/tcp || true  # PostgreSQL
        sudo firewall-cmd --reload || true
        log_success "방화벽 포트 개방 완료: PostgreSQL(5432)"
    fi

    # PostgreSQL 시작
    log_info "PostgreSQL Docker 컨테이너 시작 중..."
    (cd postgres && ./start-postgres.sh)

    if [ $? -eq 0 ]; then
        log_success "PostgreSQL 설치 및 시작 완료"
    else
        log_error "PostgreSQL 시작 실패"
        exit 1
    fi

    # psycopg2 설치 확인 및 설치
    log_info "PostgreSQL Python 드라이버 설치 확인 중..."
    source venv/bin/activate
    if ! python -c "import psycopg2" 2>/dev/null; then
        log_info "psycopg2-binary 설치 중..."
        pip install psycopg2-binary
        if [ $? -eq 0 ]; then
            log_success "psycopg2-binary 설치 완료"
        else
            log_warning "psycopg2-binary 설치 실패 (수동 설치 필요)"
        fi
    else
        log_success "psycopg2-binary 이미 설치됨"
    fi

    # PostgreSQL 스키마 초기화
    log_info "PostgreSQL 스키마 초기화 중..."
    if [ -f "scripts/init_postgres_schema.py" ]; then
        chmod +x scripts/init_postgres_schema.py
        export DATABASE_URL=postgresql://proxmox:proxmox123@localhost:5432/proxmox_manager
        python scripts/init_postgres_schema.py
        
        if [ $? -eq 0 ]; then
            log_success "PostgreSQL 스키마 초기화 완료"
        else
            log_warning "PostgreSQL 스키마 초기화 실패 (수동 실행 필요)"
        fi
    else
        log_warning "PostgreSQL 스키마 초기화 스크립트를 찾을 수 없습니다"
    fi

    log_success "PostgreSQL (Docker) 설치 및 시작 완료"
}

# ========================================
# 11. 데이터베이스 초기화
# ========================================

setup_database() {
    log_step "11. 데이터베이스 초기화 중..."
    
    # PostgreSQL 사용 시 스키마 초기화는 이미 완료됨
    if [ -n "$DATABASE_URL" ] && [[ "$DATABASE_URL" == postgresql* ]]; then
        log_info "PostgreSQL 데이터베이스 사용 중 - 스키마 초기화는 이미 완료됨"
        log_success "PostgreSQL 데이터베이스 초기화 완료"
        return 0
    fi
    
    # SQLite 사용 시 (폴백) - PostgreSQL 사용 시에는 실행되지 않음
    log_info "SQLite 데이터베이스 초기화 중 (PostgreSQL 사용 시에는 실행되지 않음)..."
    
    # instance 디렉토리 생성 (SQLite용)
    if [ ! -d "instance" ]; then
        log_info "instance 디렉토리 생성 중..."
        mkdir -p instance
    fi
    
    # 기존 SQLite 데이터베이스 백업 (재설치 지원)
    if [ -f "instance/proxmox_manager.db" ]; then
        log_info "기존 SQLite 데이터베이스 백업 중..."
        cp instance/proxmox_manager.db instance/proxmox_manager.db.backup.$(date +%Y%m%d_%H%M%S)
        log_success "SQLite 데이터베이스 백업 완료"
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # SQLite 데이터베이스 테이블 생성
    if [ -f "scripts/create_tables.py" ]; then
        log_info "SQLite 데이터베이스 테이블 생성 중..."
        python3 scripts/create_tables.py
        
        if [ $? -eq 0 ]; then
            log_success "SQLite 데이터베이스 테이블 생성 완료"
            
            # SQLite 데이터베이스 파일 확인
            if [ -f "instance/proxmox_manager.db" ]; then
                log_success "SQLite 데이터베이스 파일 생성 확인: instance/proxmox_manager.db"
            else
                log_warning "SQLite 데이터베이스 파일이 생성되지 않았습니다"
            fi
        else
            log_warning "SQLite 데이터베이스 테이블 생성 실패 (계속 진행)"
        fi
    else
        log_error "create_tables.py 파일을 찾을 수 없습니다"
        exit 1
    fi
    
    log_success "데이터베이스 초기화 완료"
}

# ========================================
# 12. 보안 설정
# ========================================

setup_security() {
    log_step "12. 보안 설정 중..."
    
    # 방화벽 설정 (RedHat 계열)
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        if command -v firewall-cmd &> /dev/null; then
            log_info "방화벽 포트 설정 중..."
            sudo firewall-cmd --permanent --add-port=5000/tcp  # Flask
            sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
            sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
            sudo firewall-cmd --permanent --add-port=8200/tcp  # Vault
            sudo firewall-cmd --reload
            log_success "방화벽 설정 완료"
        fi
    fi
    
    # Docker 네트워크 Trust Zone 등록
    if command -v firewall-cmd &> /dev/null; then
        log_info "Docker 네트워크 Trust Zone 등록 중..."
        
        # 모든 Docker 네트워크를 Trust Zone에 등록
        for network in $(docker network ls --format "{{.Name}}" | grep -v "bridge\|host\|none"); do
            NETWORK_SUBNET=$(docker network inspect "$network" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "")
            if [ -n "$NETWORK_SUBNET" ]; then
                log_info "Docker 네트워크 Trust Zone 등록: $network ($NETWORK_SUBNET)"
                sudo firewall-cmd --permanent --add-source="$NETWORK_SUBNET" --zone=trusted
            fi
        done
        
        # 방화벽 재로드
        sudo firewall-cmd --reload
        log_success "Docker 네트워크 Trust Zone 등록 완료"
    fi
    
    # SSH 키 생성 (없는 경우)
    if [ ! -f ~/.ssh/id_rsa ]; then
        log_info "SSH 키 생성 중..."
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
        log_success "SSH 키 생성 완료"
    fi
    
    log_success "보안 설정 완료"
}

# ========================================
# 13. 서비스 시작
# ========================================

start_services() {
    log_step "13. 서비스 시작 중..."
    
    # Vault 서비스 시작
    if [ -f "docker-compose.vault.yaml" ]; then
        log_info "Vault 서비스 시작 중..."
        docker-compose -f docker-compose.vault.yaml up -d
        
        if [ $? -eq 0 ]; then
            log_success "Vault 서비스 시작 완료"
        else
            log_warning "Vault 서비스 시작 실패"
        fi
    elif [ -f "docker-compose.vault.yaml" ]; then
        log_info "Vault 서비스 시작 중..."
        
        # Vault 데이터 볼륨 확인 및 생성
        if ! docker volume ls | grep -q vault-data; then
            log_info "Vault 데이터 볼륨 생성 중..."
            docker volume create vault-data
        fi
        
        docker-compose -f docker-compose.vault.yaml up -d
        
        if [ $? -eq 0 ]; then
            log_success "Vault 서비스 시작 완료"
        else
            log_warning "Vault 서비스 시작 실패"
        fi
    fi
    
    # Vault 초기화 및 Unseal 자동화
    log_info "Vault 초기화 및 Unseal 설정 중..."
    
    # Vault 서비스가 완전히 시작될 때까지 대기
    log_info "Vault 서비스 초기화 대기 중..."
    sleep 15
    
    # Vault 상태 확인 및 초기화
    if docker ps | grep -q vault-dev; then
        log_info "Vault 상태 확인 중..."
        
        # Vault 초기화 상태 확인
        VAULT_INIT_STATUS=$(docker exec vault-dev vault status 2>/dev/null | grep "Initialized" | awk '{print $2}')
        
        if [ "$VAULT_INIT_STATUS" = "true" ]; then
            log_info "Vault가 이미 초기화되어 있습니다."
            
            # Vault Unseal 상태 확인
            VAULT_SEALED=$(docker exec vault-dev vault status 2>/dev/null | grep "Sealed" | awk '{print $2}')
            
            if [ "$VAULT_SEALED" = "true" ]; then
                log_info "Vault가 sealed 상태입니다. Unseal을 진행합니다..."
                
                # Unseal 키 파일 확인
                if [ -f "vault_unseal_keys.txt" ]; then
                    log_info "저장된 Unseal 키를 사용합니다..."
                    UNSEAL_KEY=$(cat vault_unseal_keys.txt)
                    
                    # Vault Unseal 실행
                    if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                        log_success "Vault Unseal 성공"
                    else
                        log_error "Vault Unseal 실패"
                    fi
                elif [ -f "vault_init.txt" ]; then
                    log_info "vault_init.txt에서 Unseal 키를 추출합니다..."
                    UNSEAL_KEY=$(grep "Unseal Key 1:" vault_init.txt | awk '{print $4}')
                    
                    if [ -n "$UNSEAL_KEY" ]; then
                        # Unseal 키를 별도 파일에 저장
                        echo "$UNSEAL_KEY" > vault_unseal_keys.txt
                        chmod 600 vault_unseal_keys.txt
                        log_success "Unseal 키를 vault_unseal_keys.txt에 저장했습니다."
                        
                        # Vault Unseal 실행
                        if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                            log_success "Vault Unseal 성공"
                        else
                            log_error "Vault Unseal 실패"
                        fi
                    else
                        log_error "vault_init.txt에서 Unseal 키를 찾을 수 없습니다."
                    fi
                else
                    log_warning "Unseal 키 파일이 없습니다. Vault를 다시 초기화합니다."
                    
                    # Vault 재초기화 시 사용자 입력 받기
                    echo ""
                    echo -e "${YELLOW}🔐 Vault 재초기화를 위한 정보를 입력해주세요:${NC}"
                    echo ""
                    
                    # Proxmox 비밀번호 입력
                    read -p "Proxmox root 비밀번호를 입력하세요: " -s PROXMOX_PASSWORD
                    echo ""
                    
                    # VM 비밀번호 입력
                    read -p "VM 기본 비밀번호를 입력하세요: " -s VM_PASSWORD
                    echo ""
                    
                    # Vault 볼륨 권한 설정 (권한 문제 해결)
                    log_info "Vault 볼륨 권한 설정 중..."
                    docker exec vault-dev sh -c "mkdir -p /vault/data && chmod 755 /vault/data" 2>/dev/null || true
                    
                    # Vault 재초기화 실행
                    log_info "Vault 재초기화 실행 중..."
                    VAULT_INIT_OUTPUT=$(docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 2>/dev/null)
                    
                    if [ $? -eq 0 ]; then
                        VAULT_TOKEN=$(echo "$VAULT_INIT_OUTPUT" | grep "Initial Root Token:" | awk '{print $4}')
                        UNSEAL_KEY=$(echo "$VAULT_INIT_OUTPUT" | grep "Unseal Key 1:" | awk '{print $4}')
                        
                        # 토큰과 Unseal 키를 파일에 저장
                        echo "$VAULT_TOKEN" > vault_token.txt
                        echo "$UNSEAL_KEY" > vault_unseal_keys.txt
                        chmod 600 vault_token.txt
                        chmod 600 vault_unseal_keys.txt
                        
                        log_success "Vault 재초기화 완료 및 키 저장"
                        
                        # 환경변수에 토큰 설정
                        export VAULT_TOKEN="$VAULT_TOKEN"
                        export TF_VAR_vault_token="$VAULT_TOKEN"
                        
                        # .env 파일에 토큰 업데이트
                        if [ -f ".env" ]; then
                            sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                            sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                        fi
                        
                        # Vault 시크릿 설정 (Base64 암호화)
                        log_info "Vault 시크릿 설정 중 (Base64 암호화)..."
                        
                        # Proxmox 비밀번호 Base64 암호화
                        PROXMOX_PASSWORD_B64=$(echo -n "$PROXMOX_PASSWORD" | base64)
                        VM_PASSWORD_B64=$(echo -n "$VM_PASSWORD" | base64)
                        
                        # Vault에 시크릿 저장
                        docker exec vault-dev vault kv put secret/proxmox username=root@pam password="$PROXMOX_PASSWORD_B64" password_plain="$PROXMOX_PASSWORD"
                        docker exec vault-dev vault kv put secret/vm username=rocky password="$VM_PASSWORD_B64" password_plain="$VM_PASSWORD"
                        
                        log_success "Vault 시크릿 설정 완료 (Base64 암호화)"
                        
                        # 중요 정보 출력
                        echo ""
                        echo -e "${CYAN}📋 Vault 재초기화 완료 정보:${NC}"
                        echo "  Vault Token: $VAULT_TOKEN"
                        echo "  Unseal Key: $UNSEAL_KEY"
                        echo "  Proxmox Password (Base64): $PROXMOX_PASSWORD_B64"
                        echo "  VM Password (Base64): $VM_PASSWORD_B64"
                        echo ""
                        echo -e "${YELLOW}⚠️  중요: 이 정보들을 안전한 곳에 보관하세요!${NC}"
                        echo ""
                        
                    else
                        log_error "Vault 재초기화 실패"
                        exit 1
                    fi
                fi
            else
                log_success "Vault가 이미 unsealed 상태입니다."
            fi
            
            # 토큰 복원
            if [ -f "vault_token.txt" ]; then
                VAULT_TOKEN=$(cat vault_token.txt)
                export VAULT_TOKEN="$VAULT_TOKEN"
                export TF_VAR_vault_token="$VAULT_TOKEN"
                
                # .env 파일에 토큰 업데이트
                if [ -f ".env" ]; then
                    sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                    sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                    log_success "Vault 토큰이 .env 파일에 업데이트되었습니다."
                fi
            elif [ -f "vault_init.txt" ]; then
                log_info "vault_init.txt에서 Vault 토큰을 추출합니다..."
                VAULT_TOKEN=$(grep "Initial Root Token:" vault_init.txt | awk '{print $4}')
                
                if [ -n "$VAULT_TOKEN" ]; then
                    # 토큰을 별도 파일에 저장
                    echo "$VAULT_TOKEN" > vault_token.txt
                    chmod 600 vault_token.txt
                    log_success "Vault 토큰을 vault_token.txt에 저장했습니다."
                    
                    export VAULT_TOKEN="$VAULT_TOKEN"
                    export TF_VAR_vault_token="$VAULT_TOKEN"
                    
                    # .env 파일에 토큰 업데이트
                    if [ -f ".env" ]; then
                        sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                        sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                        log_success "Vault 토큰이 .env 파일에 업데이트되었습니다."
                    fi
                else
                    log_error "vault_init.txt에서 Vault 토큰을 찾을 수 없습니다."
                fi
            fi
            
            # Vault 시크릿 설정 확인
            log_info "Vault 시크릿 설정 확인 중..."
            
            # Proxmox 시크릿 확인
            if ! docker exec vault-dev vault kv get secret/proxmox 2>/dev/null | grep -q "password"; then
                log_info "Proxmox 시크릿을 Vault에 저장 중..."
                docker exec vault-dev vault kv put secret/proxmox username=root@pam password=YzaxdJOA2j9Itv8S
                log_success "Proxmox 시크릿 저장 완료"
            else
                log_info "Proxmox 시크릿이 이미 존재합니다."
            fi
            
            # VM 시크릿 확인
            if ! docker exec vault-dev vault kv get secret/vm 2>/dev/null | grep -q "password"; then
                log_info "VM 시크릿을 Vault에 저장 중..."
                docker exec vault-dev vault kv put secret/vm username=rocky password=rocky123
                log_success "VM 시크릿 저장 완료"
            else
                log_info "VM 시크릿이 이미 존재합니다."
            fi
            
        else
            log_info "Vault 초기화 중..."
            
            # Vault 초기화 시 사용자 입력 받기
            echo ""
            echo -e "${YELLOW}🔐 Vault 초기화를 위한 정보를 입력해주세요:${NC}"
            echo ""
            
            # Proxmox 비밀번호 입력
            read -p "Proxmox root 비밀번호를 입력하세요: " -s PROXMOX_PASSWORD
            echo ""
            
            # VM 비밀번호 입력
            read -p "VM 기본 비밀번호를 입력하세요: " -s VM_PASSWORD
            echo ""
            
            # Vault 볼륨 권한 설정 (권한 문제 해결)
            log_info "Vault 볼륨 권한 설정 중..."
            docker exec vault-dev sh -c "mkdir -p /vault/data && chmod 755 /vault/data" 2>/dev/null || true
            
            # Vault 초기화 실행
            log_info "Vault 초기화 실행 중..."
            VAULT_INIT_OUTPUT=$(docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 2>/dev/null)
            
            if [ $? -eq 0 ]; then
                VAULT_TOKEN=$(echo "$VAULT_INIT_OUTPUT" | grep "Initial Root Token:" | awk '{print $4}')
                UNSEAL_KEY=$(echo "$VAULT_INIT_OUTPUT" | grep "Unseal Key 1:" | awk '{print $4}')
                
                # 토큰과 Unseal 키를 파일에 저장
                echo "$VAULT_TOKEN" > vault_token.txt
                echo "$UNSEAL_KEY" > vault_unseal_keys.txt
                chmod 600 vault_token.txt
                chmod 600 vault_unseal_keys.txt
                
                log_success "Vault 초기화 완료 및 키 저장"
                
                # 환경변수에 토큰 설정
                export VAULT_TOKEN="$VAULT_TOKEN"
                export TF_VAR_vault_token="$VAULT_TOKEN"
                
                # .env 파일에 토큰 업데이트
                if [ -f ".env" ]; then
                    sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                    sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                fi
                
                # Vault 시크릿 설정 (Base64 암호화)
                log_info "Vault 시크릿 설정 중 (Base64 암호화)..."
                
                # Proxmox 비밀번호 Base64 암호화
                PROXMOX_PASSWORD_B64=$(echo -n "$PROXMOX_PASSWORD" | base64)
                VM_PASSWORD_B64=$(echo -n "$VM_PASSWORD" | base64)
                
                # Vault에 시크릿 저장
                docker exec vault-dev vault kv put secret/proxmox username=root@pam password="$PROXMOX_PASSWORD_B64" password_plain="$PROXMOX_PASSWORD"
                docker exec vault-dev vault kv put secret/vm username=rocky password="$VM_PASSWORD_B64" password_plain="$VM_PASSWORD"
                
                log_success "Vault 시크릿 설정 완료 (Base64 암호화)"
                
                # 중요 정보 출력
                echo ""
                echo -e "${CYAN}📋 Vault 초기화 완료 정보:${NC}"
                echo "  Vault Token: $VAULT_TOKEN"
                echo "  Unseal Key: $UNSEAL_KEY"
                echo "  Proxmox Password (Base64): $PROXMOX_PASSWORD_B64"
                echo "  VM Password (Base64): $VM_PASSWORD_B64"
                echo ""
                echo -e "${YELLOW}⚠️  중요: 이 정보들을 안전한 곳에 보관하세요!${NC}"
                echo ""
                
            else
                log_error "Vault 초기화 실패"
                exit 1
            fi
        fi
        
        log_success "Vault 초기화 및 Unseal 설정 완료"
    else
        log_warning "Vault 컨테이너가 실행되지 않았습니다."
    fi
    
    # Flask 애플리케이션 systemd 서비스 등록
    log_info "Flask 애플리케이션 systemd 서비스 등록 중..."
    
    # 현재 디렉토리 경로 가져오기
    APP_DIR=$(pwd)
    VENV_PYTHON="$APP_DIR/venv/bin/python"
    
    # 가상환경 Python 경로 확인
    if [ ! -f "$VENV_PYTHON" ]; then
        log_error "가상환경을 찾을 수 없습니다. Python 패키지 설치를 먼저 완료하세요."
        log_error "가상환경 경로: $VENV_PYTHON"
        exit 1
    else
        log_info "가상환경 Python 사용: $VENV_PYTHON"
        
        # 가상환경에서 필수 패키지 확인
        log_info "가상환경 패키지 확인 중..."
        if ! $VENV_PYTHON -c "import dotenv" 2>/dev/null; then
            log_warning "python-dotenv가 설치되지 않았습니다. 설치 중..."
            $VENV_PYTHON -m pip install python-dotenv
        fi
        
        if ! $VENV_PYTHON -c "import flask" 2>/dev/null; then
            log_warning "Flask가 설치되지 않았습니다. 설치 중..."
            $VENV_PYTHON -m pip install flask flask-sqlalchemy flask-login
        fi
        
        if ! $VENV_PYTHON -c "import requests" 2>/dev/null; then
            log_warning "requests가 설치되지 않았습니다. 설치 중..."
            $VENV_PYTHON -m pip install requests
        fi
    fi
    
    # 가상환경 Python 실행 권한 확인 및 설정
    log_info "가상환경 Python 실행 권한 설정 중..."
    
    # 가상환경 Python 파일 권한 확인
    if [ -f "$VENV_PYTHON" ]; then
        CURRENT_PERMS=$(ls -l "$VENV_PYTHON" | awk '{print $1}')
        log_info "현재 Python 파일 권한: $CURRENT_PERMS"
        
        # 실행 권한이 없는 경우에만 설정 시도
        if [[ ! "$CURRENT_PERMS" =~ x ]]; then
            log_info "실행 권한이 없습니다. 권한 설정 시도 중..."
            if chmod +x "$VENV_PYTHON" 2>/dev/null; then
                log_success "Python 파일 실행 권한 설정 완료"
            else
                log_warning "Python 파일 권한 설정 실패 (계속 진행)"
                log_info "가상환경 재생성을 시도합니다..."
                
                # 가상환경 재생성
                log_info "기존 가상환경 백업 중..."
                if [ -d "venv" ]; then
                    mv venv venv.backup.$(date +%Y%m%d_%H%M%S)
                fi
                
                log_info "새 가상환경 생성 중..."
                if command -v python3.12 &> /dev/null; then
                    python3.12 -m venv venv
                elif command -v python3 &> /dev/null; then
                    python3 -m venv venv
                else
                    log_error "Python을 찾을 수 없습니다"
                    exit 1
                fi
                
                # 새 가상환경에서 Python 패키지 재설치
                log_info "가상환경 활성화 및 패키지 재설치 중..."
                source venv/bin/activate
                pip install -r requirements.txt
                
                # 새 Python 경로 업데이트
                VENV_PYTHON="$APP_DIR/venv/bin/python"
                log_info "새 가상환경 Python 경로: $VENV_PYTHON"
            fi
        else
            log_success "Python 파일에 이미 실행 권한이 있습니다"
        fi
    else
        log_error "가상환경 Python 파일을 찾을 수 없습니다: $VENV_PYTHON"
        exit 1
    fi
    
    # config.py 파일 자동 생성 (TerraformConfig 클래스 포함)
    log_info "config.py 파일 자동 생성 중..."
    cat > config/config.py << 'EOF'
import os
from datetime import timedelta

class VaultConfig:
    """Vault 설정"""
    VAULT_ADDR = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN')
    
    @classmethod
    def get_secret(cls, secret_path, key):
        """Vault에서 시크릿 가져오기"""
        try:
            import hvac
            client = hvac.Client(url=cls.VAULT_ADDR, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(path=secret_path)
                return response['data']['data'].get(key)
            else:
                raise ValueError("Vault 인증 실패")
        except ImportError:
            # hvac 패키지가 없으면 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')
        except Exception as e:
            print(f"Vault에서 시크릿 가져오기 실패: {e}")
            # 폴백: 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')


class TerraformConfig:
    """Terraform 변수 자동 매핑"""
    
    # 환경변수 → Terraform 변수 매핑 (.env 파일 기반)
    MAPPINGS = {
        'VAULT_TOKEN': 'TF_VAR_vault_token',
        'VAULT_ADDR': 'TF_VAR_vault_address',
        'PROXMOX_ENDPOINT': 'TF_VAR_proxmox_endpoint',
        'PROXMOX_USERNAME': 'TF_VAR_proxmox_username',
        'PROXMOX_PASSWORD': 'TF_VAR_proxmox_password',
        'PROXMOX_NODE': 'TF_VAR_proxmox_node',
        'SSH_USER': 'TF_VAR_vm_username',
        'SSH_PUBLIC_KEY_PATH': 'TF_VAR_ssh_keys'
    }
    
    @classmethod
    def setup_terraform_vars(cls):
        """환경변수를 Terraform 변수로 자동 매핑"""
        for source_var, target_var in cls.MAPPINGS.items():
            value = os.getenv(source_var)
            if value and not os.getenv(target_var):
                os.environ[target_var] = value
                print(f"✅ {source_var} → {target_var}")
    
    @classmethod
    def get_terraform_var(cls, var_name):
        """Terraform 변수 가져오기"""
        return os.getenv(f'TF_VAR_{var_name}')
    
    @classmethod
    def get_all_terraform_vars(cls):
        """모든 Terraform 변수 가져오기"""
        return {k: v for k, v in os.environ.items() if k.startswith('TF_VAR_')}
    
    @classmethod
    def validate_terraform_vars(cls):
        """Terraform 변수 검증"""
        required_vars = ['vault_token', 'vault_address', 'proxmox_endpoint', 'proxmox_username', 'proxmox_password']
        missing_vars = []
        
        for var in required_vars:
            if not cls.get_terraform_var(var):
                missing_vars.append(f'TF_VAR_{var}')
        
        if missing_vars:
            print(f"⚠️ 누락된 Terraform 변수: {', '.join(missing_vars)}")
            return False
        
        print("✅ 모든 필수 Terraform 변수가 설정되었습니다")
        return True
    
    @classmethod
    def debug_terraform_vars(cls):
        """Terraform 변수 디버깅 정보 출력"""
        print("🔧 Terraform 변수 상태:")
        for source_var, target_var in cls.MAPPINGS.items():
            source_value = os.getenv(source_var, '❌ 없음')
            target_value = os.getenv(target_var, '❌ 없음')
            print(f"  {source_var}: {'✅ 설정됨' if source_value != '❌ 없음' else '❌ 없음'}")
            print(f"  {target_var}: {'✅ 설정됨' if target_value != '❌ 없음' else '❌ 없음'}")
            print()


class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # SQLAlchemy 설정
    basedir = os.path.abspath(os.path.dirname(__file__))
    # 프로젝트 루트 디렉토리로 이동 (config 디렉토리의 상위)
    project_root = os.path.dirname(basedir)
    instance_dir = os.path.join(project_root, "instance")
    
    # instance 디렉토리가 없으면 생성
    if not os.path.exists(instance_dir):
        try:
            os.makedirs(instance_dir, mode=0o755, exist_ok=True)
        except Exception as e:
            print(f"⚠️ instance 디렉토리 생성 실패: {e}")
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(instance_dir, "proxmox_manager.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Proxmox 설정 (환경 변수 필수)
    PROXMOX_ENDPOINT = os.environ.get('PROXMOX_ENDPOINT', 'https://localhost:8006')
    PROXMOX_USERNAME = os.environ.get('PROXMOX_USERNAME', 'root@pam')
    PROXMOX_PASSWORD = os.environ.get('PROXMOX_PASSWORD', 'password')
    PROXMOX_NODE = os.environ.get('PROXMOX_NODE', 'pve')
    PROXMOX_DATASTORE = os.environ.get('PROXMOX_DATASTORE', 'local-lvm')
    
    # 세션 보안 설정
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Strict')
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 28800))  # 8시간으로 연장
    )
    
    # 로깅 설정
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
    
    # SSH 설정
    SSH_PRIVATE_KEY_PATH = os.environ.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
    SSH_PUBLIC_KEY_PATH = os.environ.get('SSH_PUBLIC_KEY_PATH', '~/.ssh/id_rsa.pub')
    SSH_USER = os.environ.get('SSH_USER', 'rocky')
    
    # 모니터링 설정 (환경 변수)
    GRAFANA_URL = os.environ.get('GRAFANA_URL', 'http://localhost:3000')
    GRAFANA_USERNAME = os.environ.get('GRAFANA_USERNAME', 'admin')
    GRAFANA_PASSWORD = os.environ.get('GRAFANA_PASSWORD', 'admin')
    GRAFANA_ORG_ID = os.environ.get('GRAFANA_ORG_ID', '1')
    GRAFANA_DASHBOARD_UID = os.environ.get('GRAFANA_DASHBOARD_UID', 'system_monitoring')
    GRAFANA_ANONYMOUS_ACCESS = os.environ.get('GRAFANA_ANONYMOUS_ACCESS', 'false').lower() == 'true'
    GRAFANA_AUTO_REFRESH = os.environ.get('GRAFANA_AUTO_REFRESH', '5s')
    
    PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    PROMETHEUS_USERNAME = os.environ.get('PROMETHEUS_USERNAME', '')
    PROMETHEUS_PASSWORD = os.environ.get('PROMETHEUS_PASSWORD', '')
    
    NODE_EXPORTER_AUTO_INSTALL = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
    NODE_EXPORTER_PORT = int(os.environ.get('NODE_EXPORTER_PORT', '9100'))
    NODE_EXPORTER_VERSION = os.environ.get('NODE_EXPORTER_VERSION', '1.6.1')
    
    MONITORING_DEFAULT_TIME_RANGE = os.environ.get('MONITORING_DEFAULT_TIME_RANGE', '1h')
    MONITORING_HEALTH_CHECK_INTERVAL = os.environ.get('MONITORING_HEALTH_CHECK_INTERVAL', '30s')
    MONITORING_PING_TIMEOUT = os.environ.get('MONITORING_PING_TIMEOUT', '5s')
    MONITORING_SSH_TIMEOUT = os.environ.get('MONITORING_SSH_TIMEOUT', '10s')
    
    ALERTS_ENABLED = os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true'
    ALERTS_EMAIL = os.environ.get('ALERTS_EMAIL', 'admin@example.com')
    ALERTS_CPU_WARNING_THRESHOLD = float(os.environ.get('ALERTS_CPU_WARNING_THRESHOLD', '80'))
    ALERTS_CPU_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_CPU_CRITICAL_THRESHOLD', '95'))
    ALERTS_MEMORY_WARNING_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_WARNING_THRESHOLD', '85'))
    ALERTS_MEMORY_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_CRITICAL_THRESHOLD', '95'))
    
    SECURITY_ENABLE_HTTPS = os.environ.get('SECURITY_ENABLE_HTTPS', 'false').lower() == 'true'
    SECURITY_ENABLE_AUTH = os.environ.get('SECURITY_ENABLE_AUTH', 'true').lower() == 'true'
    SECURITY_SESSION_TIMEOUT = int(os.environ.get('SECURITY_SESSION_TIMEOUT', '3600'))
    SECURITY_MAX_LOGIN_ATTEMPTS = int(os.environ.get('SECURITY_MAX_LOGIN_ATTEMPTS', '5'))

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

# 환경별 설정 매핑
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
EOF
    
    log_success "config.py 파일 생성 완료"
    
    # 필수 패키지 설치 확인 및 재설치 (완전 자동화)
    log_info "필수 패키지 설치 확인 중..."
    
    # 가상환경 활성화 및 패키지 설치를 위한 스크립트 생성
    cat > fix_venv.sh << 'EOF'
#!/bin/bash
# 현재 디렉토리에서 실행

# 가상환경 활성화
source venv/bin/activate

# 필수 패키지 설치
pip install python-dotenv flask flask-sqlalchemy flask-login requests paramiko

# 가상환경 비활성화
deactivate

echo "가상환경 패키지 설치 완료"
EOF
    
    chmod +x fix_venv.sh
    
    # 가상환경 패키지 설치 실행
    log_info "가상환경 패키지 자동 설치 중..."
    if ./fix_venv.sh; then
        log_success "가상환경 패키지 설치 완료"
    else
        log_warning "가상환경 패키지 설치 실패, 수동 설치 시도 중..."
        
        # 수동 설치 시도
        if ! $VENV_PYTHON -c "import dotenv" 2>/dev/null; then
            log_warning "python-dotenv가 설치되지 않았습니다. 재설치 중..."
            $VENV_PYTHON -m pip install python-dotenv
        fi
        
        if ! $VENV_PYTHON -c "import flask" 2>/dev/null; then
            log_warning "Flask가 설치되지 않았습니다. 재설치 중..."
            $VENV_PYTHON -m pip install flask flask-sqlalchemy flask-login
        fi
        
        if ! $VENV_PYTHON -c "import requests" 2>/dev/null; then
            log_warning "requests가 설치되지 않았습니다. 재설치 중..."
            $VENV_PYTHON -m pip install requests
        fi
    fi
    
    # 임시 스크립트 정리
    rm -f fix_venv.sh
    
    # run.py 파일 권한 설정
    if [ -f "$APP_DIR/run.py" ]; then
        chmod +x "$APP_DIR/run.py" 2>/dev/null || log_warning "run.py 권한 설정 실패"
    fi
    
    # systemd 서비스 파일 생성 (가상환경 문제 해결)
    sudo tee /etc/systemd/system/proxmox-manager.service > /dev/null << EOF
[Unit]
Description=Proxmox Manager Flask Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=VIRTUAL_ENV=$APP_DIR/venv
Environment=PYTHONPATH=$APP_DIR
ExecStart=$VENV_PYTHON run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# 보안 설정 (권한 문제 해결을 위해 일부 완화)
NoNewPrivileges=true
PrivateTmp=false
ProtectSystem=false
ProtectHome=false
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    # 서비스 등록 및 시작
    log_info "Flask 애플리케이션 서비스 시작 중..."
    sudo systemctl daemon-reload
    sudo systemctl enable proxmox-manager
    
    # 서비스 시작 전 기본 검증
    log_info "서비스 시작 전 기본 검증 중..."
    
    # 가상환경 Python 실행 테스트
    if ! $VENV_PYTHON -c "import dotenv, flask, requests" 2>/dev/null; then
        log_warning "가상환경 패키지 문제 감지. 수동으로 해결하세요:"
        log_warning "  source venv/bin/activate"
        log_warning "  pip install --upgrade python-dotenv flask flask-sqlalchemy flask-login requests"
        log_warning "  deactivate"
    fi
    
    # 서비스 시작 시도 (재시도 로직 포함)
    MAX_RETRIES=3
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        log_info "서비스 시작 시도 $((RETRY_COUNT + 1))/$MAX_RETRIES"
        
        if sudo systemctl start proxmox-manager; then
            log_success "Flask 애플리케이션 서비스 시작 완료"
            
            # 서비스 상태 확인
            sleep 5
            if sudo systemctl is-active --quiet proxmox-manager; then
                log_success "Flask 애플리케이션 서비스가 정상적으로 실행 중입니다"
                log_info "서비스 상태: $(sudo systemctl is-active proxmox-manager)"
                break
            else
                log_warning "서비스가 시작되었지만 상태가 불안정합니다. 재시도 중..."
                sudo systemctl stop proxmox-manager
                sleep 2
            fi
        else
            log_warning "서비스 시작 실패. 재시도 중..."
            sleep 3
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done
    
    # 최종 상태 확인
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        log_error "Flask 애플리케이션 서비스 시작 실패 (최대 재시도 횟수 초과)"
        log_info "서비스 로그를 확인하세요: sudo journalctl -u proxmox-manager -n 20"
        log_info "수동으로 다음 명령어를 실행해보세요:"
        log_info "  sudo systemctl restart proxmox-manager"
        log_info "  sudo systemctl status proxmox-manager"
        exit 1
    fi
    
    log_success "서비스 시작 완료"
    
    # 자동 복구 스크립트 생성 (사용자가 systemctl start만 해도 문제 해결)
    log_info "자동 복구 스크립트 생성 중..."
    sudo tee /usr/local/bin/proxmox-manager-fix > /dev/null << 'EOF'
#!/bin/bash
# Proxmox Manager 자동 복구 스크립트
# 사용법: sudo systemctl start proxmox-manager (자동으로 이 스크립트가 실행됨)

# Proxmox Manager 프로젝트 디렉토리로 이동
cd /data/terraform-proxmox || {
    echo "❌ Proxmox Manager 디렉토리를 찾을 수 없습니다: /data/terraform-proxmox"
    exit 1
}

echo "🔧 Proxmox Manager 자동 복구 시작..."
echo "📁 작업 디렉토리: $(pwd)"

# Vault Unseal 및 토큰 복원
echo "🔐 Vault Unseal 및 토큰 복원 중..."

# Vault 상태 확인
if docker ps | grep -q vault-dev; then
    VAULT_SEALED=$(docker exec vault-dev vault status 2>/dev/null | grep "Sealed" | awk '{print $2}')
    
    if [ "$VAULT_SEALED" = "true" ]; then
        echo "⚠️ Vault가 sealed 상태입니다. Unseal을 진행합니다..."
        
        # Unseal 키 파일 확인
        if [ -f "vault_unseal_keys.txt" ]; then
            echo "📋 저장된 Unseal 키를 사용합니다..."
            UNSEAL_KEY=$(cat vault_unseal_keys.txt)
            
            # Vault Unseal 실행
            if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                echo "✅ Vault Unseal 성공"
            else
                echo "❌ Vault Unseal 실패"
            fi
        elif [ -f "vault_init.txt" ]; then
            echo "📋 vault_init.txt에서 Unseal 키를 추출합니다..."
            UNSEAL_KEY=$(grep "Unseal Key 1:" vault_init.txt | awk '{print $4}')
            
            if [ -n "$UNSEAL_KEY" ]; then
                # Unseal 키를 별도 파일에 저장
                echo "$UNSEAL_KEY" > vault_unseal_keys.txt
                chmod 600 vault_unseal_keys.txt
                echo "✅ Unseal 키를 vault_unseal_keys.txt에 저장했습니다."
                
                # Vault Unseal 실행
                if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                    echo "✅ Vault Unseal 성공"
                else
                    echo "❌ Vault Unseal 실패"
                fi
            else
                echo "❌ vault_init.txt에서 Unseal 키를 찾을 수 없습니다."
            fi
        else
            echo "❌ Unseal 키 파일이 없습니다:"
            echo "  - vault_unseal_keys.txt"
            echo "  - vault_init.txt"
        fi
    else
        echo "✅ Vault가 이미 unsealed 상태입니다."
    fi
    
    # 토큰 복원
    if [ -f "vault_token.txt" ]; then
        VAULT_TOKEN=$(cat vault_token.txt)
        export VAULT_TOKEN="$VAULT_TOKEN"
        export TF_VAR_vault_token="$VAULT_TOKEN"
        
        # .env 파일에 토큰 업데이트
        if [ -f ".env" ]; then
            sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
            sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
        fi
        
        echo "✅ Vault 토큰 복원 완료"
    elif [ -f "vault_init.txt" ]; then
        echo "📋 vault_init.txt에서 Vault 토큰을 추출합니다..."
        VAULT_TOKEN=$(grep "Initial Root Token:" vault_init.txt | awk '{print $4}')
        
        if [ -n "$VAULT_TOKEN" ]; then
            # 토큰을 별도 파일에 저장
            echo "$VAULT_TOKEN" > vault_token.txt
            chmod 600 vault_token.txt
            echo "✅ Vault 토큰을 vault_token.txt에 저장했습니다."
            
            export VAULT_TOKEN="$VAULT_TOKEN"
            export TF_VAR_vault_token="$VAULT_TOKEN"
            
            # .env 파일에 토큰 업데이트
            if [ -f ".env" ]; then
                sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
            fi
            
            echo "✅ Vault 토큰 복원 완료"
        else
            echo "❌ vault_init.txt에서 Vault 토큰을 찾을 수 없습니다."
        fi
    else
        echo "⚠️ 저장된 Vault 토큰이 없습니다:"
        echo "  - vault_token.txt"
        echo "  - vault_init.txt"
    fi
else
    echo "⚠️ Vault 컨테이너가 실행되지 않았습니다."
fi

# 가상환경 패키지 문제 해결
# 현재 디렉토리에서 실행되므로 상대 경로 사용
if ! ./venv/bin/python -c "import dotenv, flask, requests" 2>/dev/null; then
    echo "⚠️  가상환경 패키지 문제 감지. 수동으로 해결하세요:"
    echo "  cd /data/terraform-proxmox"
    echo "  source venv/bin/activate"
    echo "  pip install --upgrade python-dotenv flask flask-sqlalchemy flask-login requests paramiko"
    echo "  deactivate"
    echo "  sudo systemctl restart proxmox-manager"
fi

# 데이터베이스 디렉토리 및 권한 설정
echo "🗄️ 데이터베이스 디렉토리 설정 중..."
mkdir -p instance
chmod 755 instance
chown $USER:$USER instance 2>/dev/null || true

# 데이터베이스 파일 권한 설정 (존재하는 경우)
if [ -f "instance/proxmox_manager.db" ]; then
    chmod 664 instance/proxmox_manager.db
    chown $USER:$USER instance/proxmox_manager.db 2>/dev/null || true
    echo "✅ 데이터베이스 파일 권한 설정 완료"
else
    echo "ℹ️ 데이터베이스 파일이 아직 생성되지 않았습니다 (정상)"
fi

# config.py import 문제 해결
echo "🔍 config.py import 테스트 중..."
if ! ./venv/bin/python -c "import sys; sys.path.insert(0, '.'); from config.config import TerraformConfig" 2>/dev/null; then
    echo "⚠️  config.py import 문제 감지. 수동으로 해결하세요:"
    echo "  cd /data/terraform-proxmox"
    echo "  mkdir -p config"
    echo "  echo '"""Config 패키지 초기화 파일"""' > config/__init__.py"
    echo "  # config.py 파일이 있는지 확인하세요"
    echo "  sudo systemctl restart proxmox-manager"
else
    echo "✅ config.py import 정상"
fi

# 데이터베이스 초기화 (필요한 경우)
echo "🗄️ 데이터베이스 초기화 확인 중..."
if [ ! -f "instance/proxmox_manager.db" ]; then
    echo "📝 데이터베이스 초기화 중..."
    ./venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from app import create_app, db
from app.models.datastore import Datastore
app = create_app()
with app.app_context():
    db.create_all()
    print('✅ 데이터베이스 초기화 완료')
    print('✅ Datastore 모델 포함됨')
" 2>/dev/null || echo "⚠️ 데이터베이스 초기화 실패 (서비스 시작 시 자동 생성됨)"
else
    echo "✅ 데이터베이스 파일이 이미 존재합니다"
    echo "🔄 기존 DB에 새로운 테이블 추가 확인 중..."
    ./venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from app import create_app, db
from app.models.datastore import Datastore
app = create_app()
with app.app_context():
    try:
        db.create_all()
        print('✅ 기존 DB에 새로운 테이블 추가 완료')
    except Exception as e:
        print(f'⚠️ DB 업데이트 중 오류: {e}')
" 2>/dev/null || echo "⚠️ DB 업데이트 실패 (서비스 시작 시 자동 처리됨)"
fi

# systemd 서비스 재시작 (sudo 없이 - systemd가 자동으로 처리)
echo "🔄 systemd 서비스 재시작 중..."
echo "ℹ️ systemd가 자동으로 서비스를 재시작합니다"

# 서비스 상태 확인 (sudo 없이)
sleep 3
if systemctl is-active --quiet proxmox-manager; then
    echo "✅ Proxmox Manager 서비스가 정상적으로 실행 중입니다"
    echo "🌐 웹 인터페이스: http://$(hostname -I | awk '{print $1}'):5000"
else
    echo "❌ 서비스 시작 실패. 로그를 확인하세요:"
    echo "   sudo journalctl -u proxmox-manager -n 20"
fi
EOF
    
    sudo chmod +x /usr/local/bin/proxmox-manager-fix
    
    # systemd 서비스에 자동 복구 스크립트 연결
    log_info "systemd 서비스에 자동 복구 기능 추가 중..."
    sudo tee /etc/systemd/system/proxmox-manager.service > /dev/null << EOF
[Unit]
Description=Proxmox Manager Flask Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=VIRTUAL_ENV=$APP_DIR/venv
Environment=PYTHONPATH=$APP_DIR
ExecStartPre=/usr/local/bin/proxmox-manager-fix
ExecStart=$VENV_PYTHON run.py
Restart=always
RestartSec=10
ExecReload=/bin/kill -HUP $MAINPID
StandardOutput=journal
StandardError=journal

# 보안 설정 (권한 문제 해결을 위해 일부 완화)
NoNewPrivileges=true
PrivateTmp=false
ProtectSystem=false
ProtectHome=false
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    
    log_success "자동 복구 스크립트 생성 완료"
    log_info "이제 'sudo systemctl start proxmox-manager'만 실행하면 모든 문제가 자동으로 해결됩니다!"
}

# ========================================
# 13.5 Celery Worker 등록/실행
# ========================================
setup_celery_worker() {
    log_step "13.5. Celery Worker 등록/실행 중..."

    APP_DIR=$(pwd)
    VENV_PYTHON="$APP_DIR/venv/bin/python"
    VENV_CELERY="$APP_DIR/venv/bin/celery"

    if [ ! -f "$VENV_CELERY" ]; then
        log_error "Celery 실행 파일을 찾을 수 없습니다: $VENV_CELERY"
        log_info "pip로 Celery 설치 후 다시 시도하세요 (requirements.txt 포함)."
        return 1
    fi

    sudo tee /etc/systemd/system/celery-worker.service > /dev/null << EOF
[Unit]
Description=Celery Worker for Proxmox Manager
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=VIRTUAL_ENV=$APP_DIR/venv
Environment=PYTHONPATH=$APP_DIR
ExecStart=$VENV_CELERY -A app.celery_app worker --loglevel=info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable celery-worker
    if sudo systemctl restart celery-worker; then
        log_success "Celery Worker 시작 완료"
    else
        log_warning "Celery Worker 시작 실패. 로그를 확인하세요: sudo journalctl -u celery-worker -n 50"
    fi
}

# ========================================
# 14. 설치 완료 및 정보 출력
# ========================================

show_completion_info() {
    log_step "14. 설치 완료!"
    
    echo -e "${GREEN}"
    echo "=========================================="
    echo "🎉 Proxmox Manager 설치 완료!"
    echo "  ✅ Docker 및 Docker Compose"
    echo "  ✅ Terraform"
    echo "  ✅ Ansible"
    echo "  ✅ HashiCorp Vault"
    echo "  ✅ Prometheus (모니터링)"
    echo "  ✅ Grafana (대시보드)"
    echo "  ✅ Node Exporter"
    echo "  ✅ Redis (캐시/큐)"
    echo "  ✅ Celery (비동기 작업)"
    echo "  ✅ PostgreSQL (데이터베이스)"
    echo "  ✅ 보안 설정"
    
    echo ""
    echo -e "${CYAN}🌐 접속 정보:${NC}"
    echo "  📱 웹 관리 콘솔: http://$(hostname -I | awk '{print $1}'):5000"
    echo "  📊 Grafana 대시보드: http://$(hostname -I | awk '{print $1}'):3000"
    echo "  📈 Prometheus: http://$(hostname -I | awk '{print $1}'):9090"
    echo "  🌸 Celery Flower: http://$(hostname -I | awk '{print $1}'):5555"
    echo "  🔐 Vault: http://$(hostname -I | awk '{print $1}'):8200"
    
    echo ""
    echo -e "${CYAN}🔧 서비스 관리 명령어:${NC}"
    echo "  Flask 애플리케이션:"
    echo "    상태 확인: sudo systemctl status proxmox-manager"
    echo "    시작: sudo systemctl start proxmox-manager"
    echo "    중지: sudo systemctl stop proxmox-manager"
    echo "    재시작: sudo systemctl restart proxmox-manager"
    echo "    로그 확인: sudo journalctl -u proxmox-manager -f"
    echo ""
    echo "  모니터링 서비스 (Docker):"
    echo "    상태 확인: cd monitoring && docker-compose ps"
    echo "    시작: cd monitoring && docker-compose up -d"
    echo "    중지: cd monitoring && docker-compose down"
    echo "    재시작: cd monitoring && docker-compose restart"
    echo "    로그 확인: cd monitoring && docker-compose logs -f"
    echo ""
    echo "  Redis + Celery 서비스 (Docker):"
    echo "    상태 확인: cd redis && docker-compose ps"
    echo "    시작: cd redis && docker-compose up -d"
    echo "    중지: cd redis && docker-compose down"
    echo "    재시작: cd redis && docker-compose restart"
    echo "    로그 확인: cd redis && docker-compose logs -f"
    echo ""
    echo "  PostgreSQL 서비스 (Docker):"
    echo "    상태 확인: cd postgres && docker-compose ps"
    echo "    시작: cd postgres && docker-compose up -d"
    echo "    중지: cd postgres && docker-compose down"
    echo "    재시작: cd postgres && docker-compose restart"
    echo "    로그 확인: cd postgres && docker-compose logs -f"
    echo ""
    echo "  Vault 서비스:"
    echo "    상태 확인: docker exec vault-dev vault status"
    echo "    중지: docker-compose -f docker-compose.vault.yaml down"
    
    echo ""
    echo -e "${CYAN}📁 중요 파일:${NC}"
    echo "  환경설정: .env"
    echo "  PostgreSQL: Docker 컨테이너 (postgres/)"
    echo "  Vault 초기화: vault_init.txt"
    echo "  Flask 서비스: /etc/systemd/system/proxmox-manager.service"
    
    echo ""
    echo -e "${YELLOW}⚠️  다음 단계:${NC}"
    echo "  1. 웹 브라우저에서 관리 콘솔에 접속"
    echo "  2. .env 파일에서 추가 설정 확인"
    echo "  3. Proxmox 서버 연결 테스트"
    echo "  4. 첫 번째 VM 생성 테스트"
    
    echo ""
    echo -e "${GREEN}🚀 설치가 완료되었습니다!${NC}"
}

# ========================================
# 메인 실행 함수
# ========================================

main() {
    echo -e "${PURPLE}"
    echo "=========================================="
    echo "🚀 Proxmox Manager 완전 통합 설치 시작"
    echo "=========================================="
    echo "ℹ️  이 스크립트는 재설치에 안전합니다."
    echo "ℹ️  기존 설치가 있어도 자동으로 정리하고 재설치합니다."
    echo "=========================================="
    echo -e "${NC}"
    
    # 설치 단계 실행
    pre_validation
    check_system
    install_essential_packages
    setup_python
    install_nodejs
    install_docker
    install_terraform
    install_ansible
    setup_environment
    setup_vault
    install_monitoring
    install_redis
    install_postgresql
    setup_database
    setup_security
    start_services
    setup_celery_worker
    show_completion_info
    
    echo -e "${GREEN}✅ 모든 설치가 완료되었습니다!${NC}"
}

# 스크립트 실행
main "$@"
