#!/usr/bin/env python3
import os
import sys
import time
import json
import argparse
import requests


def log(msg):
    print(msg, flush=True)


def try_login(session: requests.Session, base_url: str, username: str, password: str) -> bool:
    """여러 로그인 엔드포인트를 시도하여 세션을 획득한다."""
    candidates = [
        {
            'url': f"{base_url}/api/auth/login",
            'json': {'username': username, 'password': password},
            'headers': {'Content-Type': 'application/json'},
            'method': 'post_json'
        },
        {
            'url': f"{base_url}/login",
            'data': {'username': username, 'password': password},
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'method': 'post_form'
        },
    ]

    for cand in candidates:
        try:
            if cand['method'] == 'post_json':
                resp = session.post(cand['url'], json=cand['json'], headers=cand['headers'], timeout=10)
            else:
                resp = session.post(cand['url'], data=cand['data'], headers=cand['headers'], timeout=10)

            log(f"[LOGIN] {cand['url']} -> {resp.status_code}")

            # 성공 판단: 200/302 등 쿠키가 세팅되었는지로도 확인
            if resp.status_code in (200, 201, 204, 302):
                # 응답 JSON에 success 혹은 error 유무 체크 (있다면)
                ok = True
                try:
                    data = resp.json()
                    if isinstance(data, dict) and data.get('error'):
                        ok = False
                except Exception:
                    pass

                # 세션 쿠키가 존재하면 성공으로 간주
                if ok and session.cookies:
                    return True
        except Exception as e:
            log(f"[LOGIN] 실패: {e}")

    return False


def create_server_async(session: requests.Session, base_url: str, name: str, cpu: int, memory: int, disk: int = 20, os_type: str = 'ubuntu'):
    url = f"{base_url}/api/servers/async"
    payload = {
        'name': name,
        'cpu': cpu,
        'memory': memory,
        'disk': disk,
        'os_type': os_type,
    }
    resp = session.post(url, json=payload, timeout=20)
    log(f"[ASYNC CREATE] {url} -> {resp.status_code}")
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {'raw': resp.text}


def poll_task(session: requests.Session, base_url: str, task_id: str, timeout_sec: int = 120):
    url = f"{base_url}/api/tasks/{task_id}/status"
    start = time.time()
    while True:
        resp = session.get(url, timeout=10)
        try:
            data = resp.json()
        except Exception:
            data = {'raw': resp.text}
        log(f"[TASK] {resp.status_code} -> {data}")

        if isinstance(data, dict):
            status = data.get('status', '').lower()
            if status in ('completed', 'failed', 'success'):  # 다양한 표기 허용
                return data

        if time.time() - start > timeout_sec:
            return {'status': 'timeout', 'message': 'Polling timeout', 'last': data}

        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description='Login 후 비동기 서버 생성 API 테스트')
    parser.add_argument('--base-url', default=os.getenv('BASE_URL', 'http://localhost:5000'))
    parser.add_argument('--username', default=os.getenv('USERNAME', 'admin'))
    parser.add_argument('--password', default=os.getenv('PASSWORD', 'admin'))
    parser.add_argument('--name', default='test-async')
    parser.add_argument('--cpu', type=int, default=2)
    parser.add_argument('--memory', type=int, default=4)
    parser.add_argument('--disk', type=int, default=20)
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()

    sess = requests.Session()

    log(f"[INFO] BASE_URL={args.base_url}")
    if not try_login(sess, args.base_url, args.username, args.password):
        log("[ERROR] 로그인 실패. 사용자/비밀번호 혹은 로그인 엔드포인트 확인 필요")
        sys.exit(1)

    log("[INFO] 로그인 성공. 비동기 서버 생성 요청")
    status_code, body = create_server_async(sess, args.base_url, args.name, args.cpu, args.memory, args.disk)
    log(f"[ASYNC CREATE] 응답: {status_code} -> {body}")

    if status_code != 200 or not isinstance(body, dict) or not body.get('success'):
        log("[ERROR] 비동기 서버 생성 API 실패")
        sys.exit(2)

    task_id = body.get('task_id')
    if not task_id:
        log("[ERROR] task_id가 응답에 없습니다")
        sys.exit(3)

    log(f"[INFO] 작업 상태 폴링 시작: {task_id}")
    result = poll_task(sess, args.base_url, task_id, timeout_sec=args.timeout)
    log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")


if __name__ == '__main__':
    main()


