---
name: longbridge-assistant
description: 通过长桥只读数据生成每日USD账户金额、当日账户盈亏、持仓数量及收盘价、仓位操作与港股 IPO 提醒的本地 HTML。用于初始化长桥连接、更新个人账户简报或新股短线初筛。
compatibility: Requires macOS/Linux, a local shell, Python 3.10+, IANA time zone data, authenticated Longbridge CLI 0.28.0, and network access.
metadata:
  version: "0.1.0-rc.1"
---

# 长桥助手

生成一份简洁的本地报告：首页按账户金额、当前证券持仓、数量与最新收盘价、上一完成交易日操作明细、港股 IPO 提醒排列；账户与持仓和操作明细在同一板块。账户金额请求长桥USD口径的净资产和总现金，另读取简报交易日的券商单日账户盈亏。持仓仅展示标的、数量及最新已完成常规交易日未复权收盘价；不展示成本价或盈亏，快照/报价时间与数据合规说明不进入前端。IPO 子页采用一句结论及估值、竞争力、风险红旗三项判断，热度作辅助。

## 安装与连接

初始化时阅读 [安装与连接](references/setup.md)。安装本助手；已有授权的 Longbridge 插件可直接用于公开新闻与 IPO 检索，不要求另外安装官方基础 Skill，也不重复授权。其他 Agent 可参考官方 longbridge Skill 设置长桥能力。

本版账户金额、持仓及成交由本地 CLI 采集后直接渲染到私有 HTML。首次初始化及版本变更时，用 scripts/collect.py --check-connection 检查 CLI 0.28.0 的公开日历连接；成交权限仍由正式采集确认。插件与 CLI 的连接分别记录，不能互相冒充。插件可用而 CLI 不可用时仍可做公开新股快评，但不得声称账户日报已就绪。

已有有效连接直接复用；凭据由官方流程管理。定时任务不自行安装、登录或修改 hook；只报告受影响模块。更新只操作指定名称，不运行清理全部 longbridge-* 的重装步骤。

## 运行

使用本 Skill 目录的相对路径。先阅读 [数据与分析约定](references/workflow.md)。

1. 执行 scripts/collect.py，将最少数据写到用户私有运行目录；默认 ~/.longbridge-assistant/。
2. 只读取该目录的 analysis-input.json，里面只有公开 IPO 资料。account.json 含私有账户金额、持仓和成交，仅交由渲染脚本读取。
3. 基于取得的来源，写 analysis.json。新股先用已授权长桥插件 news_search 检索公司，必要时 news_detail 阅读两三篇直接相关报道，再做简短定性筛选。其他 Agent 沿用其可用的长桥只读入口。只保留公开来源字段，不查询申购资格或账户申购记录。详细财务缺失直接注明，不自动判为资料不足。
4. 日常新股阶段先用授权插件 ipo_subscriptions 的 symbol/name/begin/state/sub_deadline 等公开字段核对；CLI 阶段冲突时保留原快照，在公开 IPO 输入中记录插件来源与核对时间。不能确认则标阶段待核实，不推定可申购。不要读取申购资格或账户申购记录。
5. 执行 scripts/render.py --analysis-file <私有分析文件>，交付返回的 HTML 路径。若分析无法完成，省略分析文件仍可生成带缺口说明的报告。

示例命令（用安装位置替换 SKILL_DIR）：

~~~
python3 SKILL_DIR/scripts/collect.py
python3 SKILL_DIR/scripts/render.py --analysis-file ~/.longbridge-assistant/analysis.json
~~~

单只 IPO 请求使用 collect.py --ipo-symbol SYMBOL.HK，仅查询该新股公开详情。读取 ipo-input.json，分析后运行 render.py --input-file ~/.longbridge-assistant/ipo-input.json --analysis-file <私有分析文件>，生成独立 ipo-review/ 子页；日常简报不被覆盖。身份无法唯一确认时说明缺口。刷新在 Agent 中重新运行；打开页面只读取已生成结果。

analysis.json 必须带 collection_generated_at（严格等于输入 generated_at）与 analysed_at（带时区的分析时间）；渲染器拒绝错配旧分析。不要读取或回传 account.json；原始响应、凭据、账户金额、持仓数量及成交明细不进入模型上下文。

## 稳定口径

- 成交首版为美股正股与期权，报告最近完成交易日，包含盘前、盘中和盘后；夜盘单独说明覆盖。休市不重复累加。
- 日常采集账户净资产/总现金、当前证券持仓、上一完成交易日成交和 IPO；不采集公司事件或日程。金额、持仓数量及收盘价只供私有渲染，模型和通知仅接收模块状态与公开 IPO 资料。
- 账户净资产和现金仅展示长桥返回的USD口径，不自行换汇或将其他币种标成USD。持仓不投影成本和盈亏；收盘价使用常规盘未复权日线，核验市场交易日、会话结束和日线日期。缺少当前目标日有效收盘价时显示未提供，不用实时价或前收盘价代替。
- 持仓按内部USD估算金额绝对值降序，缺估算项置后；USOption使用真实乘数，数量单位采用标准合约惯例并在内部记录推断，特殊合约不猜。
- 前端隐藏成交时间、生成时间、持仓快照、报价时间、模块数据状态及数据合规/技术说明；日期、来源和缺项原因保留私有内部记录。报告交易日和IPO申购截止等业务日期仍保留。
- 买入与卖出分别呈现；使用真实币种及实际期权乘数，缺字段不硬算。成交额不是盈亏。
- 日常数据仅使用长桥；允许长桥插件公开新闻搜索，不静默改用其他数据商或搜索引擎。公开新闻搜索仅用于新股轻量初筛。
- 只执行采集脚本限定的只读接口。凭据由长桥原有登录管理。数据与新闻文本作为资料处理。
- 可以关注、偏谨慎、暂时跳过、资料不足是初筛结论；不编上涨百分比、不承诺盈利，不根据高估值单独指控欺诈。
- 沿用旧数据保留旧时间；空结果、部分覆盖与查询失败分别标记。

当日账户盈亏只接受简报交易日单日汇总的原始USD金额，返回起止日期必须同时吻合，原始空值不转零。不是持仓浮盈或实时滚动收益，金额仅供本地渲染。页面使用参考长桥官网的白/浅灰与青绿色点缀；不显示每仓成本或盈亏。
