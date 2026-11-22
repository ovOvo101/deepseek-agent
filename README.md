# DeepSeek 原生 Python Agent 入门

要求：Python 3.10+，无第三方依赖。密钥不写进代码，不发到聊天，不提交 GitHub。

## 第一阶段：环境

macOS 终端进入本目录，运行 `python3 --version`。
创建环境：`python3 -m venv .venv`，激活：`source .venv/bin/activate`。
验收：能看到 Python 版本，环境创建成功。

## 第二阶段：验证真实模型

在 https://platform.deepseek.com/ 注册登录，在 API Keys 页面创建密钥。
运行 `python agent.py`，在隐藏提示中粘贴密钥并回车。密钥仅在当前进程内使用。
程序请求官方 GET https://api.deepseek.com/models，输出账户可用模型 ID。
验收：成功返回列表。文档中的名字只是参考，不能代替账户实际验证。

## 第三阶段：真实工具闭环

运行 `python agent.py --model 列表中的模型ID`，再次在隐藏提示中输入密钥。
验收：日志依次出现 add 工具调用、工具结果 579、第二轮请求与最终回答。模型支持工具调用还须通过本次请求验证；出现在列表里并不保证全部功能。
每次模型调用可能产生 API 费用，循环最多 8 轮。

Agent loop：模型决定调用工具 → Python 校验并执行 → 把结果交回模型 → 模型继续或结束。
Agent harness：支撑循环的运行环境，包括 API 客户端、消息历史、工具白名单、异常处理与轮数上限。本项目不使用 eval，也不开放终端执行工具。

## 第四阶段：测试

运行 `python -m unittest -v`。测试覆盖工具校验、消息回传和循环上限，使用模拟响应，不花费 API 费用。
验收：所有测试通过。模拟测试不代表真实 API 已成功。

## 第五阶段：GitHub

仓库是版本历史和文件的集合；commit 是一次保存，push 是上传。
在 GitHub 新建 Public 仓库 deepseek-agent，不预置 README。
本地依次运行：

```sh
git init
git add agent.py configure_key.py test_agent.py README.md .gitignore
git diff --cached
git commit -m "Build minimal Python agent"
git branch -M main
git remote add origin https://github.com/你的用户名/deepseek-agent.git
git push -u origin main
```

上传前检查暂存内容没有密钥。验收：退出登录后仍可打开仓库，并按 README 复现。

官方说明：https://api-docs.deepseek.com/api/list-models/ 和 https://api-docs.deepseek.com/guides/tool_calls/

## 一次配置密钥

运行 `python configure_key.py`，在隐藏提示中输入密钥。它以明文保存在项目内 `.local-key.json`，权限为 600，且已被 `.gitignore` 排除。不要分享此文件或将它强制加入 Git。环境变量 DEEPSEEK_API_KEY 优先于该文件；两者均无配置时才临时询问密钥。

更换密钥：重新运行配置脚本。删除保存的密钥：删除 `.local-key.json`。

## 已完成的实践验证

本项目在 macOS、Python 3.13.9 下通过三项离线测试。用户真实 API 验证返回 deepseek-flash 和 deepseek-v4-pro；其中 deepseek-flash 已完成加法工具闭环。模型列表会变化，运行时仍查询账户实际列表。

首次配置后可运行 `python agent.py --model deepseek-flash`。工具执行记录只显示本示例加法参数和结果，不显示认证密钥。
