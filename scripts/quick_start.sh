#!/bin/bash

# ========================================
# Proxmox Manager 빠른 시작 스크립트
# ========================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${PURPLE}"
echo "=========================================="
echo "🚀 Proxmox Manager 빠른 시작"
echo "=========================================="
echo -e "${NC}"

# 1. 설치 확인
if [ ! -f "install_complete_system.sh" ]; then
    echo -e "${RED}❌ install_complete_system.sh 파일을 찾을 수 없습니다${NC}"
    exit 1
fi

# 2. 실행 권한 설정
chmod +x install_complete_system.sh
chmod +x ansible/dynamic_inventory.py

# 3. 설치 실행
echo -e "${BLUE}📦 Proxmox Manager 설치를 시작합니다...${NC}"
echo -e "${YELLOW}⚠️  이 과정은 몇 분이 소요될 수 있습니다${NC}"
echo ""

./install_complete_system.sh

echo ""
echo -e "${GREEN}🎉 설치가 완료되었습니다!${NC}"
echo -e "${CYAN}웹 브라우저에서 http://$(hostname -I | awk '{print $1}'):5000 에 접속하세요${NC}"
