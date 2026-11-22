"""仅使用 Python 标准库的入门智能体。"""
import argparse
from pathlib import Path
import getpass
import json
import os
import urllib.request
import urllib.error

TOOLS = [{"type": "function", "function": {"name": "add", "description": "计算两个数的和", "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"], "additionalProperties": False}}}]


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


def execute(name, args):
    if name != 'add' or not isinstance(args, dict) or set(args) != {'a', 'b'}:
        raise ValueError('工具或参数不符合白名单')
    if any(type(value) not in (int, float) for value in args.values()):
        raise ValueError('参数必须是数字')
    return args['a'] + args['b']


def run(prompt, model, call, trace=lambda message: None):
    messages = [{'role': 'system', 'content': '你是中文教学助手。加法必须调用 add 工具。'}, {'role': 'user', 'content': prompt}]
    for step in range(8):
        trace(f'[第 {step + 1} 轮] 请求模型')
        result = call({'model': model, 'messages': messages, 'tools': TOOLS, 'thinking': {'type': 'disabled'}, 'max_tokens': 1024})
        choice = result['choices'][0]
        message = choice['message']
        messages.append(message)
        calls = message.get('tool_calls', [])
        if not calls:
            if choice.get('finish_reason') != 'stop':
                raise RuntimeError('模型未正常结束回答')
            trace('[完成] 模型返回最终回答')
            return message.get('content', '')
        for tool in calls:
            try:
                name = tool['function']['name']
                arguments = json.loads(tool['function']['arguments'])
                trace(f'[工具调用] {name}，参数：{json.dumps(arguments, ensure_ascii=False)}')
                value = execute(name, arguments)
                output = {'result': value}
            except (ValueError, TypeError, KeyError):
                output = {'error': '工具名称或参数无效'}
            trace(f'[工具结果] {json.dumps(output, ensure_ascii=False)}')
            messages.append({'role': 'tool', 'tool_call_id': tool['id'], 'content': json.dumps(output)})
    raise RuntimeError('已达到 8 轮上限')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model')
    parser.add_argument('--prompt', default='请用工具计算 123 加 456，并解释过程。')
    args = parser.parse_args()
    key = os.environ.get('DEEPSEEK_API_KEY')
    local_config = Path(__file__).resolve().parent / '.local-key.json'
    if not key and local_config.exists():
        key = json.loads(local_config.read_text())['api_key']
    if not key:
        key = getpass.getpass('DeepSeek API Key（输入隐藏，仅本次使用）: ')
    if not key.strip():
        raise RuntimeError('尚未提供密钥')
    models = [item['id'] for item in request('models', key)['data']]
    print('账户实际可用模型：', ', '.join(models))
    if not args.model:
        print('请从上述列表选择模型，再使用 --model 模型ID 运行。')
        return
    if args.model not in models:
        raise RuntimeError('所选模型不在账户模型列表内')
    print(run(args.prompt, args.model, lambda body: request('chat/completions', key, body), trace=print))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, KeyError, ValueError) as error:
        print('未完成：', str(error))
        raise SystemExit(1)
