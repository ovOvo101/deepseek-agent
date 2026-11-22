"""用模拟响应验证闭环及失败恢复，不消耗 API。"""
import json
import unittest
from agent import execute, run


def response(message):
    return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', **message}}]}


def plan(done=False, adjustment='根据观察继续'):
    return response({'content': json.dumps({'goal': '完成计算', 'criteria': '工具结果支持回答', 'adjustment': adjustment, 'done': done})})


def tool(name, a, b):
    return response({'tool_calls': [{'id': 't', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps({'a': a, 'b': b})}}]})


class AgentTests(unittest.TestCase):
    def test_operations_and_boundary(self):
        for name, expected in [('add', 9), ('subtract', 3), ('multiply', 18), ('divide', 2)]:
            self.assertEqual(execute(name, {'a': 6, 'b': 3}), expected)
        for name, args in [('shell', {}), ('add', {'a': True, 'b': 2}), ('divide', {'a': 1, 'b': 0}), ('add', {'a': float('inf'), 'b': 1})]:
            with self.assertRaises(ValueError):
                execute(name, args)

    def test_observe_adjust_and_finish(self):
        replies = iter([plan(), tool('divide', 12, 0), plan(adjustment='修正零除数'), tool('divide', 12, 3), plan(), response({'content': '答案是 4'}), plan(True)])
        bodies = []
        def call(body):
            bodies.append(json.loads(json.dumps(body)))
            return next(replies)
        logs = []
        self.assertEqual(run('计算12除以3', '模拟', call, logs.append), '答案是 4')
        observations = [m for body in bodies for m in body['messages'] if m['role'] == 'tool']
        self.assertTrue(any('error' in json.loads(m['content']) for m in observations))
        self.assertTrue(any(json.loads(m['content']).get('result') == 4 for m in observations))
        self.assertTrue(any('修正零除数' in line for line in logs))

    def test_bad_json_recovery_preserves_observation(self):
        replies = iter([plan(), tool('add', 54, 8), response({'content': '{"done": nope}'}), plan(), response({'content': '62'}), plan(True)])
        bodies = []
        def call(body):
            bodies.append(json.loads(json.dumps(body)))
            return next(replies)
        self.assertEqual(run('计算总费用', '模拟', call), '62')
        self.assertEqual(sum('tools' in body for body in bodies), 2)
        for body in bodies[2:4]:
            self.assertTrue(any(m['role'] == 'tool' and json.loads(m['content']).get('result') == 62 for m in body['messages']))

    def test_retry_exhaustion(self):
        calls = []
        def call(body):
            calls.append(body)
            return response({'content': '无效 JSON'})
        with self.assertRaisesRegex(RuntimeError, '连续 3 次'):
            run('测试', '模拟', call)
        self.assertEqual(len(calls), 3)

    def test_limit(self):
        def call(body):
            return plan() if 'response_format' in body else tool('add', 1, 2)
        with self.assertRaises(RuntimeError):
            run('测试', '模拟', call, max_rounds=2)

    def test_invalid_plan(self):
        with self.assertRaises(RuntimeError):
            run('测试', '模拟', lambda body: response({'content': '{}'}))

    def test_truncation(self):
        with self.assertRaises(RuntimeError):
            run('测试', '模拟', lambda body: {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]})


if __name__ == '__main__':
    unittest.main()
