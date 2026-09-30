# 数据与分析约定

## 命令与输出

首版脚本在 macOS/Linux 运行，私有目录使用 0700、文件使用 0600。通用 Agent 安装不代表所有操作系统已通过运行核验。

collect.py 的默认输出根目录是 ~/.longbridge-assistant/，必须在 Git 仓库之外。可用 --output-root 改到明确的用户私有目录。采集器只输出状态与文件入口，原始 API 响应只在内存处理。

- account.json：只供渲染器读取的成交投影；没有账户标识、订单 ID 或成交 ID。
- analysis-input.json：公开新闻、公司日程和 IPO 资料；没有持仓数量、成交量价、成本或资金。
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
  "events": [
    {"id": "来自 analysis-input 的事件 id", "summary": "一句事实摘要和直接关联说明", "importance": 1}
  ],
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

只引用输入中存在的事件 id 与 IPO symbol。建议对各只 IPO 都生成条目。无法取得同行、发行估值或核心业务事实时不能写可以关注。evidence_status 的每项使用 已核对 / 未核对 / 缺失。只有取得并核对估值、经营竞争力与所声明红旗范围的具体事实，才可标已核对；链接存在或一段公司简介不代表已核对。core_gaps 列出核心缺项，只有没有核心缺项时才为空。积极初筛要求三项均已核对、core_gaps为空、三项判断有内容及输入中可核对的发行资料来源；不得用热度补齐缺失的估值或竞争力依据。明确重大不利证据可以支持暂时跳过，同时保留其他缺口。结论不能替代申购决定。

中签概率与获配后涨跌不同；本版不建立概率模型。费用、融资利息会影响净收益，只作简短提示，不设计融资金额或订单。

events 数组显式为空表示已筛选但未选中重要事件；省略表示尚未完成精选。分析文件仅含公开内容，由 Agent 直接写在私有输出根目录中，不写 Git 或外部服务；随后将其文件权限设为 0600。

来源仅用输入中长桥提供的 URL。资料时间采用采集时间及各事件/发行资料自身时间。沿用此前分析时必须说明沿用，并保留原时间。

## 当前接口合同与限制

初始化的官方 Skill 依赖、同一 Agent 发现与连接步骤见 [安装与连接](setup.md)。--check-connection 只查询公开交易日历，输出状态并明确账户权限未核验；不会采集其他模块或改写报告/游标。官方基础 Skill 的通用资产读取和搜索回退不改变本助手范围。

- 成交优先 api.get /v3/trade/execution/all，start_at/end_at 为 Unix 秒字符串，page 从 1 开始；has_more=false 才认定分页完成。该接口支持当天与历史成交。
- 只有成交方向或币种缺失时才按成交的 order_id 查询 trade.order_detail，并校验订单和标的一致，仅保留 side/currency。
- 持仓用 trade.stock_positions 的 list/stock_info；仅保留事件范围需要的证券身份。
- 日历查询最近 28 天（每次不超过一个月），合并 trading_days 与 half_trading_days；时段用 quote.trading_session。为晨间报告保守等待标准盘后结束，不凭平日时段猜半日市特殊收市；夜盘归属未核验时不并入。
- 期权使用 quote.option_quote 的真实 contract_multiplier，必须大于零；lot_size 不代表乘数。
- 标的 news 是最近新闻接口；无法证明完整覆盖时标成部分完成，不能称完整历史检索。
- 公司日程先用长桥只读身份转换接口 POST /v1/quote/symbol-to-counter-ids 核对 ST/ETF 等证券身份；无法核验时标缺口。此 POST 仅转换公开证券身份，不改变账户。财经日历按单标的、单类型查询，并跟随 next_date；包含 report/financial、dividend、split/merge。日期或时区不完整时保留日期及缺口，不能猜精确时刻。
- 港股数字代码转 counter_id 时按官方规则去前导零，例如 09998.HK → ST/HK/9998。
- IPO subscriptions/wait-listing 使用官方 CLI 私有子进程并只保留 hk 投影。公开 detail 只用 /v1/ipo/profile 和 /v1/ipo/timeline，避免额外读取申购资格及持有信息。
- 未上市公司估值和财务覆盖仍需真实接入核验。profile 有字段不代表核心经营资料齐备。

子进程使用白名单环境、私有 cwd 与空 .env，关闭 CLI 内容日志和 analytics，并排除 LONGBRIDGE_LOG_PATH/LONGPORT_LOG_PATH。0.28.0 仍会初始化默认日志文件，这不等于启用内容记录；不能声称完全阻止默认日志文件创建。

[CLI 0.28.0 源码](https://github.com/longbridge/longbridge-terminal/tree/2f0df27333769840b7b70ee64c41cdea4f4efb64)
· [完整成交分页](https://open.longbridge.com/docs/trade/execution/all_executions)
· [期权乘数](https://open.longbridge.com/docs/quote/pull/option-quote)

不调用 auth status 做预检：该命令还读取账户和结单。采集器直接启动 serve 并以超时/安全错误处理认证失败，不主动运行 auth login；SDK 在令牌临近过期时可能刷新或等待授权，由子进程超时终止。

尚未开始的 IPO 仅以已取得的 sub_date 开放时间排序；缺失时排后并写开放时间未提供，不能使用申购截止冒充开放时间。显示列表日期时标明是开放、券商截止还是上市日。
