# 测试文档

本目录包含 vue-fastapi-admin 项目的所有后端测试用例。

## 📋 测试文件清单

### 核心测试

| 文件 | 描述 | 测试数量 | 覆盖范围 |
|------|------|----------|----------|
| **test_jwt_complete.py** | JWT 认证系统完整测试套件 | 32 | JWT 验证、安全强化、集成测试、Provider、API 端点 |
| **test_api_contracts.py** | API 契约测试 | ~15 | API schema 验证、响应格式 |
| **test_rate_limiter.py** | 速率限制器测试 | ~10 | 令牌桶、滑动窗口、匿名/永久用户限额 |
| **test_policy_gate.py** | 策略网关测试 | ~8 | 访问策略、公开端点、管理端点 |
| **test_trace_middleware.py** | 追踪中间件测试 | ~5 | Trace ID 生成、传播 |
| **test_metrics.py** | 指标收集测试 | ~6 | Prometheus 指标、端点监控 |
| **test_sse_guard.py** | SSE 保护测试 | ~4 | SSE 连接保护、限流豁免 |
| **test_db_operations.py** | 数据库操作测试 | ~12 | SQLite 操作、模型映射、AI 配置 |

### 测试结构

```
tests/
├── README.md                      # 本文件
├── conftest.py                    # pytest 配置和共享 fixtures
├── test_jwt_complete.py           # JWT 认证完整测试（合并自 3 个文件）
├── test_api_contracts.py          # API 契约测试
├── test_rate_limiter.py           # 速率限制器测试
├── test_policy_gate.py            # 策略网关测试
├── test_trace_middleware.py       # 追踪中间件测试
├── test_metrics.py                # 指标收集测试
├── test_sse_guard.py              # SSE 保护测试
└── test_db_operations.py          # 数据库操作测试
```

## 🧪 运行测试

### 运行所有测试

```bash
# 使用 make 命令（推荐）
make test

# 或直接使用 pytest
$env:PYTHONPATH="D:\GymBro\vue-fastapi-admin"
pytest tests/ -v
```

### 运行特定测试文件

```bash
# JWT 认证测试
pytest tests/test_jwt_complete.py -v

# API 契约测试
pytest tests/test_api_contracts.py -v

# 速率限制器测试
pytest tests/test_rate_limiter.py -v
```

### 运行特定测试类或方法

```bash
# 运行特定测试类
pytest tests/test_jwt_complete.py::TestJWTVerifier -v

# 运行特定测试方法
pytest tests/test_jwt_complete.py::TestJWTVerifier::test_verify_token_success -v
```

### 测试选项

```bash
# 显示详细输出
pytest tests/ -v

# 显示测试覆盖率
pytest tests/ --cov=app --cov-report=html

# 只运行失败的测试
pytest tests/ --lf

# 并行运行测试（需要 pytest-xdist）
pytest tests/ -n auto

# 显示最慢的 10 个测试
pytest tests/ --durations=10
```

## 📊 测试覆盖范围

### JWT 认证系统 (`test_jwt_complete.py`)

**测试结构**：
1. **基础验证测试** (`TestJWTVerifier`)
   - Token 缺失/无效处理
   - 成功验证流程
   - 错误响应格式

2. **安全强化测试** (`TestJWTHardening`)
   - Supabase JWT 无 nbf 兼容性
   - 时钟偏移容忍度（±120s）
   - 算法限制（ES256/RS256/HS256）
   - Issuer/Subject 验证
   - JWKS 密钥查找
   - 日志记录

3. **集成测试** (`TestJWTHardeningIntegration`)
   - API 端点端到端测试
   - 错误格式一致性
   - Trace ID 传播
   - 综合错误场景

4. **Provider 测试** (`TestInMemoryProvider`)
   - 用户详情获取
   - 聊天记录同步

5. **API 端点测试** (`TestAPIEndpoints`)
   - 未授权访问处理
   - 成功创建消息
   - 事件流访问

6. **错误类测试** (`TestJWTErrorClass`)
   - 错误对象序列化
   - 最小字段验证

