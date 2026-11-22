"""仅使用 Python 标准库的入门智能体。"""
from shopping import optimize
import math
import operator
import argparse
from pathlib import Path
import getpass
import json
import os
import urllib.request
import urllib.error

OPERATIONS = {'add': operator.add, 'subtract': operator.sub, 'multiply': operator.mul, 'divide': operator.truediv}
TOOLS = [{'type': 'function', 'function': {'name': name, 'description': description, 'parameters': {'type': 'object', 'properties': {'a': {'type': 'number'}, 'b': {'type': 'number'}}, 'required': ['a', 'b'], 'additionalProperties': False}}} for name, description in zip(OPERATIONS, ['加法', '减法', '乘法', '除法'])]


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
    if name not in OPERATIONS or not isinstance(args, dict) or set(args) != {'a', 'b'}:
        raise ValueError('工具或参数不符合白名单')
    if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e100 for v in args.values()):
        raise ValueError('参数必须是有限数字，绝对值不超过 1e100')
    if name == 'divide' and args['b'] == 0:
        raise ValueError('除数不能为零，请调整方案或说明无法计算')
    value = OPERATIONS[name](args['a'], args['b'])
    if not math.isfinite(value):
        raise ValueError('计算结果超出范围')
    return value


def get_plan(messages, model, call, trace):
    instruction = ('根据原始目标与工具观察输出一个合法 JSON 对象，不要 Markdown。'
                   '格式示例：{"goal":"计算余额","criteria":"余额有工具结果支持","adjustment":"继续核算","done":false}。'
                   '四个字段必须齐全；前三个值为非空字符串，done 为 JSON 布尔值 true 或 false。'
                   '完成标准描述待核验条件，不提前填写尚未由工具证实的答案。'
                   '只有已有最终回答且证据支持时 done 才可为 true。无法完成时应明确限制。')
    review_messages = messages + [{'role': 'user', 'content': instruction}]
    for attempt in range(3):
        review = call({'model': model, 'messages': review_messages, 'response_format': {'type': 'json_object'}, 'thinking': {'type': 'disabled'}, 'max_tokens': 1024})
        try:
            choice = review['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('输出未完整结束')
            state = json.loads(choice['message']['content'])
            if not isinstance(state, dict) or type(state.get('done')) is not bool or any(not isinstance(state.get(k), str) or not state[k].strip() for k in ('goal', 'criteria', 'adjustment')):
                raise ValueError('字段类型不正确')
            return state
        except (ValueError, TypeError, KeyError, IndexError):
            if attempt == 2:
                raise RuntimeError('规划连续 3 次格式无效，已停止；本次任务尚未完成') from None
            trace(f'[Adjust 格式恢复] 规划格式无效，正在重新规划（重试 {attempt + 1}/2），保留已有工具观察')
            # 不把错误输出加入执行历史，也不重复执行工具。
            review_messages = messages + [{'role': 'user', 'content': instruction + ' 上次输出格式无效。请严格按示例返回完整 JSON，字符串用双引号，布尔值不要加引号。'}]


def run(prompt, model, call, trace=lambda message: None, max_rounds=8, shopping=None):
    if not 1 <= max_rounds <= 20:
        raise ValueError('轮数必须在 1 到 20 之间')
    messages = [{'role': 'system', 'content': '你是目标驱动的中文助手。算术必须使用工具，工具结果是事实依据。用户原始目标不得擅自改变。只给简短行动摘要，不输出内部推理。'}, {'role': 'user', 'content': prompt}]
    state = {'goal': prompt, 'criteria': '满足用户请求，计算有工具结果支持', 'adjustment': '先明确目标与完成标准'}
    tools = list(TOOLS)
    if shopping is not None:
        optimize(shopping)
        tools.append({'type': 'function', 'function': {'name': 'optimize_discounts', 'description': '枚举用户已提供且固定的购物车与优惠规则，计算最低实付，参数为空。不允许改写规则。', 'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}})
        messages.append({'role': 'user', 'content': '请必须调用 optimize_discounts 求解以下规则，不自行猜测活动，解释最优方案及计算范围：' + json.dumps(shopping, ensure_ascii=False)})
    proposal = None
    for step in range(max_rounds):
        state = get_plan(messages, model, call, trace)
        trace(f"[Adjust 调整] {state['adjustment']}")
        trace(f"[Goal 第 {step + 1} 轮] {state['goal']}")
        trace(f"[完成标准] {state['criteria']}")
        if state['done'] and proposal:
            trace('[完成] 模型依据观察判定完成；请按完成标准验收')
            return proposal
        messages.append({'role': 'user', 'content': '保持原始目标。当前子目标与调整：' + json.dumps(state, ensure_ascii=False) + '。请执行下一步；完成时给出最终回答。'})
        trace('[Action 行动] 请求模型选择工具或提交回答')
        result = call({'model': model, 'messages': messages, 'tools': tools, 'thinking': {'type': 'disabled'}, 'max_tokens': 1024})
        choice = result['choices'][0]
        message = choice['message']
        messages.append(message)
        calls = message.get('tool_calls', [])
        if not calls:
            if choice.get('finish_reason') != 'stop' or not message.get('content'):
                raise RuntimeError('模型未正常结束回答')
            proposal = message['content']
            trace('[Observe 观察] 收到候选回答，下一轮检查是否达到目标')
            continue
        proposal = None
        if len(calls) > 8:
            raise RuntimeError('单轮工具调用超过 8 次上限')
        for tool in calls:
            try:
                name = tool['function']['name']
                arguments = json.loads(tool['function']['arguments'])
                trace(f'[Action 工具] {name}，参数：{json.dumps(arguments, ensure_ascii=False)}')
                if name == 'optimize_discounts' and shopping is not None:
                    if arguments != {}:
                        raise ValueError('优惠工具参数必须为空')
                    output = {'result': optimize(shopping)}
                else:
                    output = {'result': execute(name, arguments)}
            except (ValueError, TypeError, KeyError) as error:
                output = {'error': str(error)}
            trace(f'[Observe 工具结果] {json.dumps(output, ensure_ascii=False)}')
            messages.append({'role': 'tool', 'tool_call_id': tool['id'], 'content': json.dumps(output)})
    raise RuntimeError('达到轮数上限，目标尚未验收完成；可拆分任务后重试')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model')
    parser.add_argument('--shopping', type=Path, help='优惠规则 JSON 文件')
    parser.add_argument('--max-rounds', type=int, default=8)
    parser.add_argument('--prompt', default='请用工具计算 123 加 456，并解释过程。')
    args = parser.parse_args()
    shopping = None
    if args.shopping:
        shopping = json.loads(args.shopping.read_text())
        optimize(shopping)
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
    print(run(args.prompt, args.model, lambda body: request('chat/completions', key, body), trace=print, max_rounds=args.max_rounds, shopping=shopping))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, KeyError, ValueError) as error:
        print('未完成：', str(error))
        raise SystemExit(1)
