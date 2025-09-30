# GymBro Supabase 快速设置清单

**⏱️ 预计时间**: 10-15分钟
**📋 总步骤**: 6步

## ✅ 执行清单

### 步骤1: 准备工作 (2分钟)
- [ ] 打开 [Supabase Dashboard](https://supabase.com/dashboard)
- [ ] 选择GymBro项目
- [ ] 导航到 **SQL Editor**
- [ ] 确认项目状态正常

### 步骤2: 执行主要数据库脚本 (5-8分钟)
- [ ] 打开文件: `docs/jwt改造/GYMBRO_COMPLETE_SUPABASE_SCHEMA.sql`
- [ ] 复制全部内容（约1200行，以实际为准）
- [ ] 粘贴到SQL Editor
- [ ] 点击 **Run** 执行

**⚠️ 如遇超时，按以下分段执行**:
- [ ] 第1段: 第1-400行 (表结构)
- [ ] 第2段: 第401-700行 (索引和外键)
- [ ] 第3段: 第701-1000行 (RLS策略)
- [ ] 第4段: 第1001-1200行 (匿名用户支持)

### 步骤3: 验证表创建 (1分钟)
执行验证查询:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```
- [ ] 确认返回30个表
- [ ] 检查关键表存在: `users`, `chat_sessions`, `workout_sessions`

### 步骤4: 验证RLS策略 (1分钟)
执行策略检查:
```sql
SELECT tablename, policyname FROM pg_policies
WHERE tablename IN ('users', 'chat_sessions', 'workout_sessions')
ORDER BY tablename;
```
- [ ] 确认每个表有4-5个策略
- [ ] 检查包含 `_user_select`, `_service_all` 策略

### 步骤5: 执行匿名用户RLS策略 (2分钟)
- [ ] 打开文件: `docs/jwt改造/ANON/ANON_RLS_POLICIES.sql`
- [ ] 复制全部内容
- [ ] 在SQL Editor中执行
- [ ] 确认无错误信息
- [ ] 注：若已执行完整架构脚本且匿名策略与清理函数已创建，则本步骤可跳过

### 步骤6: 最终验证 (1分钟)
执行完整验证:
```sql
-- 验证匿名用户策略
SELECT policyname FROM pg_policies
WHERE policyname LIKE '%anonymous%';

-- 验证审计字段
SELECT table_name, column_name FROM information_schema.columns
WHERE column_name = 'user_type_audit';

-- 验证清理函数
SELECT proname FROM pg_proc WHERE proname = 'cleanup_anonymous_user_data';
```

预期结果:
- [ ] 匿名用户策略: 2个
- [ ] 审计字段: 8个表
- [ ] 清理函数: 1个

## 🎯 成功标准

### 数据库结构 ✅
- [x] 29个表已创建
- [x] 所有索引已建立
- [x] 外键约束已设置

### 安全策略 ✅
- [x] RLS已启用所有用户表
- [x] Owner-only策略已应用
- [x] 服务角色完全访问已配置

### 匿名用户支持 ✅
- [x] 匿名用户限制策略已创建
- [x] 审计字段已添加
- [x] 数据清理函数已部署

## 🚨 常见问题快速解决

### 问题1: 扩展未启用
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_cron";
```

### 问题2: 权限错误
- 确认使用 **service_role** 密钥
- 检查项目设置中的API密钥

### 问题3: 超时错误
- 分段执行脚本 (每段200-300行)
- 等待1-2分钟后继续下一段

### 问题4: 表已存在
- 脚本使用 `IF NOT EXISTS`，可安全重复执行
- 如需重建，先删除表再执行

## 📞 紧急联系

如遇到无法解决的问题:
1. 检查Supabase项目状态页面
2. 查看SQL执行日志详细错误
3. 参考 `SUPABASE_DASHBOARD_SETUP.md` 详细指南

## 🎉 完成后的下一步

设置完成后，您可以:
1. **配置应用连接**: 更新 `.env` 文件中的Supabase配置
2. **测试API连接**: 运行 `python scripts/verify_supabase_config.py`
3. **启动应用**: 执行 `python run.py`
4. **验证功能**: 测试用户注册、登录、聊天等功能

---

**🏆 恭喜！您已成功设置GymBro APP的完整Supabase数据库结构！**
