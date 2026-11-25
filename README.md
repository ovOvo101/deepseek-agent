# English Studio

**从轻松聊天开始，把你的真实经历变成能直接说出口的英语。**

想练口语，却不知道聊什么？English Studio 每次只问一个生活中的小问题。你回答一两句话，它会顺着你的经历继续聊，在旁边逐步整理一份属于你的口语范例。

适合希望积累个人口语素材、练习日常表达，或为 IELTS / TOEFL 口语练习寻找内容的人。

## 你可以做什么

- **从熟悉的话题开始。** 打开网页就有开场问题，也可选择住处、工作学习、食物、音乐、周末等话题。
- **像聊天一样练习。** 每次回答一两句话即可。没思路时可以用中文求助，或直接说“换个话题”。
- **得到克制的语言反馈。** 展开“本轮语言反馈与微调”，查看语法、句式检查和建议表达。对话区只保留回应与追问。
- **使用新问题的回答提示。** 输入框中的浅色英文是回答当前问题的句型支架；方括号里的内容由你自己填写。参考文字不会自动发送。
- **实时形成口语范例。** 右侧草稿将已聊到的信息组织成第一人称答案，可点击标题收起或展开。
- **发现可复用表达。** 草稿内多色高亮可迁移到其他话题的短语，颜色不代表分数或等级。
- **直接修改草稿。** 可以在正文里增删、修改。手动编辑后，后续自动更新会保留你的正文。

只有当你继续分享购买地点、喜欢的原因或一次具体经历，答案才会进一步丰富。它不会为了把段落写长，替你编造一家店或一个故事。生成内容仍请你核对。

## 开始使用

需要 **Python 3.10 或以上版本**、现代浏览器，以及一个可用的 **API Key**。项目仅使用 Python 标准库，不需要安装第三方 Python 包。

以下命令适用于 macOS / Linux。

### 1. 下载项目并创建环境

```sh
git clone https://github.com/ovOvo101/deepseek-agent.git
cd deepseek-agent
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 配置一次密钥

推荐使用 [DeepSeek 开放平台](https://platform.deepseek.com/)创建 API Key，然后运行：

```sh
python configure_key.py
```

在终端提示中粘贴密钥并回车。输入不会显示。密钥保存在本机 `.local-key.json`，文件仅当前账户可读写，且已排除 Git 上传。不要将密钥或此文件发给别人。

若已设置 `DEEPSEEK_API_KEY` 环境变量，服务会优先使用它。更换本地密钥时，重新运行配置脚本即可。

### 3. 启动网页

```sh
python server.py
```

打开 **[http://127.0.0.1:8765](http://127.0.0.1:8765)**。

直接回答页面上的开场问题，点击“发送回答”。模型栏预填 `deepseek-flash`；若你的账户不支持该模型，请改为账户实际可用的模型 ID。后端会通过 DeepSeek 模型列表接口核验，不保证预填名称始终有效。

不要直接双击 HTML 文件，网页需要本机服务。终端保持运行；结束使用时按 `Ctrl+C` 停止服务。

### 下次使用

无需重复配置密钥：

```sh
cd deepseek-agent
source .venv/bin/activate
python server.py
```

## 数据与使用费用

- 网页服务仅监听本机 `127.0.0.1`，不提供公网访问或多人账户。
- 密钥在 Python 后端读取，不返回浏览器；服务也不提供项目目录或密钥文件下载。
- 学习目标、当前回答与必要对话历史会发送至 DeepSeek。不要输入不愿发送给该服务的私人信息。
- 每轮包含语言反馈、追问和素材整理，通常需要多次模型请求，因此会产生 API 用量，也可能需要等待一段时间。
- 初始生活问题来自本地自拟题库，不消耗 API。刷新或关闭页面不保证取消已经发送的模型请求。
- AI 的纠错、润色和素材整理可能出错，请以你的真实经历为准。当前是文字练习，不支持语音输入、发音评测或正式考试评分。


## 开发与测试

```sh
python -m unittest -v
```

测试使用模拟 API，不消耗真实模型用量，覆盖反馈顺序、参数校验、错误恢复、素材原话引用、网页接口和文件访问边界。通过测试不等于真实模型在所有输入下均能正确教学。

```text
server.py           本机网页服务
api.py              DeepSeek API 客户端
tutor.py            对话与素材整理的工具循环
speaking_prompt.py  自然口语及范例生成规则
configure_key.py    本地密钥配置
web/index.html      聊天与实时素材网页
test_tutor.py       教学和素材工具测试
test_server.py      网页接口集成测试
```

## 教学设计参考

口语表达以自然沟通为目标，接受上下文清楚的省略与短回答，适当使用缩写，不为“高级”而强行扩写。

- [Cambridge：Ellipsis](https://dictionary.cambridge.org/grammar/british-grammar/ellipsis)
- [Cambridge：Contractions](https://dictionary.cambridge.org/grammar/british-grammar/contractions)
- [British Council：Short forms](https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/short-forms)
- [IDP IELTS：Speaking Part 1](https://ielts.idp.com/prepare/article-ielts-speaking-test-part-1/)

