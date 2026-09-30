# 长桥助手 · Longbridge Assistant

每天看清相关事件、上一交易日的成交，以及港股新股提醒。一个标准 Agent Skill，输出可离线阅读的本地 HTML。

## 当前状态

公开仓库已建立，当前为首版开发阶段。README、产品需求和发布说明已提供；Skill 全目录仍待精确差异批准。长桥 CLI 的公开交易日历连接已核验，真实账户、事件与 IPO 接入仍待分模块核验。

下面是正式交付后的推荐安装入口。只有仓库默认分支实际包含 Skill 后，该命令才可安装；任务分支验证使用明确提交 SHA，见下文。

## 安装

完整初始化包括两个 Skill 的安装与长桥连接验证。使用现成的 [skills CLI](https://github.com/vercel-labs/skills)，两次选择**同一个 Agent、同一种安装范围**：

```bash
npx skills add longbridge/skills --skill longbridge --global
npx skills add archerthegoat/longbridge-assistant --skill longbridge-assistant --global
```

第一条安装[长桥官方基础 Skill `longbridge`](https://open.longbridge.com/skill)，第二条安装长桥助手。两个命令都需要执行；安装器不会自动递归安装 Skill 依赖，也不会完成长桥登录。已有官方 Skill 时先核对来源和当前 Agent 是否可发现，避免重复安装。

`--global` 表示个人全局安装；省略时安装到当前项目。安装器支持 Codex、Claude Code、Cursor、Gemini CLI、GitHub Copilot、OpenCode 等。安装器支持范围与本项目实际运行核验分开记录。

安装器当前版本 `skills 1.7.0` 要求 Node.js ≥22.20.0；Node/npm/npx 仅用于安装。本项目无需单独发布或安装自己的 npm 包。[安装器版本要求](https://registry.npmjs.org/skills/latest)

无需 Node 时，也可分别下载两个仓库 ZIP，把官方 `skills/longbridge` 和本仓库 `skills/longbridge-assistant` 的完整文件夹放进同一个 Agent 支持的 Skill 目录；保留脚本、引用和模板的相对目录结构。之后仍需完成下方连接验证。

### 运行依赖

- 支持 Agent Skills、能执行本地命令的 Agent。
- 当前 Agent 可发现官方基础 Skill `longbridge` 与 `longbridge-assistant`。
- 首版脚本运行环境为 macOS / Linux，使用 POSIX 文件权限保护私有报告；其他系统尚未核验。
- Python 3.10+，使用标准库；系统提供 IANA 时区数据。缺少时区库的环境按 Python 官方说明安装 `tzdata`。
- Longbridge CLI 0.28.0 与用户已有有效登录；脚本按该版本接口核对，网络和数据权限由长桥提供。

macOS / Linux 的长桥官方安装与登录入口：

```bash
brew install --cask longbridge/tap/longbridge-terminal
longbridge auth login
```

其他系统参见[长桥 CLI 官方安装文档](https://open.longbridge.com/docs/cli/install)。已有有效登录时直接复用。凭据由官方登录流程管理，不复制到助手、HTML 或提示词。

### 验证连接，完成初始化

安装后确认当前 Agent 的 Skill 列表可发现两个名称；必要时按该 Agent 的方式重新加载会话。文件存在不等于已被发现。

再执行助手的安全连接检查，用实际安装位置替换 `SKILL_DIR`：

```bash
python3 SKILL_DIR/scripts/collect.py --check-connection
```

该入口核对 CLI 0.28.0，仅查询公开美股交易日历，返回连接状态；不读取持仓、成交或结单。成功表示 CLI 路径可连接，账户、事件和 IPO 权限仍由正式采集分模块确认。已有 MCP 连接不能替代 CLI 连接验证。

**初始化完成条件：** 同一 Agent 可发现两个 Skill，CLI 版本符合要求，安全公开查询成功。任一步缺失都报告“初始化未完成”。可以对 Agent 说：“初始化长桥助手，同时安装官方 longbridge Skill，并验证连接。”

首次使用也会检查这些前提；定时运行缺依赖时报告未就绪，不自行安装、重新登录或清理旧配置。采用这一通用流程：Agent Skills 标准未定义安装后 hook，核查的 skills 1.7.0 也没有可依赖的 postinstall hook。

官方 Skill 提供设置与基础能力参考；助手日报仍按自己的只读采集范围、单一来源与隐私约定执行，不扩展读取余额、资产或盈亏，不静默使用网页搜索补源。

### 固定版本与更新

安装前列出可发现的 Skill：

```bash
npx skills add longbridge/skills --skill longbridge --list
npx skills add archerthegoat/longbridge-assistant --list
```

固定版本验证时，将 `COMMIT_SHA` 替换为发布说明中的完整提交：

```bash
npx skills@1.7.0 add "https://github.com/longbridge/skills/tree/03c5fde151fb5e16d1ddd5088a06d299d9971eb8/skills/longbridge" --skill longbridge --global
npx skills@1.7.0 add "https://github.com/archerthegoat/longbridge-assistant/tree/COMMIT_SHA/skills/longbridge-assistant" --skill longbridge-assistant --global
```

更新时只选择这两个 Skill；需固定版本时使用上述具体提交入口。常规更新：

```bash
npx skills update longbridge longbridge-assistant --global
```

更新前阅读 [CHANGELOG](CHANGELOG.md)，保存私有输出；需要回退时重新安装先前已验证的固定提交。不要运行清除所有 `longbridge-*` 的批量重装步骤，这会包含 `longbridge-assistant`。

## 使用

安装后对你的 Agent 说：

> 用长桥助手更新今天的简报。

> 用长桥助手看一下这只港股新股，按估值、竞争力和明显风险做短线初筛。

首页的顺序是：

1. **相关事件**：当前持仓与上一完成交易日成交标的的相关公司事件。
2. **账户简报与成交明细**：按标的显示买入、卖出和成交额，展开查看实际工具及逐笔量价。
3. **港股 IPO 提醒**：多只新股按最近可操作截止时间排列，点进一屏左右的简短快评。

IPO 快评使用“可以关注 / 偏谨慎 / 暂时跳过 / 资料不足”四种定性结论。主要检查估值、竞争力及有来源的风险红旗，热度作为参考。

成交范围首版为美股正股与期权，IPO 为港股；各模块标明时间、覆盖与缺口。未查询成功的内容不能显示为零或没有事件。输出读取长桥数据，不进行下单或申购。

## 本地报告

账户量价和完整合约只保存在用户的私有本地目录，默认 `~/.longbridge-assistant/`，输出 `current/index.html` 和相应 IPO 子页。网页离线可读；打开页面不会访问券商凭据或触发模型调用。

仓库、样例和发布附件只保留合成数据。每日定时调用由所用 Agent 的调度能力配置；建议工作日早上运行，按交易日历读取最近完成的交易日。

## 文档与发布

- [产品需求与验收标准](docs/PRD.md)
- [变更记录](CHANGELOG.md)
- [首版发布说明草稿](docs/release-notes/v0.1.0-rc.1.md)

发布说明会列明已验证的代码提交、CLI 版本、安装器、Agent 环境及限制。演示运行、真实接入和人类验收分别记录。
