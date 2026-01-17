# Testing Policy

> vue-fastapi-admin 项目的测试策略和验收标准

## 测试层级

```
┌─────────────────────────────────────────────────┐
│                  E2E / 冒烟测试                  │  ← 生产就绪验证
├─────────────────────────────────────────────────┤
│                  集成测试                        │  ← API 契约验证
├─────────────────────────────────────────────────┤
│                  单元测试                        │  ← 函数/类级别
└─────────────────────────────────────────────────┘
```

## 测试命令速查

| 测试类型 | 命令 | 说明 |
|----------|------|------|
| 全量测试 | `make test` | 运行所有 pytest 测试 |
| JWT 测试 | `pytest tests/test_jwt_*.py -v` | JWT 认证相关 |
| API 契约 | `pytest tests/test_api_contracts.py -v` | API schema 验证 |
| 冒烟测试 | `python scripts/smoke_test.py` | 端到端流程验证 |
| 健康检查 | `curl http://localhost:9999/api/v1/healthz` | 服务存活检查 |
| 代码检查 | `make lint` | ruff 静态分析 |

---

## 验收底线（必须通过）

### 1. 构建/启动成功

```bash
# 后端启动无错误
python run.py
# 预期：服务在 :9999 启动，无异常日志

# 健康检查通过
curl http://localhost:9999/api/v1/healthz
# 预期：返回 200 {"status": "healthy", ...}
```

### 2. 测试通过

```bash
# 全量测试
make test
# 预期：所有测试 PASSED，无 FAILED 或 ERROR
```

### 3. Lint 通过

```bash
make lint
# 预期：无错误输出
```

---

## 测试场景分类

### JWT 认证测试

**文件**: `tests/test_jwt_auth.py`, `tests/test_jwt_hardening.py`

| 场景 | 测试点 | 预期结果 |
|------|--------|----------|
| 有效 token | 正确签名的 JWT | 认证成功，返回用户信息 |
| 过期 token | `exp` 已过期 | 401 + `token_expired` |
| 时钟偏移 | `exp` 在容忍范围内 | 认证成功（±120s） |
| 无 nbf | Supabase token 缺少 nbf | 认证成功（`JWT_REQUIRE_NBF=false`） |
| 错误算法 | 非允许的签名算法 | 401 + `invalid_token` |
| 匿名用户 | `user_type=anonymous` | 受限访问 |
| 永久用户 | `user_type=permanent` | 完整访问 |

**运行命令**:
```bash
pytest tests/test_jwt_auth.py tests/test_jwt_hardening.py -v
```

### API 契约测试

**文件**: `tests/test_api_contracts.py`

| 场景 | 测试点 | 预期结果 |
|------|--------|----------|
| 健康检查 | `GET /api/v1/healthz` | 200 + 正确 schema |
| 模型列表 | `GET /api/v1/llm/models` | 200 + 分页数据 |
| 认证接口 | `POST /api/v1/base/access_token` | 200 + JWT |
| 错误响应 | 无效请求 | 标准错误格式 |

**运行命令**:
```bash
pytest tests/test_api_contracts.py -v
```

### 冒烟测试

**文件**: `scripts/smoke_test.py`

完整 E2E 流程验证：

```
注册 → JWT 获取 → API 调用 → SSE 连接 → 数据持久化
```

**运行命令**:
```bash
python scripts/smoke_test.py
```

---

## 测试触发规则

### 必须运行测试的场景

| 变更类型 | 必须运行的测试 |
|----------|----------------|
| JWT/认证相关 | `pytest tests/test_jwt_*.py` |
| API 端点变更 | `pytest tests/test_api_contracts.py` |
| 数据库模型变更 | `make test` + 验证迁移 |
| 中间件变更 | `make test` + 冒烟测试 |
| 任何 PR | `make test` + `make lint` |

### 可选测试的场景

| 变更类型 | 建议运行的测试 |
|----------|----------------|
| 文档更新 | 无需测试 |
| 注释修改 | 无需测试 |
| 配置变更 | 健康检查 |

---

## 测试环境配置

### 环境变量

```bash
# .env.test（测试专用）
DATABASE_URL=sqlite:///./test.db
JWT_SECRET=test-secret-key
JWT_CLOCK_SKEW_SECONDS=120
JWT_REQUIRE_NBF=false
RATE_LIMIT_ENABLED=false
```

### pytest 配置

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

---

## 测试编写规范

### 命名规范

```python
# 文件名：test_<模块名>.py
# 函数名：test_<功能>_<场景>_<预期结果>

def test_jwt_validation_expired_token_returns_401():
    """过期 token 应返回 401"""
    pass

def test_api_healthz_returns_correct_schema():
    """健康检查应返回正确的 schema"""
    pass
```

### 测试结构

```python
import pytest
from fastapi.testclient import TestClient
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

class TestJWTValidation:
    """JWT 验证测试组"""

    def test_valid_token_succeeds(self, client):
        """有效 token 应认证成功"""
        # Arrange
        token = create_valid_token()

        # Act
        response = client.get(
            "/api/v1/protected",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 200
```

### Mock 使用

```python
from unittest.mock import patch, MagicMock

def test_supabase_connection_failure_handled():
    """Supabase 连接失败应优雅处理"""
    with patch('app.db.supabase_client') as mock_client:
        mock_client.table.side_effect = Exception("Connection failed")
        # ... 测试逻辑
```

---

## CI/CD 集成

### GitHub Actions 示例

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: make lint
      - run: make test
```

### 本地 CI 脚本

```bash
# scripts/k5_build_and_test.py
python scripts/k5_build_and_test.py
```

---

## 失败处理

### 测试失败时

1. **不要忽略失败** - 必须修复或标记为已知问题
2. **记录失败原因** - 在 Issue CSV 的 Notes 中记录
3. **创建修复 Issue** - 如果无法立即修复

### 常见失败原因

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| JWT 测试失败 | JWKS 缓存过期 | 运行 `scripts/verify_jwks_cache.py` |
| API 测试超时 | 后端未启动 | `python run.py` 启动服务 |
| 数据库测试失败 | 迁移未执行 | `make upgrade` |
| Import 错误 | 依赖缺失 | `pip install -r requirements.txt` |

---

## 与 AGENTS.md 的关系

本文档是 `AGENTS.md` 中 Testing Policy 部分的详细实现。

**AGENTS.md 中的规则**:
- 每次变更后运行 `make test`
- 启动后执行健康检查 `GET /api/v1/healthz`
- 关键功能变更需冒烟测试
- JWT 相关变更需运行 `tests/test_jwt_*.py`
- 数据库变更需验证迁移成功

**参考文档**:
- `AGENTS.md` - Agent 行为规范
- `CLAUDE.md` - 项目技术文档
- `issues/README.md` - Issue CSV 规范
