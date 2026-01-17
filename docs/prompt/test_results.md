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

*注：gemini-pro/minimax 在 v5.0 测试时出现端点错误（非 prompt 问题）

## 当前版本 v6.0

**字符数**: 1500 bytes（较基线压缩 68%）

### 测试结果 (2026-01-17)

| 模型 | 状态 | 通过率 | 测试规格 | 备注 |
|------|------|--------|----------|------|
| grok | ✅ PASS | 3/3 (100%) | runs=3, turns=1 | grok-4-1-fast-reasoning |
| deepseek | ✅ PASS | 3/3 (100%) | runs=3, turns=1 | deepseek-reasoner |
| claude-sonnet | ✅ PASS | 3/3 (100%) | runs=3, turns=1 | claude-sonnet-4-5-thinking |

### 关键改进
1. **跨模型稳定**：deepseek / grok / claude-sonnet 结构校验稳定通过
2. **SERP 注释块稳定**：明确 `<final>` 内末尾三行无缩进格式
3. **避免重复标签**：禁止 ``` 代码块/复述模板，减少模型“粘贴示例”导致解析失败

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

---

## 端点可用性说明

已验证可用：
- deepseek：PASS（openai 端点）
- claude-sonnet：PASS（反重力 Anthropic Messages 端点）

未复测（需后续补齐）：
- gemini-pro / minimax
- gpt-5.2
- gemini-flash

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
├── test_results.md       # 本文档
└── CHANGELOG.md          # 变更日志
```
