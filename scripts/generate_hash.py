#!/usr/bin/env python3
from werkzeug.security import generate_password_hash

# 기본 계정들의 비밀번호 해시 생성
passwords = {
    'admin': 'admin123!',
    'dev1': 'dev123!',
    'dev2': 'dev123!'
}

print("=== 비밀번호 해시 생성 ===")
for username, password in passwords.items():
    hash_value = generate_password_hash(password)
    print(f"{username}: {hash_value}")

print("\n=== users.json에 복사할 내용 ===")
print('{')
for i, (username, password) in enumerate(passwords.items()):
    hash_value = generate_password_hash(password)
    comma = ',' if i < len(passwords) - 1 else ''
    print(f'  "{username}": {{')
    print(f'    "password_hash": "{hash_value}",')
    print(f'    "role": "{"admin" if username == "admin" else "developer"}",')
    print(f'    "email": "{username}@dmcmedia.co.kr",')
    print(f'    "name": "{"시스템 관리자" if username == "admin" else f"개발자 {username[-1] if username != "admin" else ""}"}",')
    print(f'    "created_at": "2024-01-01T00:00:00Z",')
    print(f'    "last_login": null,')
    print(f'    "is_active": true')
    print(f'  }}{comma}')
print('}') 