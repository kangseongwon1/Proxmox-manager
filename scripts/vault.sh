#!/bin/bash

# 통합 Vault 스크립트
# Vault 설치부터 환경변수 설정, 시크릿 저장까지 모든 것을 처리합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

echo "🚀 통합 Vault 스크립트 시작..."
echo ""

# 1. Docker 및 Docker Compose 확인
check_docker() {
    log_info "1. Docker 및 Docker Compose 확인 중..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다!"
        log_info "Docker 설치 방법:"
        log_info "sudo dnf install -y docker"
        log_info "sudo systemctl enable docker"
        log_info "sudo systemctl start docker"
        log_info "sudo usermod -aG docker \$USER"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_warning "Docker Compose가 설치되지 않았습니다. 설치를 시도합니다..."
        
        # Docker Compose 설치 시도
        if command -v dnf &> /dev/null; then
            # Rocky 8에서 Docker Compose 바이너리 직접 설치
            log_info "Rocky 8에서 Docker Compose 바이너리 직접 설치 중..."
            
            # EPEL 설치 (다른 패키지용)
            sudo dnf install -y epel-release
            
            # 바이너리 직접 설치
            log_info "최신 Docker Compose 바이너리 다운로드 중..."
            COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)
            COMPOSE_VERSION=${COMPOSE_VERSION#v}
            
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
        elif command -v apt &> /dev/null; then
            sudo apt install -y docker-compose
        fi
        
        # 재확인
        if ! command -v docker-compose &> /dev/null; then
            log_error "Docker Compose 설치에 실패했습니다!"
            log_info "수동 설치 방법:"
            log_info "sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
            log_info "sudo chmod +x /usr/local/bin/docker-compose"
            exit 1
        else
            log_success "Docker Compose 설치 완료"
        fi
    fi
    
    if ! sudo systemctl is-active --quiet docker; then
        log_warning "Docker 서비스가 실행되지 않았습니다. 시작 중..."
        sudo systemctl start docker
    fi
    
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
            log_error "Docker 권한 문제가 지속됩니다."
            log_info "수동 해결 방법:"
            log_info "  1. 새 터미널 세션 시작"
            log_info "  2. 또는 'newgrp docker' 실행"
            log_info "  3. 또는 로그아웃 후 재로그인"
            exit 1
        fi
    else
        log_success "Docker 권한 확인 완료"
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
}

# 2. .env 파일 확인
check_env() {
    log_info "2. .env 파일 확인 중..."
    
    if [ ! -f ".env" ]; then
        log_error ".env 파일이 없습니다!"
        log_info "test.env를 .env로 복사하세요:"
        log_info "cp test.env .env"
        exit 1
    fi
    
    source .env
    log_success ".env 파일 로드 완료"
}

# 3. 기존 Vault 컨테이너 정리
cleanup_vault() {
    log_info "3. 기존 Vault 컨테이너 정리 중..."
    
    # Docker Compose로 실행 중인 Vault 중지
    if [ -f "docker-compose.vault.yaml" ]; then
        docker-compose -f docker-compose.vault.yaml down 2>/dev/null || true
    elif [ -f "docker-compose.vault.yaml" ]; then
        docker-compose -f docker-compose.vault.yaml down 2>/dev/null || true
    fi
    
    # 기존 Vault 컨테이너 중지 및 제거
    docker stop vault-dev 2>/dev/null || true
    docker rm vault-dev 2>/dev/null || true
    
    # 기존 Vault 볼륨 제거
    docker volume rm vault-data 2>/dev/null || true
    
    log_success "기존 Vault 컨테이너 정리 완료"
}

