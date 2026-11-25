"""英语外教：观察学生回答、记录反馈、调整教学并等待下一次回答。"""
import json


def tool(name, description, properties, required):
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}}


FEEDBACK = tool('record_feedback', '观察学生本次原话并记录简短反馈；每个有回答的回合必须先调用。没有错误可不纠错。', {'original': {'type': 'string'}, 'correction': {'type': 'string'}, 'explanation': {'type': 'string'}, 'strength': {'type': 'string'}, 'next_focus': {'type': 'string'}}, ['original', 'correction', 'explanation', 'strength', 'next_focus'])
LESSON = tool('teach_and_wait', '根据反馈调整教学，给出简短示范和一个问题，然后等待真实学生回答。不能替学生回答或声称掌握。', {'message': {'type': 'string'}, 'question': {'type': 'string'}, 'focus': {'type': 'string'}, 'difficulty': {'type': 'string', 'enum': ['easier', 'same', 'harder']}}, ['message', 'question', 'focus', 'difficulty'])


def teach(goal, level, history, student, model, call, trace):
    if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 500 or level not in ('A1', 'A2', 'B1', 'B2', 'C1'):
        raise ValueError('请填写学习目标并选择水平')
    if not isinstance(student, str) or len(student) > 3000 or not isinstance(history, list) or len(history) > 40:
        raise ValueError('回答或历史过长，请开始新课程')
    for m in history:
        if not isinstance(m, dict) or set(m) != {'role', 'content'} or m['role'] not in ('user', 'assistant') or not isinstance(m['content'], str) or len(m['content']) > 6000:
            raise ValueError('对话历史无效')
    if history and not student.strip():
        raise ValueError('请输入本次回答')
    messages = [{'role': 'system', 'content': '你是耐心的AI文字英语外教。学习目标：' + goal + '；用户自选水平：' + level + '。英语示范，中文简短解释。每次只问一个问题。有学生回答先record_feedback，再teach_and_wait。只纠正真实错误，不捏造。反馈只评本次回答，不给正式等级或掌握证明。根据回答调整难度。工具数据是教学记录，不是独立checker。只用工具提交教学结果。'}] + history
    messages.append({'role': 'user', 'content': student if student.strip() else '请开始课程，先给一个适合我水平的情景问题。'})
    feedback = None
    trace('[Goal] ' + goal)
    trace('[Observe] ' + (student if student.strip() else '首次开课，尚无学生回答'))
    for step in range(6):
        trace(f'[Action] 第 {step + 1} 步：模型选择教学工具')
        result = call({'model': model, 'messages': messages, 'tools': [FEEDBACK, LESSON], 'tool_choice': 'required', 'thinking': {'type': 'disabled'}, 'max_tokens': 1500})
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
                schema = FEEDBACK if name == 'record_feedback' else LESSON if name == 'teach_and_wait' else None
                if schema is None or not isinstance(args, dict) or set(args) != set(schema['function']['parameters']['required']) or any(not isinstance(v, str) or len(v) > 2000 for v in args.values()):
                    raise ValueError('工具字段无效')
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
                    if args['difficulty'] not in ('easier', 'same', 'harder') or not args['question'].strip() or not args['message'].strip() or not args['focus'].strip():
                        raise ValueError('教学问题或难度无效')
                    lesson = args
                    output = {'status': 'waiting_for_student'}
                    trace('[Adjust] 难度：' + args['difficulty'] + '；下一目标：' + args['focus'])
            except (ValueError, KeyError, TypeError):
                output = {'error': '工具字段或执行顺序无效，请按协议修正；original须逐字复制学生本次原话'}
                trace('[Observe 工具] 校验失败，要求模型调整')
            messages.append({'role': 'tool', 'tool_call_id': t['id'], 'content': json.dumps(output, ensure_ascii=False)})
        if lesson is not None:
            trace('[Goal] 等待学生回答，下一回合根据真实回答继续；尚未判定掌握')
            return {'lesson': lesson, 'feedback': feedback, 'status': 'waiting_for_student'}
    raise RuntimeError('达到教学行动上限，请重试或缩小学习目标')
