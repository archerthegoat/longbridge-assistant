# 长桥助手 · Longbridge Assistant

每天看清账户金额、单日账户盈亏、当前持仓和上一交易日的买卖，以及有哪些港股新股可关注。一个标准 Agent Skill，输出私有、可离线阅读的 HTML。

## 当前状态

当前正式 v1.8：资产/现金统一 USD，显示与简报交易日一致的券商单日账户盈亏；持仓仅显示标的、数量和最新已完成常规盘收盘价，按绝对估算 USD 金额降序排列。参考长桥官网采用白灰与青绿色；成交时间、成本、逐仓盈亏及生成/快照/报价时间和数据合规说明不在前端展示。无相关事件；打新只做轻量公开搜索。

精确八文件与原任务提示词已获批准并应用，代码 `8d28175b43db8ac567bc19bb67432fef137b48d2` 已推送 `codex/longbridge-assistant`，安装副本一致。重用同字节候选代码的真实采集，正式渲染再次成功：金额、单日盈亏、持仓收盘价完整，排序已应用；标准 USOption 数量采用合约惯例推断，内部排序状态部分完成，未知金额排后。

原 automation-2 提示词已通过工具同步并读回 ACTIVE；时间继续每周二至周六上海 09:00，项目/cwd/模型保留。首次自动调度 PENDING。语法、源码复核、真实采集及离线结构/权限读回分别记录；测试未新增/未运行，浏览器本地 file 策略阻止视觉检查，人类验收 PENDING，22 项清单绑定本次代码与用例版本，旧结果保留。

CLI/插件 IPO 阶段差异仍未改映射，本次页面根据实际公开插件字段核实。Agent catalog 已列出助手；main 尚未合并 Skill，未发布 tag/Release。固定提交安装入口如下。本次私有 PNG 简报为单次本地数据排版导出，未增加定时图片输出契约。

## 安装与连接

安装本助手，使用现成 [skills CLI](https://github.com/vercel-labs/skills) 选择所用 Agent：

```bash
npx skills add archerthegoat/longbridge-assistant --skill longbridge-assistant --global
```

上面的简短命令在 main 交付 Skill 后使用。当前已交付的固定代码入口（安装器的该版本发现仍待核对）：

```bash
npx skills@1.7.0 add "https://github.com/archerthegoat/longbridge-assistant/tree/8d28175b43db8ac567bc19bb67432fef137b48d2/skills/longbridge-assistant" --skill longbridge-assistant --global
```

`--global` 为个人安装，省略为项目安装。Node/npm/npx 仅用于安装，无需发布自己的 npm 包。已核查安装器 1.7.0 要求 Node ≥22.20.0。无 Node 时下载仓库，把完整 `skills/longbridge-assistant` 放入 Agent 的 Skill 目录，保留相对结构。安装器支持范围与实际运行证据分开记录。

**已有授权 Longbridge 插件直接复用，无需另装官方基础 Skill，也无需重复授权。** 插件的公开新闻搜索已在本次实际调用成功。其他 Agent 可选参考 [官方基础 Skill](https://open.longbridge.com/skill) 设置长桥能力。

本版精确成交由 CLI 本地采集后直接渲染，避免经过模型；因此账户日报还需要 macOS/Linux、Python 3.10+、IANA 时区数据、Longbridge CLI 0.28.0 与有效 CLI 登录。插件与 CLI 的授权分别核实，已有连接直接复用。

```bash
# 仅未安装/未登录时按官方流程设置
brew install --cask longbridge/tap/longbridge-terminal
longbridge auth login

# 用实际安装目录替换 SKILL_DIR
python3 SKILL_DIR/scripts/collect.py --check-connection
```

公开日历检查不证明成交权限，正式采集分别确认。CLI 不可用时仍可做插件公开新股初筛，账户模块标未就绪；定时运行不自动安装、登录或修改 hook。凭据由长桥管理。

## 每日输出

1. **仓位操作简报与成交明细**：最近完成美股交易日，按标的分开显示买入、卖出、笔数和成交额，展开实际工具和逐笔数据；支持正股与期权。当前 v1.8 同一板块显示 USD 净资产、总现金、简报日账户盈亏和持仓三列，持仓按估算金额降序；展开明细隐藏成交时间。
2. **港股打新提示**：多只新股按阶段和关键日期排列，点击阅读简短子页。一句结论、两三条理由、估值粗判断/业务支撑/明显风险、热度参考，来源折叠。

结论为可以关注 / 偏谨慎 / 暂时跳过 / 资料不足。详细财务缺项不自动阻断初筛；不编上涨百分比，不承诺获利。这里只考虑短线参与。

本机任务每周二至周六 09:00（上海）；周六通常汇报美东周五，休市回退最近完成交易日。生成本地 HTML，网页不触发模型、联网采集或交易。

> 用长桥助手更新今天的仓位操作简报和打新提示。

## 隐私与更新

账户金额、持仓、盈亏与精确成交只写用户私有目录，默认 `~/.longbridge-assistant/`；输出 `current/index.html` 和 IPO 子页。目录 0700、文件 0600，Git 和通知不包含账户明细。当前 v1.8 不投影持仓成本或计算逐仓盈亏；账户单日盈亏仅接受与简报日匹配的券商 USD 汇总，不能冒称实时今日收益。排序估算只用于内部排序，不显示为账户实际市值。日常只读长桥数据，无下单或申购。

```bash
npx skills update longbridge-assistant --global
```

更新前保存私有输出，回退用旧固定提交。不要批量清理 `longbridge-*`。每日调度使用 Agent 自身能力；Skill 安装不自动建立任务。

## 文档

- [PRD 与验收标准](docs/PRD.md)
- [变更记录](CHANGELOG.md)
- [首版发布说明草稿](docs/release-notes/v0.1.0-rc.1.md)
