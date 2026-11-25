"""仅监听本机的网页 Agent 服务；只公开首页，不公开项目文件。"""
import json
import os
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from agent import run, request
from shopping import optimize
from tutor import teach

ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()


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
        if self.path not in ('/api/run', '/api/tutor'):
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
            key = load_key()
            models = [m['id'] for m in request('models', key)['data']]
            if model not in models:
                raise ValueError('模型不在账户实际可用列表中')
            if self.path == '/api/tutor':
                result = teach(data.get('goal'), data.get('level'), data.get('history', []), data.get('student', ''), model, lambda body: request('chat/completions', key, body), lambda message: emit('trace', message=message))
                emit('result', **result)
                return
            shopping = data.get('shopping')
            optimize(shopping)
            prompt = data.get('prompt')
            if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
                raise ValueError('请填写有效目标')
            quote = None
            def trace(message):
                nonlocal quote
                # 只接受真实工具执行后产生的观察，不以浏览器计算代替。
                prefix = '[Observe 工具结果] '
                if message.startswith(prefix):
                    result = json.loads(message[len(prefix):]).get('result')
                    if isinstance(result, dict) and '最低实付' in result:
                        quote = result
                emit('trace', message=message)
            answer = run(prompt, model, lambda body: request('chat/completions', key, body), trace=trace, shopping=shopping)
            if quote is None:
                raise RuntimeError('模型没有执行优惠工具，本次未通过验收，请重试')
            emit('result', answer=answer, quote=quote)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, RuntimeError) as error:
            emit('error', message=str(error))
        except Exception:
            emit('error', message='服务执行异常，任务尚未完成；请检查配置后重试')
        finally:
            if acquired:
                LOCK.release()


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('网页地址：http://127.0.0.1:8765 （按 Ctrl+C 停止）', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
