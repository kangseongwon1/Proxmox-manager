# Ansible 변수 관리 가이드

## 📁 변수 파일 구조

```
ansible/
├── group_vars/
│   ├── all.yml              # 모든 서버 공통 변수
│   ├── web.yml              # 웹 서버 전용 변수
│   ├── db.yml               # 데이터베이스 서버 전용 변수
│   ├── was.yml              # WAS 서버 전용 변수
│   ├── search.yml           # 검색 서버 전용 변수
│   ├── ftp.yml              # FTP 서버 전용 변수
│   ├── java.yml             # Java 관련 공통 변수
│   └── README.md           # 이 파일
├── host_vars/
│   ├── server1.yml         # 특정 서버 전용 변수
│   └── server2.yml
└── role_playbook.yml       # 메인 플레이북
```

## 🔄 변수 우선순위 (높은 순서)

1. **명령행 변수** (`-e` 옵션)
2. **플레이북 변수** (`role_playbook.yml`의 `vars:`)
3. **역할 변수** (`roles/*/defaults/main.yml`)
4. **그룹 변수** (`group_vars/*.yml`)
5. **호스트 변수** (`host_vars/*.yml`)
6. **역할 기본값** (`roles/*/defaults/main.yml`)

## 📋 변수 파일별 역할

### `all.yml` - 공통 변수
- 모든 서버에 적용되는 기본 설정
- 포트 번호, 버전 정보, 공통 경로 등

### `web.yml` - 웹 서버 변수
- Nginx 설정, SSL 설정, 로드 밸런싱 등
- `web` 역할을 가진 서버에만 적용

### `db.yml` - 데이터베이스 변수
- MySQL 설정, 백업 설정, 복제 설정 등
- `db` 역할을 가진 서버에만 적용

### `was.yml` - WAS 서버 변수
- Tomcat 설정, JVM 튜닝, 연결 풀 설정 등
- `was` 역할을 가진 서버에만 적용

### `production.yml` - 프로덕션 환경
- 보안 강화, 성능 최적화, 모니터링 강화
- 프로덕션 서버에만 적용

### `development.yml` - 개발 환경
- 개발 편의 설정, 디버깅 활성화
- 개발 서버에만 적용

## 🎯 사용 예시

### 1. 기본 변수 사용
```yaml
# group_vars/all.yml
nginx_port: 80
mysql_port: 3306
```

### 2. 역할별 변수 오버라이드
```yaml
# group_vars/web.yml
nginx_port: 8080  # 웹 서버는 8080 포트 사용
```

### 3. 환경별 변수 오버라이드
```yaml
# group_vars/production.yml
nginx_worker_connections: 2048  # 프로덕션은 더 많은 연결
```

### 4. 특정 서버 변수 오버라이드
```yaml
# host_vars/web-server1.yml
nginx_port: 9000  # 특정 서버만 9000 포트 사용
```

## 🔧 변수 추가 방법

### 1. 새로운 공통 변수 추가
```yaml
# group_vars/all.yml에 추가
new_variable: "value"
```

### 2. 새로운 역할별 변수 추가
```yaml
# group_vars/web.yml에 추가
web_specific_variable: "value"
```

### 3. 환경별 변수 추가
```yaml
# group_vars/production.yml에 추가
production_only_variable: "value"
```

## ⚠️ 주의사항

1. **변수명 규칙**: `snake_case` 사용 (예: `mysql_root_password`)
2. **기본값 설정**: `{{ variable | default('default_value') }}` 사용
3. **보안 변수**: 환경변수로 관리 (`ansible_mysql_root_password`)
4. **변수 충돌**: 우선순위를 고려하여 변수명 설계
5. **문서화**: 새로운 변수 추가 시 이 README 업데이트

## 🚀 실행 예시

```bash
# 기본 실행 (모든 변수 파일 자동 로드)
ansible-playbook -i dynamic_inventory.py role_playbook.yml

# 특정 변수 오버라이드
ansible-playbook -i dynamic_inventory.py role_playbook.yml -e "nginx_port=8080"

# 특정 그룹만 실행
ansible-playbook -i dynamic_inventory.py role_playbook.yml --limit web
```

## 🐍 Python 코드에서 사용

### 1. AnsibleService에서 자동 사용
```python
from app.services.ansible_service import AnsibleService

ansible_service = AnsibleService()
# 변수는 자동으로 group_vars에서 로드됨
success, message = ansible_service.assign_role_to_server("server1", "web")
```

### 2. 직접 변수 관리자 사용
```python
from app.services.ansible_variables import AnsibleVariableManager

variable_manager = AnsibleVariableManager()

# 특정 역할의 변수 가져오기
web_vars = variable_manager.get_role_variables("web")
print(web_vars['nginx_port'])  # 80

# 특정 변수 값 가져오기
mysql_password = variable_manager.get_variable("mysql_root_password", "default_password")

# Ansible 실행용 변수 생성
extra_vars = variable_manager.get_ansible_extra_vars("web", {"custom_var": "value"})
```

### 3. 환경 변수 설정 (통합 관리)
```bash
# .env 파일에서 모든 설정 관리 (권장)
cp env_template.txt .env
nano .env

# 또는 환경 변수로 직접 설정
export ANSIBLE_MYSQL_ROOT_PASSWORD=your_secure_password
export ANSIBLE_FTP_PASSWORD=your_ftp_password
```

**💡 권장사항**: 모든 설정은 `.env` 파일에서 통합 관리하는 것이 좋습니다.

## 🔧 변수 추가/수정 방법

### 1. 새로운 공통 변수 추가
```yaml
# group_vars/all.yml에 추가
new_common_variable: "value"
```

### 2. 새로운 역할별 변수 추가
```yaml
# group_vars/web.yml에 추가
web_specific_variable: "value"
```

### 3. 새로운 역할별 변수 추가
```yaml
# group_vars/search.yml에 추가
search_specific_variable: "value"
```

### 4. Python 코드에서 동적 변수 설정
```python
variable_manager = AnsibleVariableManager()
variable_manager.set_variable("dynamic_var", "dynamic_value")
```
