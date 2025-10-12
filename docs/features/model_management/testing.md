# 模型管理测试记录

## 自动化
- `tests/test_model_mapping_service.py`：校验 Prompt 映射入库与 fallback 读写。
- `tests/test_jwt_test_service.py`：验证 JWT 模拟、并发压测摘要及 run 查询。
- `tests/test_ai_config_service_push.py`：覆盖 Supabase 推送覆盖/跳过逻辑、备份轮转与缺失项删除。
- 运行方式：`python -m pytest tests/test_model_mapping_service.py tests/test_jwt_test_service.py tests/test_ai_config_service_push.py`
  - （当前环境缺少 `pytest` 包，需安装后执行：`pip install pytest`。）

## 手工验证

### 系统首页路由测试（优先级：高）
1. **登录跳转测试**
   - 清除浏览器缓存和localStorage（Ctrl+Shift+Delete）
   - 访问 `http://localhost:3101/login`
   - 输入 `admin` / `123456` 登录
   - **预期**: 自动跳转到 `http://localhost:3101/dashboard`
   - **验证**: URL正确且页面显示Dashboard内容（非404）

2. **Dashboard首页验证**
   - **位置**: 左侧菜单最顶部
   - **图标**: mdi:view-dashboard-outline
   - **内容**: 显示系统统计、AI模块快速入口、模型统计
   - **跳转**: 可通过卡片跳转到模型目录/映射/JWT测试

3. **动态路由加载测试**
   - 打开浏览器Console（F12）
   - 登录后执行: `localStorage.getItem('token')`（应有值）
   - 刷新页面，观察Network面板 `/api/v1/base/usermenu` 请求
   - **预期**: 返回3个顶级菜单，Dashboard在第一个（order:0）
   - **验证**: 左侧菜单按order排序显示（Dashboard → AI模型管理 → 系统管理）

### AI模型管理测试
1. **模型概览（/ai/model-suite/dashboard）**
   - 访问AI模型管理下的"模型概览"，确认端点统计、映射统计展示正确。
   - 若存在默认端点，面板应展示默认端点名称及状态。
2. **模型目录**
   - 打开"模型目录"，确认列表加载、默认模型标记、候选模型数量展示。
   - 点击"设为默认" -> 后端返回 200，并刷新后显示新默认。
   - 点击"同步" -> 弹出对话框，可选择推送/拉取/双向及覆盖、删除选项；执行后提示成功并刷新。
   - 使用"全量同步"按钮，确认双向同步并保留备份文件。
3. **模型映射**
   - 新增 Prompt 映射：选择 Prompt、候选模型、默认模型 -> 保存成功并在表格展示。
   - 编辑映射修改默认模型 -> 保存后刷新映射列表，`ai_prompts.tools_json` 出现 `_model_mapping` 字段。
   - 利用"设为默认"按钮选择候选模型，确认默认值更新。
4. **JWT 对话模拟**
   - 选择 Prompt + 接口，输入消息执行 -> 返回 JWT token 与模型回复。
   - 并发压测（如 batch=10, concurrency=5）-> 摘要显示成功/失败统计；刷新 run 可查看 `ai_prompt_tests` 中对应记录，并能在模型下拉中选择端点候选模型。
5. **fallback 清理（可选）**
   - 检查 `storage/ai_runtime` 下生成 `model_mappings.json`、`jwt_runs.json`，确认内容与操作一致。

## 新增测试用例

### 模型映射服务测试 (`tests/test_model_mapping_service.py`)

#### 核心测试函数
| 函数名 | 测试场景 | 验证点 |
|--------|----------|--------|
| `test_list_mappings` | 映射列表查询与过滤 | 按 scope_type/scope_key 过滤,源标记(prompt/fallback) |
| `test_upsert_mapping` | 映射创建与更新 | Prompt 映射写入 tools_json,Fallback 映射写入 JSON |
| `test_activate_default` | 激活默认模型 | 默认模型切换,候选列表包含性 |
| `test_prompt_mapping_roundtrip` | Prompt 映射完整流程 | 写入→查询→验证 tools_json 结构 |
| `test_fallback_mapping` | Fallback 映射存储 | 独立 JSON 文件创建与数据一致性 |

#### 测试覆盖要点
- **Prompt 映射**: 验证 `ai_prompts.tools_json` 中 `__model_mapping` 字段写入
- **Fallback 映射**: 验证 `model_mappings.json` 文件生成
- **过滤查询**: 验证 scope_type/scope_key 组合过滤逻辑
- **激活默认**: 验证默认模型切换与候选模型验证
- **数据源标记**: 验证 source 字段 (prompt/fallback) 正确标识

### JWT 测试服务测试 (`tests/test_jwt_test_service.py`)

#### 核心测试函数
| 函数名 | 测试场景 | 验证点 |
|--------|----------|--------|
| `test_simulate_dialog_success` | 单次对话模拟成功 | JWT token 生成,latency_ms 返回 |
| `test_run_load_test` | 并发压测正常流程 | 成功/失败计数,测试详情记录 |
| `test_run_load_test_stop_on_error` | 遇错停止模式 | 失败后终止,状态标记 partial/failed |
| `test_get_run_summary` | 压测结果查询 | run_id 关联,测试样本检索 |

#### 测试覆盖要点
- **JWT 生成**: 验证 JWT token 包含用户信息与有效期
- **并发控制**: 验证 batch_size 与 concurrency 参数控制并发数
- **错误处理**: 验证 stop_on_error 开关对失败场景的控制
- **数据持久化**: 验证 `ai_prompt_tests` 表与 `jwt_runs.json` 同步写入
- **摘要统计**: 验证 success_count/failure_count/avg_latency 计算准确性
- **测试样本检索**: 验证通过 run_id 查询完整测试记录

### 运行测试
```bash
# 安装依赖
pip install pytest pytest-asyncio

# 运行所有模型管理测试
python -m pytest tests/test_model_mapping_service.py tests/test_jwt_test_service.py tests/test_ai_config_service_push.py -v

# 运行单个测试文件
python -m pytest tests/test_model_mapping_service.py -v

# 运行特定测试函数
python -m pytest tests/test_jwt_test_service.py::test_run_load_test -v
```