# 4. Vault Docker Compose 실행
start_vault() {
    log_info "4. Vault Docker Compose 실행 중..."
    
    # Vault 데이터 디렉토리 생성
    mkdir -p vault-data
    
    # Docker Compose로 Vault 실행
    if [ -f "docker-compose.vault.yaml" ]; then
        docker-compose -f docker-compose.vault.yaml up -d
    else
        docker-compose -f docker-compose.vault.yaml up -d
    fi
    
    # Vault 초기화 대기
    log_info "Vault 초기화 대기 중..."
    sleep 15
    
    # Vault 상태 확인
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec vault-dev vault status 2>/dev/null | grep -q "Version"; then
            log_success "Vault 컨테이너 시작 완료"
            
            # 추가 대기 시간 (볼륨 마운트 완료 대기)
            log_info "Vault 볼륨 마운트 완료 대기 중..."
            sleep 5
            
            return 0
        fi
        
        log_info "Vault 시작 대기 중... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    log_error "Vault 시작 실패"
    exit 1
}

# 5. Vault 초기화 및 언실
init_vault() {
    log_info "5. Vault 초기화 및 언실 중..."

    # Vault 초기화 (최초 1회)
    if docker exec vault-dev vault status | grep -q "Initialized.*false"; then
        log_info "Vault 초기화 실행 중..."
        docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 > vault_init.txt

        if [ $? -ne 0 ]; then
            log_error "Vault 초기화 실패"
            exit 1
        fi

        log_success "Vault 초기화 완료"
    else
        log_info "Vault가 이미 초기화되어 있습니다."
    fi

    # Unseal 키 추출
    UNSEAL_KEY=$(grep 'Unseal Key 1:' vault_init.txt | awk '{print $NF}')
    ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')

    # Vault 언실
    log_info "Vault 언실 중..."
    docker exec vault-dev vault operator unseal $UNSEAL_KEY

    if [ $? -ne 0 ]; then
        log_error "Vault 언실 실패"
        exit 1
    fi

    # Root 토큰으로 로그인
    log_info "Vault 인증 중..."
    docker exec vault-dev vault login $ROOT_TOKEN

    if [ $? -ne 0 ]; then
        log_error "Vault 인증 실패"
        exit 1
    fi

    log_success "Vault 초기화 및 언실 완료"
}


# 6. Vault 설정
configure_vault() {
    log_info "6. Vault 설정 중..."
    
    # KV v2 엔진 활성화
    log_info "KV v2 엔진 활성화 중..."
    docker exec vault-dev vault secrets enable -path=secret kv-v2
    
    # SSH 키 읽기
    local ssh_public_key=""
    if [ -f ~/.ssh/id_rsa.pub ]; then
        ssh_public_key=$(cat ~/.ssh/id_rsa.pub)
        log_info "SSH 공개키 읽기 완료"
    else
        log_warning "SSH 공개키가 없습니다. SSH 키를 먼저 생성하세요."
        log_info "ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N \"\" -C \"proxmox-manager\""
    fi
    
    # Proxmox 자격증명 저장
    log_info "Proxmox 자격증명 저장 중..."
    docker exec vault-dev vault kv put secret/proxmox \
        username="${PROXMOX_USERNAME}" \
        password="${PROXMOX_PASSWORD}"
    
    # VM 자격증명 저장
    log_info "VM 자격증명 저장 중..."
    docker exec vault-dev vault kv put secret/vm \
        username="${VM_USERNAME}" \
        password="${VM_PASSWORD}"
    
    # SSH 키 저장
    if [ -n "$ssh_public_key" ]; then
        log_info "SSH 키 저장 중..."
        docker exec vault-dev vault kv put secret/ssh \
            public_key="$ssh_public_key"
    fi
    
    # .env 파일에 Vault 토큰 업데이트
    log_info ".env 파일에 Vault 토큰 업데이트 중..."
    
    # .env 파일 경로 확인 (상위 디렉토리 우선)
    ENV_FILE=""
    if [ -f ".env" ]; then
        ENV_FILE=".env"
    elif [ -f ".env" ]; then
        ENV_FILE=".env"
    fi
    
    if [ -n "$ENV_FILE" ]; then
        # 현재 ROOT_TOKEN을 .env 파일에 업데이트
        sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$ROOT_TOKEN|" "$ENV_FILE"
        log_success ".env 파일에 Vault 토큰 업데이트 완료: $ROOT_TOKEN"
        log_info "업데이트된 파일: $ENV_FILE"
        
        # 환경변수도 즉시 업데이트
        export VAULT_TOKEN="$ROOT_TOKEN"
        export TF_VAR_vault_token="$ROOT_TOKEN"
    else
        log_warning ".env 파일을 찾을 수 없습니다 (현재 디렉토리와 상위 디렉토리 모두 확인함)"
    fi
    
    log_success "Vault 설정 완료"
}

