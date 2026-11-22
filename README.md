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

## 第二版：目标驱动循环

阶段顺序：Goal（子目标与标准）→ Action（模型选择工具）→ Observe（Python 执行结果）→ Adjust（模型据结果调整）→ Goal。启动时先规划；每轮调整和下一子目标由一次独立 JSON 规划请求产生。原始用户目标始终保留在消息历史里，调整的是子目标。

工具新增 subtract、multiply、divide，保留 add。工具严格检查数字和参数；除零等错误作为观察返回模型，使其有机会修正。候选回答必须经过下一轮检查，才可退出。完成检查属于模型自评，不代表数学证明或独立验证。当前工具用浮点数，金额等精确十进制业务需进一步扩展。

```sh
python agent.py --model deepseek-flash --prompt '预算100元，买3件每件18元的商品，再付8元运费。请用工具分步计算总费用和余额，并检查是否超预算。'
```

验收：日志显示各阶段；工具证据包含商品费用54、总费用62、余额38；最终指出未超预算。工具调用可能合并在同一轮，具体安排由模型决定。

`--max-rounds 8` 设置最大轮数（1～20）。每轮最多一次规划请求和一次行动请求，每次行动最多8个工具调用，因此比第一版消耗更多 API token。最后一轮尚未通过完成检查时明确报未完成。默认不保存日志，避免自动把任务内容上传到 Git。

离线测试命令仍为 `python -m unittest -v`；覆盖四则运算、非法输入、除零后恢复、完成检查、轮数上限及截断响应。真实 API 验收需另外运行上面示例。

规划格式恢复：JSON 解析、字段校验或截断失败时最多重试2次，保留当前任务的工具观察，不重复执行工具；连续3次失败则明确停止。每轮规划请求因此最多3次，另加最多1次行动请求。程序退出后暂不支持断点恢复，重新启动会从原始任务开始。

## 双十一优惠 Agent（规则由用户提供）

本版支持固定购物车、单店单笔订单：商品单价及数量、固定运费、满减（一次或每满）、一张门槛券、满减与券是否叠加，以及券门槛按原价或满减后价格计算。多个满减规则互斥，多张券互斥；商品均参与优惠；优惠不抵扣运费。不支持拆单、跨店分配、凑单、折扣券、会员价、红包和支付优惠。示例是教学规则，不代表任何平台真实活动。

金额字符串以元为单位，最多两位小数，Python 内部以整数分计算。完整枚举所有允许组合（包括不用优惠），最低实付仅是在上述明确范围内的最优解。返回并列最优数量，列表最多展示10项。

无需 API 的确定性验算：

```sh
python shopping.py shopping.example.json
```

接入 Goal → Action → Observe → Adjust → Goal：

```sh
python agent.py --model deepseek-flash --shopping shopping.example.json --prompt '请计算这个购物车最大优惠，解释为什么不是使用面额最大的优惠券。'
```

优惠工具无可填写参数，只计算启动时提供的规则；模型不能通过工具参数改写优惠条件。验收应看到 optimize_discounts 工具结果，最低实付336.00元，优惠80.00元。此示例商品408元，满减后358元，满400减40券不达门槛；选择满300减30券，加8元运费实付336元。若 coupon_basis 改为 original，最低实付变为326元；若 stackable 改为 false，最低实付366元。

复制示例 JSON 后修改为自己的价格与规则；original 表示按原商品总额判断券门槛，after_reduction 表示按满减后的商品总额判断。具体以活动说明为准。不明确或不在支持范围内的规则，不应据此声称得到真实最低价。Agent 最终解释仍由模型生成，应与确定性工具结果核对。
