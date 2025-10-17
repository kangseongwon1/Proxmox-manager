output "vm_ips" {
  value = { for k, m in module.server : k => m.ip }
}

output "vm_names" {
  value = { for k, m in module.server : k => m.name }
}

output "vm_ids" {
  value = { for k, m in module.server : k => m.vmid }
}