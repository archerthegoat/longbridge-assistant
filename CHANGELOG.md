# Changelog

## Unreleased

首版准备中：标准 Agent Skills 结构、通用安装文档、相关事件、账户成交展开明细和港股 IPO 简短初筛。实际功能和验证结果将在对应提交交付后记录。

- 已在开发分支交付完整 Skill：只读采集、私有离线 HTML、成交展开与独立 IPO 子页，代码提交 `efd9adcbf205ec7e6635a3966a447ca782b67cb3`。
- 新公开连接入口实际通过；Python 3.12.14 下真实账户采集完整，事件保留窗口覆盖不足提示，IPO 名单和日程完整。核心 IPO 估值/财务分析资料不足；实际安装、定时切换及人类验收待完成。

当前未创建发布 tag，未发布 GitHub Release。

- 明确首次初始化需同时安装官方 `longbridge` Skill 与助手，在同一 Agent 发现后验证 CLI 连接；采用显式流程，首次使用检查作为补充。
- 仅更新指定 Skill，避免官方批量重装清理 `longbridge-*` 时误删助手。
