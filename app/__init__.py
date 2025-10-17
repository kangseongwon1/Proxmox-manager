"""
Proxmox Manager Flask Application Factory
"""
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import logging
import os
from logging.handlers import RotatingFileHandler

# 전역 객체들
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def load_vault_environment():
    """Vault 환경변수를 .bashrc에서 로드"""
    try:
        import subprocess
        
        # .bashrc에서 Vault 환경변수 추출
        bashrc_path = os.path.expanduser('~/.bashrc')
        if os.path.exists(bashrc_path):
            # bash -c "source ~/.bashrc && env" 명령어로 환경변수 추출
            result = subprocess.run(
                ['bash', '-c', f'source {bashrc_path} && env'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # 환경변수 파싱
                for line in result.stdout.split('\n'):
                    if '=' in line and any(var in line for var in ['VAULT_', 'TF_VAR_']):
                        key, value = line.split('=', 1)
                        os.environ[key] = value
                        print(f"🔧 Vault 환경변수 로드: {key}")
                
                print("✅ Vault 환경변수 로드 완료")
            else:
                print(f"⚠️ .bashrc 로드 실패: {result.stderr}")
        else:
            print("⚠️ .bashrc 파일을 찾을 수 없습니다")
            
    except Exception as e:
        print(f"⚠️ Vault 환경변수 로드 중 오류: {e}")

def create_app(config_name='development'):
    """Flask 애플리케이션 팩토리"""
    app = Flask(__name__)
    
    # Vault 환경변수 로드
    load_vault_environment()
    
    # 설정 로드
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
    
    app.config.from_object(config[config_name])
    
    # 데이터베이스 초기화
    db.init_app(app)
    
    # 마이그레이션 초기화
    migrate.init_app(app, db)
    
    # 로그인 매니저 초기화
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '이 페이지에 접근하려면 로그인이 필요합니다.'
    
    # 로깅 설정
    setup_logging(app)
    
    # 블루프린트 등록
    register_blueprints(app)
    
    # 에러 핸들러 등록
    register_error_handlers(app)
    
    # 보안 헤더 설정
    setup_security_headers(app)
    
    # 정적 파일 MIME 타입 설정
    setup_static_files(app)
    
    return app

def setup_logging(app):
    """로깅 설정"""
    # 기존에 붙어있는 핸들러가 있으면 중복 추가를 방지하기 위해 정리
    if app.logger.handlers:
        app.logger.handlers.clear()

    # 콘솔 핸들러 설정 (항상 활성화, 중복 방지)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG)
    app.logger.addHandler(console_handler)
    
    if not app.debug and not app.testing:
        # 로그 디렉토리 생성
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # 파일 핸들러 설정
        file_handler = RotatingFileHandler(
            'logs/proxmox_manager.log', 
            maxBytes=10240000, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.DEBUG)
    app.logger.info('Proxmox Manager startup')

    # 하위 로거(app.*)들이 루트로 전파되어 중복 출력되지 않도록 차단
    pkg_logger = logging.getLogger('app')
    pkg_logger.propagate = False
    pkg_logger.setLevel(logging.DEBUG)

def register_blueprints(app):
    """블루프린트 등록"""
    from app.routes import main, auth, admin, servers, firewall, notification, backup
    from app.routes.monitoring import bp as monitoring
    from app.routes.servers_async import async_bp
    from app.routes.cleanup import cleanup_bp
    from app.routes.role_routes import role_bp
    
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(servers)
    app.register_blueprint(async_bp)  # 비동기 작업
    app.register_blueprint(cleanup_bp)  # 자동 정리
    app.register_blueprint(role_bp)  # 역할 할당
    app.register_blueprint(firewall)
    app.register_blueprint(notification)
    app.register_blueprint(backup)
    app.register_blueprint(monitoring)

def register_error_handlers(app):
    """에러 핸들러 등록"""
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

def setup_security_headers(app):
    """보안 헤더 설정"""
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

def setup_static_files(app):
    """정적 파일 MIME 타입 설정"""
    # Flask의 정적 파일 서빙 설정
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    # 명시적 정적 파일 라우트 추가 (ChatGPT 추천 방법)
    @app.route('/static/<path:filename>')
    def custom_static(filename):
        """정적 파일을 명시적으로 MIME 타입과 함께 서빙"""
        try:
            import os
            from flask import send_from_directory, current_app
            
            # 파일 확장자 확인
            file_ext = os.path.splitext(filename)[1].lower()
            
            # MIME 타입 매핑
            mime_types = {
                '.js': 'application/javascript; charset=utf-8',
                '.css': 'text/css; charset=utf-8',
                '.json': 'application/json; charset=utf-8',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.svg': 'image/svg+xml',
                '.woff': 'font/woff',
                '.woff2': 'font/woff2',
                '.ttf': 'font/ttf',
                '.eot': 'application/vnd.ms-fontobject'
            }
            
            # 파일 경로
            static_folder = os.path.join(current_app.root_path, 'static')
            file_path = os.path.join(static_folder, filename)
            
            print(f"🔍 정적 파일 요청: {filename}")
            print(f"📁 파일 경로: {file_path}")
            print(f"📄 파일 확장자: {file_ext}")
            
            if os.path.exists(file_path):
                # MIME 타입 설정
                content_type = mime_types.get(file_ext, 'application/octet-stream')
                print(f"🎯 MIME 타입: {content_type}")
                
                # 파일 전송
                response = send_from_directory(static_folder, filename)
                response.headers['Content-Type'] = content_type
                response.headers['Cache-Control'] = 'no-cache'
                print(f"✅ 정적 파일 서빙 성공: {filename}")
                return response
            else:
                print(f"❌ 파일을 찾을 수 없음: {file_path}")
                return 'File not found', 404
                
        except Exception as e:
            print(f"❌ 정적 파일 서빙 오류: {e}")
            return 'Internal Server Error', 500
    
    @app.after_request
    def add_static_mime_types(response):
        """응답 후 MIME 타입 강제 설정"""
        # 요청 URL에서 파일 확장자 확인
        request_path = request.path.lower()
        
        # JavaScript 파일
        if request_path.endswith('.js'):
            response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
            response.headers['Cache-Control'] = 'no-cache'
            print(f"🔧 JavaScript MIME 타입 강제 설정: {request_path}")
        # CSS 파일
        elif request_path.endswith('.css'):
            response.headers['Content-Type'] = 'text/css; charset=utf-8'
            response.headers['Cache-Control'] = 'no-cache'
        # JSON 파일
        elif request_path.endswith('.json'):
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
        # 이미지 파일들
        elif request_path.endswith('.png'):
            response.headers['Content-Type'] = 'image/png'
        elif request_path.endswith('.jpg') or request_path.endswith('.jpeg'):
            response.headers['Content-Type'] = 'image/jpeg'
        elif request_path.endswith('.gif'):
            response.headers['Content-Type'] = 'image/gif'
        elif request_path.endswith('.svg'):
            response.headers['Content-Type'] = 'image/svg+xml'
        # 폰트 파일들
        elif request_path.endswith('.woff'):
            response.headers['Content-Type'] = 'font/woff'
        elif request_path.endswith('.woff2'):
            response.headers['Content-Type'] = 'font/woff2'
        elif request_path.endswith('.ttf'):
            response.headers['Content-Type'] = 'font/ttf'
        elif request_path.endswith('.eot'):
            response.headers['Content-Type'] = 'application/vnd.ms-fontobject'
        
        return response 