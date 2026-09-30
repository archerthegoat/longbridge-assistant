# 长桥助手 · Longbridge Assistant

每天看清相关事件、上一交易日的成交，以及港股新股提醒。一个标准 Agent Skill，输出可离线阅读的本地 HTML。

## 当前状态

公开仓库已建立，当前为首版开发阶段。README、产品需求和发布说明已提供；Skill 全目录仍待精确差异批准，真实长桥接入尚未完成。

下面是正式交付后的推荐安装入口。只有仓库默认分支实际包含 Skill 后，该命令才可安装；任务分支验证使用明确提交 SHA，见下文。

## 安装

使用现成的 [skills CLI](https://github.com/vercel-labs/skills)，交互选择你使用的 Agent：

```bash
npx skills add archerthegoat/longbridge-assistant --skill longbridge-assistant --global
```

`--global` 表示个人全局安装；省略时安装到当前项目。安装器支持 Codex、Claude Code、Cursor、Gemini CLI、GitHub Copilot、OpenCode 等。安装器支持范围与本项目实际运行核验分开记录。

安装器当前版本 `skills 1.7.0` 要求 Node.js ≥22.20.0；Node/npm/npx 仅用于安装。本项目无需单独发布或安装自己的 npm 包。[安装器版本要求](https://registry.npmjs.org/skills/latest)

无需 Node 时，也可下载仓库 ZIP，把完整的 `skills/longbridge-assistant` 文件夹放进你的 Agent 支持的 Skill 目录；保留脚本、引用和模板的相对目录结构。

### 运行依赖

- 支持 Agent Skills、能执行本地命令的 Agent。
- 首版脚本运行环境为 macOS / Linux，使用 POSIX 文件权限保护私有报告；其他系统尚未核验。
- Python 3.10+，使用标准库；系统提供 IANA 时区数据。缺少时区库的环境按 Python 官方说明安装 `tzdata`。
- Longbridge CLI 0.28.0 与用户已有有效登录；脚本按该版本接口核对，网络和数据权限由长桥提供。

macOS / Linux 的长桥官方安装与登录入口：

```bash
brew install --cask longbridge/tap/longbridge-terminal
longbridge auth login
```

其他系统参见[长桥 CLI 官方安装文档](https://open.longbridge.com/docs/cli/install)。Skill 使用 CLI 读取数据；无需另装长桥 Skill 或某个 Agent 专属插件。

### 固定版本与更新

安装前列出可发现的 Skill：

```bash
npx skills add archerthegoat/longbridge-assistant --list
```

固定版本验证时，将 `COMMIT_SHA` 替换为发布说明中的完整提交：

```bash
npx skills@1.7.0 add "https://github.com/archerthegoat/longbridge-assistant/tree/COMMIT_SHA/skills/longbridge-assistant" --skill longbridge-assistant --global
```

常规更新：

```bash
npx skills update longbridge-assistant --global
```

更新前阅读 [CHANGELOG](CHANGELOG.md)，保存私有输出；需要回退时重新安装先前已验证的固定提交。

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
