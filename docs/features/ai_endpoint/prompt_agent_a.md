# Agent-A 开发任务总提示

## 背景
- 项目目标：实现 GymBro AI Endpoint（参照 `docs/features/ai_endpoint/plan.md`）。
- 你是执行开发的主力 Agent，需严格遵循监管人提供的规划与进度规范。

## 行动要求
1. 启动前先阅读：
   - `docs/features/ai_endpoint/plan.md`
   - `docs/features/ai_endpoint/progress.md`
2. 每个阶段任务完成后，在 `progress.md` 的“周期记录”中追加条目，并按“汇报模板”提交你的阶段小结。
3. 遵循 YAGNI / KISS / DRY 原则，禁止引入超范围功能。
4. 代码变更需包含：
   - 配套单元测试（若涉及后端逻辑）。
   - 文档更新（若接口或配置发生变化）。
5. 如遇阻塞或不确定事项，在汇报中标注“遇到问题”并等待监管审批。

## 验收条件
- 阶段交付物须对应 `plan.md` 中列出的 Phase 任务。
- 提交代码前自查：Lint、测试、文档同步。
- 监管人会根据 `progress.md` 条目进行审核与反馈。

## 注意
- 所有汇报与提交均使用中文。
- 不得修改 `progress.md` 中非自身汇报区块的内容；如需调整，先向监管人申请。
- 保持文件编码为 UTF-8，避免引入非 ASCII 字符（除中文描述外）。
