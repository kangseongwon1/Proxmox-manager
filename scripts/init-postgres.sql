-- PostgreSQL 초기화 스크립트
-- Proxmox Manager 데이터베이스 설정

-- 데이터베이스 생성 (이미 생성됨)
-- CREATE DATABASE proxmox_manager;

-- 연결 풀 설정
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- 인덱스 최적화 설정
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;

-- 로그 설정
ALTER SYSTEM SET log_statement = 'none';
ALTER SYSTEM SET log_min_duration_statement = 1000;

-- 설정 적용
SELECT pg_reload_conf();

-- 확장 설치
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 사용자 권한 설정
GRANT ALL PRIVILEGES ON DATABASE proxmox_manager TO proxmox;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO proxmox;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO proxmox;