# .bashrc 환경변수 설정 함수
setup_bashrc_environment() {
    local bashrc_file="$HOME/.bashrc"
    local vault_section_start="# ========================================"
    local vault_section_end="# ========================================"
    local vault_section_title="# Vault Environment Variables (Auto-generated)"
    local vault_section_comment="# Generated by vault.sh - DO NOT EDIT MANUALLY"
    
    # .bashrc 파일이 없으면 생성
    if [ ! -f "$bashrc_file" ]; then
        touch "$bashrc_file"
        log_info ".bashrc 파일이 없어서 새로 생성했습니다"
    fi
    
    # 기존 Vault 환경변수 섹션 제거
    log_info "기존 Vault 환경변수 섹션 제거 중..."
    
    # 임시 파일 생성
    local temp_file=$(mktemp)
    
    # 기존 Vault 섹션을 제외하고 복사
    local in_vault_section=false
    local skip_next=false
    
    while IFS= read -r line; do
        if [[ "$skip_next" == true ]]; then
            skip_next=false
            continue
        fi
        
        if [[ "$line" == "$vault_section_start" ]]; then
            in_vault_section=true
            skip_next=true  # 다음 줄(제목)도 건너뛰기
            continue
        elif [[ "$line" == "$vault_section_end" && "$in_vault_section" == true ]]; then
            in_vault_section=false
            continue
        elif [[ "$in_vault_section" == true ]]; then
            continue
        else
            echo "$line" >> "$temp_file"
        fi
    done < "$bashrc_file"
    
    # 새 Vault 환경변수 섹션 추가
    log_info "새 Vault 환경변수 섹션 추가 중..."
    cat >> "$temp_file" << EOF

$vault_section_start
$vault_section_title
$vault_section_comment
$vault_section_start

# Vault 환경변수
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="$ROOT_TOKEN"

# Terraform 환경변수 (TF_VAR_ 접두사 사용)
export TF_VAR_vault_token="$ROOT_TOKEN"
export TF_VAR_vault_address="http://127.0.0.1:8200"

$vault_section_end

EOF
    
    # 임시 파일을 .bashrc로 복사
    mv "$temp_file" "$bashrc_file"
    
    log_success ".bashrc 환경변수 설정 완료"
    
    # 현재 세션에 적용
    log_info "현재 세션에 환경변수 적용 중..."
    source "$bashrc_file"
    
    if [ $? -eq 0 ]; then
        log_success "환경변수가 현재 세션에 적용되었습니다"
    else
        log_warning "환경변수 적용 실패 (수동으로 source ~/.bashrc 실행하세요)"
    fi
}

