# 🔒 密钥泄露紧急处理指南

> **泄露的密钥**: `<redacted>`  
> **泄露的文件**: `storage/ai_router/supabase_endpoints-latest.json`  
> **泄露的 commit**: `<redacted>`

## 📋 执行清单（15分钟完成）

### ✅ 步骤 1: 撤销泄露的密钥（5分钟）

1. 登录 xAI Console: https://console.x.ai/api-keys
2. 找到并删除密钥: `<redacted>`
3. 生成新密钥并保存到密码管理器
4. 更新 `.env` 文件：
   ```bash
   # 编辑 .env
   XAI_API_KEY=<新密钥>
   ```

### ✅ 步骤 2: 清理 Git 历史（5分钟）

```powershell
# 运行清理脚本
make remove-leaked-key

# 或直接执行
pwsh -ExecutionPolicy Bypass -File ./scripts/remove_leaked_key.ps1
```

**脚本会自动:**
- 删除文件的所有历史记录
- 清理 Git 引用和 reflog
- 执行垃圾回收

### ✅ 步骤 3: 强制推送（2分钟）

```bash
# 推送清理后的历史
git push origin --force --all
git push origin --force --tags
```

### ✅ 步骤 4: 安装防护（3分钟）

```bash
# 安装 pre-commit hooks
make setup-git-hooks

# 验证防护生效
make check-secrets
```

---

## 🛡️ 防护措施已就位

### 已更新的文件

1. **`.gitignore`** - 严格忽略所有敏感文件：
   - `*.env`
   - `**/*_endpoints*.json`
   - `**/*-latest.json`
   - `storage/**/*.json`

2. **`.gitattributes`** - 标记敏感文件类型

3. **`.pre-commit-config.yaml`** - 自动扫描密钥泄露

4. **`Makefile`** - 新增安全命令：
   - `make remove-leaked-key` - 清理历史
   - `make setup-git-hooks` - 安装防护
   - `make check-secrets` - 扫描泄露

---

## ⚠️ 重要提醒

### 团队成员需要重新 clone

发送通知：

```
⚠️ Git 历史已清理，请重新 clone 仓库！

操作步骤：
1. 备份未提交代码: git stash
2. 删除旧仓库: cd .. && rm -rf vue-fastapi-admin
3. 重新 clone: git clone <仓库地址>
4. 安装 hooks: cd vue-fastapi-admin && make setup-git-hooks
```

### 验证清理成功

```bash
# 搜索泄露的密钥（应该找不到）
git log --all --full-history --source --pretty=format:"%H %s" | grep "<redacted>"

# 搜索文件历史（应该不存在）
git log --all -- storage/ai_router/supabase_endpoints-latest.json
```

---

## 📞 需要帮助？

- **技术问题**: 查看 `docs/runbooks/security/KEY_LEAK_RESPONSE.md`
- **紧急联系**: DevOps 团队

**文档版本**: v1.0  
**最后更新**: 2025-10-14
