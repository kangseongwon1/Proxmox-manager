# Terraform 구조 가이드

- modules/: 재사용 가능한 모듈
- envs/: 환경별(main.tf, 변수 등)
- variables.tf, outputs.tf: 공통 변수/출력

환경별로 상태파일, 변수, 백엔드 분리 권장 