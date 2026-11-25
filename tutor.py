"""英语外教：观察学生回答、记录反馈、调整教学并等待下一次回答。"""
import json
from speaking_prompt import SPOKEN_STYLE, MATERIAL_STYLE

from pathlib import Path

# 只保存参考资料的主题与自行改写的聊天问题，不复制范文。
TOPICS = json.loads((Path(__file__).resolve().parent / 'topics.json').read_text())
CHAT_STARTERS = {item['title']: {'opening': item['opening'], 'follow_up': item['follow_up']} for item in TOPICS}


def tool(name, description, properties, required):
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}}


FEEDBACK = tool('record_feedback', '先检查本次原话的语法和句式错误，再进行克制润色。不得把风格建议说成语法错误；保留事实和语气，不能编造经历。', {k: {'type': 'string'} for k in ['original', 'grammar_check', 'sentence_check', 'suggested_answer', 'refinements', 'next_focus']}, ['original', 'grammar_check', 'sentence_check', 'suggested_answer', 'refinements', 'next_focus'])
LESSON = tool('teach_and_wait', '像朋友一样每次只问一个容易用一两句话回答的生活小问题，顺着用户刚说的细节自然追问；不重复Suggested answer，不替用户作答。', {k: {'type': 'string'} for k in ['message', 'question', 'focus', 'difficulty', 'answer_hint']}, ['message', 'question', 'focus', 'difficulty', 'answer_hint'])
LESSON['function']['parameters']['properties']['difficulty'] = {'type': 'string', 'enum': ['easier', 'same', 'harder'], 'description': '只能填这三个英文值之一；不是中文，也不是等级'}

CARD = tool('save_material_card', '把已提供的真实经历整理成待用户确认的复用卡片，未知写待补充；证据逐字引用用户原话。', {'title': {'type': 'string'}, 'story': {'type': 'string'}, 'reusable_phrases': {'type': 'array', 'items': {'type': 'string'}}, 'missing_details': {'type': 'array', 'items': {'type': 'string'}}, 'evidence': {'type': 'array', 'items': {'type': 'string'}}, 'practice_matches': {'type': 'array', 'items': {'type': 'object', 'properties': {'exam': {'type': 'string', 'enum': ['IELTS', 'TOEFL']}, 'question': {'type': 'string'}, 'connection': {'type': 'string'}}, 'required': ['exam', 'question', 'connection'], 'additionalProperties': False}}}, ['title', 'story', 'reusable_phrases', 'missing_details', 'evidence', 'practice_matches'])


def validate(args, schema):
    if not isinstance(args, dict) or set(args) != set(schema['function']['parameters']['required']):
        raise ValueError('工具字段无效')
    for key, spec in schema['function']['parameters']['properties'].items():
        value = args[key]
        if spec['type'] == 'string':
            if not isinstance(value, str) or len(value) > 4000:
                raise ValueError('文本字段无效')
        elif not isinstance(value, list) or len(value) > 12:
            raise ValueError('列表字段无效')
        elif key == 'practice_matches':
            for match in value:
                if not isinstance(match, dict) or set(match) != {'exam', 'question', 'connection'} or match['exam'] not in ('IELTS', 'TOEFL') or any(not isinstance(v, str) or not v.strip() or len(v)>1500 for v in match.values()):
                    raise ValueError('题目匹配格式无效')
        elif any(not isinstance(v, str) or not v.strip() or len(v)>2000 for v in value):
            raise ValueError('列表内容无效')


