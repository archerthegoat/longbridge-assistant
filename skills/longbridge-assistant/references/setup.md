# 安装与连接

## 安装助手

使用标准 Agent Skills 安装器，选择所用 Agent 和安装范围：

```bash
npx skills add archerthegoat/longbridge-assistant --skill longbridge-assistant --global
```

--global 为个人安装，省略则为项目安装。main 尚无 Skill 时使用 README 的已核验固定提交入口。无需自建 npm 包；没有 Node 时下载仓库，将完整 skills/longbridge-assistant 文件夹放进 Agent 的 Skill 目录。核对当前 Agent 已发现助手，必要时按其机制重新加载。

## 长桥能力

- 已授权 Longbridge 插件：直接复用，公开 IPO/新闻查询成功即记录该插件对应能力可用；不要求另外安装官方基础 Skill，不重复登录。
- 其他 Agent：可选安装官方基础 Skill longbridge 作为连接设置参考。插件、官方基础 Skill 与本助手是不同组件；安装 Skill 不自动产生券商授权。
- 本版私有账户日报：仍使用 Longbridge CLI 0.28.0、Python 3.10+、IANA 时区数据及 macOS/Linux。此本地通道使账户金额、持仓与精确成交无需经过模型即可生成 HTML。已有 CLI 有效登录直接复用。

需要设置 CLI 时使用官方安装及登录流程：

```bash
brew install --cask longbridge/tap/longbridge-terminal
longbridge auth login
```

凭据不写入 Skill、HTML、Git、模型或日志。插件授权与 CLI 登录分别核实；有一个可用不能推断另一个可用。首次初始化及版本变化时，用实际安装路径替换 SKILL_DIR：

```bash
python3 SKILL_DIR/scripts/collect.py --check-connection
```

公开日历检查不读取成交或结单；账户权限由正式采集确认。不用 auth status 做预检。CLI 不可用时可继续用插件做公开新股快评，账户模块标未就绪。定时运行不自行安装、重新登录、删除副本或改 hook。

## 更新与范围

```bash
npx skills update longbridge-assistant --global
```

更新前保存私有输出，回退使用先前验证的固定提交。可选的官方基础 Skill 单独更新；不要批量清除 longbridge-*。Agent Skills 没有统一安装后 hook，首版使用显式初始化，不声称安装会自动授权。

账户采集仍按本助手限定的只读接口执行；公开研究可用长桥插件 news_search/news_detail。官方通用建议不扩大账户读取，只保留用户要求的USD净资产、USD总现金、简报单日账户盈亏、证券持仓数量与已完成常规盘收盘价，以及仅用于金额排序的必要乘数/汇率，不额外获取购买力、结单、流水或交易接口。原始金额、持仓数量及价格不进入模型。

[CLI 官方安装](https://open.longbridge.com/docs/cli/install) · [可选官方基础 Skill](https://github.com/longbridge/skills/tree/03c5fde151fb5e16d1ddd5088a06d299d9971eb8/skills/longbridge) · [Agent Skills 规范](https://agentskills.io/specification)
