terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.0"
    }
  }
}

provider "proxmox" {
  endpoint = var.proxmox_endpoint
  username = var.proxmox_username
  password = data.vault_generic_secret.proxmox.data["password"]
  insecure = false

  ssh {
    agent = true
  }
}

provider "vault" {
  address = var.vault_address
  token   = var.vault_token
}

# Vault 데이터 소스는 main.tf에서 관리