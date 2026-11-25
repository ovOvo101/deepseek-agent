"""DeepSeek API 客户端，仅使用 Python 标准库。"""
import json
import urllib.request
import urllib.error


def request(path, key, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request('https://api.deepseek.com/' + path, data=data, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'API 返回 HTTP {exc.code}，请检查账户、余额和模型权限。') from None
    except urllib.error.URLError:
        raise RuntimeError('网络连接失败，请检查网络。') from None

