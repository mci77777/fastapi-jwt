# JWT 验证器硬化指南

## 概述

本文档说明 GymBro API 中 JWT 验证器的硬化功能，包括 Supabase 兼容性增强、时钟偏移处理、算法限制和统一错误响应。

## 🔒 硬化功能

### 1. Supabase JWT 兼容性

**问题**: Supabase 签发的 JWT 通常不包含 `nbf` (not before) 声明，但标准 JWT 验证器可能要求此字段。

**解决方案**: 
- `nbf` 声明现在是可选的（默认 `JWT_REQUIRE_NBF=false`）
- 如果 `nbf` 存在，仍会进行验证
- 完全兼容 Supabase 认证流程

```bash
# 环境配置
JWT_REQUIRE_NBF=false  # Supabase 兼容性
```

### 2. 时钟偏移容忍

**问题**: 分布式系统中服务器时钟可能存在偏差，导致合法 JWT 被错误拒绝。

**解决方案**:
- 支持 ±120 秒的时钟偏移窗口
- 对 `iat` 未来时间进行特殊检查
- 防止时间攻击

```bash
# 环境配置
JWT_CLOCK_SKEW_SECONDS=120      # 时钟偏移容忍度
JWT_MAX_FUTURE_IAT_SECONDS=120  # iat 最大未来时间
```

### 3. 算法安全限制

**问题**: 某些 JWT 算法存在安全风险或不适合生产环境。

**解决方案**:
- 默认只允许 `ES256`, `RS256`, `HS256`
- 优先推荐 `ES256` (椭圆曲线数字签名)
- 可配置允许的算法列表

```bash
# 环境配置
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256
```

### 4. 统一错误响应

**问题**: 不一致的错误格式影响客户端处理和调试。

**解决方案**:
- 统一错误响应格式
- 包含 `status`, `code`, `message`, `trace_id`, `hint`
- 401 错误不泄露敏感信息

```json
{
  "status": 401,
  "code": "token_expired",
  "message": "Token has expired",
  "trace_id": "abc123def456",
  "hint": "Please refresh your token"
}
```

## 📋 配置参数

### 基础 JWT 配置

```bash
# 基础配置
SUPABASE_JWKS_URL=https://your-project.supabase.co/.well-known/jwks.json
SUPABASE_ISSUER=https://your-project.supabase.co/auth/v1
SUPABASE_AUDIENCE=authenticated
JWT_LEEWAY_SECONDS=30

# 硬化配置
JWT_CLOCK_SKEW_SECONDS=120
JWT_MAX_FUTURE_IAT_SECONDS=120
JWT_REQUIRE_NBF=false
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `JWT_CLOCK_SKEW_SECONDS` | 120 | 时钟偏移容忍度（秒） |
| `JWT_MAX_FUTURE_IAT_SECONDS` | 120 | iat 最大未来时间（秒） |
| `JWT_REQUIRE_NBF` | false | 是否要求 nbf 声明 |
| `JWT_ALLOWED_ALGORITHMS` | ES256,RS256,HS256 | 允许的签名算法 |

## 🔍 验证流程

### 1. 基础验证
- ✅ JWT 格式和头部解析
- ✅ 算法在允许列表中
- ✅ JWKS 密钥匹配 (kid)
- ✅ 签名验证

### 2. 声明验证
- ✅ `iss` (issuer) - 必需，匹配配置
- ✅ `sub` (subject) - 必需，非空
- ✅ `aud` (audience) - 必需，匹配配置
- ✅ `exp` (expiration) - 必需，未过期
- ✅ `iat` (issued at) - 必需，不能过于未来
- 🔄 `nbf` (not before) - 可选，存在时验证

### 3. 时间验证
- ✅ `exp` 检查（考虑时钟偏移）
- ✅ `iat` 未来时间检查
- ✅ `nbf` 检查（如果存在）

## 🚨 错误代码

### 认证错误

| 错误代码 | HTTP状态 | 说明 |
|----------|----------|------|
| `token_missing` | 401 | 缺失 Authorization token |
| `invalid_token_header` | 401 | JWT 头部格式无效 |
| `algorithm_missing` | 401 | JWT 头部缺失 alg 字段 |
| `unsupported_alg` | 401 | 不支持的签名算法 |
| `jwks_key_not_found` | 401 | JWKS 中未找到匹配密钥 |

### 声明错误

| 错误代码 | HTTP状态 | 说明 |
|----------|----------|------|
| `token_expired` | 401 | Token 已过期 |
| `token_not_yet_valid` | 401 | Token 尚未生效 (nbf) |
| `iat_too_future` | 401 | iat 时间过于未来 |
| `invalid_audience` | 401 | 受众验证失败 |
| `invalid_issuer` | 401 | 签发者验证失败 |
| `issuer_not_allowed` | 401 | 签发者不在允许列表 |
| `subject_missing` | 401 | 缺失 subject 声明 |

## 📊 日志记录

### 成功验证日志

```json
{
  "level": "INFO",
  "message": "JWT verification successful",
  "trace_id": "abc123def456",
  "subject": "user-123",
  "audience": "authenticated",
  "issuer": "https://project.supabase.co/auth/v1",
  "kid": "key-id-123",
  "algorithm": "ES256",
  "event": "jwt_verification_success"
}
```

### 失败验证日志

```json
{
  "level": "WARNING", 
  "message": "JWT verification failed",
  "trace_id": "abc123def456",
  "code": "token_expired",
  "reason": "Token has expired",
  "subject": "user-123",
  "audience": "authenticated",
  "issuer": "https://project.supabase.co/auth/v1",
  "kid": "key-id-123",
  "algorithm": "ES256",
  "event": "jwt_verification_failure"
}
```

## 🧪 测试场景

### 正面测试
- ✅ 标准 Supabase JWT（无 nbf）
- ✅ 包含 nbf 的 JWT
- ✅ 时钟偏移范围内的 JWT
- ✅ ES256 算法 JWT

### 负面测试
- ❌ iat 过于未来的 JWT
- ❌ nbf 未来时间的 JWT
- ❌ 不支持算法的 JWT
- ❌ 无效签发者的 JWT
- ❌ 缺失 subject 的 JWT
- ❌ JWKS 密钥不匹配

## 🔧 故障排除

### 常见问题

1. **Supabase JWT 被拒绝**
   - 检查 `JWT_REQUIRE_NBF=false`
   - 确认 issuer 和 audience 配置正确

2. **时钟偏移错误**
   - 调整 `JWT_CLOCK_SKEW_SECONDS`
   - 检查服务器时间同步

3. **算法不支持**
   - 检查 `JWT_ALLOWED_ALGORITHMS` 配置
   - 确认 JWKS 中的算法匹配

### 调试工具

```bash
# 运行硬化功能测试
python -m pytest tests/test_jwt_hardening.py -v

# 运行集成测试
python -m pytest tests/test_jwt_integration_hardening.py -v

# 检查配置
python scripts/verify_jwt_config.py
```

## 📚 相关文档

- [Supabase JWT 配置指南](./SUPABASE_JWT_SETUP.md)
- [JWT 认证系统实现总结](./jwt改/IMPLEMENTATION_SUMMARY.md)
- [API 端点文档](http://localhost:9999/docs)

## 🔄 版本历史

### v1.1.0 - JWT 硬化版本
- ✅ Supabase nbf 兼容性
- ✅ 时钟偏移容忍
- ✅ 算法安全限制
- ✅ 统一错误响应
- ✅ 增强日志记录
