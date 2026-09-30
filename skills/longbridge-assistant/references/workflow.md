# 数据与分析约定

## 命令与输出

首版脚本在 macOS/Linux 运行，私有目录使用 0700、文件使用 0600。通用 Agent 安装不代表所有操作系统已通过运行核验。

collect.py 的默认输出根目录是 ~/.longbridge-assistant/，必须在 Git 仓库之外。可用 --output-root 改到明确的用户私有目录。采集器只输出状态与文件入口，原始 API 响应只在内存处理。

- account.json：只供渲染器读取的成交投影；没有账户标识、订单 ID 或成交 ID。
- analysis-input.json：公开 IPO 资料；没有持仓数量、成交量价、成本或资金。
- analysis.json：Agent 写入的简短公开内容分析，绑定本次采集版本。
- ipo-input.json、ipo-review/*.html：单只新股模式的公开资料与独立子页，不读取账户或改写每日简报。
- current/index.html、current/ipo/*.html：本地私有报告。
- previous/：最近一次报告，用于恢复；生成失败保留上次成功页面。

采集器针对 Longbridge CLI 0.28.0 的官方合同实现。其他版本先核对接口与日志行为再使用；版本不匹配时不会读取账户。

## 分析 JSON

~~~json
{
  "collection_generated_at": "逐字复制输入 generated_at",
  "analysed_at": "本次分析完成时间，ISO 8601 且带时区",
  "ipo": [
    {
      "symbol": "09998.HK",
      "conclusion": "资料不足",
      "evidence_status": {"valuation": "缺失", "competitiveness": "未核对", "red_flags": "未核对"},
      "core_gaps": ["未取得发行估值与可比口径"],
      "summary": "一句总体判断",
      "valuation": "适用指标、比较口径、时间及结论，或明确缺项",
      "competitiveness": "产品、客户、经营或行业竞争的事实及判断",
      "red_flags": "已核对的具体事实和范围，或未取得资料",
      "heat": "来源、日期与指标范围；预计倍数必须标成预计",
      "sources": [{"title": "来源名称", "url": "长桥提供的来源链接"}]
    }
  ]
}
~~~

只评估输入中存在的 IPO symbol。新股只需少量直接相关公开来源，通常搜索一次，必要时阅读两三篇报道；已有发行或业务资料可复用。写一句结论、两三条关键理由，简单说明发行估值是否明显偏高、公司是否有业务支撑、已知明显风险及认购热度。能取得粗略估值比较时使用；亏损不强算 PE，不以入场费代替公司估值。

详细财务缺项不自动判为资料不足。已知事实足以初筛时可以给偏谨慎或暂时跳过，并在 core_gaps 中列最重要的未知项；资料不足仅用于身份、发行或基本业务信息不足以形成有用判断。可以关注需要估值与业务的实际支持事实及来源，已知重大风险不得被热度抵消；不要求完整财报或把所有风险都核查完。evidence_status 按已核对 / 未核对 / 缺失填写，已核对只表示相关陈述的事实有来源，不能代表全面尽调；未知风险直接注明。渲染器对积极结论缺少估值/业务支持时降为偏谨慎，并保留缺口。

中签概率与获配后涨跌不同；本版不建立概率模型。费用、融资利息会影响净收益，只作简短提示，不设计融资金额或订单。

分析文件仅含新股公开分析，由 Agent 写在私有输出根目录，权限 0600；不写 Git 或外部服务。日常无相关事件板块、新闻精选任务或当前持仓读取。仓位操作以真实成交为准，不推断期初/期末仓位或开平仓含义。

来源可用输入中的发行资料 URL，或实际长桥插件 news_search/news_detail 返回的新闻 URL。新增新闻来源写 provider: Longbridge 和 time（带时区的实际发布时间），标题写原报道出处；只保留 id、标题、摘要、来源、时间、URL 等公开字段。新闻搜索响应可能为数组，按实际结构投影；不要把账户或申购记录混入模型。搜索结果不是发行人原文，判断中明确是公开报道。不得编造链接、事实或发布时间。资料时间采用采集时间及新闻/发行资料自身时间。沿用此前分析时必须说明沿用，并保留原时间。

## 当前接口合同与限制

插件复用、可选官方 Skill 与本地 CLI 连接步骤见 [安装与连接](setup.md)。--check-connection 只查询公开交易日历，输出状态并明确账户权限未核验；不会采集其他模块或改写报告/游标。官方基础 Skill 的通用资产读取和搜索回退不改变本助手范围。

- 成交优先 api.get /v3/trade/execution/all，start_at/end_at 为 Unix 秒字符串，page 从 1 开始；has_more=false 才认定分页完成。该接口支持当天与历史成交。
- 只有成交方向或币种缺失时才按成交的 order_id 查询 trade.order_detail，并校验订单和标的一致，仅保留 side/currency。
- 日历查询最近 28 天（每次不超过一个月），合并 trading_days 与 half_trading_days；时段用 quote.trading_session。为晨间报告保守等待标准盘后结束，不凭平日时段猜半日市特殊收市；夜盘归属未核验时不并入。
- 期权使用 quote.option_quote 的真实 contract_multiplier，必须大于零；lot_size 不代表乘数。
- 港股数字代码转 counter_id 时按官方规则去前导零，例如 09998.HK → ST/HK/9998。
- IPO subscriptions/wait-listing 使用官方 CLI 私有子进程并只保留 hk 投影。公开 detail 只用 /v1/ipo/profile 和 /v1/ipo/timeline，避免额外读取申购资格及持有信息。
- 未上市公司详细财务可能缺失，轻量初筛可结合长桥公开新闻。缺项直接说明，不把完整财务覆盖设为日常快评前提。

子进程使用白名单环境、私有 cwd 与空 .env，关闭 CLI 内容日志和 analytics，并排除 LONGBRIDGE_LOG_PATH/LONGPORT_LOG_PATH。0.28.0 仍会初始化默认日志文件，这不等于启用内容记录；不能声称完全阻止默认日志文件创建。

[CLI 0.28.0 源码](https://github.com/longbridge/longbridge-terminal/tree/2f0df27333769840b7b70ee64c41cdea4f4efb64)
· [完整成交分页](https://open.longbridge.com/docs/trade/execution/all_executions)
· [期权乘数](https://open.longbridge.com/docs/quote/pull/option-quote)

不调用 auth status 做预检：该命令还读取账户和结单。采集器直接启动 serve 并以超时/安全错误处理认证失败，不主动运行 auth login；SDK 在令牌临近过期时可能刷新或等待授权，由子进程超时终止。

尚未开始的 IPO 仅以已取得的 sub_date 开放时间排序；缺失时排后并写开放时间未提供，不能使用申购截止冒充开放时间。显示列表日期时标明是开放、券商截止还是上市日。
