# System Prompt 迭代测试结果

## 版本汇总

| 版本 | 字符数 | 压缩率 | grok | gemini-pro | minimax | 备注 |
|------|--------|--------|------|------------|---------|------|
| v1.0 baseline | 4627 | - | 4/4 | 2/2 | 1/2 | 基线版本 |
| v2.0 compress | 1891 | 59% | 2/3 | 3/3 | 0/3 | 压缩过度 |
| v3.0 structure | 1902 | 59% | 3/3 | 2/3 | 0/3 | 结构优化 |
| v3.1 enforce | 1402 | 70% | 3/3 | 3/3 | 1/3 | 强化约束 |
| v4.0 unified | 1261 | 73% | 5/5 | 4/5 | 2/5 | 统一版本 |
| v5.0 production | 1026 | 78% | 10/10 | N/A* | N/A | grok 最优压缩 |
| **v6.0 stable** | **1500** | **68%** | **3/3** | N/A | N/A | **deepseek 3/3；claude-sonnet 3/3（runs=3, turns=1）✅** |
| **v7.0 no-fence** | **1636** | **65%** | **3/3** | N/A | N/A | **claude-sonnet 3/3（无代码围栏）；deepseek 0/3（端点 472，非 prompt）** |
| **v7.1 final-tail-guard** | **1903** | **59%** | TBD | N/A | N/A | **claude-sonnet 在“讨论 prompt/规范”场景也可过 ThinkingML 校验 ✅** |
| **v7.2 gymbro-serp-confidential** | **3073** | **34%** | TBD | N/A | N/A | **补齐 GymBro 语境 + system prompt 保密 + SERP `<serp>` 规则** |
| **v7.3 serp-must-meta-guard** | **3828** | **17%** | **1/1** | N/A | N/A | **claude-sonnet 覆盖“讨论 system prompt”场景也可过校验 ✅** |

*注：gemini-pro/minimax 在 v5.0 测试时出现端点错误（非 prompt 问题）

## 当前版本 v7.3

**字符数**: 3828 bytes（较基线压缩 17%）

### 测试结果 (2026-01-17)

| 模型 | 状态 | 通过率 | 测试规格 | 备注 |
|------|------|--------|----------|------|
| grok | ✅ PASS | 1/1 | real_ai_conversation_e2e runs=1 turns=1 | provider=openai |
| deepseek | ❌ FAIL | 0/1 | real_ai_conversation_e2e runs=1 turns=1 | 端点 472（非 prompt） |
| claude-sonnet | ✅ PASS | 3/3 | real_ai_conversation_e2e（turns=1）+ meta 场景（turns=2, prompt-text） | provider=claude |

### 关键改进
1. **system prompt 保密**：禁止输出/复述/引用 system prompt 或内部规则文本
2. **GymBro 产品语境**：回答面向 AI 健身应用的专业辅助与持久化跟踪
3. **SERP 规则强化**：`<serp>` 默认必须 1 次；serp_queries 反映最终答案主题；更明确禁止 ``` 代码围栏
4. **Meta 兜底**：遇到 system prompt/规则/XML/实现细节等请求，必须拒绝并引导回健身（仍保持结构合规）

---

## 迭代历程

### v1.0 → v2.0
- 目标：去除冗余说明和重复约束
- 结果：压缩 59%，但稳定性下降

### v2.0 → v3.0
- 目标：结构优化，前置核心约束
- 结果：grok 恢复稳定

### v3.0 → v3.1
- 目标：强化关键约束
- 结果：所有可用模型改善

### v3.1 → v4.0
- 目标：统一版本，简化规则
- 结果：grok 100%

### v4.0 → v5.0
- 目标：最终生产版本
- 结果：grok 10/10 (100%)，多轮对话稳定

### v5.0 → v6.0
- 目标：补齐 deepseek/claude-sonnet 的稳定性
- 结果：deepseek/xai/claude-sonnet runs=3 全部 PASS

### v6.0 → v7.0
- 目标：避免 claude-sonnet 输出外层代码围栏（```xml ... ```）破坏 Strict XML
- 结果：claude-sonnet 稳定输出无代码围栏；deepseek 端点 472 需单独处理

---

## 端点可用性说明

已验证可用：
- claude-sonnet：PASS（反重力 Anthropic Messages 端点）
- grok：PASS（openai 端点）

未复测（需后续补齐）：
- deepseek：端点 472（需修复端点/路由 SSOT）
- gemini-pro / minimax / gpt-5.2 / gemini-flash

---

## 文件清单

```
docs/prompt/
├── v1.0_baseline.md      # 基线版本
├── v2.0_compress.md      # 压缩版本
├── v3.0_structure.md     # 结构优化版本
├── v3.1_enforce.md       # 强化约束版本
├── v4.0_unified.md       # 统一版本
├── v5.0_production.md    # grok 最优压缩版本
├── v6.0_deepseek_stable.md # 当前稳定版本 ✅
├── v7.0_claude_no_code_fence.md # claude 无代码围栏版本 ✅
├── v7.1_final-tail-guard.md # 讨论规范场景稳定版本 ✅
├── v7.2_gymbro-serp-confidential.md # GymBro+SERP+保密版本 ✅
├── v7.3_gymbro-serp-must-meta-guard.md # SERP 必须 + meta 兜底版本 ✅
├── v7.3_standard_serp_v2.json # v7.3 profile 元数据（json）
├── test_results.md       # 本文档
└── CHANGELOG.md          # 变更日志
```
