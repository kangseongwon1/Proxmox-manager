from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import subprocess
import os
import json
import yaml
from datetime import datetime
import threading
import time
import logging
import tempfile
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import db
import requests
import uuid
from typing import Dict, List, Optional, Tuple, Any, Union

# .env 파일 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv가 설치되지 않았습니다. pip install python-dotenv")
    pass

# 로깅 설정 (파일 상단으로 이동)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Vault 토큰 자동 설정
def setup_vault_token():
    """Vault 토큰을 자동으로 설정"""
    try:
        # .env.tokens 파일에서 토큰 읽기
        tokens_file = '.env.tokens'
        if os.path.exists(tokens_file):
            with open(tokens_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('FLASK_TOKEN='):
                        flask_token = line.split('=', 1)[1]
                        os.environ['VAULT_TOKEN'] = flask_token
                        print(f"[Vault] Flask 토큰이 설정되었습니다.")
                        return True
        
        # 환경 변수에서 직접 확인
        if 'FLASK_TOKEN' in os.environ:
            os.environ['VAULT_TOKEN'] = os.environ['FLASK_TOKEN']
            print(f"[Vault] 환경 변수에서 Flask 토큰을 설정했습니다.")
            return True
            
        print("[Vault] Flask 토큰을 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"[Vault] 토큰 설정 중 오류: {e}")
        return False

# Vault 토큰 설정 실행
setup_vault_token()

# 설정 파일 import
try:
    from config.config import config
except ImportError:
    # 대안 방법으로 config 로드
    import importlib.util
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.py')
    spec = importlib.util.spec_from_file_location("config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    config = config_module.config

app = Flask(__name__)

# 전역 작업 상태 dict (확장 시 Redis 등으로 교체)
tasks = {}  # task_id: {status, type, message, ...}

def create_task(status, type, message):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': status, 'type': type, 'message': message}
    return task_id

def update_task(task_id, status, message=None):
    if task_id in tasks:
        tasks[task_id]['status'] = status
        if message:
            tasks[task_id]['message'] = message

@app.route('/tasks/status')
def get_task_status():
    task_id = request.args.get('task_id')
    if not task_id or task_id not in tasks:
        return jsonify({'error': 'Invalid task_id'}), 404
    return jsonify(tasks[task_id])

# 예시: 서버 생성/삭제에서 사용
# 서버 생성/삭제 요청 시
# task_id = create_task('pending', '서버 생성', '서버 생성 대기 중...')
# Thread(target=실제_작업_함수, args=(task_id, ...)).start()
# 실제_작업_함수 내에서 update_task(task_id, 'success'/'error', '메시지')


# 환경 변수에서 설정 로드
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# --- 권한/상수/데코레이터 정의를 상단에 위치 ---
TERRAFORM_DIR = 'terraform'
ANSIBLE_DIR = 'ansible'
PROJECTS_DIR = 'projects'
TFVARS_PATH = os.path.join(TERRAFORM_DIR, 'terraform.tfvars.json')

PERMISSION_LIST = [
    'view_all', 'create_server', 'start_server', 'stop_server', 'reboot_server', 'delete_server', 'assign_roles', 'remove_roles', 'manage_users', 'view_logs', 'manage_roles', 'manage_storage', 'manage_network'
]

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        user = get_user(session['user_id'])
        if not user or 'admin' != user.get('role'):
            return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                print(f"[권한검증] 세션에 user_id 없음")
                return jsonify({'error': '로그인이 필요합니다.'}), 401
            
            user = db.get_user_by_username(session['user_id'])
            if not user:
                print(f"[권한검증] 사용자 정보를 찾을 수 없음: {session['user_id']}")
                return jsonify({'error': '사용자 정보를 찾을 수 없습니다.'}), 403
            
            # admin은 무조건 통과
            if user.get('role') == 'admin':
                print(f"[권한검증] admin 사용자 통과: {session['user_id']}")
                return f(*args, **kwargs)
            
            # DB에서 권한 확인
            has_perm = db.has_permission(user['id'], permission)
            print(f"[권한검증] 사용자: {session['user_id']}, 요청권한: {permission}, 권한보유: {has_perm}")
            
            if not has_perm:
                print(f"[권한검증] 권한 없음: {session['user_id']} -> {permission}")
                return jsonify({'error': '권한이 없습니다.'}), 403
            
            print(f"[권한검증] 권한 통과: {session['user_id']} -> {permission}")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 보안 헤더 설정 (개발 환경에서는 비활성화)
@app.after_request
def add_security_headers(response):
    # 기존 보안 헤더
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if not app.config.get('DEBUG', False):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://code.jquery.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com"
    # 캐시 방지 헤더 추가
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# 로그인 필요 데코레이터
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# 데이터베이스 기반 사용자 관리
def get_user(username):
    """사용자 정보 조회 (DB에서)"""
    return db.get_user_with_permissions(username)

def update_user_login(username):
    """사용자 마지막 로그인 시간 업데이트 (DB에서)"""
    db.update_user_login(username)

def get_all_users():
    """모든 사용자 정보 조회 (DB에서)"""
    users = db.get_all_users()
    result = {}
    for user in users:
        permissions = db.get_user_permissions(user['id'])
        result[user['username']] = {
            'id': user['id'],
            'username': user['username'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'is_active': user['is_active'],
            'created_at': user['created_at'],
            'last_login': user['last_login'],
            'permissions': permissions
        }
    return result

# 기존 JSON 사용자들을 DB로 마이그레이션
def migrate_users_from_json():
    """기존 users.json 파일의 사용자들을 DB로 마이그레이션"""
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            json_users = json.load(f)
        
        migrated_count = 0
        for username, user_data in json_users.items():
            # 이미 DB에 존재하는지 확인
            existing_user = db.get_user_by_username(username)
            if existing_user:
                print(f"[마이그레이션] 사용자 {username}은 이미 DB에 존재합니다.")
                continue
            
            # 새 사용자 생성
            user_id = db.create_user_with_hash(
                username=username,
                password_hash=user_data['password_hash'],
                name=user_data['name'] if 'name' in user_data else username,
                email=user_data['email'] if 'email' in user_data else '',
                role=user_data['role'] if 'role' in user_data else 'developer'
            )
            
            # 권한 부여
            permissions = user_data['permissions'] if 'permissions' in user_data else ['view_all']
            db.add_user_permissions(user_id, permissions)
            
            migrated_count += 1
            print(f"[마이그레이션] 사용자 {username} 마이그레이션 완료")
        
        if migrated_count > 0:
            print(f"[마이그레이션] 총 {migrated_count}명의 사용자가 DB로 마이그레이션되었습니다.")
        else:
            print("[마이그레이션] 마이그레이션할 사용자가 없습니다.")
            
    except FileNotFoundError:
        print("[마이그레이션] users.json 파일이 없습니다.")
    except Exception as e:
        print(f"[마이그레이션] 마이그레이션 중 오류 발생: {e}")

# 마이그레이션 실행
migrate_users_from_json()

# 초기 사용자 로드 (DB에서)
USERS = get_all_users()

# 알림 관리 함수
def load_notifications():
    """notifications.json에서 알림 데이터 로드"""
    try:
        with open('notifications.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        default_data = {
            "notifications": [],
            "last_id": 0,
            "settings": {
                "max_notifications": 100,
                "auto_clear_days": 7
            }
        }
        save_notifications(default_data)
        return default_data

def save_notifications(data):
    """알림 데이터를 notifications.json에 저장"""
    with open('notifications.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_notification(type, title, message, details=None, severity='info', user_id=None):
    """새 알림 추가"""
    data = load_notifications()
    
    # ID 증가
    data['last_id'] += 1
    
    # user_id 처리: 백그라운드 스레드에서 안전하게 처리
    if user_id is None:
        try:
            from flask import session
            user_id = session.get('user_id', 'system')
        except RuntimeError:
            # 백그라운드 스레드에서는 'system'으로 설정
            user_id = 'system'
    
    notification = {
        'id': data['last_id'],
        'type': type,  # 'server_create', 'server_error', 'terraform_error', 'ansible_error'
        'title': title,
        'message': message,
        'details': details,
        'severity': severity,  # 'info', 'warning', 'error', 'success'
        'timestamp': datetime.now().isoformat(),
        'read': False,
        'user_id': user_id
    }
    
    data['notifications'].insert(0, notification)  # 최신 알림을 맨 위에
    
    # 최대 알림 수 제한
    if len(data['notifications']) > data['settings']['max_notifications']:
        data['notifications'] = data['notifications'][:data['settings']['max_notifications']]
    
    save_notifications(data)
    return notification

def get_unread_count():
    """읽지 않은 알림 수 반환"""
    data = load_notifications()
    return len([n for n in data['notifications'] if not n.get('read', False)])

def mark_as_read(notification_id):
    """알림을 읽음으로 표시"""
    data = load_notifications()
    for notification in data['notifications']:
        if notification['id'] == notification_id:
            notification['read'] = True
            break
    save_notifications(data)

# terraform.tfvars.json의 servers map 읽기

def read_servers_from_tfvars():
    try:
        with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
            obj = json.load(f)
            return obj.get('servers', {})
    except FileNotFoundError:
        logger.warning(f"terraform.tfvars.json 파일이 존재하지 않습니다: {TFVARS_PATH}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"terraform.tfvars.json 파일 파싱 오류: {e}")
        return {}
    except Exception as e:
        logger.error(f"terraform.tfvars.json 파일 읽기 오류: {e}")
        return {}

def write_servers_to_tfvars(servers, other_vars=None):
    try:
        # 파일이 존재하면 읽기, 없으면 새로 생성
        if os.path.exists(TFVARS_PATH):
            with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
                obj = json.load(f)
        else:
            obj = {}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"기존 terraform.tfvars.json 파일을 읽을 수 없어 새로 생성합니다: {e}")
        obj = {}
    
    # 기존 서버들의 file_format 보존
    existing_servers = obj.get('servers', {})
    for server_name, new_server_data in servers.items():
        if server_name in existing_servers:
            existing_server_data = existing_servers[server_name]
            # 기존 디스크 설정 보존
            if 'disks' in existing_server_data and 'disks' in new_server_data:
                for i, new_disk in enumerate(new_server_data['disks']):
                    if i < len(existing_server_data['disks']):
                        existing_disk = existing_server_data['disks'][i]
                        # 기존 file_format이 명시적으로 설정되어 있다면 보존
                        if 'file_format' in existing_disk and existing_disk['file_format'] != 'auto':
                            new_disk['file_format'] = existing_disk['file_format']
    
    obj['servers'] = servers
    if other_vars:
        # Terraform에서 정의된 변수들만 허용
        allowed_vars = {
            'proxmox_endpoint', 'proxmox_username', 'proxmox_node', 
            'vm_username', 'vault_token'
        }
        filtered_vars = {k: v for k, v in other_vars.items() if k in allowed_vars}
        obj.update(filtered_vars)
    with open(TFVARS_PATH, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

# 서버 역할 정의
# 1. 서버 역할 정의에 OS별 패키지 추가
SERVER_ROLES = {
    'web': {
        'name': '웹서버(Nginx)',
        'description': 'Nginx 웹서버를 설치합니다.'
    },
    'was': {
        'name': 'WAS(Python3.12)',
        'description': 'Python 3.12 환경을 설치합니다.'
    },
    'java': {
        'name': 'JAVA(17.0.7)',
        'description': 'OpenJDK 17.0.7 환경을 설치합니다.'
    },
    'search': {
        'name': '검색(Elasticsearch7)',
        'description': 'Elasticsearch 7.17.10 및 OpenJDK 17.0.7을 설치합니다.'
    },
    'ftp': {
        'name': 'FTP(vsftpd)',
        'description': 'vsftpd FTP 서버를 설치합니다.'
    },
    'db': {
        'name': 'DB(MariaDB10.11)',
        'description': 'MariaDB 10.11을 설치하고 root 비밀번호를 초기화합니다.'
    }
}

        

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = get_user(session['user_id'])
    # 세션에 permissions 저장
    session['permissions'] = user.get('permissions', []) if user else []
    return render_template('index.html', roles=SERVER_ROLES)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # DB에서 사용자 인증
        user = db.verify_user(username, password)
        if user and (user['is_active'] if 'is_active' in user else True):
            session['user_id'] = username
            session['role'] = user['role']
            session['user_name'] = user['name'] if 'name' in user else username
            session['user_email'] = user['email'] if 'email' in user else ''
            # 권한 정보 가져오기
            permissions = db.get_user_permissions(user['id'])
            session['permissions'] = permissions
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='잘못된 사용자명 또는 비밀번호입니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/users', methods=['GET'])
@permission_required('manage_users')
def list_users():
    """사용자 목록 조회 (권한 필요)"""
    users = get_all_users()
    # 비밀번호 해시는 제외하고 반환
    safe_users = {}
    for username, user_data in users.items():
        safe_users[username] = {
            'name': user_data['name'] if 'name' in user_data else username,
            'email': user_data['email'] if 'email' in user_data else '',
            'role': user_data['role'] if 'role' in user_data else 'user',
            'is_active': user_data['is_active'] if 'is_active' in user_data else True,
            'created_at': user_data['created_at'] if 'created_at' in user_data else '',
            'last_login': user_data['last_login'] if 'last_login' in user_data else '',
            'permissions': user_data['permissions'] if 'permissions' in user_data else []
        }
    return jsonify({'users': safe_users})

@app.route('/users', methods=['POST'])
@permission_required('manage_users')
def create_user():
    """새 사용자 생성 (권한 필요)"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    name = data.get('name', username)
    email = data.get('email', '')
    role = data.get('role', 'viewer')
    permissions = data.get('permissions')
    if not permissions:
        # 기본 권한: view_all만 부여
        permissions = ['view_all']
    if role == 'admin':
        permissions = PERMISSION_LIST.copy()
    if not username or not password:
        return jsonify({'error': '사용자명과 비밀번호는 필수입니다.'}), 400
    
    # 기존 사용자 확인
    existing_user = db.get_user_by_username(username)
    if existing_user:
        return jsonify({'error': '이미 존재하는 사용자명입니다.'}), 400
    
    # 새 사용자 생성
    user_id = db.create_user(username, password, name, email, role)
    # 권한 부여
    db.add_user_permissions(user_id, permissions)
    
    return jsonify({'success': True, 'message': f'사용자 {username}이(가) 생성되었습니다.'})

@app.route('/users/<username>', methods=['DELETE'])
@permission_required('manage_users')
def delete_user(username):
    """사용자 삭제 (권한 필요)"""
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    if user['role'] == 'admin':
        return jsonify({'error': '관리자 계정은 삭제할 수 없습니다.'}), 400
    
    # 사용자 삭제 (권한은 CASCADE로 자동 삭제됨)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
    
    return jsonify({'success': True, 'message': f'사용자 {username}이(가) 삭제되었습니다.'})

def update_user_permissions(username, permissions):
    """사용자 권한 업데이트 (공통 함수)"""
    user = db.get_user_by_username(username)
    if not user:
        return False, '사용자를 찾을 수 없습니다.'
    
    if user.get('role') == 'admin':
        return False, 'admin 권한은 변경할 수 없습니다.'
    
    # 권한 완전 교체
    db.set_user_permissions(user['id'], permissions)
    return True, f'{username}의 권한이 변경되었습니다.'

def update_user_role(username, new_role):
    """사용자 역할 업데이트 (공통 함수)"""
    user = db.get_user_by_username(username)
    if not user:
        return False, '사용자를 찾을 수 없습니다.'
    
    # 역할 변경
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET role = ?, updated_at = CURRENT_TIMESTAMP
            WHERE username = ?
        ''', (new_role, username))
        conn.commit()
    
    # admin으로 변경 시 모든 권한 부여
    if new_role == 'admin':
        db.set_user_permissions(user['id'], PERMISSION_LIST.copy())
    
    return True, f'{username}의 역할이 {new_role}로 변경되었습니다.'

@app.route('/users/<username>/permissions', methods=['POST'])
@permission_required('manage_users')
def change_user_permissions(username):
    data = request.json
    permissions = data.get('permissions', [])
    
    success, message = update_user_permissions(username, permissions)
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

@app.route('/users/<username>/role', methods=['POST'])
@permission_required('manage_users')
def change_user_role(username):
    data = request.json
    new_role = data.get('role')
    
    success, message = update_user_role(username, new_role)
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """현재 사용자의 비밀번호 변경"""
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        return jsonify({'error': '모든 필드를 입력해주세요.'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': '새 비밀번호가 일치하지 않습니다.'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '새 비밀번호는 최소 6자 이상이어야 합니다.'}), 400
    
    user_id = session.get('user_id')
    user = db.get_user_by_username(user_id)
    
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    # 현재 비밀번호 확인
    if not check_password_hash(user['password_hash'], current_password):
        return jsonify({'error': '현재 비밀번호가 올바르지 않습니다.'}), 400
    
    # 새 비밀번호로 업데이트
    db.update_user_password(user_id, new_password)
    
    # 알림 추가
    add_notification(
        type='password_change',
        title='비밀번호 변경',
        message=f'사용자 {user_id}의 비밀번호가 변경되었습니다.',
        severity='info',
        user_id=user_id
    )
    
    return jsonify({'success': True, 'message': '비밀번호가 성공적으로 변경되었습니다.'})

@app.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """현재 사용자 프로필 조회"""
    user_id = session.get('user_id')
    user = db.get_user_by_username(user_id)
    
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    return jsonify({
        'username': user_id,
        'name': user.get('name', user_id),
        'email': user.get('email', ''),
        'role': user.get('role', 'user'),
        'created_at': user.get('created_at', ''),
        'last_login': user.get('last_login', '')
    })

@app.route('/profile-page')
@login_required
def profile_page():
    """프로필 페이지 렌더링"""
    return render_template('profile.html')

@app.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """알림 목록 조회"""
    data = load_notifications()
    limit = request.args.get('limit', 20, type=int)
    notifications = data['notifications'][:limit]
    return jsonify({
        'notifications': notifications,
        'unread_count': get_unread_count()
    })

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """알림을 읽음으로 표시"""
    mark_as_read(notification_id)
    return jsonify({'success': True})

@app.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """읽지 않은 알림 수 조회"""
    return jsonify({'unread_count': get_unread_count()})

@app.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """모든 알림 삭제"""
    data = load_notifications()
    data['notifications'] = []
    data['last_id'] = 0
    save_notifications(data)
    return jsonify({'success': True, 'message': '모든 알림이 삭제되었습니다.'})

@app.route('/notifications/add', methods=['POST'])
def add_notification_api():
    data = request.form or request.json
    add_notification(
        type=data.get('type', 'info'),
        title=data.get('title', ''),
        message=data.get('message', ''),
        severity=data.get('type', 'info'),
        user_id=session.get('user_id', 'system')
    )
    return jsonify({'success': True})


@app.route('/create_server', methods=['POST'])
@permission_required('create_server')
def create_server():
    """단일 서버 생성 - JSON 데이터 처리"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'JSON 데이터가 필요합니다.'}), 400
        
        task_id = create_task('pending', '서버 생성', '서버 생성 대기 중...')
        threading.Thread(target=do_create_server, args=(task_id, data)).start()
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        logger.exception("[create_server] 서버 생성 중 예외 발생")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/create_servers_bulk', methods=['POST'])
@permission_required('create_server')
def create_servers_bulk():
    """다중 서버 생성 - JSON 데이터 처리"""
    try:
        data = request.json
        servers_input = data.get('servers')
        if not servers_input or not isinstance(servers_input, list) or len(servers_input) == 0:
            return jsonify({'success': False, 'error': '입력값 오류: servers 배열이 필요합니다.'}), 400
        
        task_id = create_task('pending', '다중 서버 생성', f'{len(servers_input)}개 서버 생성 대기 중...')
        threading.Thread(target=do_create_servers_bulk, args=(task_id, servers_input)).start()
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        logger.exception("[create_servers_bulk] 다중 서버 생성 중 예외 발생")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/servers', methods=['GET'])
@permission_required('view_all')
def list_servers():
    servers = read_servers_from_tfvars()
    return jsonify({'servers': servers})

def run_terraform_apply():
    import subprocess
    lock_path = os.path.join(TERRAFORM_DIR, '.terraform.tfstate.lock.info')
    print(f"[terraform] run_terraform_apply 진입, lock_path: {lock_path}")
    
    # Vault 토큰 설정
    terraform_env = os.environ.copy()
    try:
        # .env.tokens 파일에서 Terraform 토큰 읽기
        tokens_file = '.env.tokens'
        if os.path.exists(tokens_file):
            with open(tokens_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('TERRAFORM_TOKEN='):
                        terraform_token = line.split('=', 1)[1]
                        terraform_env['TF_VAR_vault_token'] = terraform_token
                        print(f"[terraform] Terraform 토큰이 설정되었습니다.")
                        break
        else:
            print("[terraform] .env.tokens 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"[terraform] 토큰 설정 중 오류: {e}")
    
    # apply 전 락 파일이 남아있으면 자동 삭제(비정상 종료/중복 락 방지)
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
            print(f"[terraform] 기존 락 파일 자동 삭제: {lock_path}")
        except Exception as e:
            print(f"[terraform] 락 파일 삭제 실패: {e}")
            return False, '', f'기존 terraform 락 파일이 남아있어 삭제에 실패했습니다: {e}'
    
    # 항상 terraform init 먼저 실행
    print("[terraform] terraform init 실행")
    init_result = subprocess.run(['terraform', 'init', '-input=false'], cwd=TERRAFORM_DIR, capture_output=True, text=True, env=terraform_env)
    print(f"[terraform] init stdout: {init_result.stdout}")
    print(f"[terraform] init stderr: {init_result.stderr}")
    if init_result.returncode != 0:
        print(f"[terraform] init 실패: {init_result.stderr}")
        return False, init_result.stdout, init_result.stderr
    
    try:
        print("[terraform] terraform apply 실행")
        result = subprocess.run(
            ['terraform', 'apply', '-auto-approve', '-lock-timeout=30s'],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=180,  # 3분 제한
            env=terraform_env
        )
        print(f"[terraform] apply stdout: {result.stdout}")
        print(f"[terraform] apply stderr: {result.stderr}")
        print(f"[terraform] apply returncode: {result.returncode}")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        print(f"[terraform] apply timeout: {e}")
        return False, '', f'terraform apply timeout: {e}'
    except Exception as e:
        # apply 중 예외 발생 시 락 파일 자동 정리
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
                print(f"[terraform] apply 예외 발생, 락 파일 자동 삭제: {lock_path}")
            except Exception as e2:
                print(f"[terraform] apply 예외+락 파일 삭제 실패: {e2}")
        print(f"[terraform] apply 예외 발생: {e}")
        return False, '', f'terraform apply 중 예외 발생: {e}'

def run_ansible_playbook():
    # 실제 환경에 맞게 inventory, playbook 경로 조정 필요
    import subprocess
    result = subprocess.run(['ansible-playbook', '-i', 'inventory', 'playbook.yml'], cwd=ANSIBLE_DIR, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

# 넷마스크를 CIDR로 변환하는 함수 추가
def netmask_to_cidr(netmask):
    try:
        return str(sum([bin(int(x)).count('1') for x in netmask.split('.')]))
    except Exception:
        return netmask  # 변환 실패 시 원래 값 반환





# --- 서버 생성 비동기 처리 ---
def do_create_server(task_id, data):
    try:
        update_task(task_id, 'progress', '서버 생성 중...')
        
        # 공통 알림 함수 사용
        add_server_notification(
            'server_create',
            '서버 생성 시작',
            f'서버 "{data.get("name", "Unknown")}" 생성이 시작되었습니다.',
            severity='info'
        )
        
        servers = read_servers_from_tfvars()
        server_name = data['name']
        
        # 유효성 검사
        if not server_name:
            logger.error("[create_server] 서버 이름 누락")
            update_task(task_id, 'error', '서버 이름(name)을 입력해야 합니다.')
            return
        
        # tfvars 중복 체크
        if server_name in servers:
            logger.error(f"[create_server] tfvars 중복 서버 이름: {server_name}")
            update_task(task_id, 'error', f'이미 동일한 이름({server_name})의 서버가 tfvars에 존재합니다.')
            return
        
        # DB 중복 체크
        existing_server = db.get_server_by_name(server_name)
        if existing_server:
            logger.error(f"[create_server] DB 중복 서버 이름: {server_name}")
            update_task(task_id, 'error', f'이미 동일한 이름({server_name})의 서버가 DB에 존재합니다.')
            return
        
        # 공통 서버 데이터 처리 함수 사용
        os_type = data.get('os_type', 'rocky')
        data = process_server_data(data, os_type)
        
        # 새 서버 정보를 tfvars에 먼저 기록 (Terraform apply 전)
        servers[server_name] = data
        write_servers_to_tfvars(servers)
        
        # Terraform apply 실행
        ok, out, terr = run_terraform_apply()
        if not ok:
            # 공통 실패 처리 함수 사용
            handle_terraform_failure(servers, [server_name], task_id, terr)
            return
        
        # 공통 DB 저장 함수 사용
        vm_info = get_vm_info_from_proxmox(server_name)
        save_server_to_db(server_name, data, vm_info)
        
        # 공통 알림 함수 사용
        add_server_notification(
            'server_create',
            '서버 생성 완료',
            f'서버 "{server_name}" 생성이 완료되었습니다.',
            severity='success'
        )
        
        update_task(task_id, 'success', f'{server_name} 서버 생성 완료')
    except Exception as e:
        update_task(task_id, 'error', f'서버 생성 중 예외: {str(e)}')
        add_server_notification(
            'server_error',
            '서버 생성 실패',
            f'서버 생성 중 예외가 발생했습니다.',
            details=str(e),
            severity='error'
        )

# --- 다중 서버 생성 비동기 처리 ---
def do_create_servers_bulk(task_id, servers_input):
    try:
        update_task(task_id, 'progress', f'{len(servers_input)}개 서버 생성 중...')
        
        # 공통 알림 함수 사용
        add_server_notification(
            'server_create',
            '다중 서버 생성 시작',
            f'{len(servers_input)}개의 서버 생성이 시작되었습니다.',
            severity='info'
        )
        
        servers = read_servers_from_tfvars()
        created = []
        failed = []
        names = []
        
        # 서버 데이터 전처리
        for s in servers_input:
            name = s.get('name')
            if not name or not s.get('network_devices'):
                failed.append({'name': name or '(이름없음)', 'error': '서버명, 네트워크 정보 필요'})
                continue
            if name in servers:
                failed.append({'name': name, 'error': 'tfvars에 이미 존재하는 서버 이름'})
                continue
            
            # DB 중복 체크
            existing_server = db.get_server_by_name(name)
            if existing_server:
                failed.append({'name': name, 'error': 'DB에 이미 존재하는 서버 이름'})
                continue
            
            # 공통 서버 데이터 처리 함수 사용
            os_type = s.get('os_type', 'rocky')
            server_data = process_server_data(s, os_type)
            
            created.append(name)
            names.append(name)
        
        # 새 서버 정보를 tfvars에 먼저 기록 (Terraform apply 전)
        for s in servers_input:
            name = s.get('name')
            if name in names:  # 생성할 서버들을 tfvars에 추가
                servers[name] = s
        write_servers_to_tfvars(servers)
        
        # Terraform apply 실행
        ok, out, terr = run_terraform_apply()
        if not ok:
            # 공통 실패 처리 함수 사용
            handle_terraform_failure(servers, names, task_id, terr)
            return
        
        # Proxmox에서 VM 정보 조회 및 DB 저장 (각 서버별)
        for name in names:
            vm_info = get_vm_info_from_proxmox(name)
            save_server_to_db(name, servers[name], vm_info)
        
        # 공통 알림 함수 사용
        add_server_notification(
            'server_create',
            '다중 서버 생성 완료',
            f'{len(created)}개의 서버가 성공적으로 생성되었습니다.',
            severity='success'
        )
        
        update_task(task_id, 'success', f'{len(created)}개 서버 생성 완료')
    except Exception as e:
        update_task(task_id, 'error', f'다중 서버 생성 중 예외: {str(e)}')
        add_server_notification(
            'server_error',
            '다중 서버 생성 실패',
            f'서버 생성 중 예외 발생: {str(e)}',
            severity='error'
        )

@app.route('/delete_server/<server_name>', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    task_id = create_task('pending', '서버 삭제', '서버 삭제 대기 중...')
    threading.Thread(target=do_delete_server, args=(task_id, server_name)).start()
    return jsonify({'success': True, 'task_id': task_id})

# --- 서버 삭제 비동기 처리 ---
def do_delete_server(task_id, server_name):
    try:
        update_task(task_id, 'progress', '서버 stop(강제종료) 시도 중...')
        # 1. VMID 조회
        server_row = db.get_server_by_name(server_name)
        if not server_row or not server_row['vmid']:
            # Proxmox에 실제로 서버가 존재하는지 확인
            exists = check_proxmox_vm_exists(server_name)
            if exists:
                update_task(task_id, 'error', f'{server_name} 서버 삭제 실패: DB에 VMID 정보가 없으나 Proxmox에는 서버가 존재합니다. 관리자에게 문의하세요.')
            else:
                update_task(task_id, 'success', f'{server_name} 서버가 이미 삭제되어 있습니다.')
            return
        vmid = server_row['vmid']
        # 2. Proxmox에 stop(강제종료) 요청 (lock 에러 시 unlock 후 재시도)
        ok, err = proxmox_vm_action(vmid, 'stop')
        if not ok and err and 'lock' in err:
            unlock_ok, unlock_err = proxmox_vm_unlock(vmid)
            if unlock_ok:
                ok, err = proxmox_vm_action(vmid, 'stop')
        if not ok:
            update_task(task_id, 'error', f'Proxmox stop(강제종료) 요청 실패: {err}')
            return
        # 3. 30초 대기 (stop 완료+lock 해제까지 polling)
        waited = 0
        poll_interval = 3
        stop_ok = False
        while waited < 30:
            ok, err = wait_for_vm_shutdown(server_name, max_wait=poll_interval)
            if ok:
                # lock 상태 확인
                lock_free = True
                try:
                    proxmox_url = app.config['PROXMOX_ENDPOINT']
                    node = app.config['PROXMOX_NODE']
                    auth = proxmox_api_auth()
                    if not auth:
                        lock_free = False
                    else:
                        url = f"{proxmox_url}/api2/json/nodes/{node}/qemu/{vmid}/config"
                        headers = {
                            'Cookie': f'PVEAuthCookie={auth["ticket"]}',
                            'CSRFPreventionToken': auth['csrf']
                        }
                        resp = requests.get(url, headers=headers, verify=False)
                        if resp.status_code == 200:
                            data = resp.json().get('data', {})
                            lock_free = ('lock' not in data)
                        else:
                            lock_free = False
                except Exception:
                    lock_free = False
                if lock_free:
                    stop_ok = True
                    break
            time.sleep(poll_interval)
            waited += poll_interval
        if not stop_ok:
            update_task(task_id, 'error', 'stop(강제종료) 후 30초 내에 lock이 해제되지 않음')
            return
        # 4. tfvars에서 서버 삭제하고 Terraform apply 실행
        servers = read_servers_from_tfvars()
        tfvars_existed = server_name in servers
        
        if tfvars_existed:
            # 1단계: tfvars에서 서버 정보 임시 제거
            server_data = servers[server_name]  # 백업용
            del servers[server_name]
            write_servers_to_tfvars(servers)
            
            # 2단계: Terraform apply 실행
            ok, out, terr = run_terraform_apply()
            
            if not ok:
                # 1-1단계: Terraform apply 실패 시 tfvars 복구
                servers[server_name] = server_data
                write_servers_to_tfvars(servers)
                update_task(task_id, 'error', f'Terraform apply 실패: {terr}')
                return
            
            # 1-2단계: Terraform apply 성공 시 VM 존재 여부 확인
            vm_exists = check_proxmox_vm_exists(server_name)
            if vm_exists:
                # VM이 여전히 존재하면 tfvars 복구
                servers[server_name] = server_data
                write_servers_to_tfvars(servers)
                update_task(task_id, 'error', f'VM 삭제 확인 실패: {server_name}이 여전히 Proxmox에 존재합니다.')
                return
            
            # 2단계: VM이 실제로 삭제되었음을 확인했으므로 DB에서 서버 정보 삭제
            db_deleted = db.delete_server_by_name(server_name)
            if db_deleted:
                logger.info(f"[delete_server] DB에서 서버 {server_name} 삭제 완료")
            else:
                logger.warning(f"[delete_server] DB에서 서버 {server_name} 삭제 실패 (이미 삭제되었거나 존재하지 않음)")
        else:
            # tfvars에 서버가 없는 경우: DB에서만 삭제
            logger.info(f"[delete_server] tfvars에 서버가 없음, DB에서만 삭제: {server_name}")
            db_deleted = db.delete_server_by_name(server_name)
            if db_deleted:
                logger.info(f"[delete_server] DB에서 서버 {server_name} 삭제 완료")
            else:
                logger.warning(f"[delete_server] DB에서 서버 {server_name} 삭제 실패 (이미 삭제되었거나 존재하지 않음)")
        
        update_task(task_id, 'success', f'{server_name} 서버 삭제 완료')
    except Exception as e:
        update_task(task_id, 'error', f'서버 삭제 중 예외: {str(e)}')

def wait_for_vm_shutdown(server_name, max_wait=180, poll_interval=5):
    """Proxmox에서 VM이 완전히 stopped 될 때까지 대기"""
    waited = 0
    while waited < max_wait:
        # VM 상태 확인
        status = None
        try:
            proxmox_url = app.config['PROXMOX_ENDPOINT']
            username = app.config['PROXMOX_USERNAME']
            password = app.config['PROXMOX_PASSWORD']
            node = app.config['PROXMOX_NODE']
            auth_url = f"{proxmox_url}/api2/json/access/ticket"
            auth_data = {'username': username, 'password': password}
            auth_response = requests.post(auth_url, data=auth_data, verify=False)
            if auth_response.status_code != 200:
                return False, 'Proxmox 인증 실패'
            ticket = auth_response.json()['data']['ticket']
            csrf_token = auth_response.json()['data']['CSRFPreventionToken']
            headers = {
                'Cookie': f'PVEAuthCookie={ticket}',
                'CSRFPreventionToken': csrf_token
            }
            vms_url = f"{proxmox_url}/api2/json/nodes/{node}/qemu"
            vms_response = requests.get(vms_url, headers=headers, verify=False)
            if vms_response.status_code != 200:
                return False, 'Proxmox VM 목록 조회 실패'
            vms = vms_response.json().get('data', [])
            for vm in vms:
                if vm['name'] == server_name:
                    status = vm.get('status')
                    break
        except Exception as e:
            return False, f'Proxmox 상태 확인 중 예외: {e}'
        if status == 'stopped':
            return True, None
        time.sleep(poll_interval)
        waited += poll_interval
    return False, 'VM shutdown 대기 timeout'

@app.route('/stop_server/<server_name>', methods=['POST'])
@permission_required('stop_server')
def stop_server(server_name):
    logger.info(f"[stop_server] 요청: {server_name}")
    try:
        server = db.get_server_by_name(server_name)
        if not server or not server['vmid']:
            return jsonify({'success': False, 'error': 'DB에서 VMID 정보를 찾을 수 없습니다.'}), 400
        vmid = server['vmid']
        ok, err = proxmox_vm_action(vmid, 'stop')
        if ok:
            logger.info(f"[stop_server] VM 중지 요청: vmid={vmid}")
            return jsonify({'success': True, 'message': f'{server_name} 서버가 중지되었습니다.'})
        else:
            logger.error(f"[stop_server] 중지 실패: {err}")
            return jsonify({'success': False, 'error': err}), 500
    except Exception as e:
        logger.exception(f"[stop_server] 예외 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reboot_server/<server_name>', methods=['POST'])
@permission_required('reboot_server')
def reboot_server(server_name):
    logger.info(f"[reboot_server] 요청: {server_name}")
    try:
        server = db.get_server_by_name(server_name)
        if not server or not server['vmid']:
            return jsonify({'success': False, 'error': 'DB에서 VMID 정보를 찾을 수 없습니다.'}), 400
        vmid = server['vmid']
        ok, err = proxmox_vm_action(vmid, 'reset')
        if ok:
            logger.info(f"[reboot_server] VM 리부팅 요청: vmid={vmid}")
            return jsonify({'success': True, 'message': f'{server_name} 서버가 리부팅되었습니다.'})
        else:
            logger.error(f"[reboot_server] 리부팅 실패: {err}")
            return jsonify({'success': False, 'error': err}), 500
    except Exception as e:
        logger.exception(f"[reboot_server] 예외 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/server_status/<server_name>', methods=['GET'])
@login_required
def get_server_status(server_name):
    """특정 서버의 상태를 Proxmox에서 가져오기"""
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 공통 인증 함수 사용
        headers, error = get_proxmox_auth()
        if error:
            return jsonify({'error': error}), 401
        
        # 공통 VM 목록 조회 함수 사용
        vms, error = get_proxmox_vms(headers)
        if error:
            return jsonify({'error': error}), 500
        
        # 특정 서버 찾기
        for vm in vms:
            if vm['name'] == server_name:
                status_info = {
                    'name': vm['name'],
                    'status': vm['status'],
                    'vmid': vm['vmid'],
                    'node': vm['node'],
                    'cpu': vm.get('cpu', 0),
                    'memory': vm.get('mem', 0),
                    'maxmem': vm.get('maxmem', 0),
                    'uptime': vm.get('uptime', 0),
                    'disk': vm.get('disk', 0),
                    'maxdisk': vm.get('maxdisk', 0)
                }
                return jsonify(status_info)
        
        return jsonify({'error': f'서버 {server_name}을 찾을 수 없습니다'}), 404
        
    except Exception as e:
        return jsonify({'error': f'서버 상태 확인 실패: {str(e)}'}), 500

@app.route('/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 서버의 상태를 Proxmox에서 가져오기"""
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 공통 인증 함수 사용
        headers, error = get_proxmox_auth()
        if error:
            return jsonify({'error': error}), 401
        
        # Proxmox 노드 정보 조회 (전체 리소스 확인)
        proxmox_url = app.config['PROXMOX_ENDPOINT']
        node = app.config['PROXMOX_NODE']
        node_url = f"{proxmox_url}/api2/json/nodes/{node}/status"
        node_response = requests.get(node_url, headers=headers, verify=False)
        
        if node_response.status_code != 200:
            return jsonify({'error': '노드 정보를 가져올 수 없습니다'}), 500
        
        node_data = node_response.json()['data']
        node_cpu_count = node_data.get('cpuinfo', {}).get('cpus', 0)
        node_memory_total = node_data.get('memory', {}).get('total', 0)
        node_memory_used = node_data.get('memory', {}).get('used', 0)
        
        # 공통 VM 목록 조회 함수 사용
        vms, error = get_proxmox_vms(headers)
        if error:
            return jsonify({'error': error}), 500
        
        all_servers = {}
        vm_total_cpu = 0
        vm_total_memory = 0
        vm_used_cpu = 0
        vm_used_memory = 0
        running_count = 0
        stopped_count = 0
        
        # terraform.tfvars.json에 있는 서버만 필터링
        servers = read_servers_from_tfvars()
        
        for vm in vms:
            if vm['name'] in servers:
                server_data = servers[vm['name']]
                # IP 정보 추출 (network_devices 또는 ip_addresses)
                ip_list = []
                if 'network_devices' in server_data and server_data['network_devices']:
                    ip_list = [nd.get('ip_address') for nd in server_data['network_devices'] if nd.get('ip_address')]
                elif 'ip_addresses' in server_data and server_data['ip_addresses']:
                    ip_list = server_data['ip_addresses']
                
                # CPU 정보 추출 (tfvars에서 가져오거나 기본값 사용)
                vm_cpu = server_data.get('cpu', 1)
                
                # DB에서 방화벽 그룹 정보 가져오기
                db_server = db.get_server_by_name(vm['name'])
                firewall_group = None
                if db_server:
                    try:
                        firewall_group = db_server['firewall_group']
                    except (KeyError, TypeError, IndexError):
                        firewall_group = None
                
                status_info = {
                    'name': vm['name'],
                    'status': vm['status'],
                    'vmid': vm['vmid'],
                    'node': vm['node'],
                    'cpu': vm.get('cpu', 0),
                    'memory': vm.get('mem', 0),
                    'maxmem': vm.get('maxmem', 0),
                    'uptime': vm.get('uptime', 0),
                    'disk': vm.get('disk', 0),
                    'maxdisk': vm.get('maxdisk', 0),
                    'role': server_data.get('role', 'unknown'),
                    'firewall_group': firewall_group,
                    'ip_addresses': ip_list,
                    'vm_cpu': vm_cpu  # tfvars에서 가져온 CPU 코어 수
                }
                all_servers[vm['name']] = status_info
                
                # VM 통계 계산
                if vm['status'] == 'running':
                    running_count += 1
                    vm_total_memory += vm.get('maxmem', 0)
                    vm_used_memory += vm.get('mem', 0)  # 현재 사용 중인 메모리
                    vm_total_cpu += vm_cpu
                    vm_used_cpu += vm_cpu  # 실행 중인 서버는 CPU를 모두 사용 중
                else:
                    stopped_count += 1
                    vm_total_memory += vm.get('maxmem', 0)
                    vm_total_cpu += vm_cpu
                    # 중지된 서버는 CPU/메모리 사용량 0
        
        # 노드 기준 통계 정보 추가
        stats = {
            'total_servers': len(all_servers),
            'running_servers': running_count,
            'stopped_servers': stopped_count,
            # 노드 전체 리소스
            'node_total_cpu': node_cpu_count,
            'node_total_memory_gb': round(node_memory_total / (1024 * 1024 * 1024), 1),
            'node_used_memory_gb': round(node_memory_used / (1024 * 1024 * 1024), 1),
            # VM 할당된 리소스
            'vm_total_cpu': vm_total_cpu,
            'vm_total_memory_gb': round(vm_total_memory / (1024 * 1024 * 1024), 1),
            'vm_used_cpu': vm_used_cpu,
            'vm_used_memory_gb': round(vm_used_memory / (1024 * 1024 * 1024), 1),
            # 사용률 계산
            'cpu_usage_percent': round((vm_used_cpu / node_cpu_count * 100) if node_cpu_count > 0 else 0, 1),
            'memory_usage_percent': round((vm_used_memory / node_memory_total * 100) if node_memory_total > 0 else 0, 1),
            'cpu_allocation_percent': round((vm_total_cpu / node_cpu_count * 100) if node_cpu_count > 0 else 0, 1),
            'memory_allocation_percent': round((vm_total_memory / node_memory_total * 100) if node_memory_total > 0 else 0, 1)
        }
        
        return jsonify({
            'servers': all_servers,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': f'서버 상태 확인 실패: {str(e)}'}), 500

@app.route('/proxmox_storage', methods=['GET'])
def proxmox_storage():
    logger.info("[proxmox_storage] 스토리지 정보 요청")
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 공통 인증 함수 사용
        headers, error = get_proxmox_auth()
        if error:
            return {'error': error}, 401
        
        # 스토리지 정보 조회
        proxmox_url = app.config['PROXMOX_ENDPOINT']
        node = app.config['PROXMOX_NODE']
        storage_url = f"{proxmox_url}/api2/json/nodes/{node}/storage"
        storage_response = requests.get(storage_url, headers=headers, verify=False)
        
        logger.info(f"[proxmox_storage] Proxmox 응답: {storage_response.status_code}, {storage_response.text}")
        if storage_response.status_code != 200:
            logger.error("[proxmox_storage] 스토리지 정보를 가져올 수 없습니다")
            return {'error': '스토리지 정보를 가져올 수 없습니다'}, 500
        
        storages = storage_response.json().get('data', [])
        # 용량 정보만 추출
        result = []
        for s in storages:
            if 'total' in s and 'used' in s:
                result.append({
                    'storage': s.get('storage'),
                    'type': s.get('type'),
                    'total': s.get('total', 0),
                    'used': s.get('used', 0)
                })
        logger.info(f"[proxmox_storage] 반환: {result}")
        return {'storages': result}
    except Exception as e:
        logger.exception(f"[proxmox_storage] 예외 발생: {e}")
        return {'error': str(e)}, 500


# app.py는 변수 전달 및 결과 처리만 담당

def deploy_infrastructure(project_path, config):
    """인프라 배포 실행"""
    try:
        # Terraform 초기화
        subprocess.run(['terraform', 'init'], cwd=project_path, check=True)
        
        # Terraform 계획
        subprocess.run(['terraform', 'plan'], cwd=project_path, check=True)
        
        # Terraform 적용
        result = subprocess.run(['terraform', 'apply', '-auto-approve'], 
                              cwd=project_path, check=True, capture_output=True, text=True)
        
        # 생성된 IP 주소 추출
        output_result = subprocess.run(['terraform', 'output', '-json'], 
                                     cwd=project_path, capture_output=True, text=True)
        
        if output_result.returncode == 0:
            outputs = json.loads(output_result.stdout)
            vm_ips = outputs.get('vm_ips', {}).get('value', [])
            
            # 서버가 준비될 때까지 대기
            time.sleep(30)
            
            # Ansible 플레이북 실행
            subprocess.run(['ansible-playbook', '-i', 'inventory', 'playbook.yml'], 
                          cwd=project_path, check=True)
            
            print(f"Infrastructure deployed successfully for project: {config['project_name']}")
            print(f"VM IPs: {vm_ips}")
        
    except subprocess.CalledProcessError as e:
        print(f"Error deploying infrastructure: {e}")
        print(f"Error output: {e.stderr if hasattr(e, 'stderr') else ''}")

def get_vm_info_from_proxmox(server_name):
    """Proxmox API에서 VM 이름으로 vmid, ip 등 정보 조회"""
    headers, error = get_proxmox_auth()
    if error:
        return None
    
    vms, error = get_proxmox_vms(headers)
    if error:
        return None
    
    for vm in vms:
        if vm['name'] == server_name:
            return {
                'vmid': vm['vmid'],
                'status': vm.get('status', ''),
                'ip_address': None  # 필요시 별도 조회
            }
    return None

def check_proxmox_vm_exists(server_name):
    """Proxmox에서 VM 존재 여부 확인"""
    headers, error = get_proxmox_auth()
    if error:
        return False  # 인증 실패 시 존재하지 않는 것으로 간주
    
    vms, error = get_proxmox_vms(headers)
    if error:
        return False  # 조회 실패 시 존재하지 않는 것으로 간주
    
    for vm in vms:
        if vm['name'] == server_name:
            return True  # 아직 존재함
    return False  # 존재하지 않음

def proxmox_api_auth():
    """기존 호환성을 위한 함수 (deprecated)"""
    headers, error = get_proxmox_auth()
    if error:
        return None
    
    # 기존 형식으로 변환
    cookie = headers.get('Cookie', '')
    csrf = headers.get('CSRFPreventionToken', '')
    
    if 'PVEAuthCookie=' in cookie:
        ticket = cookie.split('PVEAuthCookie=')[1].split(';')[0]
        return {
            'ticket': ticket,
            'csrf': csrf
        }
    return None

def proxmox_vm_action(vmid, action):
    proxmox_url = app.config['PROXMOX_ENDPOINT']
    node = app.config['PROXMOX_NODE']
    auth = proxmox_api_auth()
    if not auth:
        return False, 'Proxmox 인증 실패'
    url = f"{proxmox_url}/api2/json/nodes/{node}/qemu/{vmid}/status/{action}"
    headers = {
        'Cookie': f'PVEAuthCookie={auth["ticket"]}',
        'CSRFPreventionToken': auth['csrf']
    }
    resp = requests.post(url, headers=headers, verify=False)
    if resp.status_code == 200:
        return True, None
    else:
        return False, resp.text

@app.route('/assign_role/<server_name>', methods=['POST'])
@permission_required('assign_roles')
def assign_role(server_name):
    logger.info(f"[assign_role] 서버: {server_name}, 요청 데이터: {request.form.to_dict() if request.form else request.json}")
    try:
        role = request.form.get('role') if request.form else request.json.get('role')
        if not role:
            return jsonify({'success': False, 'error': '역할(role)을 지정해야 합니다.'}), 400
        servers = read_servers_from_tfvars()
        if server_name not in servers:
            return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404
        server = servers[server_name]
        ip = None
        if 'network_devices' in server and server['network_devices']:
            ip = server['network_devices'][0].get('ip_address')
        if not ip:
            return jsonify({'success': False, 'error': '서버의 IP 정보를 찾을 수 없습니다.'}), 400
        username = server.get('vm_username', get_default_username(server.get('os_type', 'rocky')))
        # 임시 인벤토리 파일 생성
        import datetime, tempfile, os
        now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        log_dir = os.path.join('logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f'assign_role_{server_name}_{now_str}.log')
        with tempfile.NamedTemporaryFile('w', delete=False, dir='/tmp', prefix=f'inventory_{server_name}_', suffix='.ini') as f:
            f.write(f'{server_name} ansible_host={ip} ansible_user={username} ansible_ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"\n')
            inventory_path = f.name
        # ansible-playbook 실행
        result = subprocess.run([
            'ansible-playbook', '-i', inventory_path, 'role_playbook.yml',
            '-e', f'role={role}'
        ], cwd=ANSIBLE_DIR, capture_output=True, text=True)
        os.unlink(inventory_path)
        # 로그 파일 저장
        with open(log_path, 'w', encoding='utf-8') as logf:
            logf.write('=== STDOUT ===\n')
            logf.write(result.stdout)
            logf.write('\n=== STDERR ===\n')
            logf.write(result.stderr)
        if result.returncode == 0:
            # 역할 변경
            server['role'] = role
            servers[server_name] = server
            write_servers_to_tfvars(servers)
            logger.info(f"[assign_role] 역할 할당 성공: {server_name}")
            return jsonify({'success': True, 'message': f'역할({role})이 적용되었습니다.', 'stdout': result.stdout, 'stderr': result.stderr, 'log_path': log_path})
        else:
            logger.error(f"[assign_role] Ansible 실행 실패: {result.stderr}")
            return jsonify({'success': False, 'error': 'Ansible 실행 실패', 'stdout': result.stdout, 'stderr': result.stderr, 'log_path': log_path}), 500
    except Exception as e:
        logger.exception(f"[assign_role] 역할 할당 중 예외 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/remove_role/<server_name>', methods=['POST'])
@permission_required('remove_role')
def remove_role(server_name):
    servers = read_servers_from_tfvars()
    if server_name not in servers:
        return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404
    # 역할 제거
    servers[server_name]['role'] = ''
    write_servers_to_tfvars(servers)
    # (옵션) ansible-playbook로 서비스 중지/삭제 역할 실행 가능
    return jsonify({'success': True, 'message': '역할이 삭제되었습니다.'})

@app.route('/start_server/<server_name>', methods=['POST'])
@permission_required('start_server')  # 필요시 권한 조정
def start_server(server_name):
    logger.info(f"[start_server] 요청: {server_name}")
    try:
        server = db.get_server_by_name(server_name)
        if not server or not server['vmid']:
            return jsonify({'success': False, 'error': 'DB에서 VMID 정보를 찾을 수 없습니다.'}), 400
        vmid = server['vmid']
        ok, err = proxmox_vm_action(vmid, 'start')
        if ok:
            logger.info(f"[start_server] VM 시작 요청: vmid={vmid}")
            return jsonify({'success': True, 'message': f'{server_name} 서버가 시작되었습니다.'})
        else:
            logger.error(f"[start_server] 시작 실패: {err}")
            return jsonify({'success': False, 'error': err}), 500
    except Exception as e:
        logger.exception(f"[start_server] 예외 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def get_default_username(os_type):
    """OS별 기본 사용자명 반환"""
    defaults = {
        'rocky': 'rocky',
        'ubuntu': 'ubuntu'
    }
    return defaults.get(os_type, 'rocky')

def get_default_password(os_type):
    """OS별 기본 비밀번호 반환"""
    defaults = {
        'rocky': 'rocky123',
        'ubuntu': 'ubuntu123'
    }
    return defaults.get(os_type, 'rocky123')



@app.route('/admin/iam', methods=['GET'])
@admin_required
def admin_iam_api():
    """IAM 관리 API - 사용자 목록과 권한 목록 반환 (DB에서)"""
    users = get_all_users()
    return jsonify({
        'users': users,
        'permissions': PERMISSION_LIST
    })

@app.route('/admin/iam/<username>/permissions', methods=['POST'])
@admin_required
def admin_iam_set_permissions(username):
    data = request.json
    permissions = data.get('permissions', [])
    
    success, message = update_user_permissions(username, permissions)
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

@app.route('/admin/iam/<username>/role', methods=['POST'])
@admin_required
def admin_iam_set_role(username):
    data = request.json
    new_role = data.get('role')
    
    success, message = update_user_role(username, new_role)
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

@app.route('/dashboard/content')
def dashboard_content():
    # 실제 서버/메모리 통계 정보 계산 (예시)
    # 실제 구현에서는 db 또는 API에서 값을 가져와야 함
    try:
        from database import db
        servers = db.get_all_servers() if hasattr(db, 'get_all_servers') else []
        # Row 객체를 dict로 변환
        servers = [dict(s) for s in servers]
    except Exception:
        servers = []
    total_servers = len(servers)
    running_servers = sum(1 for s in servers if s.get('status') == 'running')
    stopped_servers = sum(1 for s in servers if s.get('status') == 'stopped')
    total_memory_gb = sum(s.get('memory', 0) for s in servers) / 1024 / 1024 / 1024 if servers else 0
    return render_template(
        'partials/dashboard_content.html',
        total_servers=total_servers,
        running_servers=running_servers,
        stopped_servers=stopped_servers,
        total_memory_gb=total_memory_gb,
        node_name=app.config.get('PROXMOX_NODE', 'prox')
    )

@app.route('/instances/content')
def instances_content():
    # roles 변수 준비 (예시)
    roles = {
        'web': {'name': '웹서버', 'description': '웹 서비스 제공'},
        'was': {'name': 'WAS', 'description': '애플리케이션 서버'},
        'java': {'name': 'JAVA', 'description': '자바 서버'},
        'search': {'name': '검색', 'description': '검색 서버'},
        'ftp': {'name': 'FTP', 'description': '파일 서버'},
        'db': {'name': 'DB', 'description': '데이터베이스 서버'}
    }
    return render_template('partials/instances_content.html', roles=roles)

@app.route('/instances/multi-server-summary')
def multi_server_summary():
    return render_template('partials/multi_server_summary.html')

@app.route('/storage/content')
def storage_content():
    return render_template('partials/storage_content.html')

@app.route('/admin/iam/content')
def admin_iam_content():
    return render_template('partials/admin_iam_content.html')

@app.route('/firewall/groups/content')
def firewall_groups_content():
    return render_template('partials/firewall_groups_content.html')

@app.route('/firewall/group-detail/content')
def firewall_group_detail_content():
    return render_template('partials/firewall_group_detail_content.html')

@app.route('/users/<username>/password', methods=['POST'])
@permission_required('manage_users')
def admin_change_user_password(username):
    """관리자가 특정 사용자의 비밀번호를 변경"""
    data = request.json
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not new_password or not confirm_password:
        return jsonify({'error': '새 비밀번호와 확인을 입력해주세요.'}), 400
    if new_password != confirm_password:
        return jsonify({'error': '새 비밀번호가 일치하지 않습니다.'}), 400
    if len(new_password) < 6:
        return jsonify({'error': '새 비밀번호는 최소 6자 이상이어야 합니다.'}), 400

    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404

    db.update_user_password(username, new_password)
    add_notification(
        type='password_change',
        title='비밀번호 변경',
        message=f'관리자가 {username}의 비밀번호를 변경했습니다.',
        severity='info',
        user_id=user['id']
    )
    return jsonify({'success': True, 'message': f'{username}의 비밀번호가 변경되었습니다.'})

# --- 방화벽 그룹 샘플 데이터 (전역 관리) ---
FIREWALL_GROUPS = [
    {'name': 'web-allow', 'description': '웹서버 허용'},
    {'name': 'db-only', 'description': 'DB 접근만 허용'},
]

def get_group_index(name):
    for i, g in enumerate(FIREWALL_GROUPS):
        if g['name'] == name:
            return i
    return -1

@app.route('/firewall/groups', methods=['GET'])
def get_firewall_groups():
    try:
        cursor = db.get_connection().cursor()
        cursor.execute("""
            SELECT firewall_group, COUNT(*) as instance_count 
            FROM servers 
            WHERE firewall_group IS NOT NULL 
            GROUP BY firewall_group
        """)
        group_counts = {row['firewall_group']: row['instance_count'] for row in cursor.fetchall()}
        groups = FIREWALL_GROUPS.copy()
        for group in groups:
            group['instance_count'] = group_counts.get(group['name'], 0)
        return jsonify({'groups': groups})
    except Exception as e:
        logger.error(f"방화벽 그룹 목록 조회 실패: {str(e)}")
        return jsonify({'groups': []})

@app.route('/firewall/groups/<group_name>', methods=['DELETE'])
def delete_firewall_group(group_name):
    idx = get_group_index(group_name)
    if idx == -1:
        return jsonify({'success': False, 'error': '존재하지 않는 그룹입니다.'}), 404
    del FIREWALL_GROUPS[idx]
    return jsonify({'success': True, 'message': '그룹이 삭제되었습니다.'})

@app.route('/firewall/groups/<group_name>/rules')
def get_firewall_group_rules(group_name):
    rules = db.get_firewall_rules(group_name)
    return jsonify({'group': {'name': group_name, 'description': f'{group_name} 그룹 설명'}, 'rules': rules})

@app.route('/firewall/groups/<group_name>/rules', methods=['POST'])
def add_firewall_group_rule(group_name):
    direction = request.form.get('direction')
    protocol = request.form.get('protocol')
    port = request.form.get('port')
    source = request.form.get('source')
    description = request.form.get('description')
    if not direction or not protocol or not port:
        return jsonify({'success': False, 'error': '필수 항목 누락'}), 400
    db.add_firewall_rule(group_name, direction, protocol, port, source, description)
    return jsonify({'success': True, 'message': '규칙이 추가되었습니다.'})

@app.route('/firewall/groups/<group_name>/rules/<int:rule_id>', methods=['DELETE'])
def delete_firewall_group_rule(group_name, rule_id):
    ok = db.delete_firewall_rule(group_name, rule_id)
    if not ok:
        return jsonify({'success': False, 'error': '규칙을 찾을 수 없습니다.'}), 404
    return jsonify({'success': True, 'message': '규칙이 삭제되었습니다.'})


@app.route('/assign_firewall_group/<server_name>', methods=['POST'])
@permission_required('assign_firewall_group')
def assign_firewall_group(server_name):
    """서버에 방화벽 그룹 할당"""
    try:
        firewall_group = request.form.get('firewall_group')
        if not firewall_group:
            return jsonify({'success': False, 'error': '방화벽 그룹이 지정되지 않았습니다.'}), 400
        
        # TODO: Proxmox API를 통해 실제 방화벽 그룹 할당
        # 현재는 DB에만 저장 (임시)
        
        # 서버 정보 업데이트
        db.execute("""
            UPDATE servers 
            SET firewall_group = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE name = ?
        """, (firewall_group, server_name))
        
        if db.total_changes > 0:
            add_server_notification(
                'firewall_group_assigned',
                '방화벽 그룹 할당',
                f'{server_name} 서버에 {firewall_group} 방화벽 그룹이 할당되었습니다.',
                severity='info'
            )
            return jsonify({'success': True, 'message': f'{firewall_group} 방화벽 그룹이 할당되었습니다.'})
        else:
            return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404
            
    except Exception as e:
        logger.error(f"방화벽 그룹 할당 실패: {str(e)}")
        return jsonify({'success': False, 'error': f'방화벽 그룹 할당 실패: {str(e)}'}), 500

@app.route('/remove_firewall_group/<server_name>', methods=['POST'])
@permission_required('remove_firewall_group')
def remove_firewall_group(server_name):
    """서버에서 방화벽 그룹 해제"""
    try:
        # 서버 정보 업데이트
        db.execute("""
            UPDATE servers 
            SET firewall_group = NULL, updated_at = CURRENT_TIMESTAMP 
            WHERE name = ?
        """, (server_name,))
        
        if db.total_changes > 0:
            add_server_notification(
                'firewall_group_removed',
                '방화벽 그룹 해제',
                f'{server_name} 서버의 방화벽 그룹이 해제되었습니다.',
                severity='info'
            )
            return jsonify({'success': True, 'message': '방화벽 그룹이 해제되었습니다.'})
        else:
            return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404
            
    except Exception as e:
        logger.error(f"방화벽 그룹 해제 실패: {str(e)}")
        return jsonify({'success': False, 'error': f'방화벽 그룹 해제 실패: {str(e)}'}), 500

# --- 공통 유틸리티 함수들 ---

def get_proxmox_auth() -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Proxmox API 인증 정보 반환 (공통 함수)"""
    try:
        proxmox_url = app.config['PROXMOX_ENDPOINT']
        username = app.config['PROXMOX_USERNAME']
        password = app.config['PROXMOX_PASSWORD']
        
        auth_url = f"{proxmox_url}/api2/json/access/ticket"
        auth_data = {'username': username, 'password': password}
        
        auth_response = requests.post(auth_url, data=auth_data, verify=False)
        if auth_response.status_code != 200:
            return None, 'Proxmox 인증 실패'
        
        auth_result = auth_response.json()
        if 'data' not in auth_result:
            return None, '인증 토큰을 가져올 수 없습니다'
        
        ticket = auth_result['data']['ticket']
        csrf_token = auth_result['data']['CSRFPreventionToken']
        
        headers = {
            'Cookie': f'PVEAuthCookie={ticket}',
            'CSRFPreventionToken': csrf_token
        }
        
        return headers, None
    except Exception as e:
        return None, f'인증 중 예외 발생: {str(e)}'

def get_proxmox_vms(headers: Dict[str, str]) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Proxmox에서 모든 VM 목록 조회 (공통 함수)"""
    try:
        proxmox_url = app.config['PROXMOX_ENDPOINT']
        
        # 모든 노드에서 VM 검색
        nodes_url = f"{proxmox_url}/api2/json/nodes"
        nodes_response = requests.get(nodes_url, headers=headers, verify=False)
        
        if nodes_response.status_code != 200:
            return None, '노드 정보를 가져올 수 없습니다'
        
        nodes = nodes_response.json().get('data', [])
        all_vms = []
        
        for node in nodes:
            node_name = node['node']
            vms_url = f"{proxmox_url}/api2/json/nodes/{node_name}/qemu"
            vms_response = requests.get(vms_url, headers=headers, verify=False)
            
            if vms_response.status_code == 200:
                vms = vms_response.json().get('data', [])
                for vm in vms:
                    vm['node'] = node_name
                all_vms.extend(vms)
        
        return all_vms, None
    except Exception as e:
        return None, f'VM 목록 조회 중 예외 발생: {str(e)}'

def process_server_data(server_data: Dict[str, Any], os_type: str = 'rocky') -> Dict[str, Any]:
    """서버 데이터 전처리 (공통 함수)"""
    # vm_username, vm_password 기본값 설정
    if 'vm_username' not in server_data or not server_data['vm_username']:
        server_data['vm_username'] = get_default_username(os_type)
    if 'vm_password' not in server_data or not server_data['vm_password']:
        server_data['vm_password'] = get_default_password(os_type)
    
    # 디스크 설정 처리
    if 'disks' in server_data:
        for disk in server_data['disks']:
            if 'datastore_id' not in disk or not disk['datastore_id']:
                disk['datastore_id'] = 'local-lvm'
            # datastore_id에서 disk_type 추론
            if 'disk_type' not in disk:
                if disk['datastore_id'] == 'ssd':
                    disk['disk_type'] = 'ssd'
                else:
                    disk['disk_type'] = 'hdd'
            # 파일 포맷 기본값 설정
            if 'file_format' not in disk:
                disk['file_format'] = 'auto'
    
    # 네트워크 설정 처리
    if 'network_devices' in server_data:
        for net in server_data['network_devices']:
            if 'bridge' not in net or not net['bridge']:
                net['bridge'] = 'vmbr0'
    
    return server_data

def save_server_to_db(server_name: str, server_data: Dict[str, Any], vm_info: Optional[Dict[str, Any]]) -> None:
    """서버 정보를 DB에 저장 (공통 함수)"""
    if vm_info:
        db.add_server(
            name=server_name,
            vmid=vm_info.get('vmid'),
            status=vm_info.get('status', 'pending'),
            ip_address=vm_info.get('ip_address'),
            role=server_data.get('role', ''),
            os_type=server_data.get('os_type', ''),
            cpu=int(server_data.get('cpu', 0)) if server_data.get('cpu') is not None else None,
            memory=int(server_data.get('memory', 0)) if server_data.get('memory') is not None else None
        )

def add_server_notification(notification_type: str, title: str, message: str, 
                           details: Optional[str] = None, severity: str = 'info') -> None:
    """서버 관련 알림 추가 (공통 함수)"""
    add_notification(
        type=notification_type,
        title=title,
        message=message,
        details=details,
        severity=severity,
        user_id='system'
    )

def handle_terraform_failure(servers: Dict[str, Any], server_names: List[str], 
                           task_id: str, error_msg: str) -> None:
    """Terraform 실패 시 정리 작업 (공통 함수)"""
    # tfvars에서 새 서버 정보 제거
    for name in server_names:
        if name in servers:
            del servers[name]
    write_servers_to_tfvars(servers)
    
    update_task(task_id, 'error', f'Terraform apply 실패: {error_msg}')
    add_server_notification(
        'server_error',
        '서버 생성 실패',
        f'서버 생성 중 오류 발생: {error_msg}',
        details=error_msg,
        severity='error'
    )

@app.route('/firewall/groups', methods=['POST'])
def add_firewall_group():
    """방화벽 그룹 추가 (임시: 샘플 데이터에 추가)"""
    name = request.form.get('name')
    description = request.form.get('description', '')
    # TODO: Proxmox 연동 및 DB 저장
    # 임시: 성공만 반환
    return jsonify({'success': True, 'message': '그룹이 추가되었습니다.'})

if __name__ == '__main__':
    # 필요한 디렉토리 생성
    os.makedirs('templates', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)