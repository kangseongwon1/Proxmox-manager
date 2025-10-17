"""
자동 정리 관련 API 엔드포인트
"""
from flask import Blueprint, jsonify, request
from app.services.cleanup_service import CleanupService
from app.models import Server
from app import db
import logging

logger = logging.getLogger(__name__)

cleanup_bp = Blueprint('cleanup', __name__)

@cleanup_bp.route('/api/cleanup/status/<server_name>', methods=['GET'])
def get_cleanup_status(server_name):
    """서버 정리 상태 확인"""
    try:
        cleanup_service = CleanupService()
        status = cleanup_service.get_cleanup_status(server_name)
        
        return jsonify({
            'success': True,
            'server_name': server_name,
            'status': status,
            'needs_cleanup': any(status.values())
        })
        
    except Exception as e:
        logger.error(f"❌ 정리 상태 확인 실패: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@cleanup_bp.route('/api/cleanup/clean/<server_name>', methods=['POST'])
def manual_cleanup(server_name):
    """수동 정리 실행"""
    try:
        cleanup_service = CleanupService()
        results = cleanup_service.cleanup_failed_server_creation(
            server_name=server_name,
            failure_stage='manual',  # 수동 정리
            error_message='사용자 요청에 의한 수동 정리'
        )
        
        return jsonify({
            'success': True,
            'server_name': server_name,
            'cleanup_results': results
        })
        
    except Exception as e:
        logger.error(f"❌ 수동 정리 실패: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@cleanup_bp.route('/api/cleanup/failed-servers', methods=['GET'])
def get_failed_servers():
    """실패한 서버 목록 조회"""
    try:
        # 상태가 'failed'인 서버들 조회
        failed_servers = Server.query.filter_by(status='failed').all()
        
        server_list = []
        for server in failed_servers:
            cleanup_service = CleanupService()
            status = cleanup_service.get_cleanup_status(server.name)
            
            server_list.append({
                'name': server.name,
                'status': server.status,
                'created_at': server.created_at.isoformat() if server.created_at else None,
                'cleanup_status': status,
                'needs_cleanup': any(status.values())
            })
        
        return jsonify({
            'success': True,
            'failed_servers': server_list,
            'count': len(server_list)
        })
        
    except Exception as e:
        logger.error(f"❌ 실패한 서버 목록 조회 실패: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@cleanup_bp.route('/api/cleanup/bulk-clean', methods=['POST'])
def bulk_cleanup():
    """대량 정리 실행"""
    try:
        data = request.get_json()
        server_names = data.get('server_names', [])
        
        if not server_names:
            return jsonify({
                'success': False,
                'error': 'server_names가 필요합니다'
            }), 400
        
        cleanup_service = CleanupService()
        results = []
        
        for server_name in server_names:
            try:
                result = cleanup_service.cleanup_failed_server_creation(
                    server_name=server_name,
                    failure_stage='bulk_manual',
                    error_message='대량 수동 정리'
                )
                results.append({
                    'server_name': server_name,
                    'success': True,
                    'results': result
                })
            except Exception as e:
                results.append({
                    'server_name': server_name,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(server_names),
            'successful': len([r for r in results if r['success']])
        })
        
    except Exception as e:
        logger.error(f"❌ 대량 정리 실패: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
