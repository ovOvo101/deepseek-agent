import unittest
from agent import execute, run

class AgentTests(unittest.TestCase):
    def test_tool_boundary(self):
        self.assertEqual(execute('add', {'a': 123, 'b': 456}), 579)
        with self.assertRaises(ValueError):
            execute('shell', {})
        with self.assertRaises(ValueError):
            execute('add', {'a': True, 'b': 2})

    def test_loop(self):
        def call(body):
            if body['messages'][-1]['role'] == 'tool':
                self.assertEqual(json_value(body['messages'][-1]['content']), 579)
                return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '579'}}]}
            return {'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [{'id': '1', 'type': 'function', 'function': {'name': 'add', 'arguments': '{"a":123,"b":456}'}}]}}]}
        self.assertEqual(run('计算', '测试模型', call), '579')

    def test_limit(self):
        def call(body):
            return {'choices': [{'message': {'role': 'assistant', 'tool_calls': [{'id': 'x', 'function': {'name': 'unknown', 'arguments': '{}'}}]}}]}
        with self.assertRaises(RuntimeError):
            run('测试', '测试模型', call)


def json_value(content):
    import json
    return json.loads(content)['result']

if __name__ == '__main__':
    unittest.main()
