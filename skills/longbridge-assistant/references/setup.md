# 安装与连接

## 完整初始化

初始化完成需要：同一 Agent 可发现官方基础 Skill longbridge 与 longbridge-assistant，CLI 版本为已适配的 0.28.0，安全公开查询成功。当前 Agent 的 Skill 列表是发现依据；仅找到文件时仍需按该 Agent 的方式加载。安装器不会自动递归安装依赖或完成授权。

1. 使用标准安装器，两次选择同一个 Agent、同一种范围。已有同名官方 Skill 时先核对来源与发现结果后复用。

~~~bash
npx skills add longbridge/skills --skill longbridge --global
npx skills add archerthegoat/longbridge-assistant --skill longbridge-assistant --global
~~~

--global 为个人安装，省略则为项目安装。Node/npm/npx 只用于安装；无需发布自己的 npm 包。没有 Node 时下载两个仓库，将两个完整 Skill 文件夹放进同一 Agent 的发现目录，保留相对结构。

2. 按官方基础 Skill 的 references/setup.md 设置 CLI。脚本适配 Longbridge CLI 0.28.0；其他版本先核对接口和日志合同，不自动接受升级版本。macOS 的官方入口：

~~~bash
brew install --cask longbridge/tap/longbridge-terminal
longbridge auth login
~~~

已有有效登录时直接复用，不重复授权、不退出登录、不迁移凭据。需要授权时按官方流程由用户完成；凭据不写入 Skill、HTML、Git、模型输入或日志。MCP 与 CLI 的认证分别记录，已有 MCP 连接不能作为 CLI 已就绪的证据。

3. 用本助手的受控子进程验证连接，以实际安装目录替换 SKILL_DIR：

~~~bash
python3 SKILL_DIR/scripts/collect.py --check-connection
~~~

该模式只查询最近七天的公开美股交易日历，核对返回结构，不读取持仓、成交、IPO 或结单，不直接检查或回传认证文件，不改写每日报告和事件游标；保留受控私有临时目录、日志关闭及超时约束。不要使用 auth status 代替，该命令会额外读取账户和结单。

成功返回 connection_check=PASS、account_capability=NOT_CHECKED。账户、事件和 IPO 权限由正式采集分模块确认；不能把公开连接成功写成全部账户能力已就绪。失败只报告安全原因，先核对 CLI 版本、网络和官方连接说明，不自动重新登录。需要诊断时不把原始错误或账户响应输出到模型上下文。

## 首次使用与定时运行

首次使用和安装版本变更后重复上述发现与公开连接检查。初始化可以由一句用户请求启动：初始化长桥助手，同时安装官方 longbridge Skill，并验证连接。对每一步报告已完成或未完成；授权与当前环境权限规则继续适用。

已初始化的日常运行仍确认两个 Skill 在当前 Agent 可发现，并由采集器核对 CLI 版本及各模块读取状态。定时运行缺依赖时报告未就绪并停止，不自行安装、授权、删除副本或修改 hook。

采用显式初始化流程。Agent Skills 标准没有统一的安装后 hook 协议，核查的 skills 1.7.0 也没有可依赖的 postinstall hook。不要宣称仅安装助手就会自动安装官方依赖和完成登录。

## 固定版本、更新与范围

已核查官方基础 Skill 提交为 03c5fde151fb5e16d1ddd5088a06d299d9971eb8；需要复现时按 README 的具体提交安装。更新只选择精确名称：

~~~bash
npx skills update longbridge longbridge-assistant --global
~~~

不要运行清除 longbridge 或全部 longbridge-* 的批量重装脚本，它会包含本助手。更新后重新核对发现、CLI 兼容性和连接；保存私有输出，回退用先前已验证提交。

官方 Skill 提供基础能力与设置参考；本助手的只读采集器、单一长桥来源和最小数据范围继续约束日报。不要因官方通用建议额外读取余额、购买力、净值、盈亏、结单或下单接口，不使用 WebSearch/其他数据商填补资料。官方兄弟 Skill 不是本助手的必装项。

[官方 Skill 入口](https://open.longbridge.com/skill)
· [官方基础 Skill 固定来源](https://github.com/longbridge/skills/tree/03c5fde151fb5e16d1ddd5088a06d299d9971eb8/skills/longbridge)
· [CLI 官方设置](https://github.com/longbridge/skills/blob/03c5fde151fb5e16d1ddd5088a06d299d9971eb8/skills/longbridge/references/setup.md)
· [Agent Skills 规范](https://agentskills.io/specification)
