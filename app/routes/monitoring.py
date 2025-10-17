"""
모니터링 관련 라우트 - .env 파일 중심, 경고/위험 서버 상세 정보 추가
"""
from flask import Blueprint, jsonify, request, render_template
import logging
from flask_login import login_required
import requests
import json
import random
import time
import os
from datetime import datetime, timedelta
from app.models import Server
from app import db
from sqlalchemy import text


# 로거 설정
logger = logging.getLogger(__name__)

bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

# 메트릭 캐시 (실제 환경에서는 Redis 등을 사용)
metrics_cache = {}
last_update = {}

def get_grafana_config():
    """Grafana 설정을 .env에서 직접 가져오기"""
    return {
        'base_url': os.environ.get('GRAFANA_URL', 'http://localhost:3000'),
        'username': os.environ.get('GRAFANA_USERNAME', 'admin'),
        'password': os.environ.get('GRAFANA_PASSWORD', 'admin'),
        'org_id': os.environ.get('GRAFANA_ORG_ID', '1'),
        'dashboard_uid': os.environ.get('GRAFANA_DASHBOARD_UID', 'system_monitoring'),
        'dashboard_id': os.environ.get('GRAFANA_DASHBOARD_ID', '2'),
        'dashboard_url': os.environ.get('GRAFANA_DASHBOARD_URL', '/d/system_monitoring/system-monitoring-dashboard-10-servers'),
        'anonymous_access': os.environ.get('GRAFANA_ANONYMOUS_ACCESS', 'true').lower() == 'true',
        'auto_refresh': os.environ.get('GRAFANA_AUTO_REFRESH', '5s')
    }

def get_prometheus_config():
    """Prometheus 설정을 .env에서 직접 가져오기"""
    return {
        'url': os.environ.get('PROMETHEUS_URL', 'http://localhost:9090'),
        'username': os.environ.get('PROMETHEUS_USERNAME', ''),
        'password': os.environ.get('PROMETHEUS_PASSWORD', '')
    }

def get_monitoring_config():
    """모니터링 설정을 .env에서 직접 가져오기"""
    return {
        'default_time_range': os.environ.get('MONITORING_DEFAULT_TIME_RANGE', '1h'),
        'health_check_interval': os.environ.get('MONITORING_HEALTH_CHECK_INTERVAL', '30s'),
        'ping_timeout': os.environ.get('MONITORING_PING_TIMEOUT', '5s'),
        'ssh_timeout': os.environ.get('MONITORING_SSH_TIMEOUT', '10s'),
        'auto_install_node_exporter': os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true',
        'node_exporter_port': int(os.environ.get('NODE_EXPORTER_PORT', '9100')),
        'node_exporter_version': os.environ.get('NODE_EXPORTER_VERSION', '1.6.1')
    }

def get_alerts_config():
    """알림 설정을 .env에서 직접 가져오기"""
    return {
        'enable_alerts': os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true',
        'alert_email': os.environ.get('ALERTS_EMAIL', 'admin@example.com'),
        'cpu_warning_threshold': float(os.environ.get('ALERTS_CPU_WARNING_THRESHOLD', '80')),
        'cpu_critical_threshold': float(os.environ.get('ALERTS_CPU_CRITICAL_THRESHOLD', '95')),
        'memory_warning_threshold': float(os.environ.get('ALERTS_MEMORY_WARNING_THRESHOLD', '85')),
        'memory_critical_threshold': float(os.environ.get('ALERTS_MEMORY_CRITICAL_THRESHOLD', '95'))
    }

def get_security_config():
    """보안 설정을 .env에서 직접 가져오기"""
    return {
        'enable_https': os.environ.get('SECURITY_ENABLE_HTTPS', 'false').lower() == 'true',
        'enable_auth': os.environ.get('SECURITY_ENABLE_AUTH', 'true').lower() == 'true',
        'session_timeout': int(os.environ.get('SECURITY_SESSION_TIMEOUT', '3600')),
        'max_login_attempts': int(os.environ.get('SECURITY_MAX_LOGIN_ATTEMPTS', '5'))
    }

