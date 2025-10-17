"""
메인 라우트 블루프린트
"""

"""랜더링 용"""
from flask import Blueprint, render_template, current_app, jsonify, request, send_from_directory
import logging
from flask_login import login_required, current_user
from app.models import User, Server, Notification
from app.services import ProxmoxService
import json


# 로거 설정
logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    """메인 페이지"""
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    """대시보드"""
    servers = Server.query.all()
    return render_template('dashboard.html', servers=servers)

@bp.route('/servers')
@login_required
def servers():
    """서버 목록"""
    servers = Server.query.all()
    return render_template('servers/index.html', servers=servers)

@bp.route('/admin')
@login_required
def admin():
    """관리자 페이지"""
    users = User.query.all()
    servers = Server.query.all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(5).all()
    return render_template('admin/index.html', users=users, servers=servers, notifications=notifications)

# 기존 템플릿과 호환성을 위한 라우트들
@bp.route('/instances/content')
@login_required
def instances_content():
    """인스턴스 콘텐츠 (기존 템플릿 호환)"""
    # roles 변수 준비 (기존 app.py와 동일)
    roles = {
        'web': {'name': '웹서버', 'description': '웹 서비스 제공'},
        'was': {'name': 'WAS', 'description': '애플리케이션 서버'},
        'java': {'name': 'JAVA', 'description': '자바 서버'},
        'search': {'name': '검색', 'description': '검색 서버'},
        'ftp': {'name': 'FTP', 'description': '파일 서버'},
        'db': {'name': 'DB', 'description': '데이터베이스 서버'}
    }
    
    try:
        logger.info("🔍 /instances/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        # servers 변수 초기화
        servers = {}
        server_list = []
        
        if result['success']:
            servers = result['data']['servers']
            # 서버 목록을 템플릿에서 사용할 수 있는 형식으로 변환
            for server_name, server_info in servers.items():
                vm_info = {
                    'vmid': server_info.get('vmid'),
                    'name': server_name,
                    'status': server_info.get('status', 'unknown'),
                    'cpu': server_info.get('cpu', 0),
                    'mem': server_info.get('memory', 0),
                    'maxmem': server_info.get('maxmem', 0),
                    'disk': server_info.get('disk', 0),
                    'maxdisk': server_info.get('maxdisk', 0),
                    'uptime': server_info.get('uptime', 0),
                    'role': server_info.get('role', 'unknown'),
                    'ip_addresses': server_info.get('ip_addresses', [])
                }
                server_list.append(vm_info)
        else:
            # 데이터베이스에서 직접 조회
            with proxmox_service._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, vmid, status, ip_address, role, os_type, cpu, memory, firewall_group
                    FROM servers
                ''')
                db_servers = cursor.fetchall()
                
                for db_server in db_servers:
                    vm_info = {
                        'vmid': db_server['vmid'],
                        'name': db_server['name'],
                        'status': db_server['status'] or 'unknown',
                        'cpu': db_server['cpu'] or 0,
                        'mem': 0,
                        'maxmem': db_server['memory'] or 0,
                        'disk': 0,
                        'maxdisk': 0,
                        'uptime': 0,
                        'ip_address': db_server['ip_address'],
                        'role': db_server['role'],
                        'firewall_group': db_server['firewall_group'],
                        'os_type': db_server['os_type']
                    }
                    server_list.append(vm_info)
        
        return render_template('partials/instances_content.html', servers=server_list, roles=roles, server_data=servers)
    except Exception as e:
        logger.error(f"/instances/content 예외 발생: {str(e)}")
        return render_template('partials/instances_content.html', servers=[], roles=roles, server_data={})

@bp.route('/dashboard/content')
@login_required
def dashboard_content():
    """대시보드 콘텐츠 (기존 템플릿 호환)"""
    try:
        logger.info("🔍 /dashboard/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        logger.info(f"🔍 get_all_vms 결과: {result}")
        
        if result['success']:
            servers = result['data']['servers']
            stats = result['data']['stats']
            total = stats.get('total_servers', 0)
            running = stats.get('running_servers', 0)
            stopped = stats.get('stopped_servers', 0)
            
            logger.info(f"🔍 서버 수: {len(servers)}")
            logger.info(f"🔍 통계: total={total}, running={running}, stopped={stopped}")
        else:
            logger.error(f"get_all_vms 실패: {result.get('message', '알 수 없는 오류')}")
            # 데이터베이스에서 직접 조회
            with proxmox_service._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, vmid, status, ip_address, role, os_type, cpu, memory, firewall_group
                    FROM servers
                ''')
                db_servers = cursor.fetchall()
                
                servers = []
                for db_server in db_servers:
                    vm_info = {
                        'vmid': db_server['vmid'],
                        'name': db_server['name'],
                        'status': db_server['status'] or 'unknown',
                        'cpu': db_server['cpu'] or 0,
                        'mem': 0,
                        'maxmem': db_server['memory'] or 0,
                        'disk': 0,
                        'maxdisk': 0,
                        'uptime': 0,
                        'ip_address': db_server['ip_address'],
                        'role': db_server['role'],
                        'firewall_group': db_server['firewall_group'],
                        'os_type': db_server['os_type']
                    }
                    servers.append(vm_info)
                
                total = len(servers)
                running = len([s for s in servers if s['status'] == 'running'])
                stopped = len([s for s in servers if s['status'] == 'stopped'])
        
        return render_template('partials/dashboard_content.html', 
                             servers=servers, total=total, running=running, stopped=stopped)
    except Exception as e:
        logger.error(f"/dashboard/content 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('partials/dashboard_content.html', servers=[], total=0, running=0, stopped=0)

@bp.route('/storage/content')
@login_required
def storage_content():
    """스토리지 콘텐츠 (기존 템플릿 호환)"""
    try:
        logger.info("🔍 /storage/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_storage_info()
        
        logger.info(f"🔍 get_storage_info 결과: {result}")
        
        if result['success']:
            storages = result['data']
            logger.info(f"🔍 스토리지 수: {len(storages)}")
        else:
            logger.error(f"get_storage_info 실패: {result.get('message', '알 수 없는 오류')}")
            storages = []
        
        return render_template('partials/storage_content.html', storages=storages)
    except Exception as e:
        logger.error(f"/storage/content 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('partials/storage_content.html', storages=[])

@bp.route('/admin/iam/content')
@login_required
def admin_iam_content():
    """관리자 IAM 콘텐츠 (기존 템플릿 호환)"""
    try:
        logger.info("🔍 /admin/iam/content 호출됨")
        users = User.query.all()
        return render_template('partials/admin_iam_content.html', users=users)
    except Exception as e:
        logger.error(f"/admin/iam/content 예외 발생: {str(e)}")
        return render_template('partials/admin_iam_content.html', users=[])

@bp.route('/firewall/groups/content')
@login_required
def firewall_groups_content():
    """방화벽 그룹 콘텐츠 (기존 템플릿 호환)"""
    try:
        logger.info("🔍 /firewall/groups/content 호출됨")
        # 방화벽 그룹 데이터는 JavaScript에서 AJAX로 가져옴
        return render_template('partials/firewall_groups_content.html')
    except Exception as e:
        logger.error(f"/firewall/groups/content 예외 발생: {str(e)}")
        return render_template('partials/firewall_groups_content.html')

@bp.route('/firewall/group-detail/content')
@login_required
def firewall_group_detail_content():
    """방화벽 그룹 상세 콘텐츠 (기존 템플릿 호환)"""
    try:
        logger.info("🔍 /firewall/group-detail/content 호출됨")
        group_name = request.args.get('group')
        return render_template('partials/firewall_group_detail_content.html', group_name=group_name)
    except Exception as e:
        logger.error(f"/firewall/group-detail/content 예외 발생: {str(e)}")
        return render_template('partials/firewall_group_detail_content.html', group_name='')

@bp.route('/backups/content')
@login_required
def backups_content():
    """백업관리 콘텐츠"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_node_backups()
        data = result['data'] if result.get('success') else {'backups': [], 'node_stats': {}, 'total_count': 0, 'total_size_gb': 0}
        return render_template('partials/backups_content.html', data=data)
    except Exception as e:
        logger.error(f"/backups/content 예외 발생: {str(e)}")
        return render_template('partials/backups_content.html', data={'backups': [], 'node_stats': {}, 'total_count': 0, 'total_size_gb': 0})

@bp.route('/instances/multi-server-summary')
@login_required
def multi_server_summary():
    """멀티 서버 요약"""
    try:
        return render_template('partials/multi_server_summary.html')
    except Exception as e:
        logger.error(f"멀티 서버 요약 예외 발생: {str(e)}")
        return render_template('partials/multi_server_summary.html')

# 프론트에서 /api 경로로 호출하는 호환용 엔드포인트
@bp.route('/api/instances/multi-server-summary')
@login_required
def api_multi_server_summary():
    try:
        return render_template('partials/multi_server_summary.html')
    except Exception as e:
        logger.error(f"멀티 서버 요약(API) 예외 발생: {str(e)}")
        return render_template('partials/multi_server_summary.html')

@bp.route('/favicon.ico')
def favicon():
    """파비콘"""
    from flask import send_from_directory
    return send_from_directory('static', 'favicon.ico')

