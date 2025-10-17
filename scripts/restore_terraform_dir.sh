#!/bin/bash

# Terraform 디렉토리 복원 스크립트
# terraform 디렉토리가 삭제된 경우 이 스크립트를 실행하여 복원

set -e

# 로깅 함수들
log_info() {
    echo -e "\033[0;34m[INFO]\033[0m $1"
}

log_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

log_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

log_warning() {
    echo -e "\033[0;33m[WARNING]\033[0m $1"
}

echo "=========================================="
echo "  Terraform 디렉토리 복원 스크립트"
echo "=========================================="

# terraform 디렉토리가 이미 존재하는지 확인
if [ -d "terraform" ]; then
    log_warning "terraform 디렉토리가 이미 존재합니다."
    read -p "덮어쓰시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "복원을 취소했습니다."
        exit 0
    fi
    rm -rf terraform
fi

log_info "terraform 디렉토리 생성 중..."
mkdir -p terraform

log_info "기본 Terraform 파일들 생성 중..."

# main.tf 생성
cat > terraform/main.tf << 'EOF'
# Proxmox Provider 설정
terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
      version = "~> 2.9"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.0"
    }
  }
}

# Vault에서 Proxmox 자격증명 가져오기
data "vault_generic_secret" "proxmox" {
  path = "secret/proxmox"
}

# Vault에서 VM 자격증명 가져오기
data "vault_generic_secret" "vm" {
  path = "secret/vm"
}

# Proxmox Provider 설정
provider "proxmox" {
  pm_api_url          = var.proxmox_api_url
  pm_api_token_id     = var.proxmox_token_id
  pm_api_token_secret = data.vault_generic_secret.proxmox.data["password"]
  pm_tls_insecure     = true
}

# Vault Provider 설정
provider "vault" {
  address = var.vault_address
  token   = var.vault_token
}

# 서버 모듈 호출
module "server" {
  source = "./modules/server"
  
  for_each = var.servers
  
  name        = each.value.name
  vmid        = each.value.vmid
  target_node = each.value.target_node
  template    = each.value.template
  cores       = each.value.cores
  memory      = each.value.memory
  disk_size   = each.value.disk_size
  ip_address  = each.value.ip_address
  gateway     = each.value.gateway
  nameserver  = each.value.nameserver
  username    = data.vault_generic_secret.vm.data["username"]
  password    = data.vault_generic_secret.vm.data["password"]
  ssh_key     = var.ssh_key
}
EOF

# variables.tf 생성
cat > terraform/variables.tf << 'EOF'
variable "proxmox_api_url" {
  description = "Proxmox API URL"
  type        = string
}

variable "proxmox_token_id" {
  description = "Proxmox API Token ID"
  type        = string
}

variable "vault_address" {
  description = "Vault server address"
  type        = string
  default     = "http://localhost:8200"
}

variable "vault_token" {
  description = "Vault token"
  type        = string
  sensitive   = true
}

variable "ssh_key" {
  description = "SSH public key"
  type        = string
}

variable "servers" {
  description = "Map of servers to create"
  type = map(object({
    name        = string
    vmid        = number
    target_node = string
    template    = string
    cores       = number
    memory      = number
    disk_size   = string
    ip_address  = string
    gateway     = string
    nameserver  = string
  }))
  default = {}
}
EOF

# providers.tf 생성
cat > terraform/providers.tf << 'EOF'
# Proxmox Provider 설정
terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
      version = "~> 2.9"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.0"
    }
  }
}

# Proxmox Provider 설정
provider "proxmox" {
  pm_api_url          = var.proxmox_api_url
  pm_api_token_id     = var.proxmox_token_id
  pm_api_token_secret = data.vault_generic_secret.proxmox.data["password"]
  pm_tls_insecure     = true
}

# Vault Provider 설정
provider "vault" {
  address = var.vault_address
  token   = var.vault_token
}
EOF

# outputs.tf 생성
cat > terraform/outputs.tf << 'EOF'
output "server_ips" {
  description = "IP addresses of created servers"
  value = {
    for k, v in module.server : k => v.ip_address
  }
}

output "server_names" {
  description = "Names of created servers"
  value = {
    for k, v in module.server : k => v.name
  }
}
EOF

# modules/server 디렉토리 생성
log_info "server 모듈 디렉토리 생성 중..."
mkdir -p terraform/modules/server

# modules/server/main.tf 생성
cat > terraform/modules/server/main.tf << 'EOF'
# Proxmox VM 생성
resource "proxmox_vm_qemu" "vm" {
  name        = var.name
  vmid        = var.vmid
  target_node = var.target_node
  clone       = var.template
  
  # VM 설정
  cores   = var.cores
  memory  = var.memory
  sockets = 1
  
  # 디스크 설정
  disk {
    size    = var.disk_size
    type    = "scsi"
    storage = "local-lvm"
  }
  
  # 네트워크 설정
  network {
    model  = "virtio"
    bridge = "vmbr0"
  }
  
  # 클라우드 초기화 설정
  ciuser     = var.username
  cipassword = var.password
  sshkeys    = var.ssh_key
  
  # IP 설정
  ipconfig0 = "ip=${var.ip_address}/24,gw=${var.gateway}"
  nameserver = var.nameserver
  
  # 자동 시작
  onboot = true
  
  # 에이전트 활성화
  agent = 1
}
EOF

# modules/server/variables.tf 생성
cat > terraform/modules/server/variables.tf << 'EOF'
variable "name" {
  description = "VM name"
  type        = string
}

variable "vmid" {
  description = "VM ID"
  type        = number
}

variable "target_node" {
  description = "Target Proxmox node"
  type        = string
}

variable "template" {
  description = "Template to clone from"
  type        = string
}

variable "cores" {
  description = "Number of CPU cores"
  type        = number
  default     = 2
}

variable "memory" {
  description = "Memory in MB"
  type        = number
  default     = 2048
}

variable "disk_size" {
  description = "Disk size"
  type        = string
  default     = "20G"
}

variable "ip_address" {
  description = "IP address"
  type        = string
}

variable "gateway" {
  description = "Gateway IP"
  type        = string
}

variable "nameserver" {
  description = "Nameserver IP"
  type        = string
}

variable "username" {
  description = "VM username"
  type        = string
}

variable "password" {
  description = "VM password"
  type        = string
  sensitive   = true
}

variable "ssh_key" {
  description = "SSH public key"
  type        = string
}
EOF

# modules/server/outputs.tf 생성
cat > terraform/modules/server/outputs.tf << 'EOF'
output "name" {
  description = "VM name"
  value       = proxmox_vm_qemu.vm.name
}

output "vmid" {
  description = "VM ID"
  value       = proxmox_vm_qemu.vm.vmid
}

output "ip_address" {
  description = "VM IP address"
  value       = proxmox_vm_qemu.vm.default_ipv4_address
}

output "status" {
  description = "VM status"
  value       = proxmox_vm_qemu.vm.status
}
EOF

log_success "terraform 디렉토리 복원 완료!"
log_info "복원된 파일들:"
echo "  - terraform/main.tf"
echo "  - terraform/variables.tf"
echo "  - terraform/providers.tf"
echo "  - terraform/outputs.tf"
echo "  - terraform/modules/server/main.tf"
echo "  - terraform/modules/server/variables.tf"
echo "  - terraform/modules/server/outputs.tf"

log_info "이제 vault.sh를 다시 실행할 수 있습니다."
