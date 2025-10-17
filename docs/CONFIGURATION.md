# 구성/환경 설정

## 환경 변수(.env)
- Flask/Proxmox/Vault/Monitoring 관련 변수
- 설치 스크립트에서 템플릿 제공(민감정보는 하드코딩 금지)

## 애플리케이션 설정
- 파일: `config/config.py`
- 로그: `logs/proxmox_manager.log`(회전 설정), DEBUG 기본 False

## 경로 일관성
- 코드 전반에서 상대경로 사용, 컨테이너/서버 경로 차이를 흡수
- Vault, Monitoring, Terraform/Ansible 경로는 스크립트에서 상대경로로 처리
