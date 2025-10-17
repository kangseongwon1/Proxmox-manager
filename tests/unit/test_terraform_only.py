#!/usr/bin/env python3
"""
Terraform 서비스만 테스트하는 스크립트
"""

import os
import sys
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.terraform_service import TerraformService

def test_terraform_service():
    """Terraform 서비스 테스트"""
    print("🔧 Terraform 서비스 테스트 시작")
    
    # Terraform 서비스 초기화
    terraform_service = TerraformService()
    
    # 1. tfvars 파일 로드 테스트
    print("\n🔧 tfvars 파일 로드 테스트")
    try:
        tfvars = terraform_service.load_tfvars()
        print(f"✅ tfvars 로드 성공: {len(tfvars.get('servers', {}))}개 서버")
        print(f"📄 tfvars 내용 미리보기: {json.dumps(list(tfvars.get('servers', {}).keys()), indent=2)}")
    except Exception as e:
        print(f"❌ tfvars 로드 실패: {e}")
        return
    
    # 2. 서버 설정 생성 테스트
    print("\n🔧 서버 설정 생성 테스트")
    test_server_data = {
        'name': 'test-terraform-only',
        'cpu': 2,
        'memory': 4096,
        'role': 'web',
        'ip_address': ['192.168.1.102'],
        'disks': [
            {
                'size': 50,
                'interface': 'scsi0',
                'file_format': 'auto',
                'disk_type': 'ssd',
                'datastore_id': 'local-lvm'
            }
        ],
        'network_devices': [
            {
                'bridge': 'vmbr0',
                'ip_address': '192.168.1.102',
                'subnet': 24,
                'gateway': '192.168.1.1'
            }
        ],
        'template_vm_id': 8000,
        'vm_username': 'rocky',
        'vm_password': 'rocky123'
    }
    
    try:
        config_success = terraform_service.create_server_config(test_server_data)
        print(f"✅ 서버 설정 생성 결과: {config_success}")
        
        if config_success:
            # 3. 인프라 배포 테스트
            print("\n🔧 인프라 배포 테스트")
            deploy_success, deploy_message = terraform_service.deploy_infrastructure()
            print(f"✅ 인프라 배포 결과: success={deploy_success}")
            print(f"📄 배포 메시지: {deploy_message[:200]}...")
            
            # 4. 테스트 서버 설정 제거
            print("\n🔧 테스트 서버 설정 제거")
            remove_success = terraform_service.remove_server_config('test-terraform-only')
            print(f"✅ 서버 설정 제거 결과: {remove_success}")
        else:
            print("❌ 서버 설정 생성 실패")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Terraform 서비스 테스트 완료")

if __name__ == "__main__":
    test_terraform_service() 