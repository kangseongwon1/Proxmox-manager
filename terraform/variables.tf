variable "servers" {
  description = "서버 목록"
  type = map(object({
    name            = string
    role            = string
    cpu             = number
    memory          = number
    disks = list(object({
      size         = number
      interface    = string
      datastore_id = string
      file_format  = optional(string, "auto") # "auto", "raw", "qcow2", "vmdk"
    }))
    network_devices = list(object({
      bridge     = string
      ip_address = string
      subnet     = string
      gateway    = string
    }))
    template_vm_id = number
    vm_username    = optional(string)  # 서버별 사용자명 (기본값은 전역 vm_username 사용)
    vm_password    = optional(string)  # 서버별 비밀번호 (기본값은 전역 vm_password 사용)
  }))
  default = {}  # 기본값: 빈 맵 (설치 시 서버 없음)
}

# Vault 설정
variable "vault_address" {
  description = "Vault server address"
  type        = string
  default     = "http://127.0.0.1:8200"
}

variable "vault_token" {
  description = "Vault token for authentication"
  type        = string
  sensitive   = true
}

# Proxmox 설정 (Vault에서 가져올 예정)
variable "proxmox_endpoint" { 
  type = string
  description = "Proxmox 서버 엔드포인트"
  default = ""
}
variable "proxmox_username" { 
  type = string
  description = "Proxmox 사용자명"
  default = ""
}
variable "proxmox_password" { 
  type = string
  sensitive = true
  description = "Proxmox 비밀번호"
  default = ""
}
variable "proxmox_node" { 
  type = string
  description = "Proxmox 노드명"
  default = ""
}
variable "proxmox_hdd_datastore" { 
  type = string
  description = "HDD 데이터스토어 ID"
  default = "local-lvm"
}
variable "proxmox_ssd_datastore" { 
  type = string
  description = "SSD 데이터스토어 ID"
  default = "local"
}

# VM 설정 (Vault에서 가져올 예정)
variable "vm_username" { 
  type = string
  description = "VM 기본 사용자명"
  default = ""
}
variable "vm_password" { 
  type = string
  sensitive = true
  description = "VM 기본 비밀번호"
  default = ""
}

# 환경 설정
variable "environment" {
  type = string
  description = "환경 (development/production)"
  default = "development"
}

# datastore 설정
locals {
  datastore_config = {
    hdd = var.proxmox_hdd_datastore
    ssd = var.proxmox_ssd_datastore
  }
}