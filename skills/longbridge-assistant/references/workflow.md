# 数据与分析约定

## 命令与输出

首版脚本在 macOS/Linux 运行，私有目录使用 0700、文件使用 0600。通用 Agent 安装不代表所有操作系统已通过运行核验。

collect.py 的默认输出根目录是 ~/.longbridge-assistant/，必须在 Git 仓库之外。可用 --output-root 改到明确的用户私有目录。采集器只输出状态与文件入口，原始 API 响应只在内存处理。

- account.json：只供渲染器读取的USD账户金额、单日账户盈亏、证券持仓数量及收盘价与成交投影；没有账户标识、订单 ID 或成交 ID。
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

分析文件仅含新股公开分析，由 Agent 写在私有输出根目录，权限 0600；不写 Git 或外部服务。日常无相关事件板块或公司新闻精选任务；持仓只用于当前账户展示，不建立事件范围。仓位操作以真实成交为准，不推断期初/期末仓位或开平仓含义。

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

## 账户金额与持仓口径

请求 /v1/asset/account?currency=USD，仅接受返回 currency=USD 的 net_assets / total_cash。使用券商原始USD视图，不在本地换汇、不累加不同币种，不把现金称为购买力。空值保持缺失，有符号数保留。

/v1/asset/stock 仅投影标的、名称、数量和报价币种；不保留成本价，不计算或展示持仓盈亏。持仓列表不扩展独立基金持仓接口。

收盘价调用 quote.candlesticks，period=day、adjust=none；CLI 0.28.0 固定常规盘Intraday，返回 SDK Candlestick 数组。只接受 trade_session=Intraday、带时区时间戳、符合最新已核实完成交易日的当地日期，以及有限正 close。日线时间是开始时间，不能据此证明已收盘。用市场交易日历及常规时段结束后30分钟确定完成日期；US/HK/SG分别采用正确时区。当天半日市进入交易时段但特殊收市未核实，或其他市场/目标日期日线缺失时，不替代为实时价/前收盘价。

前端持仓表只有持仓、数量、最新收盘价三列；价格保留原币种与精度。快照时间、报价时间、数据状态和合规/技术说明不显示，内部仍保留 close_date、close_bar_time、as_of、模块状态与缺项原因。失败时仅显示相应金额/价格未提供，不伪造零或空仓。报告交易日、IPO申购截止/上市等业务日期照常展示；逐笔成交时间仅保留内部，不进入HTML。

[USD账户接口](https://open.longbridge.com/docs/trade/asset/account) · [常规盘日线](https://open.longbridge.com/docs/quote/pull/candlestick)

## 单日账户盈亏与金额排序

GET /v1/portfolio/profit-analysis-summary，仅请求简报交易日：start为该YYYY-MM-DD的UTC零点Unix秒，end=start+86399（官方日期参数转换合同）。只投影currency、sum_profit和返回期间；仅接受原始USD、有限有符号金额、返回start_date/end_date均等于简报日。空值/期间错配不显示零，不读取盈亏sublist/明细/流水。该字段是券商指定单日汇总，不称为实时今日收益、持仓浮盈或完整费后收益。

内部排序金额按abs(数量×已核实收盘价×乘数)估算；股票/ETF只接受已验证板块与币种，乘数1；USOption只用实际contract_multiplier，数量采用标准美股期权合约惯例，接口单位未明确声明的推断写sort_quantity_basis，sort_status为部分完成。USOptionS或其他未知工具估算缺失置后。非USD仅按 /v1/asset/exchange_rates 的实际average_rate转换排序：1 base=value other，other→base除、base→other乘；不展示或用于修改账户原生USD金额。缺价格/乘数/汇率置后，不充零。

视觉参考[长桥官网](https://longbridge.com/sg)：白色表面、浅灰底色、黑色正文与青绿色点缀。前端只显示金额、当日盈亏、持仓三列、无成交时间的成交明细和IPO；不出现数据合规、时间戳或技术状态。

[单日汇总合同](https://open.longbridge.com/docs/account/portfolio/profit-analysis-summary) · [汇率方向合同](https://open.longbridge.com/docs/account/portfolio/exchange-rates)
