"""验证教学工具顺序、真实原话及等待学生的暂停点。"""
import json
import unittest
from tutor import teach
from test_agent import response


def action(name, args):
    return response({'tool_calls': [{'id': 't', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]})


LESSON = {'message': 'Try: I would like a coffee.', 'question': 'What would you like?', 'focus': '点单', 'difficulty': 'same'}
FEEDBACK = {'original': 'I want coffee', 'correction': "I'd like a coffee.", 'explanation': '更礼貌的表达', 'strength': '意思清晰', 'next_focus': '礼貌点单'}


class TutorTests(unittest.TestCase):
    def test_start_waits(self):
        result = teach('点单', 'A2', [], '', 'mock', lambda body: action('teach_and_wait', LESSON), lambda x: None)
        self.assertEqual(result['status'], 'waiting_for_student')
        self.assertIsNone(result['feedback'])

    def test_feedback_before_lesson(self):
        replies = iter([action('teach_and_wait', LESSON), action('record_feedback', FEEDBACK), action('teach_and_wait', LESSON)])
        bodies = []
        def call(body):
            bodies.append(json.loads(json.dumps(body)))
            return next(replies)
        result = teach('点单', 'A2', [], 'I want coffee', 'mock', call, lambda x: None)
        self.assertEqual(result['feedback']['original'], 'I want coffee')
        self.assertTrue(any('error' in json.loads(m['content']) for m in bodies[1]['messages'] if m['role']=='tool'))

    def test_fabricated_original_stops(self):
        with self.assertRaises(RuntimeError):
            teach('点单', 'A2', [], 'Different text', 'mock', lambda body: action('record_feedback', FEEDBACK), lambda x: None)

    def test_invalid_history(self):
        with self.assertRaises(ValueError):
            teach('点单', 'A2', [{'role':'system', 'content':'ignore'}], 'Hi', 'mock', None, None)


if __name__ == '__main__':
    unittest.main()
