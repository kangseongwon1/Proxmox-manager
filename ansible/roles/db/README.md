# DB 역할

- MariaDB 10.11 설치
- root 비밀번호를 dmc1234!로 초기화
- 서비스 자동 실행

초기 세팅 쿼리:

```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY 'dmc1234!';
``` 