# 匿名访问表结构补充脚本修复说明

## 🔧 修复内容

### 问题描述
执行 `ANON_TABLES_SUPPLEMENT.sql` 时遇到错误：
```
ERROR: 42P13: cannot change name of input parameter "days_old"
HINT: Use DROP FUNCTION cleanup_anonymous_user_data(integer) first.
```

### 问题原因
`cleanup_anonymous_user_data` 函数已存在于 `COMPLETE_REBUILD_FOR_ANDROID.sql` 中，但参数名不同：
- 现有函数使用：`days_old INTEGER`
- 补充脚本使用：`retention_days INTEGER`

PostgreSQL不允许仅通过参数名变更来替换函数。

### 修复方案
已修复 `ANON_TABLES_SUPPLEMENT.sql`，包含以下更改：

1. **添加函数删除语句**：
```sql
-- 先删除现有函数（如果存在）
DROP FUNCTION IF EXISTS cleanup_anonymous_user_data(INTEGER);
```

2. **统一参数名**：
```sql
-- 使用与原函数一致的参数名
CREATE OR REPLACE FUNCTION cleanup_anonymous_user_data(days_old INTEGER DEFAULT 30)
```

3. **修正函数体中的参数引用**：
```sql
-- 将所有 retention_days 改为 days_old
cutoff_timestamp := NOW() - INTERVAL '1 day' * days_old;
```

## ✅ 修复后的执行流程

### 1. 正确的部署顺序
```bash
# 1. 执行基础重建脚本
psql -f COMPLETE_REBUILD_FOR_ANDROID.sql

# 2. 执行修复后的补充脚本
psql -f ANON_TABLES_SUPPLEMENT.sql

# 3. 配置RLS策略
psql -f ANON/ANON_RLS_POLICIES.sql
```

### 2. 验证步骤
```sql
-- 验证表是否创建成功
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('conversations', 'messages', 'chat_messages', 'public_shares');

-- 验证函数是否更新成功
SELECT routine_name, routine_type 
FROM information_schema.routines 
WHERE routine_name = 'cleanup_anonymous_user_data';

-- 测试函数执行
SELECT cleanup_anonymous_user_data(30);
```

## 📋 修复后的功能特性

### 增强的数据清理函数
修复后的函数支持清理以下数据：
- ✅ 匿名用户对话记录
- ✅ 匿名用户消息记录
- ✅ 匿名用户聊天消息（向后兼容）
- ✅ 匿名用户公开分享记录
- ✅ 匿名用户账户记录

### 完整的表结构
- ✅ conversations - 对话管理表
- ✅ messages - 消息管理表
- ✅ chat_messages - 向后兼容聊天消息表
- ✅ public_shares - 公开分享功能表

### 性能优化
- ✅ 所有表的必要索引
- ✅ user_type字段的条件索引
- ✅ 复合索引支持分析查询

## 🎯 修复确认

**状态**: ✅ 已修复  
**测试**: ✅ 语法验证通过  
**兼容性**: ✅ 与现有函数兼容  

现在可以安全执行 `ANON_TABLES_SUPPLEMENT.sql` 来补充匿名访问功能所需的表结构。

## 📝 注意事项

1. **执行顺序很重要**：必须先执行基础重建脚本
2. **数据备份**：建议在生产环境执行前备份数据
3. **权限检查**：确保执行用户有创建表和函数的权限
4. **依赖验证**：确保users表已存在且包含必要字段

修复完成后，匿名访问功能将具备完整的数据库支持。
