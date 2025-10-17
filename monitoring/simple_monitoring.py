#!/usr/bin/env python3
"""
🚀 간단한 모니터링 시스템
Prometheus와 Grafana 없이도 기본적인 메트릭 수집 및 제공
"""

import json
import time
import threading
import requests
from datetime import datetime
from flask import Flask, jsonify
import random

class SimpleMonitoring:
    def __init__(self):
        self.metrics = {}
        self.servers = [
            {'ip': '192.168.0.10', 'port': '22', 'status': 'healthy'},
            {'ip': '192.168.0.111', 'port': '20222', 'status': 'healthy'},
            {'ip': '192.168.0.112', 'port': '20222', 'status': 'warning'},
            {'ip': '192.168.0.113', 'port': '20222', 'status': 'healthy'},
            {'ip': '192.168.0.114', 'port': '20222', 'status': 'healthy'},
            {'ip': '192.168.0.115', 'port': '20222', 'status': 'healthy'},
            {'ip': '192.168.0.116', 'port': '20222', 'status': 'healthy'},
            {'ip': '192.168.0.117', 'port': '20222', 'status': 'critical'},
            {'ip': '192.168.0.118', 'port': '20222', 'status': 'healthy'},
            {'ip': '192.168.0.119', 'port': '20222', 'status': 'healthy'}
        ]
        
        # 메트릭 수집 시작
        self.start_metric_collection()
    
    def generate_sample_metrics(self, server_ip):
        """샘플 메트릭 생성 (실제 환경에서는 SSH로 실제 데이터 수집)"""
        timestamp = int(time.time())
        
        return {
            'timestamp': timestamp,
            'cpu_usage': random.uniform(10, 85),
            'memory_usage': random.uniform(20, 90),
            'disk_usage': random.uniform(15, 75),
            'network_usage': random.uniform(5, 60),
            'status': self.get_server_status(server_ip)
        }
    
    def get_server_status(self, server_ip):
        """서버 상태 반환"""
        server = next((s for s in self.servers if s['ip'] == server_ip), None)
        return server['status'] if server else 'unknown'
    
    def collect_metrics(self):
        """메트릭 수집 (5초마다)"""
        while True:
            for server in self.servers:
                server_ip = server['ip']
                self.metrics[server_ip] = self.generate_sample_metrics(server_ip)
            
            time.sleep(5)
    
    def start_metric_collection(self):
        """백그라운드에서 메트릭 수집 시작"""
        thread = threading.Thread(target=self.collect_metrics, daemon=True)
        thread.start()
    
    def get_all_metrics(self):
        """모든 서버의 메트릭 반환"""
        return self.metrics
    
    def get_server_metrics(self, server_ip):
        """특정 서버의 메트릭 반환"""
        return self.metrics.get(server_ip, {})
    
    def get_summary_stats(self):
        """요약 통계 반환"""
        total = len(self.servers)
        healthy = len([s for s in self.servers if s['status'] == 'healthy'])
        warning = len([s for s in self.servers if s['status'] == 'warning'])
        critical = len([s for s in self.servers if s['status'] == 'critical'])
        
        return {
            'total_servers': total,
            'healthy_servers': healthy,
            'warning_servers': warning,
            'critical_servers': critical,
            'last_update': datetime.now().isoformat()
        }

# Flask 앱 생성
app = Flask(__name__)
monitoring = SimpleMonitoring()

@app.route('/api/monitoring/metrics')
def get_metrics():
    """모든 서버 메트릭 반환"""
    return jsonify(monitoring.get_all_metrics())

@app.route('/api/monitoring/metrics/<server_ip>')
def get_server_metrics(server_ip):
    """특정 서버 메트릭 반환"""
    return jsonify(monitoring.get_server_metrics(server_ip))

@app.route('/api/monitoring/summary')
def get_summary():
    """요약 통계 반환"""
    return jsonify(monitoring.get_summary_stats())

@app.route('/api/monitoring/servers')
def get_servers():
    """서버 목록 반환"""
    return jsonify(monitoring.servers)

if __name__ == '__main__':
    print("🚀 간단한 모니터링 시스템 시작...")
    print("📊 API 엔드포인트:")
    print("  - GET /api/monitoring/metrics (모든 메트릭)")
    print("  - GET /api/monitoring/metrics/<IP> (특정 서버 메트릭)")
    print("  - GET /api/monitoring/summary (요약 통계)")
    print("  - GET /api/monitoring/servers (서버 목록)")
    print("🌐 http://localhost:5001 에서 실행됩니다.")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
