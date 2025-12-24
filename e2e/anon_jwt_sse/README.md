# E2E-ANON-JWT→AI→APP（SSE）闭环与策略校验

## 概述

本测试套件实现了端到端的匿名JWT认证到AI消息处理的完整闭环测试，包括：

- 🔐 **匿名JWT获取**：通过Supabase Anonymous获取真实JWT
- 📧 **真实邮箱流测试**：使用 Mail API 生成临时邮箱并接收邮件验证码/链接（见 `docs/mail-api.txt`）
- 🌊 **SSE流式调用**：测试AI消息接口的流式响应
- 🗄️ **数据库验证**：验证数据一致性和外键约束
- 🚫 **策略门测试**：验证匿名访问限制（403错误）
- ⏱️ **限流测试**：验证限流机制（429错误）
- 📊 **统一错误体**：验证错误响应格式一致性

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pnpm install
pip install -r requirements.txt

# 配置环境变量
cp e2e/anon_jwt_sse/.env.local.example e2e/anon_jwt_sse/.env.local
# 编辑 `e2e/anon_jwt_sse/.env.local` 填入正确的配置（包含 Supabase、后端 API、以及可选的 Mail API）
```

### 2. 验收检查

```bash
# 验证测试套件完整性
python e2e/anon_jwt_sse/scripts/verify_setup.py
```

### 3. 一键运行

```bash
# 运行完整的E2E测试套件
pnpm run e2e:anon
```

### 4. 单独测试

```bash
# 验证测试套件完整性
pnpm run verify:setup

# 测试匿名登录
pnpm run test:anon-signin

# 测试SSE客户端
pnpm run test:sse-client

# 测试数据库断言
pnpm run test:db-assert

# 测试策略门
pnpm run test:policy-gate

# 运行Newman回归测试
pnpm run newman:run
```

## 目录结构

```
e2e/anon_jwt_sse/
├── scripts/           # 测试脚本
│   ├── anon_signin_enhanced.py   # 匿名登录脚本（增强版）
│   ├── generate_test_token.py    # 生成 Token（auto/edge/native）
│   ├── run_e2e_enhanced.py       # 主测试运行器（增强版）
│   ├── sse_client.py             # SSE 客户端脚本
│   ├── sse_chaos.py              # SSE 混沌/压力
│   ├── validate_anon_integration.py # 匿名链路快速校验
│   └── verify_setup.py           # 环境体检
├── postman/           # Postman集合
│   ├── collection.json   # API测试集合
│   └── env.json          # 环境变量
├── sql/               # SQL脚本
│   └── assertions.sql    # 数据库断言查询
├── artifacts/         # 测试产物
│   ├── token.json        # JWT令牌缓存
│   ├── sse.log           # SSE事件日志
│   ├── sse_first.json    # 首个SSE事件
│   ├── sse_final.json    # 最终SSE事件
│   ├── policy_*.json     # 策略测试结果
│   ├── db_assert_report.md # 数据库断言报告
│   └── newman-report.html  # Newman测试报告
├── .env.local         # 本地环境配置（勿入库）
├── package.json       # Node.js依赖配置
├── requirements.txt   # Python依赖配置
└── README.md          # 本文档
```

## 测试流程

### 步骤A：匿名JWT获取
1. 使用Supabase SDK执行`signInAnonymously()`
2. 验证JWT claims包含`is_anonymous=true`
3. 缓存access_token到`artifacts/token.json`
4. 测试最小闭环调用

### 步骤B：SSE流式调用
1. 使用匿名JWT发起SSE请求到`/api/v1/messages`
2. 记录所有事件帧到`artifacts/sse.log`
3. 保存首/末帧到`sse_first.json`和`sse_final.json`
4. 验证App消费逻辑

### 步骤C：数据库断言
1. 验证用户表匿名标识正确
2. 验证会话和消息表数据一致性
3. 检查外键约束和时间戳
4. 生成断言报告

### 步骤D：策略和限流测试
1. 测试匿名用户访问受限端点（403）
2. 测试限流机制触发（429）
3. 验证统一错误体格式
4. 记录策略测试结果

## 验收标准

- [x] 匿名JWT成功获取并验证
- [x] SSE流式响应完整接收
- [x] 数据库记录符合表结构
- [x] 策略门正确拦截（403）
- [x] 限流机制正常工作（429）
- [x] 错误体格式统一
- [x] 所有测试产物生成

## 故障排除

### 常见问题

1. **匿名登录失败**
   - 检查Supabase项目是否启用Anonymous Sign-ins
   - 确认SUPABASE_ANON_KEY配置正确

2. **SSE连接失败**
   - 检查API服务是否运行
   - 确认JWT令牌有效性

3. **数据库连接失败**
   - 检查DB_CONN配置
   - 确认数据库表已创建

### 调试工具

```bash
# 查看详细日志
python e2e/anon_jwt_sse/scripts/anon_signin_enhanced.py --verbose

# 检查/解析 JWT（避免使用 python -c）
python scripts/testing/jwt/test_complete.py --token "<YOUR_TOKEN>"

# 测试API连接
curl -H "Authorization: Bearer TOKEN" http://localhost:9999/api/v1/me
```

## 相关文档

- [JWT硬化指南](../../docs/JWT_HARDENING_GUIDE.md)
- [Supabase配置指南](../../docs/SUPABASE_JWT_SETUP.md)
- [K1交付报告](../../docs/K1_DELIVERY_REPORT.md)
- [Mail API（真实邮箱流测试）](../../docs/mail-api.txt)
