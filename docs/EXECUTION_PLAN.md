# GymBro 管理后台详细执行计划

## 📋 总体规划

### 开发周期

- **总工期**：13-16个工作日
- **阶段0**：1-2天（JWT认证完善）
- **阶段1**：2-3天（数据库模型）
- **阶段2**：3-4天（后端API）
- **阶段3**：4-5天（前端界面）
- **阶段4**：1-2天（优化上线）

### 优先级策略

- **P0（最高）**：App JWT对接准备 - 必须优先完成
- **P1（高）**：RBAC核心功能 - 用户、角色、菜单管理
- **P2（中）**：前端管理界面 - 可视化操作
- **P3（低）**：系统优化 - 性能和安全加固

## 🎯 阶段0：JWT认证完善（1-2天）

### 目标

确保App可以正常对接，JWT认证流程完整可靠。

### 任务清单

#### 1. 实现Token刷新端点（4小时）

**文件**：`app/api/v1/base.py`

**实现内容**：
```python
@router.post("/refresh_token", summary="刷新Token")
async def refresh_token(
    request: Request,
    token: Optional[str] = Header(default=None, alias="token"),
) -> Dict[str, Any]:
    """
    刷新JWT token。
    
    接受即将过期或刚过期的token（不超过7天），
    返回新的token（延长1小时）。
    """
    settings = get_settings()
    
    try:
        # 验证token（允许过期但不超过7天）
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": False}  # 不验证过期时间
        )
        
        # 检查token是否过期超过7天
        exp = payload.get("exp")
        if exp and (time.time() - exp) > 7 * 24 * 3600:
            return create_response(
                code=401,
                msg="Token过期时间超过7天，请重新登录"
            )
        
        # 生成新token
        new_payload = {**payload}
        new_payload["exp"] = int(time.time()) + 3600
        new_payload["iat"] = int(time.time())
        
        new_token = jwt.encode(
            new_payload,
            settings.supabase_jwt_secret,
            algorithm="HS256"
        )
        
        return create_response(data={
            "access_token": new_token,
            "token_type": "bearer"
        })
        
    except jwt.InvalidTokenError as e:
        return create_response(
            code=401,
            msg=f"无效的token: {str(e)}"
        )
```

**验收标准**：
- ✅ 接受即将过期的token并返回新token
- ✅ 拒绝过期超过7天的token
- ✅ 拒绝无效的token
- ✅ 返回统一格式的响应

#### 2. 实现前端Token自动刷新逻辑（4小时）

**文件**：`web/src/utils/http/interceptors.js`

**实现内容**：
```javascript
let isRefreshing = false
let refreshSubscribers = []

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb)
}

function onRefreshed(token) {
  refreshSubscribers.forEach(cb => cb(token))
  refreshSubscribers = []
}

export async function resReject(error) {
  if (!error || !error.response) {
    // ... 现有逻辑
  }
  
  const { data, status, config } = error.response
  
  // 检测401错误且不是登录或刷新token请求
  if (status === 401 && !config.url.includes('/access_token') && !config.url.includes('/refresh_token')) {
    if (!isRefreshing) {
      isRefreshing = true
      
      try {
        const token = getToken()
        const res = await api.refreshToken({ token })
        
        if (res.code === 200) {
          const newToken = res.data.access_token
          setToken(newToken)
          
          // 通知所有等待的请求
          onRefreshed(newToken)
          
          // 重试原始请求
          config.headers.token = newToken
          return axios(config)
        }
      } catch (refreshError) {
        // 刷新失败，跳转登录
        const userStore = useUserStore()
        userStore.logout()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    } else {
      // 正在刷新，等待刷新完成
      return new Promise(resolve => {
        subscribeTokenRefresh(token => {
          config.headers.token = token
          resolve(axios(config))
        })
      })
    }
  }
  
  // ... 现有逻辑
}
```

**验收标准**：
- ✅ 检测到401错误时自动调用refresh_token
- ✅ 刷新成功后重试原始请求
- ✅ 刷新失败后跳转登录页
- ✅ 避免并发刷新（使用锁机制）

#### 3. 验证CORS配置（2小时）

**测试内容**：
```bash
# 测试preflight请求
curl -X OPTIONS http://localhost:9999/api/v1/base/access_token \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: token,content-type"

# 测试跨域POST请求
curl -X POST http://localhost:9999/api/v1/base/access_token \
  -H "Origin: http://localhost:3000" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

**验收标准**：
- ✅ preflight请求返回200
- ✅ 响应包含正确的CORS头
- ✅ 允许的方法包含POST、GET、PUT、DELETE
- ✅ 允许的头包含token、content-type

#### 4. 测试匿名用户和永久用户区分（2小时）

**测试脚本**：
```python
# tests/test_user_types.py
import pytest
from app.api.v1.base import create_test_jwt_token

