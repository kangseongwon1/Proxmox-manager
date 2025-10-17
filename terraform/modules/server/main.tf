terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }
  }
}

resource "proxmox_virtual_environment_vm" "this" {
  name  = var.name
  node_name = var.proxmox_node

  cpu {
    cores = var.cpu
  }

  memory {
    dedicated = var.memory
  }

  dynamic "disk" {
    for_each = var.disks
    content {
      interface    = disk.value.interface
      size         = disk.value.size
      file_format  = disk.value.file_format == "auto" ? (
        # LVM-Thin 스토리지는 raw만 지원, SSD/NVMe도 raw 사용
        can(regex(".*thin.*", disk.value.datastore_id)) || 
        can(regex(".*lvm.*", disk.value.datastore_id)) ? "raw" : "qcow2"
      ) : disk.value.file_format
      datastore_id = disk.value.datastore_id == "auto" ? var.proxmox_hdd_datastore : disk.value.datastore_id
    }
  }

  dynamic "network_device" {
    for_each = var.network_devices
    content {
      bridge = network_device.value.bridge
    }
  }

  initialization {
    datastore_id = var.disks[0].datastore_id

    user_account {
      username = var.vm_username
      password = var.vm_password
      keys     = var.ssh_keys
    }
    
    
    # 각 네트워크 디바이스별로 ip/subnet/gateway 적용
    dynamic "ip_config" {
      for_each = var.network_devices
      content {
        ipv4 {
          address = "${ip_config.value.ip_address}/${ip_config.value.subnet}"
          gateway = ip_config.value.gateway
        }
      }
    }    
  }

  operating_system {
    type = "l26"
  }

  clone {
    vm_id = var.template_vm_id
  }

  # VM 생성 후 자동 시작 (기본값: true)
  started = true

  lifecycle {
    ignore_changes = [
      disk,
      # VM의 전원 상태 변경 무시 (수동으로 중지/시작된 경우)
      started
    ]
  }
}

output "ip" {
  value = [for nd in var.network_devices : nd.ip_address]
}

output "name" {
  value = proxmox_virtual_environment_vm.this.name
}

output "vmid" {
  value = proxmox_virtual_environment_vm.this.vm_id
}