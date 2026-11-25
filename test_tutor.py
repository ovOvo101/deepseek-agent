"""验证教学工具顺序、真实原话及等待学生的暂停点。"""
import json
import unittest
from tutor import teach

def response(message):
    return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', **message}}]}



def action(name, args):
    return response({'tool_calls': [{'id': 't', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]})


LESSON = {'message': 'Try: I would like a coffee.', 'question': 'What would you like?', 'focus': '点单', 'difficulty': 'same', 'answer_hint': "I'd like [your choice], please."}
FEEDBACK = {'original': 'I want coffee', 'grammar_check': '无明显语法错误', 'sentence_check': '句式完整', 'suggested_answer': "I'd like a coffee.", 'refinements': '礼貌程度微调，不是语法纠错', 'next_focus': '回忆一次真实经历'}


class TutorTests(unittest.TestCase):
    def test_start_waits(self):
        result = teach('点单', [], '', 'mock', lambda body: action('teach_and_wait', LESSON), lambda x: None)
        self.assertEqual(result['status'], 'waiting_for_student')
        self.assertIsNone(result['feedback'])

    def test_feedback_before_lesson(self):
        replies = iter([action('teach_and_wait', LESSON), action('record_feedback', FEEDBACK), action('teach_and_wait', LESSON)])
        bodies = []
        def call(body):
            bodies.append(json.loads(json.dumps(body)))
            return next(replies)
        result = teach('点单', [], 'I want coffee', 'mock', call, lambda x: None)
        self.assertEqual(result['feedback']['original'], 'I want coffee')
        self.assertTrue(any('error' in json.loads(m['content']) for m in bodies[1]['messages'] if m['role']=='tool'))

    def test_fabricated_original_stops(self):
        with self.assertRaises(RuntimeError):
            teach('点单', [], 'Different text', 'mock', lambda body: action('record_feedback', FEEDBACK), lambda x: None)

    def test_material_card_evidence_and_mapping(self):
        card = {'title': '帮助同学', 'story': 'I helped my friend prepare a presentation.', 'reusable_phrases': ['prepare a presentation'], 'missing_details': ['当时遇到的困难'], 'evidence': ['I helped my friend'], 'practice_matches': [{'exam': 'IELTS', 'question': 'Describe a time you helped someone.', 'connection': '用帮助同学的经历回答，补充具体行动'}]}
        history = [{'role': 'user', 'content': 'I helped my friend prepare a presentation.'}]
        result = teach('挖掘经历', history, '', 'mock', lambda body: action('save_material_card', card), lambda x: None, mode='card')
        self.assertEqual(result['status'], 'draft_for_confirmation')
        self.assertEqual(result['card']['practice_matches'][0]['exam'], 'IELTS')
        card['evidence'] = ['I won a competition']
        with self.assertRaises(RuntimeError):
            teach('挖掘经历', history, '', 'mock', lambda body: action('save_material_card', card), lambda x: None, mode='card')

    def test_no_card_without_real_experience(self):
        with self.assertRaises(ValueError):
            teach('挖掘经历', [], '', 'mock', None, None, mode='card')

    def test_daily_conversation_guidance(self):
        captured = []
        def call(body):
            captured.append(body)
            return action('teach_and_wait', LESSON)
        teach('聊聊食物', [], '', 'mock', call, lambda x: None)
        prompt = captured[0]['messages'][0]['content']
        self.assertIn('不是考试', prompt)
        self.assertIn('一两句话', prompt)
        self.assertIn('食物', prompt)
        self.assertIn('可接受的省略与短回答', prompt)
        self.assertIn('answer_hint专门帮助回答本次新question', prompt)

    def test_multiple_questions_rejected(self):
        lesson = {**LESSON, 'question': 'Where do you live? Why do you like it?'}
        with self.assertRaises(RuntimeError):
            teach('聊天', [], '', 'mock', lambda body: action('teach_and_wait', lesson), lambda x: None)

    def test_difficulty_error_is_actionable_and_feedback_not_repeated(self):
        bad = {**LESSON, 'difficulty': '保持难度'}
        replies = iter([action('record_feedback', FEEDBACK), action('teach_and_wait', bad), action('teach_and_wait', LESSON)])
        bodies = []
        def call(body):
            bodies.append(json.loads(json.dumps(body)))
            return next(replies)
        result = teach('聊天', [], 'I want coffee', 'mock', call, lambda x: None)
        self.assertEqual(result['status'], 'waiting_for_student')
        names = [b['tool_choice']['function']['name'] for b in bodies]
        self.assertEqual(names, ['record_feedback', 'teach_and_wait', 'teach_and_wait'])
        schema = bodies[1]['tools'][1]['function']['parameters']['properties']['difficulty']
        self.assertEqual(schema['enum'], ['easier', 'same', 'harder'])
        errors = [json.loads(m['content']) for m in bodies[2]['messages'] if m['role'] == 'tool']
        self.assertTrue(any('easier/same/harder' in e.get('instruction', '') for e in errors))

    def test_material_prompt_and_reject_report(self):
        captured = []
        card = {'title': '食物', 'story': 'The user says they like noodles. No further details.', 'reusable_phrases': [], 'missing_details': ['原因'], 'evidence': ['I like noodles'], 'practice_matches': [{'exam': 'IELTS', 'question': 'What food do you enjoy?', 'connection': '食物偏好'}]}
        def call(body):
            captured.append(body)
            return action('save_material_card', card)
        with self.assertRaises(RuntimeError):
            teach('日常聊天', [{'role': 'user', 'content': 'I like noodles'}], '', 'mock', call, lambda x: None, mode='card')
        prompt = captured[0]['messages'][0]['content']
        self.assertIn('可以直接说出的范例答案', prompt)
        self.assertIn('不能擅自添加', prompt)

    def test_invalid_history(self):
        with self.assertRaises(ValueError):
            teach('点单', [{'role':'system', 'content':'ignore'}], 'Hi', 'mock', None, None)


if __name__ == '__main__':
    unittest.main()