def test_anonymous_user_rate_limit():
    """测试匿名用户限流策略"""
    # 创建匿名用户token
    token = create_test_jwt_token("anonymous", is_anonymous=True)
    
    # 发送6个请求（超过QPS=5）
    for i in range(6):
        response = client.post("/api/v1/messages", headers={"token": token})
        if i < 5:
            assert response.status_code == 200
        else:
            assert response.status_code == 429  # 第6个请求被限流

def test_permanent_user_rate_limit():
    """测试永久用户限流策略"""
    # 创建永久用户token
    token = create_test_jwt_token("user", is_anonymous=False)
    
    # 发送11个请求（超过QPS=10）
    for i in range(11):
        response = client.post("/api/v1/messages", headers={"token": token})
        if i < 10:
            assert response.status_code == 200
        else:
            assert response.status_code == 429
```

**验收标准**：
- ✅ 匿名用户QPS限制为5
- ✅ 永久用户QPS限制为10
- ✅ 匿名用户无法访问/api/v1/base/*管理端点
- ✅ 永久用户可以访问管理端点

#### 5. 编写App JWT对接文档（4小时）

**文件**：`docs/APP_JWT_INTEGRATION.md`

**内容大纲**：
1. 认证流程说明
2. Token格式和Claims
3. API端点列表
4. 错误码说明
5. 限流策略
6. 示例代码（Kotlin/Swift）
7. 常见问题FAQ

**验收标准**：
- ✅ 文档完整清晰
- ✅ 包含可运行的示例代码
- ✅ 错误码说明详细
- ✅ 包含测试token生成方法

### 阶段0交付物

- ✅ Token刷新端点（后端）
- ✅ Token自动刷新逻辑（前端）
- ✅ CORS配置验证报告
- ✅ 用户类型测试报告
- ✅ App JWT对接文档

---

## 🗄️ 阶段1：数据库模型和RBAC基础（2-3天）

### 目标

建立RBAC系统的数据基础，实现基础CRUD服务层。

### 任务清单

#### 1. 设计数据库Schema（4小时）

**文件**：`docs/DATABASE_SCHEMA.md`

**表结构设计**：

1. **users表**：
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

2. **roles表**：
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

3. **user_roles表**：
```sql
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
```

4. **menus表**：
```sql
CREATE TABLE menus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL,
    path VARCHAR(200),
    component VARCHAR(200),
    icon VARCHAR(50),
    parent_id UUID REFERENCES menus(id) ON DELETE CASCADE,
    order_num INTEGER DEFAULT 0,
    is_visible BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

5. **role_menus表**、**apis表**、**role_apis表**、**audit_logs表**（详见DATABASE_SCHEMA.md）

**验收标准**：
- ✅ 所有表结构定义完整
- ✅ 外键关系正确
- ✅ 索引设计合理
- ✅ 对齐Android Room schema

#### 2. 配置数据库连接（2小时）

**文件**：
- `.env`
- `app/settings/config.py`
- `app/core/database.py`

**实现内容**：
```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

def get_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

async_session_maker = sessionmaker(
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
```

**验收标准**：
- ✅ 数据库连接成功
- ✅ 连接池配置合理
- ✅ 支持异步操作

#### 3-6. 创建模型、迁移、服务层、测试（详见完整文档）

### 阶段1交付物

- ✅ 数据库Schema文档
- ✅ SQLAlchemy模型代码
- ✅ Alembic迁移脚本
- ✅ 基础CRUD服务层
- ✅ 单元测试（覆盖率>80%）

---

## 🔌 阶段2-4：详细计划

（由于篇幅限制，详细内容见后续文档补充）

### 阶段2：后端管理API实现（3-4天）
### 阶段3：前端管理界面开发（4-5天）
### 阶段4：系统优化和上线准备（1-2天）

---

## 📊 进度跟踪

使用任务管理工具跟踪进度，每个任务包含：
- 任务名称
- 负责人
- 预计工时
- 实际工时
- 状态（未开始/进行中/已完成/已取消）
- 阻塞问题

## 🚨 风险管理

### 技术风险

1. **数据库迁移失败**
   - 概率：中
   - 影响：高
   - 应对：充分测试，备份数据，使用事务回滚

2. **Token刷新逻辑错误**
   - 概率：中
   - 影响：中
   - 应对：添加刷新次数限制，失败后强制登出

3. **权限控制漏洞**
   - 概率：低
   - 影响：高
   - 应对：后端强制验证，前端仅UI控制

### 时间风险

1. **开发时间超出预期**
   - 概率：高
   - 影响：中
   - 应对：采用MVP策略，优先核心功能

2. **需求变更**
   - 概率：中
   - 影响：中
   - 应对：使用Alembic迁移，保持灵活性

## 📝 下一轮对话启动清单

1. ✅ 开始阶段0任务1：实现Token刷新端点
2. ✅ 准备测试环境和测试数据
3. ✅ 确认Android Room schema内容
4. ✅ 安装必要的依赖（SQLAlchemy, Alembic等）

---

**文档版本**：v1.0
**最后更新**：2025-09-30