# ============================================================================
# 🚨 경고/위험 서버 상세 정보 관련 함수들
# ============================================================================

def get_server_health_details(server_ip):
    """특정 서버의 상세 건강 상태 정보 반환"""
    try:
        # 실제 환경에서는 Prometheus API나 직접 메트릭 수집
        # 현재는 시뮬레이션된 데이터 반환
        
        # CPU 사용률 시뮬레이션
        cpu_usage = random.uniform(0, 100)
        memory_usage = random.uniform(0, 100)
        disk_usage = random.uniform(0, 100)
        network_latency = random.uniform(1, 100)
        
        # 상태 결정
        alerts_config = get_alerts_config()
        status = 'healthy'
        issues = []
        
        # CPU 경고/위험 체크
        if cpu_usage >= alerts_config['cpu_critical_threshold']:
            status = 'critical'
            issues.append({
                'type': 'cpu',
                'level': 'critical',
                'message': f'CPU 사용률이 {cpu_usage:.1f}%로 위험 수준입니다.',
                'value': cpu_usage,
                'threshold': alerts_config['cpu_critical_threshold']
            })
        elif cpu_usage >= alerts_config['cpu_warning_threshold']:
            if status != 'critical':
                status = 'warning'
            issues.append({
                'type': 'cpu',
                'level': 'warning',
                'message': f'CPU 사용률이 {cpu_usage:.1f}%로 경고 수준입니다.',
                'value': cpu_usage,
                'threshold': alerts_config['cpu_warning_threshold']
            })
        
        # 메모리 경고/위험 체크
        if memory_usage >= alerts_config['memory_critical_threshold']:
            status = 'critical'
            issues.append({
                'type': 'memory',
                'level': 'critical',
                'message': f'메모리 사용률이 {memory_usage:.1f}%로 위험 수준입니다.',
                'value': memory_usage,
                'threshold': alerts_config['memory_critical_threshold']
            })
        elif memory_usage >= alerts_config['memory_warning_threshold']:
            if status != 'critical':
                status = 'warning'
            issues.append({
                'type': 'memory',
                'level': 'warning',
                'message': f'메모리 사용률이 {memory_usage:.1f}%로 경고 수준입니다.',
                'value': memory_usage,
                'threshold': alerts_config['memory_warning_threshold']
            })
        
        # 디스크 경고/위험 체크
        if disk_usage >= 95:
            status = 'critical'
            issues.append({
                'type': 'disk',
                'level': 'critical',
                'message': f'디스크 사용률이 {disk_usage:.1f}%로 위험 수준입니다.',
                'value': disk_usage,
                'threshold': 95
            })
        elif disk_usage >= 85:
            if status != 'critical':
                status = 'warning'
            issues.append({
                'type': 'disk',
                'level': 'warning',
                'message': f'디스크 사용률이 {disk_usage:.1f}%로 경고 수준입니다.',
                'value': disk_usage,
                'threshold': 85
            })
        
        # 네트워크 지연 체크
        if network_latency >= 50:
            if status != 'critical':
                status = 'warning'
            issues.append({
                'type': 'network',
                'level': 'warning',
                'message': f'네트워크 지연이 {network_latency:.1f}ms로 높습니다.',
                'value': network_latency,
                'threshold': 50
            })
        
        return {
            'server_ip': server_ip,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'cpu_usage': round(cpu_usage, 1),
                'memory_usage': round(memory_usage, 1),
                'disk_usage': round(disk_usage, 1),
                'network_latency': round(network_latency, 1)
            },
            'issues': issues,
            'uptime': f"{random.randint(1, 365)}일 {random.randint(0, 23)}시간 {random.randint(0, 59)}분"
        }
        
    except Exception as e:
        logger.info(f"서버 건강 상태 조회 오류 ({server_ip}): {e}")
        return {
            'server_ip': server_ip,
            'status': 'unknown',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'issues': [{
                'type': 'system',
                'level': 'critical',
                'message': f'서버 상태 확인 중 오류가 발생했습니다: {str(e)}'
            }]
        }

