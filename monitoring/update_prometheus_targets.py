#!/usr/bin/env python3
"""
Prometheus 타겟 업데이트 스크립트
새로 생성된 서버의 Node Exporter를 Prometheus 설정에 자동으로 추가합니다.
"""

import os
import yaml
import requests
import json
from typing import List, Dict, Any

def load_prometheus_config(config_path: str = "prometheus.yml") -> Dict[str, Any]:
    """Prometheus 설정 파일 로드"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ Prometheus 설정 파일을 찾을 수 없습니다: {config_path}")
        return None
    except yaml.YAMLError as e:
        print(f"❌ YAML 파싱 오류: {e}")
        return None

def save_prometheus_config(config: Dict[str, Any], config_path: str = "prometheus.yml") -> bool:
    """Prometheus 설정 파일 저장"""
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"❌ 설정 파일 저장 실패: {e}")
        return False

def get_current_targets(config: Dict[str, Any]) -> List[str]:
    """현재 Prometheus 설정에서 Node Exporter 타겟 목록 추출"""
    targets = []
    
    for job in config.get('scrape_configs', []):
        if job.get('job_name') == 'node-exporter':
            static_configs = job.get('static_configs', [])
            for static_config in static_configs:
                targets.extend(static_config.get('targets', []))
    
    return targets

def add_node_exporter_target(config: Dict[str, Any], server_ip: str, port: int = 9100) -> bool:
    """Node Exporter 타겟 추가"""
    target = f"{server_ip}:{port}"
    
    # 기존 타겟 확인
    current_targets = get_current_targets(config)
    if target in current_targets:
        print(f"ℹ️ 타겟이 이미 존재합니다: {target}")
        return True
    
    # node-exporter job 찾기 또는 생성
    node_exporter_job = None
    for job in config.get('scrape_configs', []):
        if job.get('job_name') == 'node-exporter':
            node_exporter_job = job
            break
    
    if not node_exporter_job:
        # node-exporter job이 없으면 생성
        node_exporter_job = {
            'job_name': 'node-exporter',
            'static_configs': [],
            'scrape_interval': '10s',
            'metrics_path': '/metrics'
        }
        config['scrape_configs'].append(node_exporter_job)
    
    # 타겟 추가
    if not node_exporter_job.get('static_configs'):
        node_exporter_job['static_configs'] = []
    
    # 기존 static_configs에 타겟 추가
    if node_exporter_job['static_configs']:
        node_exporter_job['static_configs'][0]['targets'].append(target)
    else:
        node_exporter_job['static_configs'].append({
            'targets': [target]
        })
    
    print(f"✅ Node Exporter 타겟 추가: {target}")
    return True

def remove_node_exporter_target(config: Dict[str, Any], server_ip: str, port: int = 9100) -> bool:
    """Node Exporter 타겟 제거"""
    target = f"{server_ip}:{port}"
    
    for job in config.get('scrape_configs', []):
        if job.get('job_name') == 'node-exporter':
            for static_config in job.get('static_configs', []):
                targets = static_config.get('targets', [])
                if target in targets:
                    targets.remove(target)
                    print(f"✅ Node Exporter 타겟 제거: {target}")
                    return True
    
    print(f"ℹ️ 제거할 타겟을 찾을 수 없습니다: {target}")
    return True

def restart_prometheus() -> bool:
    """Prometheus 서비스 재시작"""
    try:
        import subprocess
        result = subprocess.run(['sudo', 'systemctl', 'restart', 'prometheus'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Prometheus 서비스 재시작 완료")
            return True
        else:
            print(f"❌ Prometheus 재시작 실패: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Prometheus 재시작 오류: {e}")
        return False

def test_node_exporter_connection(server_ip: str, port: int = 9100) -> bool:
    """Node Exporter 연결 테스트"""
    try:
        url = f"http://{server_ip}:{port}/metrics"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ Node Exporter 연결 성공: {server_ip}:{port}")
            return True
        else:
            print(f"❌ Node Exporter 연결 실패: {server_ip}:{port} (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Node Exporter 연결 오류: {server_ip}:{port} - {e}")
        return False

def main():
    """메인 함수"""
    import sys
    
    if len(sys.argv) < 3:
        print("사용법:")
        print("  python3 update_prometheus_targets.py add <server_ip> [port]")
        print("  python3 update_prometheus_targets.py remove <server_ip> [port]")
        print("  python3 update_prometheus_targets.py list")
        print("  python3 update_prometheus_targets.py test <server_ip> [port]")
        sys.exit(1)
    
    action = sys.argv[1]
    server_ip = sys.argv[2] if len(sys.argv) > 2 else None
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 9100
    
    # Prometheus 설정 로드
    config = load_prometheus_config()
    if not config:
        sys.exit(1)
    
    if action == "add":
        if not server_ip:
            print("❌ 서버 IP가 필요합니다")
            sys.exit(1)
        
        # Node Exporter 연결 테스트
        if not test_node_exporter_connection(server_ip, port):
            print("⚠️ Node Exporter 연결 실패. 타겟을 추가하시겠습니까? (y/n)")
            response = input().lower()
            if response != 'y':
                print("타겟 추가를 취소했습니다.")
                sys.exit(1)
        
        # 타겟 추가
        if add_node_exporter_target(config, server_ip, port):
            if save_prometheus_config(config):
                restart_prometheus()
            else:
                sys.exit(1)
    
    elif action == "remove":
        if not server_ip:
            print("❌ 서버 IP가 필요합니다")
            sys.exit(1)
        
        # 타겟 제거
        if remove_node_exporter_target(config, server_ip, port):
            if save_prometheus_config(config):
                restart_prometheus()
            else:
                sys.exit(1)
    
    elif action == "list":
        targets = get_current_targets(config)
        print("현재 Node Exporter 타겟:")
        for target in targets:
            print(f"  - {target}")
    
    elif action == "test":
        if not server_ip:
            print("❌ 서버 IP가 필요합니다")
            sys.exit(1)
        
        test_node_exporter_connection(server_ip, port)
    
    else:
        print(f"❌ 알 수 없는 액션: {action}")
        sys.exit(1)

if __name__ == "__main__":
    main()
