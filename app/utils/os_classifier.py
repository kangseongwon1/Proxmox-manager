"""
OS 분류 유틸리티
"""
import re
from typing import Optional

def classify_os_type(image_name: str, template_vm_id: Optional[str] = None) -> str:
    """
    이미지 이름이나 템플릿 VM ID를 기반으로 OS 타입을 분류합니다.
    
    Args:
        image_name: 이미지 이름 (예: 'rocky-9-template', 'ubuntu-22.04-template')
        template_vm_id: 템플릿 VM ID (선택사항)
    
    Returns:
        str: OS 계열 ('rocky', 'ubuntu', 'debian', 'centos', 'rhel' 등)
    """
    if not image_name:
        return 'rocky'  # 기본값
    
    # 문자열로 변환하여 안전하게 처리
    image_name = str(image_name)
    
    # 소문자로 변환하여 비교
    image_lower = image_name.lower()
    
    # Rocky Linux 패턴
    if any(pattern in image_lower for pattern in ['rocky', 'rockylinux']):
        return 'rocky'
    
    # CentOS 패턴
    if any(pattern in image_lower for pattern in ['centos', 'cent']):
        return 'centos'
    
    # Red Hat Enterprise Linux 패턴
    if any(pattern in image_lower for pattern in ['rhel', 'redhat', 'red-hat']):
        return 'rhel'
    
    # Ubuntu 패턴
    if any(pattern in image_lower for pattern in ['ubuntu', 'ubnt']):
        return 'ubuntu'
    
    # Debian 패턴
    if any(pattern in image_lower for pattern in ['debian', 'deb']):
        return 'debian'
    
    # AlmaLinux 패턴
    if any(pattern in image_lower for pattern in ['alma', 'almalinux']):
        return 'alma'
    
    # Fedora 패턴
    if any(pattern in image_lower for pattern in ['fedora', 'fed']):
        return 'fedora'
    
    # SUSE 패턴
    if any(pattern in image_lower for pattern in ['suse', 'opensuse', 'sles']):
        return 'suse'
    
    # 기본값 (Rocky Linux)
    return 'rocky'

def get_os_family(os_type: str) -> str:
    """
    OS 타입을 기반으로 OS 계열을 반환합니다.
    
    Args:
        os_type: OS 타입 ('rocky', 'ubuntu', 'debian' 등)
    
    Returns:
        str: OS 계열 ('RedHat', 'Debian', 'Suse' 등)
    """
    # RedHat 계열
    redhat_family = ['rocky', 'centos', 'rhel', 'alma', 'fedora']
    if os_type in redhat_family:
        return 'RedHat'
    
    # Debian 계열
    debian_family = ['ubuntu', 'debian']
    if os_type in debian_family:
        return 'Debian'
    
    # SUSE 계열
    suse_family = ['suse', 'opensuse', 'sles']
    if os_type in suse_family:
        return 'Suse'
    
    # 기본값
    return 'RedHat'

def get_default_username(os_type: str) -> str:
    """
    OS 타입에 따른 기본 사용자명을 반환합니다.
    
    Args:
        os_type: OS 타입
    
    Returns:
        str: 기본 사용자명
    """
    username_map = {
        'rocky': 'rocky',
        'centos': 'centos',
        'rhel': 'rhel',
        'ubuntu': 'ubuntu',
        'debian': 'debian',
        'alma': 'alma',
        'fedora': 'fedora',
        'suse': 'suse'
    }
    
    return username_map.get(os_type, 'rocky')

def get_default_password(os_type: str) -> str:
    """
    OS 타입에 따른 기본 비밀번호를 반환합니다.
    
    Args:
        os_type: OS 타입
    
    Returns:
        str: 기본 비밀번호
    """
    password_map = {
        'rocky': 'rocky123',
        'centos': 'centos123',
        'rhel': 'rhel123',
        'ubuntu': 'ubuntu123',
        'debian': 'debian123',
        'alma': 'alma123',
        'fedora': 'fedora123',
        'suse': 'suse123'
    }
    
    return password_map.get(os_type, 'rocky123')
