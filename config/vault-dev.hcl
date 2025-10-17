# Vault 개발 환경 설정 파일
# Docker Compose에서 사용하는 Vault 설정

# Vault 서버 설정
ui = true
disable_mlock = true

# API 주소 설정
api_addr = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"

# 스토리지 백엔드 (파일 시스템)
storage "file" {
  path = "/vault/data"
}

# 리스너 설정
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

# 개발 모드 설정 (자동 초기화 및 언실)
disable_mlock = true
raw_storage_endpoint = true