# 7. 환경변수 설정
set_environment() {
    log_info "7. 환경변수 설정 중..."
    
    # Vault 환경변수 설정
    export VAULT_ADDR="http://127.0.0.1:8200"
    export VAULT_TOKEN="$ROOT_TOKEN"
    
    # Terraform 환경변수 설정 (TF_VAR_ 접두사 사용)
    export TF_VAR_vault_token="$ROOT_TOKEN"
    export TF_VAR_vault_address="http://127.0.0.1:8200"
    
    # .env 파일에 Vault 토큰 업데이트
    log_info ".env 파일에 Vault 토큰 업데이트 중..."
    
    # .env 파일 경로 확인 (상위 디렉토리 우선)
    ENV_FILE=""
    if [ -f ".env" ]; then
        ENV_FILE=".env"
    elif [ -f ".env" ]; then
        ENV_FILE=".env"
    fi
    
    if [ -n "$ENV_FILE" ]; then
        sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$ROOT_TOKEN|" "$ENV_FILE"
        log_success ".env 파일에 Vault 토큰 업데이트 완료: $ROOT_TOKEN"
        log_info "업데이트된 파일: $ENV_FILE"
    else
        log_warning ".env 파일을 찾을 수 없습니다 (현재 디렉토리와 상위 디렉토리 모두 확인함)"
    fi
    
    # .bashrc에 환경변수 영구 저장
    log_info ".bashrc에 환경변수 영구 저장 중..."
    setup_bashrc_environment
    
    # terraform.tfvars.json 업데이트
    if [ -f "terraform/terraform.tfvars.json" ]; then
        log_info "terraform.tfvars.json 업데이트 중..."
        cd terraform
        
        # 기존 파일 백업
        cp terraform.tfvars.json terraform.tfvars.json.backup 2>/dev/null || true
        
        # 토큰 업데이트
        sed -i "s/\"vault_token\": \".*\"/\"vault_token\": \"$ROOT_TOKEN\"/" terraform.tfvars.json
        
        cd ../scripts
        log_success "terraform.tfvars.json 업데이트 완료"
    fi
    
    log_success "환경변수 설정 완료"
    log_info "설정된 환경변수:"
    echo "  VAULT_ADDR: $VAULT_ADDR"
    echo "  VAULT_TOKEN: $VAULT_TOKEN"
    echo "  TF_VAR_vault_token: $TF_VAR_vault_token"
    echo "  TF_VAR_vault_address: $TF_VAR_vault_address"
}

# 8. Terraform 테스트
test_terraform() {
    log_info "8. Terraform 테스트 중..."
    
    # terraform 디렉토리 존재 확인
    if [ ! -d "../terraform" ]; then
        log_error "terraform 디렉토리가 존재하지 않습니다!"
        log_info "terraform 디렉토리를 생성하고 기본 파일들을 복원하세요."
        log_info "또는 install_complete_system.sh를 다시 실행하여 전체 시스템을 재설치하세요."
        exit 1
    fi
    
    cd ../terraform
    
    # Terraform 초기화
    log_info "Terraform 초기화 중..."
    terraform init
    
    if [ $? -eq 0 ]; then
        log_success "Terraform 초기화 완료"
    else
        log_error "Terraform 초기화 실패"
        exit 1
    fi
    
    # .env 파일에서 Terraform 변수 설정
    log_info ".env 파일에서 Terraform 변수 설정 중..."
    
    # .env 파일 경로 확인 (상위 디렉토리 우선)
    ENV_FILE=""
    if [ -f ".env" ]; then
        ENV_FILE=".env"
    elif [ -f ".env" ]; then
        ENV_FILE=".env"
    fi
    
    if [ -n "$ENV_FILE" ]; then
        source "$ENV_FILE"
        
        # Terraform 변수로 환경변수 설정
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
        log_info "로드된 .env 파일: $ENV_FILE"
    else
        log_warning ".env 파일을 찾을 수 없습니다 (현재 디렉토리와 상위 디렉토리 모두 확인함). 기본값 사용"
    fi
    
    # Terraform 계획 실행
    log_info "Terraform 계획 실행 중..."
    terraform plan
    
    if [ $? -eq 0 ]; then
        log_success "Terraform 계획 실행 완료"
    else
        log_error "Terraform 계획 실행 실패"
        exit 1
    fi
    
    cd ..
    log_success "Terraform 테스트 완료"
}