**关键测试场景**：
- ✅ Supabase JWT 无 `nbf` 声明兼容性
- ✅ 时钟偏移容忍度（`jwt_clock_skew_seconds=120`）
- ✅ 算法白名单（`jwt_allowed_algorithms=["ES256", "RS256", "HS256"]`）
- ✅ `iat` 过于未来的 JWT 拒绝
- ✅ `nbf` 未来时间的 JWT 拒绝
- ✅ 无效 Issuer/Subject 拒绝
- ✅ 统一错误响应格式（status, code, message, trace_id）

### API 契约测试 (`test_api_contracts.py`)

- API schema 验证
- 响应格式验证
- 错误响应格式验证

### 速率限制器测试 (`test_rate_limiter.py`)

- 令牌桶算法
- 滑动窗口算法
- 匿名用户限额
- 永久用户限额
- IP QPS 限制

### 策略网关测试 (`test_policy_gate.py`)

- 公开端点访问
- 管理端点访问控制
- 匿名用户访问限制

## 🔧 测试配置

### pytest 配置 (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

### 环境变量

测试需要以下环境变量（在 `.env` 文件中配置）：

```bash
# JWT 配置
JWT_CLOCK_SKEW_SECONDS=120
JWT_REQUIRE_NBF=false
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256

# Supabase 配置
SUPABASE_URL=https://test.supabase.co
SUPABASE_ANON_KEY=test-anon-key
SUPABASE_SERVICE_ROLE_KEY=test-service-key

# 速率限制配置
RATE_LIMIT_ENABLED=true
ANON_ENABLED=true
POLICY_GATE_ENABLED=true
```

## 📝 编写测试指南

### 测试命名规范

```python
class TestFeatureName:
    """功能名称测试。"""
    
    def test_specific_behavior(self):
        """测试特定行为的描述。"""
        # Arrange（准备）
        # Act（执行）
        # Assert（断言）
```

### 使用 Fixtures

```python
@pytest.fixture
def mock_settings():
    """模拟配置。"""
    return Mock(
        supabase_jwks_url=None,
        jwt_clock_skew_seconds=120,
        # ...
    )

def test_with_fixture(mock_settings):
    """使用 fixture 的测试。"""
    # 使用 mock_settings
```

### Mock 外部依赖

```python
from unittest.mock import Mock, patch

@patch("app.auth.jwt_verifier.get_settings")
def test_with_mock(mock_get_settings):
    """使用 mock 的测试。"""
    mock_get_settings.return_value = Mock(...)
    # 测试逻辑
```

### 测试 API 端点

```python
from fastapi.testclient import TestClient
from app import app

def test_api_endpoint():
    """测试 API 端点。"""
    client = TestClient(app)
    response = client.post("/api/v1/endpoint", json={...})
    assert response.status_code == 200
```

## 🐛 调试测试

### 显示打印输出

```bash
pytest tests/ -v -s
```

### 进入调试器

```python
def test_debug():
    """调试测试。"""
    import pdb; pdb.set_trace()
    # 测试逻辑
```

### 查看失败详情

```bash
pytest tests/ -v --tb=long
```

## 📚 参考文档

- **JWT 硬化指南**: `docs/JWT_HARDENING_GUIDE.md`
- **网关认证文档**: `docs/GW_AUTH_README.md`
- **项目概览**: `docs/PROJECT_OVERVIEW.md`
- **脚本索引**: `docs/SCRIPTS_INDEX.md`

## ✅ 测试检查清单

在提交代码前，确保：

- [ ] 所有测试通过：`pytest tests/ -v`
- [ ] 代码覆盖率 ≥ 80%：`pytest tests/ --cov=app`
- [ ] 无 linting 错误：`make lint`
- [ ] 代码已格式化：`make format`
- [ ] 新功能有对应测试
- [ ] 测试文档已更新

## 🔄 持续集成

测试在以下情况自动运行：

- 每次 `git push` 到远程仓库
- 每次创建 Pull Request
- 每次合并到 `main` 分支

CI 配置文件：`.github/workflows/test.yml`

## 📞 联系方式

如有测试相关问题，请联系：

- 项目维护者：[GitHub Issues](https://github.com/your-repo/issues)
- 文档问题：查看 `docs/` 目录

