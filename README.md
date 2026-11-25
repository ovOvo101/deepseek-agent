# English Studio：Agent Loop 驱动的 AI 英语外教

文字对话外教，采用 DeepSeek API 和 Python 标准库，无第三方依赖。网页填写学习目标、自选水平及模型 ID，点击开始，再逐次回答外教问题。

## 启动

```sh
python3 -m venv .venv
source .venv/bin/activate
python configure_key.py
python server.py
```

浏览器打开 http://127.0.0.1:8765 。密钥配置一次，保存在仅当前账户可读写且被 Git 忽略的本地文件。勿分享此文件。API 会产生费用，课程目标和对话会发送至 DeepSeek。

## Agent loop

Goal：保持用户学习目标。Action：模型选择 record_feedback 或 teach_and_wait。Observe：Python 校验工具参数，检查反馈引用是否等于学生本次原话。Adjust：模型根据回答调整难度与教学重点。Goal：给出一个练习问题后暂停，等待真实学生回答，再进入下一回合。

有学生回答时必须先记录反馈，再给下一道练习；工具错误会交回模型修正，每回合最多6次模型请求。反馈是模型建议，没有独立checker；不保证语法评价绝对正确，不据一次回答声称用户已掌握。没有语音识别或发音评测。

网页显示真实后端阶段日志、聊天和纠错。课程只存在页面内存，刷新即清空；最多40条历史消息，每条有长度限制。服务只监听本机，不暴露目录和密钥。一次只允许一个任务。中断或关闭页面不一定取消已发出的 API 请求。

## 测试与验收

`python -m unittest -v` 使用模拟外部 API 验证工具顺序、输入校验、错误恢复、网页协议及原有优惠计算功能。真实验收：开课得到一个问题，输入英文回答，看到 record_feedback 反馈和下一问题及难度调整；每次均暂停等待用户。

旧版优惠功能仍保留在 agent.py、shopping.py 和 web/shopping.html，旧命令行及 /api/run 接口可用。当前网页首页已换为外教。模型 ID 通过账户 GET /models 实时核验，不假定旧版名称有效。
