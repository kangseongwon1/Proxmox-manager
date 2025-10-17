"""
Terraform 서버에서 실행되는 워커
Redis Pub/Sub를 구독하여 Terraform 작업 처리
"""

import json
import time
import subprocess
import os
from typing import Dict, Any
import redis

class TerraformWorker:
    """Terraform 작업 처리 워커"""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, 
                 redis_password: str = None):
        # Redis 연결
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )
        
        self.request_channel = "terraform:requests"
        self.response_channel = "terraform:responses"
        self.terraform_dir = "/opt/terraform"
    
    def start(self):
        """워커 시작"""
        print("🚀 Terraform 워커 시작")
        
        # Redis Pub/Sub 구독
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(self.request_channel)
        
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    self._handle_request(message['data'])
                    
        except KeyboardInterrupt:
            print("🛑 Terraform 워커 중지")
        finally:
            pubsub.close()
    
    def _handle_request(self, message_data: str):
        """요청 처리"""
        try:
            request = json.loads(message_data)
            request_id = request.get('request_id')
            command = request.get('command')
            config = request.get('config', {})
            
            print(f"📨 Terraform 요청 수신: {command} (ID: {request_id})")
            
            # Terraform 명령어 실행
            result = self._execute_terraform_command(command, config)
            
            # 응답 전송
            response = {
                "request_id": request_id,
                "success": result.get('success', False),
                "output": result.get('output', ''),
                "error": result.get('error', ''),
                "timestamp": time.time()
            }
            
            self.redis_client.publish(
                self.response_channel,
                json.dumps(response)
            )
            
            print(f"✅ Terraform 응답 전송: {request_id}")
            
        except Exception as e:
            print(f"❌ 요청 처리 실패: {e}")
            
            # 에러 응답 전송
            error_response = {
                "request_id": request.get('request_id', 'unknown'),
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
            
            self.redis_client.publish(
                self.response_channel,
                json.dumps(error_response)
            )
    
    def _execute_terraform_command(self, command: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Terraform 명령어 실행"""
        try:
            # 작업 디렉토리로 이동
            os.chdir(self.terraform_dir)
            
            # 명령어 구성
            if command == "apply":
                cmd = ["terraform", "apply", "-auto-approve"]
            elif command == "plan":
                cmd = ["terraform", "plan"]
            elif command == "destroy":
                cmd = ["terraform", "destroy", "-auto-approve"]
                if config.get('target'):
                    cmd.extend(["-target", config['target']])
            else:
                return {
                    "success": False,
                    "error": f"지원하지 않는 명령어: {command}"
                }
            
            # Terraform 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Terraform 실행 타임아웃"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Terraform 실행 실패: {str(e)}"
            }

if __name__ == "__main__":
    # 환경 변수에서 Redis 설정 읽기
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_password = os.getenv('REDIS_PASSWORD')
    
    worker = TerraformWorker(redis_host, redis_port, redis_password)
    worker.start()