def teach(goal, history, student, model, call, trace, mode="conversation"):
    if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 500:
        raise ValueError('请填写学习目标')
    if not isinstance(student, str) or len(student) > 3000 or not isinstance(history, list) or len(history) > 40:
        raise ValueError('回答或历史过长，请开始新课程')
    for m in history:
        if not isinstance(m, dict) or set(m) != {'role', 'content'} or m['role'] not in ('user', 'assistant') or not isinstance(m['content'], str) or len(m['content']) > 6000:
            raise ValueError('对话历史无效')
    if mode not in ('conversation', 'card'):
        raise ValueError('请求模式无效')
    if mode == 'card' and not any(m['role'] == 'user' for m in history):
        raise ValueError('请先分享至少一段真实经历')
    if mode == 'conversation' and history and not student.strip():
        raise ValueError('请输入本次回答')
    system = ('你是英语口语素材挖掘教练。目标：' + goal + '。帮助没话说的用户从真实经历出发；先选一个小经历，再逐层追问人物时间地点、行动、困难转折、结果、感受和影响，一次只问一个问题。用户可中英文回答。不能虚构用户经历，不为凑素材追问敏感信息。'
              '有回答先record_feedback，明确区分语法错误、句式错误与风格微调；无错就明确说无错。Suggested answer只做subtle微调：更precise词汇、自然合并碎句（如合适的定语从句），保持原意与口语自然，不强行复杂化。中文回答可忠实翻译并说明非语法纠错。'
              '再teach_and_wait追问下一个真实细节，message只作简短内容引导，不重复问题或润色答案。首次直接问一个低压力经历问题，允许用户不知道。'
              '整理卡片时只用user消息作为事实来源，不把自己问的问题、润色里的新增内容当事实。story用第一人称自然英文口语，将已经知道的事实连成可直接说的素材，不写The user says、不写信息缺失或采访笔记；reusable_phrases只选取story中实际出现的原文片段供高亮，避免列出整篇正文；缺失事实不补写，在missing_details列出；evidence逐字引用用户。practice_matches给出IELTS或TOEFL的具体自拟口语练习题及素材适用方式，绝不声称真题、官方题库或当前考试题型。卡片为待用户确认草稿。只通过工具输出。')
    system += ('聊天方式：参考IELTS Part 1的熟悉生活话题，但不是考试。每轮只要一两句话，不要求完整故事、复杂句、解释多个原因或长篇回答。不要评分、计时、要求Describe或强行追问困难转折。先简短回应用户刚说的内容，再问一个小问题；问过的问题不要重复。'
               '用户说不知道时，给轻松的二选一或换话题；用户想换话题就跟随，不纠缠。Suggested answer通常一两句，不能为增加长度补事实。首次message说明一两句就好，后续不反复提醒。'
               '以下是自拟生活引导问题与可选追问。用户指定话题时优先选对应开场；已有回答则根据真实上下文灵活追问，不机械按题库轮询：' + json.dumps(CHAT_STARTERS, ensure_ascii=False))
    system += SPOKEN_STYLE
    if mode == 'card':
        system += MATERIAL_STYLE
    messages = [{'role': 'system', 'content': system}] + history
    messages.append({'role': 'user', 'content': '请整理目前已分享的经历为素材卡片，信息不足请列出待补充。' if mode == 'card' else student if student.strip() else '请像日常聊天一样先问一个简单的生活问题，我每次只回答一两句话。'})
    feedback = None
    trace('[Goal] ' + goal)
    trace('[Observe] ' + (student if student.strip() else '首次开课，尚无学生回答'))
    for step in range(6):
        trace(f'[Action] 第 {step + 1} 步：模型选择教学工具')
        result = call({'model': model, 'messages': messages, 'tools': [CARD] if mode == 'card' else [FEEDBACK, LESSON], 'tool_choice': {'type': 'function', 'function': {'name': 'save_material_card' if mode == 'card' else 'record_feedback' if student.strip() and feedback is None else 'teach_and_wait'}}, 'thinking': {'type': 'disabled'}, 'max_tokens': 3000})
        choice = result['choices'][0]
        message = choice['message']
        if choice.get('finish_reason') not in ('tool_calls', 'stop'):
            raise RuntimeError('教学响应不完整，请重试')
        messages.append(message)
        calls = message.get('tool_calls', [])
        if not calls or len(calls) > 4:
            raise RuntimeError('模型未按教学工具协议返回，请重试')
        lesson = None
        for t in calls:
            output = None
            try:
                name = t['function']['name']
                args = json.loads(t['function']['arguments'])
                schema = {'record_feedback': FEEDBACK, 'teach_and_wait': LESSON, 'save_material_card': CARD}.get(name)
                if schema is None or (mode == 'card') != (name == 'save_material_card'):
                    raise ValueError('工具无效')
                validate(args, schema)
                if name == 'save_material_card':
                    sources = [m['content'] for m in history if m['role'] == 'user']
                    if not args['title'].strip() or not args['story'].strip() or not args['evidence'] or not args['practice_matches'] or any(not any(q in source for source in sources) for q in args['evidence']):
                        raise ValueError('卡片缺少真实原话证据或题目映射')
                    if any(marker in args['story'].lower() for marker in ('the user says', 'the user mentioned', 'no further details', 'information is missing')):
                        raise ValueError('story须为可直接开口的第一人称范例，不能写用户摘要或缺失说明')
                    trace('[Observe] 范例原话引用校验通过；内容仍需用户确认')
                    return {'card': args, 'status': 'draft_for_confirmation'}
                if name == 'record_feedback':
                    if not student.strip() or args['original'] != student:
                        raise ValueError('original必须等于本次学生原话，不能虚构')
                    feedback = args
                    trace('[Observe 工具] 已记录本次回答的模型反馈')
                    trace('[Adjust] ' + args['next_focus'])
                    output = {'recorded': True, 'next_focus': args['next_focus']}
                else:
                    if student.strip() and feedback is None:
                        raise ValueError('必须先观察并记录学生反馈，再调整教学')
                    if args['difficulty'] not in ('easier', 'same', 'harder') or not args['question'].strip() or not args['focus'].strip() or not args['answer_hint'].strip():
                        raise ValueError('教学问题或难度无效')
                    if args['question'].count('?') + args['question'].count('？') > 1:
                        raise ValueError('每次只问一个小问题')
                    lesson = args
                    output = {'status': 'waiting_for_student'}
                    trace('[Adjust] 难度：' + args['difficulty'] + '；下一目标：' + args['focus'])
            except (ValueError, KeyError, TypeError) as error:
                reason = str(error) if isinstance(error, ValueError) else '工具 JSON 字段缺失或类型错误'
                output = {'error': reason, 'instruction': '按工具schema修正。difficulty只能是easier/same/harder；每次一个问题；original逐字复制用户原话。'}
                trace('[Observe 工具] 校验失败：' + reason)
            messages.append({'role': 'tool', 'tool_call_id': t['id'], 'content': json.dumps(output, ensure_ascii=False)})
        if lesson is not None:
            trace('[Goal] 等待学生回答，下一回合根据真实回答继续；尚未判定掌握')
            return {'lesson': lesson, 'feedback': feedback, 'status': 'waiting_for_student'}
    raise RuntimeError('达到教学行动上限，请重试或缩小学习目标')
