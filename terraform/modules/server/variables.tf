variable "name" { type = string }
variable "role" { type = string }
variable "cpu" { type = number }
variable "memory" { type = number }
variable "network_devices" {
  type = list(object({
    bridge     = string
    ip_address = string
    subnet     = string
    gateway    = string
  }))
}
variable "template_vm_id" { type = number }

variable "proxmox_endpoint" { type = string }
variable "proxmox_username" { type = string }
variable "proxmox_password" { type = string }
variable "proxmox_node" { type = string }
variable "proxmox_hdd_datastore" { type = string }
variable "proxmox_ssd_datastore" { type = string }
variable "vm_username" { type = string }
variable "vm_password" { type = string }
variable "ssh_keys" { type = list(string) }

variable "disks" {
  description = "List of disks"
  type = list(object({
    size         = number
    interface    = string
    datastore_id = string
    file_format  = optional(string, "auto") # "auto", "raw", "qcow2", "vmdk"
  }))
}