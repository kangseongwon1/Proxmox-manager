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

# Vault 초기화 실행
echo "🚀 Vault 초기화 실행 중..."
VAULT_INIT_OUTPUT=$(docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 2>/dev/null)

if [ $? -eq 0 ]; then
    VAULT_TOKEN=$(echo "$VAULT_INIT_OUTPUT" | grep "Initial Root Token:" | awk '{print $4}')
    UNSEAL_KEY=$(echo "$VAULT_INIT_OUTPUT" | grep "Unseal Key 1:" | awk '{print $4}')
    
    # 토큰과 Unseal 키를 파일에 저장
    echo "$VAULT_TOKEN" > ../vault_token.txt
    echo "$UNSEAL_KEY" > ../vault_unseal_keys.txt
    chmod 600 ../vault_token.txt
    chmod 600 ../vault_unseal_keys.txt
    
    echo "✅ Vault 초기화 완료 및 키 저장"
    
    # 환경변수에 토큰 설정
    export VAULT_TOKEN="$VAULT_TOKEN"
    export TF_VAR_vault_token="$VAULT_TOKEN"
    
    # .env 파일에 토큰 업데이트
    if [ -f "../.env" ]; then
        sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" ../.env
        sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" ../.env
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
    echo "  ../vault_token.txt"
    echo "  ../vault_unseal_keys.txt"
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
