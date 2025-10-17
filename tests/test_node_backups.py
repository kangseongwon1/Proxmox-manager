#!/usr/bin/env python3
"""
노드별 백업 조회 API 테스트
"""

import requests
import json

# 웹 애플리케이션 설정
WEB_URL = "http://localhost:5000"

def test_node_backups_api():
    """노드별 백업 조회 API 테스트"""
    print("🔍 노드별 백업 조회 API 테스트")
    print("=" * 60)
    
    # 1. 모든 노드의 백업 목록 조회
    print("\n1️⃣ 모든 노드의 백업 목록 조회:")
    all_backups_url = f"{WEB_URL}/api/backups/nodes"
    
    print(f"   URL: {all_backups_url}")
    
    try:
        response = requests.get(all_backups_url, timeout=30)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Text: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 성공: {json.dumps(result, indent=2)}")
            
            # 백업 통계 출력
            if result.get('success') and result.get('data'):
                data = result['data']
                print(f"\n   📊 백업 통계:")
                print(f"      총 백업 개수: {data.get('total_count', 0)}")
                print(f"      총 크기: {data.get('total_size_gb', 0)} GB")
                
                if data.get('node_stats'):
                    print(f"      노드별 통계:")
                    for node, stats in data['node_stats'].items():
                        print(f"        {node}: {stats['backup_count']}개, {stats['total_size_gb']} GB")
        else:
            print(f"   ❌ 실패: {response.text}")
            
    except Exception as e:
        print(f"   ❌ 요청 실패: {e}")
    
    # 2. 특정 노드의 백업 목록 조회
    print("\n2️⃣ 특정 노드의 백업 목록 조회:")
    node_backups_url = f"{WEB_URL}/api/backups/nodes/prox"
    
    print(f"   URL: {node_backups_url}")
    
    try:
        response = requests.get(node_backups_url, timeout=30)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Text: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 성공: {json.dumps(result, indent=2)}")
        else:
            print(f"   ❌ 실패: {response.text}")
            
    except Exception as e:
        print(f"   ❌ 요청 실패: {e}")

if __name__ == "__main__":
    test_node_backups_api() 