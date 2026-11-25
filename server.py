"""仅监听本机的网页 Agent 服务；只公开首页，不公开项目文件。"""
import json
import os
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from api import request
from tutor import teach

ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()
ACTIVE = {}


def load_key():
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        path = ROOT / '.local-key.json'
        if path.exists():
            key = json.loads(path.read_text()).get('api_key')
    if not isinstance(key, str) or not key.strip():
        raise RuntimeError('请先在终端运行 python configure_key.py 配置密钥')
    return key.strip()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/topics':
            body = (ROOT / 'topics.json').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path not in ('/', '/index.html'):
            self.send_error(404)
            return
        page = (ROOT / 'web/index.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(page)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(page)

    def do_POST(self):
        expected = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected or self.headers.get('Origin') not in (None, 'http://' + expected):
            self.send_error(403)
            return
        if self.path == '/api/stop':
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size < 1024:
                    raise ValueError()
                data = json.loads(self.rfile.read(size))
                event = ACTIVE.get(data.get('request_id'))
                if event is not None:
                    event.set()
                body = json.dumps({'stopped': event is not None}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (ValueError, TypeError, AttributeError):
                self.send_error(400)
            return
        if self.path != '/api/tutor':
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        def emit(kind, **data):
            self.wfile.write((json.dumps({'type': kind, **data}, ensure_ascii=False) + '\n').encode())
            self.wfile.flush()
        acquired = False
        task_id = None
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 100000:
                raise ValueError('请求大小无效')
            self.connection.settimeout(30)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('请求须为对象')
            model = data.get('model')
            if not isinstance(model, str) or not 1 <= len(model) <= 100:
                raise ValueError('请填写有效模型 ID')
            acquired = LOCK.acquire(blocking=False)
            if not acquired:
                raise RuntimeError('已有任务执行中，请稍后重试')
            task_id = data.get('request_id')
            if task_id is not None and (not isinstance(task_id, str) or not 1 <= len(task_id) <= 100):
                raise ValueError('请求标识无效')
            cancelled = threading.Event()
            if task_id:
                ACTIVE[task_id] = cancelled
            def check_cancelled():
                if cancelled.is_set():
                    raise RuntimeError('任务已暂停')
            def model_call(body):
                check_cancelled()
                result = request('chat/completions', key, body)
                check_cancelled()
                return result
            def trace(message):
                check_cancelled()
                emit('trace', message=message)
            key = load_key()
            models = [m['id'] for m in request('models', key)['data']]
            if model not in models:
                raise ValueError('模型不在账户实际可用列表中')
            result = teach(data.get('goal'), data.get('history', []), data.get('student', ''), model, model_call, trace, mode=data.get('mode', 'conversation'))
            if data.get('mode', 'conversation') == 'conversation' and data.get('student', '').strip():
                trace('[Action] 根据本轮真实回答更新右侧素材草稿')
                try:
                    facts = data.get('history', []) + [{'role': 'user', 'content': data['student']}]
                    material = teach(data['goal'], facts, '', model, model_call, trace, mode='card')
                    result['live_card'] = material['card']
                except (ValueError, RuntimeError):
                    check_cancelled()
                    result['material_warning'] = '对话已完成，但素材更新失败；保留上一版，下一轮回答后会再次更新。'
            emit('result', **result)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, RuntimeError) as error:
            emit('error', message=str(error))
        except Exception:
            emit('error', message='服务执行异常，任务尚未完成；请检查配置后重试')
        finally:
            if acquired:
                if isinstance(task_id, str):
                    ACTIVE.pop(task_id, None)
                LOCK.release()


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('网页地址：http://127.0.0.1:8765 （按 Ctrl+C 停止）', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
