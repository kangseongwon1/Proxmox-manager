#!/bin/bash
# Cloud-init 설정 테스트 스크립트

set -e

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

# Cloud-init 설정 확인
check_cloud_init_config() {
    local server_ip="$1"
    local username="${2:-dev}"
    
    log_info "Cloud-init 설정 확인 중: $server_ip"
    
    # SSH 접속 테스트
    log_info "SSH 접속 테스트 중..."
    if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $username@$server_ip "echo 'SSH 접속 성공'" 2>/dev/null; then
        log_success "SSH 접속 성공"
    else
        log_error "SSH 접속 실패"
        return 1
    fi
    
    # 시간대 확인
    log_info "시간대 확인 중..."
    local timezone=$(ssh -o StrictHostKeyChecking=no $username@$server_ip "timedatectl show --property=Timezone --value" 2>/dev/null)
    if [ "$timezone" = "Asia/Seoul" ]; then
        log_success "시간대 설정 정상: $timezone"
    else
        log_warning "시간대 설정 확인 필요: $timezone"
    fi
    
    # 사용자 확인
    log_info "사용자 확인 중..."
    if ssh -o StrictHostKeyChecking=no $username@$server_ip "id $username" 2>/dev/null; then
        log_success "사용자 $username 존재"
    else
        log_error "사용자 $username 없음"
    fi
    
    # sudo 권한 확인
    log_info "sudo 권한 확인 중..."
    if ssh -o StrictHostKeyChecking=no $username@$server_ip "sudo -n true" 2>/dev/null; then
        log_success "sudo 권한 정상"
    else
        log_warning "sudo 권한 확인 필요"
    fi
    
    # SELinux 상태 확인
    log_info "SELinux 상태 확인 중..."
    local selinux_status=$(ssh -o StrictHostKeyChecking=no $username@$server_ip "getenforce" 2>/dev/null)
    if [ "$selinux_status" = "Disabled" ]; then
        log_success "SELinux 비활성화됨"
    else
        log_warning "SELinux 상태: $selinux_status"
    fi
    
    # Firewalld 상태 확인
    log_info "Firewalld 상태 확인 중..."
    local firewalld_status=$(ssh -o StrictHostKeyChecking=no $username@$server_ip "systemctl is-active firewalld" 2>/dev/null)
    if [ "$firewalld_status" = "inactive" ]; then
        log_success "Firewalld 비활성화됨"
    else
        log_warning "Firewalld 상태: $firewalld_status"
    fi
    
    # 호스트명 확인
    log_info "호스트명 확인 중..."
    local hostname=$(ssh -o StrictHostKeyChecking=no $username@$server_ip "hostname" 2>/dev/null)
    log_info "호스트명: $hostname"
    
    # 로케일 확인
    log_info "로케일 확인 중..."
    local locale=$(ssh -o StrictHostKeyChecking=no $username@$server_ip "localectl show --property=Locale --value" 2>/dev/null)
    log_info "로케일: $locale"
    
    log_success "Cloud-init 설정 확인 완료: $server_ip"
}

# 사용법
usage() {
    echo "사용법: $0 <서버_IP> [사용자명]"
    echo "예시: $0 192.168.0.21 dev"
    echo "예시: $0 192.168.0.21 rocky"
}

# 메인 실행
main() {
    if [ $# -lt 1 ]; then
        usage
        exit 1
    fi
    
    local server_ip="$1"
    local username="${2:-dev}"
    
    log_info "Cloud-init 설정 테스트 시작"
    log_info "서버 IP: $server_ip"
    log_info "사용자명: $username"
    
    check_cloud_init_config "$server_ip" "$username"
    
    log_success "모든 테스트 완료!"
}

# 스크립트 실행
main "$@"
