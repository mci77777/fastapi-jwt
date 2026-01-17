---
mode: plan
task: system-prompt-iteration-basic-message
created_at: "2026-01-17T12:31:14+08:00"
complexity: complex
---

# Plan: System Prompt 迭代优化（基础对话）

## Goal
- 压缩 `assets/prompts/serp_prompt.md` 字符量并改进结构，确保所有已配置映射模型输出严格匹配 `docs/ai预期响应结构.md`（ThinkingML v4.5 契约）
- 每个版本迭代产物存放到 `docs/prompt/` 目录，最低 5 个版本
- 逐模型测试验证，通过后才进入下一模型

## Scope
- **In**:
  - 创建 `docs/prompt/` 目录用于存放迭代版本
  - 压缩和优化 `serp_prompt.md`（减少字符、去冗余、强化结构约束）
  - 逐模型测试（xai → deepseek → 其他已配置模型）
  - 每个版本记录：版本号、字符数、测试结果、改进点
  - 最终确定的 prompt 更新回 `assets/prompts/serp_prompt.md`
- **Out**:
  - 不改动 `docs/ai预期响应结构.md`（它是契约 SSOT）
  - 不改动 `tool.md`（工具迭代在后续阶段）
  - 不使用 worktree

## Assumptions / Dependencies
- 后端服务运行中（`localhost:9999`）
- 映射模型已配置（xai、deepseek 等）
- 使用 `scripts/monitoring/real_ai_conversation_e2e.py` 或类似脚本进行测试

## Phases

### Phase 1: 环境准备与基线建立
1. 创建 `docs/prompt/` 目录
2. 复制当前 `serp_prompt.md` 为 `v1.0_baseline.md`
3. 统计基线字符数（当前约 2800+ 字符）
4. 运行基线测试，记录各模型通过率

### Phase 2: Prompt 压缩迭代（v2.0 ~ v3.0）
1. **v2.0**: 去除冗余说明和重复约束
   - 合并重叠规则
   - 移除过度解释
   - 目标：压缩 20%+ 字符
2. **v3.0**: 结构优化
   - 前置核心约束（标签白名单、顺序要求）
   - 后置示例和可选内容
   - 目标：进一步压缩 10%+

### Phase 3: 逐模型验证（v3.x 微调）
1. 针对 **xai** 模型测试 v3.0
   - 若失败：分析失败模式，微调为 v3.1
   - 若通过：进入下一模型
2. 针对 **deepseek** 模型测试
   - 若失败：微调为 v3.2
   - 若通过：进入下一模型
3. 依次测试其他已配置模型

### Phase 4: 最终版本确定（v4.0 ~ v5.0）
1. **v4.0**: 综合所有模型反馈的最小公约版本
2. **v5.0**: 最终生产版本（通过全部模型 100% 测试）
3. 更新 `assets/prompts/serp_prompt.md`
4. 更新 `standard_serp_v2.json` 版本号

### Phase 5: 文档与归档
1. 在 `docs/prompt/` 创建 `CHANGELOG.md` 记录迭代历史
2. 每个版本文件保留：`vX.Y_<描述>.md`
3. 记录字符压缩比和测试结果

## Tests & Verification
- 每个版本运行：`.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models <model> --runs 3 --turns 1`
- 验收标准：每个模型 100% PASS（结构校验通过）
- 最终验收：所有已配置模型 `--runs 5 --turns 2` 全部 PASS

## Issue CSV
- Path: `issues/2026-01-17_12-31-14-system-prompt-iteration-basic-message.csv`

## Tools / MCP
- `feedback:codebase-retrieval`：定位 prompt 注入点和测试脚本
- Bash：运行 E2E 测试脚本
- Read/Write：创建和编辑 prompt 版本文件

## Acceptance Checklist
- [ ] `docs/prompt/` 目录创建并包含 ≥5 个版本文件
- [ ] 最终版本字符数较基线压缩 ≥20%
- [ ] xai 模型 100% PASS
- [ ] deepseek 模型 100% PASS
- [ ] 其他已配置模型 100% PASS
- [ ] `assets/prompts/serp_prompt.md` 更新为最终版本
- [ ] `docs/prompt/CHANGELOG.md` 记录完整迭代历史

## Risks / Blockers
- 模型差异：不同模型对 prompt 敏感度不同，可能需要折中方案
- 过度压缩：可能导致约束不足，模型输出不稳定
- API 限流：频繁测试可能触发上游限流

## Rollback / Recovery
- 每个版本独立存档，可随时回退
- `git revert` 恢复 `assets/prompts/serp_prompt.md`

## Checkpoints
- Commit after: Phase 1 完成（基线建立）
- Commit after: Phase 3 完成（逐模型验证通过）
- Commit after: Phase 5 完成（文档归档）

## References
- `docs/ai预期响应结构.md`
- `assets/prompts/serp_prompt.md`
- `assets/prompts/standard_serp_v2.json`
- `scripts/monitoring/real_ai_conversation_e2e.py`
- `plan/2026-01-08_12-05-59-xai-deepseek-thinkingml-e2e-prompt-tuning.md`