# 9. 환경변수 영구 저장 옵션
save_permanent_env() {
    log_info "9. 환경변수 영구 저장 설정 중..."
    
    # 사용자에게 영구 저장 여부 확인
    echo ""
    log_warning "환경변수를 영구적으로 저장하시겠습니까? (y/n)"
    read -p "선택: " choice
    
    if [[ $choice == "y" || $choice == "Y" ]]; then
        log_info "환경변수 영구 저장 중..."
        
        # .bashrc 백업
        cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
        
        # 기존 Vault 관련 환경변수 제거
        sed -i '/# Vault Environment Variables/,/# End Vault Environment Variables/d' ~/.bashrc 2>/dev/null || true
        
        # 새로운 환경변수 추가
        cat >> ~/.bashrc << EOF

# Vault Environment Variables
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="$ROOT_TOKEN"
export TF_VAR_vault_token="$ROOT_TOKEN"
export TF_VAR_vault_address="http://127.0.0.1:8200"
# End Vault Environment Variables
EOF
        
        log_success "환경변수 영구 저장 완료"
        log_info "다음 로그인부터 자동으로 환경변수가 설정됩니다!"
        log_info "즉시 적용하려면: source ~/.bashrc"
    else
        log_info "환경변수 영구 저장을 건너뜁니다."
    fi
}

# 10. 완료 메시지
show_completion() {
    log_success "=========================================="
    log_success "통합 Vault 스크립트 완료!"
    log_success "=========================================="
    
    echo ""
    log_info "🔑 Vault 정보:"
    echo "  - 주소: $VAULT_ADDR"
    echo "  - 토큰: $ROOT_TOKEN"
    echo "  - 컨테이너: vault-dev"
    echo ""
    
    log_info "📋 저장된 시크릿:"
    echo "  - secret/proxmox (Proxmox 자격증명)"
    echo "  - secret/vm (VM 자격증명)"
    if [ -f ~/.ssh/id_rsa.pub ]; then
        echo "  - secret/ssh (SSH 공개키)"
    fi
    echo ""
    
    log_info "🔧 관리 명령어:"
    echo "  - 상태 확인: docker exec vault-dev vault status"
    echo "  - 시크릿 조회: docker exec vault-dev vault kv get secret/proxmox"
    echo "  - 서비스 중지: docker-compose -f docker-compose.vault.yaml down"
    echo "  - 서비스 시작: docker-compose -f docker-compose.vault.yaml up -d"
    echo ""
    
    log_info "🌐 웹 UI 접속:"
    echo "  - Vault UI: $VAULT_ADDR"
    echo "  - 토큰: $ROOT_TOKEN"
    echo ""
    
    log_info "📁 중요 파일:"
    echo "  - vault_init.txt: 초기화 정보 (안전하게 보관하세요)"
    echo "  - config/vault-dev.hcl: Vault 설정 파일"
    echo "  - docker-compose.vault.yaml: Docker Compose 설정"
    echo ""
    
    log_info "🔄 Terraform 사용:"
    echo "  # 환경변수는 이미 .bashrc에 영구 저장됨"
    echo "  # 새 터미널 세션에서는 자동으로 적용됨"
    echo "  cd terraform && terraform plan"
    echo ""
    log_info "💡 환경변수 영구 저장 완료:"
    echo "  - .bashrc에 환경변수 저장됨"
    echo "  - 새 터미널 세션에서 자동 적용"
    echo "  - 기존 환경변수는 자동으로 교체됨"
    echo ""
    
    log_warning "⚠️  주의: vault_init.txt 파일을 안전하게 보관하세요!"
}

# 메인 실행 함수
main() {
    log_info "통합 Vault 스크립트 시작..."
    
    # 각 단계 실행
    check_docker
    check_env
    cleanup_vault
    start_vault
    init_vault
    configure_vault
    set_environment
    test_terraform
    
    # 완료 메시지
    show_completion
}

# 스크립트 실행
main "$@"