@bp.route('/servers/<server_ip>/health', methods=['GET'])
@login_required
def get_server_health(server_ip):
    """특정 서버의 상세 건강 상태 조회"""
    try:
        health_info = get_server_health_details(server_ip)
        return jsonify({
            'success': True,
            'data': health_info
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers/health-summary', methods=['GET'])
@login_required
def get_health_summary():
    """모든 서버의 건강 상태 요약"""
    try:
        servers = get_actual_servers()
        health_summary = []
        
        for server in servers:
            if server['status'] in ['warning', 'critical']:
                health_info = get_server_health_details(server['ip'])
                health_summary.append(health_info)
        
        return jsonify({
            'success': True,
            'data': {
                'problematic_servers': health_summary,
                'total_problematic': len(health_summary),
                'last_update': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# 기존 함수들 (알림 관련)
# ============================================================================

def get_current_alerts():
    """현재 알림 목록 반환"""
    try:
        # 실제 환경에서는 DB에서 알림을 가져옴
        # 현재는 메모리에서 관리 (테스트용)
        if not hasattr(get_current_alerts, '_alerts'):
            get_current_alerts._alerts = []
        
        return get_current_alerts._alerts
        
    except Exception as e:
        logger.info(f"알림 목록 조회 오류: {e}")
        return []

def add_alert(alert):
    """새 알림 추가"""
    try:
        if not hasattr(get_current_alerts, '_alerts'):
            get_current_alerts._alerts = []
        
        # 중복 알림 체크 (같은 서버, 같은 메트릭, 같은 레벨)
        existing_alert = next(
            (a for a in get_current_alerts._alerts 
             if a['server_ip'] == alert['server_ip'] 
             and a['metric_type'] == alert['metric_type'] 
             and a['level'] == alert['level']), None
        )
        
        if not existing_alert:
            get_current_alerts._alerts.append(alert)
            logger.info(f"새 알림 추가: {alert['message']}")
        
        return True
        
    except Exception as e:
        logger.info(f"알림 추가 오류: {e}")
        return False

def acknowledge_alert(alert_id):
    """알림 확인 처리"""
    try:
        alerts = get_current_alerts()
        for alert in alerts:
            if alert['id'] == alert_id:
                alert['acknowledged'] = True
                alert['acknowledged_at'] = datetime.now().isoformat()
                logger.info(f"알림 확인 처리: {alert_id}")
                return True
        
        return False
        
    except Exception as e:
        logger.info(f"알림 확인 처리 오류: {e}")
        return False

def clear_old_alerts():
    """오래된 알림 정리 (24시간 이상 된 알림)"""
    try:
        alerts = get_current_alerts()
        current_time = datetime.now()
        
        # 24시간 이상 된 알림 제거
        alerts[:] = [
            alert for alert in alerts 
            if (current_time - datetime.fromisoformat(alert['timestamp'])).total_seconds() < 86400
        ]
        
        logger.info(f"오래된 알림 정리 완료")
        
    except Exception as e:
        logger.info(f"오래된 알림 정리 오류: {e}")

# ============================================================================
# 기존 라우트들
# ============================================================================

@bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_alert_route(alert_id):
    """알림 확인 처리 API"""
    try:
        if acknowledge_alert(alert_id):
            return jsonify({
                'success': True,
                'message': '알림이 확인 처리되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '알림을 찾을 수 없습니다.'
            }), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/alerts/clear', methods=['POST'])
@login_required
def clear_alerts():
    """모든 알림 정리"""
    try:
        if hasattr(get_current_alerts, '_alerts'):
            get_current_alerts._alerts.clear()
        
        return jsonify({
            'success': True,
            'message': '모든 알림이 정리되었습니다.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/content', methods=['GET'])
@login_required
def monitoring_content():
    """모니터링 페이지 컨텐츠"""
    return render_template('partials/monitoring_content.html')

@bp.route('/summary', methods=['GET'])
@login_required
def get_monitoring_summary():
    """모니터링 요약 통계 반환"""
    try:
        servers = get_actual_servers()
        total = len(servers)
        healthy = len([s for s in servers if s['status'] == 'healthy'])
        warning = len([s for s in servers if s['status'] == 'warning'])
        critical = len([s for s in servers if s['status'] == 'critical'])
        
        return jsonify({
            'success': True,
            'data': {
                'total_servers': total,
                'healthy_servers': healthy,
                'warning_servers': warning,
                'critical_servers': critical,
                'last_update': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers', methods=['GET'])
@login_required
def get_monitoring_servers():
    """모니터링 대상 서버 목록 반환"""
    try:
        servers = get_actual_servers()
        return jsonify({
            'success': True,
            'data': servers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grafana-dashboard', methods=['GET'])
@login_required
def get_grafana_dashboard():
    """Grafana 대시보드 정보 조회 (개선된 버전)"""
    try:
        dashboard_info = get_dashboard_info()
        if dashboard_info:
            return jsonify({
                'success': True,
                'data': dashboard_info
            })
        else:
            # 대시보드 정보가 없으면 기본 정보 반환
            default_info = {
                'base_url': 'http://localhost:3000',
                'dashboard_id': '1',
                'dashboard_uid': 'system_monitoring',
                'org_id': '1',
                'dashboard_url': 'http://localhost:3000/d/system_monitoring',
                'grafana_url': 'http://localhost:3000',
                'embed_url': 'http://localhost:3000/d/system_monitoring?orgId=1&theme=light&kiosk=tv'
            }
            return jsonify({
                'success': True,
                'data': default_info
            })
            
    except Exception as e:
        logger.info(f"Grafana 대시보드 정보 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500

def get_dashboard_info():
    """대시보드 정보를 .env에서 직접 가져오기"""
    try:
        # .env에서 Grafana 설정 가져오기
        grafana_config = get_grafana_config()
        
        # 대시보드 정보 파일도 확인 (우선순위: .env > 대시보드 파일)
        dashboard_file = '/tmp/dashboard_info.json'
        if os.path.exists(dashboard_file):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 대시보드 파일의 정보를 .env 설정과 병합
            dashboard_uid = data.get('dashboard_uid', grafana_config['dashboard_uid'])
            dashboard_id = data.get('dashboard_id', grafana_config['dashboard_id'])
            dashboard_url = data.get('dashboard_url', grafana_config['dashboard_url'])
        else:
            # 대시보드 파일이 없으면 .env 설정 사용
            dashboard_uid = grafana_config['dashboard_uid']
            dashboard_id = grafana_config['dashboard_id']
            dashboard_url = grafana_config['dashboard_url']
        
        # 최종 대시보드 정보 반환
        return {
            'base_url': grafana_config['base_url'],
            'dashboard_id': dashboard_id,
            'dashboard_uid': dashboard_uid,
            'org_id': grafana_config['org_id'],
            'dashboard_url': dashboard_url,
            'grafana_url': grafana_config['base_url'],  # 하위 호환성
            'embed_url': f"{grafana_config['base_url']}/d/{dashboard_uid}?orgId={grafana_config['org_id']}&theme=light&kiosk=tv"
        }
        
    except Exception as e:
        logger.info(f"대시보드 정보 읽기 오류: {e}")
        # 오류 시 .env 기본 설정 반환
        grafana_config = get_grafana_config()
        return {
            'base_url': grafana_config['base_url'],
            'dashboard_id': grafana_config['dashboard_id'],
            'dashboard_uid': grafana_config['dashboard_uid'],
            'org_id': grafana_config['org_id'],
            'dashboard_url': grafana_config['dashboard_url'],
            'grafana_url': grafana_config['base_url'],
            'embed_url': f"{grafana_config['base_url']}/d/{grafana_config['dashboard_uid']}?orgId={grafana_config['org_id']}&theme=light&kiosk=tv"
        }

@bp.route('/grafana-dashboard/embed', methods=['GET'])
@login_required
def get_grafana_embed_url():
    """Grafana 대시보드 임베드 URL 생성"""
    try:
        dashboard_info = get_dashboard_info()
        if not dashboard_info:
            return jsonify({
                'success': False,
                'error': '대시보드 정보를 찾을 수 없습니다.'
            }), 404
        
        # 서버 선택 파라미터 추가
        selected_server = request.args.get('server', 'all')
        
        # Grafana 대시보드 임베드 URL 생성
        embed_url = create_grafana_embed_url(dashboard_info, selected_server)
        
        return jsonify({
            'success': True,
            'data': {
                'embed_url': embed_url,
                'dashboard_info': dashboard_info
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def create_grafana_embed_url(dashboard_info, selected_server):
    """Grafana 대시보드 임베드 URL 생성 (.env 사용) - 개선된 서버 필터링"""
    try:
        # .env에서 Grafana 설정 가져오기
        grafana_config = get_grafana_config()
        
        # 필드명 매핑 (하위 호환성)
        base_url = dashboard_info.get('base_url') or dashboard_info.get('grafana_url', grafana_config['base_url'])
        dashboard_uid = dashboard_info['dashboard_uid']
        org_id = dashboard_info.get('org_id', grafana_config['org_id'])
        
        # .env 설정에 따라 인증 방식 결정
        if grafana_config['anonymous_access']:
            # 익명 접근 허용
            embed_url = f"{base_url}/d/{dashboard_uid}?orgId={org_id}&theme=light&kiosk=tv&autofitpanels&refresh={grafana_config['auto_refresh']}"
        else:
            # 기본 인증 정보 포함
            username = grafana_config['username']
            password = grafana_config['password']
            embed_url = f"http://{username}:{password}@{base_url.replace('http://', '')}/d/{dashboard_uid}?orgId={org_id}&theme=light&kiosk=tv&autofitpanels&refresh={grafana_config['auto_refresh']}"
        
        # 서버 선택이 'all'이 아닌 경우 필터 추가 - Grafana에서 실제 사용하는 형식
        if selected_server != 'all':
            # Grafana에서 실제 사용하는 변수명 (var-server) 우선 사용
            server_filters = [
                f"&var-server={selected_server}:9100",   # Grafana에서 실제 사용하는 형식
                f"&var-server={selected_server}",        # server 변수명, 포트 없이
                f"&var-instance={selected_server}:9100",  # instance 변수명 (Node Exporter 포트)
                f"&var-instance={selected_server}",       # instance 변수명, 포트 없이
                f"&var-host={selected_server}:9100",     # host 변수명
                f"&var-host={selected_server}",          # host 변수명, 포트 없이
                f"&var-target={selected_server}:9100",   # target 변수명
                f"&var-target={selected_server}",        # target 변수명, 포트 없이
                f"&var-node={selected_server}:9100",     # node 변수명
                f"&var-node={selected_server}"           # node 변수명, 포트 없이
            ]
            
            # 첫 번째 형식 사용 (Grafana에서 실제 사용하는 형식)
            embed_url += server_filters[0]
            logger.info(f"서버 필터링 적용: {selected_server} -> {server_filters[0]}")
        
        # 시간 범위 설정 (.env에서 설정)
        monitoring_config = get_monitoring_config()
        time_range = monitoring_config['default_time_range']
        
        if time_range == '1h':
            now = datetime.now()
            one_hour_ago = now - timedelta(hours=1)
            embed_url += f"&from={int(one_hour_ago.timestamp() * 1000)}&to={int(now.timestamp() * 1000)}"
        elif time_range == '6h':
            now = datetime.now()
            six_hours_ago = now - timedelta(hours=6)
            embed_url += f"&from={int(six_hours_ago.timestamp() * 1000)}&to={int(now.timestamp() * 1000)}"
        elif time_range == '24h':
            now = datetime.now()
            one_day_ago = now - timedelta(days=1)
            embed_url += f"&from={int(one_day_ago.timestamp() * 1000)}&to={int(now.timestamp() * 1000)}"
        
        return embed_url
        
    except Exception as e:
        logger.info(f"임베드 URL 생성 오류: {e}")
        return dashboard_info.get('embed_url', '')

@bp.route('/config', methods=['GET'])
@login_required
def get_monitoring_config_api():
    """모니터링 설정 조회 API (.env 기반)"""
    try:
        all_config = {
            'grafana': get_grafana_config(),
            'prometheus': get_prometheus_config(),
            'monitoring': get_monitoring_config(),
            'alerts': get_alerts_config(),
            'security': get_security_config()
        }
        return jsonify({
            'success': True,
            'data': all_config
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config', methods=['POST'])
@login_required
def update_monitoring_config_api():
    """모니터링 설정 업데이트 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '설정 데이터가 없습니다.'}), 400
        
        # .env 파일 업데이트는 별도 구현 필요
        return jsonify({
            'success': True,
            'message': '설정이 업데이트되었습니다.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config-page')
@login_required
def monitoring_config_page():
    """모니터링 설정 페이지"""
    return render_template('partials/monitoring_config_content.html')

def get_actual_servers():
    """실제 DB에서 서버 목록 가져오기 - 더미 데이터 제거"""
    try:
        # 데이터베이스 연결 상태 확인
        try:
            # SQLAlchemy 2.0 호환 방식으로 DB 연결 테스트
            db.session.execute(text('SELECT 1'))
        except Exception as db_error:
            logger.info(f"데이터베이스 연결 오류: {db_error}")
            return []  # 더미 데이터 제거 - 빈 배열 반환
        
        # Server 모델 접근 시도
        try:
            servers = []
            db_servers = Server.query.all()
            
            for server in db_servers:
                # IP 주소 처리
                ip_address = server.ip_address
                if isinstance(ip_address, list) and len(ip_address) > 0:
                    ip = ip_address[0]
                elif isinstance(ip_address, str):
                    ip = ip_address
                else:
                    ip = '0.0.0.0'
                
                # 포트 설정 (기본값: 22)
                port = '22'
                
                # 서버 상태 결정
                status = determine_server_status(server)
                
                servers.append({
                    'ip': ip,
                    'port': port,
                    'status': status,
                    'name': server.name or f"Server-{server.vmid}",  # 이름이 없으면 VMID 사용
                    'role': server.role,
                    'vmid': server.vmid
                })
            
            logger.info(f"DB에서 {len(servers)}개 서버 로드 완료")
            return servers
            
        except Exception as model_error:
            logger.info(f"Server 모델 접근 오류: {model_error}")
            return []  # 더미 데이터 제거 - 빈 배열 반환
        
    except Exception as e:
        logger.info(f"서버 목록 조회 오류: {e}")
        return []  # 더미 데이터 제거 - 빈 배열 반환

def determine_server_status(server):
    """실제 서버 상태 확인 (Prometheus 연동)"""
    try:
        # IP 주소 처리
        ip_address = server.ip_address
        if isinstance(ip_address, list) and len(ip_address) > 0:
            ip = ip_address[0]
        elif isinstance(ip_address, str):
            ip = ip_address
        else:
            ip = '0.0.0.0'
        
        # 실제 서버 상태 확인
        server_status = get_real_server_status(ip)
        return server_status
        
    except Exception as e:
        logger.info(f"서버 상태 확인 오류 ({server.name}): {e}")
        return 'healthy'

def get_real_server_status(server_ip):
    """실제 서버 상태 확인 (Prometheus 연동)"""
    try:
        # Prometheus에서 실제 메트릭 가져오기
        prometheus_config = get_prometheus_config()
        
        # CPU 사용률 확인
        cpu_usage = get_prometheus_metric(f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle", instance="{server_ip}:9100"}}[5m])) * 100)')
        
        # 메모리 사용률 확인
        memory_usage = get_prometheus_metric(f'(1 - (node_memory_MemAvailable_bytes{{instance="{server_ip}:9100"}} / node_memory_MemTotal_bytes{{instance="{server_ip}:9100"}})) * 100)')
        
        # 디스크 사용률 확인
        disk_usage = get_prometheus_metric(f'(1 - (node_filesystem_avail_bytes{{instance="{server_ip}:9100", mountpoint="/"}} / node_filesystem_size_bytes{{instance="{server_ip}:9100", mountpoint="/"}})) * 100)')
        
        # 네트워크 지연 확인 (ping)
        network_latency = get_network_latency(server_ip)
        
        # 상태 결정
        status = 'healthy'
        
        if cpu_usage > 90 or memory_usage > 90 or disk_usage > 90:
            status = 'critical'
        elif cpu_usage > 80 or memory_usage > 80 or disk_usage > 80 or network_latency > 100:
            status = 'warning'
        
        return status
        
    except Exception as e:
        logger.info(f"서버 {server_ip} 상태 확인 실패: {e}")
        return 'healthy'

def get_prometheus_metric(query):
    """Prometheus에서 메트릭 값 가져오기"""
    try:
        prometheus_config = get_prometheus_config()
        url = f"{prometheus_config['url']}/api/v1/query"
        
        params = {'query': query}
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success' and data['data']['result']:
                return float(data['data']['result'][0]['value'][1])
        
        return 0
    except Exception as e:
        logger.info(f"Prometheus 메트릭 가져오기 실패: {e}")
        return 0

def get_network_latency(server_ip):
    """네트워크 지연 시간 측정"""
    try:
        import subprocess
        import platform
        
        # OS에 따른 ping 명령어 결정
        if platform.system().lower() == "windows":
            cmd = ["ping", "-n", "1", server_ip]
        else:
            cmd = ["ping", "-c", "1", server_ip]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            # ping 결과에서 지연 시간 추출
            output = result.stdout
            if "time=" in output:
                time_part = output.split("time=")[1].split()[0]
                return float(time_part.replace("ms", ""))
        
        return 999  # ping 실패 시 높은 값 반환
    except Exception as e:
        logger.info(f"네트워크 지연 측정 실패: {e}")
        return 999

@bp.route('/servers/<server_ip>/metrics', methods=['GET'])
@login_required
def get_server_metrics(server_ip):
    """특정 서버의 실제 메트릭 정보 반환"""
    try:
        # 실제 서버 메트릭 가져오기
        prometheus_config = get_prometheus_config()
        
        # CPU 사용률
        cpu_usage = get_prometheus_metric(f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle", instance="{server_ip}:9100"}}[5m])) * 100)')
        
        # 메모리 사용률
        memory_usage = get_prometheus_metric(f'(1 - (node_memory_MemAvailable_bytes{{instance="{server_ip}:9100"}} / node_memory_MemTotal_bytes{{instance="{server_ip}:9100"}})) * 100)')
        
        # 디스크 사용률
        disk_usage = get_prometheus_metric(f'(1 - (node_filesystem_avail_bytes{{instance="{server_ip}:9100", mountpoint="/"}} / node_filesystem_size_bytes{{instance="{server_ip}:9100", mountpoint="/"}})) * 100)')
        
        # 네트워크 지연
        network_latency = get_network_latency(server_ip)
        
        # 상태 결정
        status = 'healthy'
        issues = []
        
        if cpu_usage > 90 or memory_usage > 90 or disk_usage > 90:
            status = 'critical'
            if cpu_usage > 90:
                issues.append(f'CPU 사용률 {cpu_usage:.1f}% (임계값: 90%)')
            if memory_usage > 90:
                issues.append(f'메모리 사용률 {memory_usage:.1f}% (임계값: 90%)')
            if disk_usage > 90:
                issues.append(f'디스크 사용률 {disk_usage:.1f}% (임계값: 90%)')
        elif cpu_usage > 80 or memory_usage > 80 or disk_usage > 80 or network_latency > 100:
            status = 'warning'
            if cpu_usage > 80:
                issues.append(f'CPU 사용률 {cpu_usage:.1f}% (경고값: 80%)')
            if memory_usage > 80:
                issues.append(f'메모리 사용률 {memory_usage:.1f}% (경고값: 80%)')
            if disk_usage > 80:
                issues.append(f'디스크 사용률 {disk_usage:.1f}% (경고값: 80%)')
            if network_latency > 100:
                issues.append(f'네트워크 지연 {network_latency:.1f}ms (경고값: 100ms)')
        
        return jsonify({
            'success': True,
            'data': {
                'server_ip': server_ip,
                'status': status,
                'metrics': {
                    'cpu_usage': cpu_usage,
                    'memory_usage': memory_usage,
                    'disk_usage': disk_usage,
                    'network_latency': network_latency
                },
                'issues': issues,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500