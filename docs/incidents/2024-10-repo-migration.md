# 🚀 迁移到新仓库指南

## 当前状态

✅ **已完成:**
- Git 历史已清理（泄露的密钥文件已从所有 194 个 commits 中删除）
- 旧远程仓库已重命名为 `old-origin`
- 新远程仓库地址已配置为 `origin`

⏳ **待完成:**
- 在 GitHub 创建新仓库 `fastapi-jwt`
- 推送清理后的代码到新仓库

---

## 📋 操作步骤

### 1️⃣ 创建 GitHub 新仓库

**访问**: https://github.com/new

**填写表单**:
```
Repository name: fastapi-jwt
Description: Modern FastAPI + Vue3 Admin Platform with JWT Auth & RBAC
Visibility: ● Private (推荐) 或 ○ Public

⚠️ 重要：以下选项全部不勾选
□ Add a README file
□ Add .gitignore
□ Choose a license
```

**点击**: 🟢 Create repository

---

### 2️⃣ 推送代码到新仓库

创建成功后，在当前终端执行：

```powershell
# 推送所有分支
git push -u origin --all

# 推送所有标签
git push origin --tags
```

**预期输出**:
```
Enumerating objects: 2725, done.
Counting objects: 100% (2725/2725), done.
Delta compression using up to 20 threads
Compressing objects: 100% (2543/2543), done.
Writing objects: 100% (2725/2725), done.
Total 2725 (delta 1194), reused 424 (delta 0)
remote: Resolving deltas: 100% (1194/1194), done.
To https://github.com/mci77777/fastapi-jwt.git
 * [new branch]      E2Etest -> E2Etest
 * [new branch]      backup/stacks-20251010-124531 -> backup/stacks-20251010-124531
 * [new branch]      feature/dashboard-phase2 -> feature/dashboard-phase2
 * [new branch]      gitbutler/target -> gitbutler/target
 * [new branch]      gitbutler/workspace -> gitbutler/workspace
 * [new branch]      main -> main
```

---

### 3️⃣ 验证迁移成功

```powershell
# 检查远程仓库
git remote -v

# 验证泄露的密钥已清除（应该无结果）
git log --all --source -S "98ef4ec9397c6627b12acae20e618aa524933073"

# 访问新仓库
start https://github.com/mci77777/fastapi-jwt
```

---

### 4️⃣ 更新本地引用

```powershell
# 更新项目文档中的仓库 URL
# 需要更新以下文件：
```

**文件清单**:
- `README.md` - 仓库链接
- `package.json` - repository 字段
- `docs/*.md` - 文档中的 GitHub 链接
- `.github/workflows/*.yml` - CI/CD 配置（如有）

**批量替换**:
```powershell
# 查找所有包含旧仓库 URL 的文件
Get-ChildItem -Recurse -File | Select-String "vue-fastapi-admin" | Select-Object Path -Unique

# 手动编辑或使用脚本替换
```

---

### 5️⃣ 通知团队成员

**发送消息** (Slack/钉钉/邮件):

```markdown
📢 重要通知：仓库已迁移

由于安全事件（密钥泄露），我们已迁移到新的干净仓库：

🆕 新仓库: https://github.com/mci77777/fastapi-jwt
🗑️ 旧仓库: https://github.com/mci77777/vue-fastapi-admin (将归档)

🔧 所有开发者需要重新 clone：

```bash
# 1. 备份当前工作
cd d:/GymBro/vue-fastapi-admin
git stash
cp -r . ../vue-fastapi-admin.backup

# 2. Clone 新仓库
cd ..
git clone https://github.com/mci77777/fastapi-jwt.git
cd fastapi-jwt

# 3. 安装依赖
pip install -r requirements.txt
cd web && pnpm install

# 4. 配置 pre-commit hooks（强制执行）
make setup-git-hooks
```

⚠️ 警告：
- 旧仓库的 Git 历史仍包含泄露的密钥，请勿继续使用
- 新仓库已清理所有敏感信息
- Pre-commit hooks 已配置，自动防止密钥泄露
```

---

## 📊 迁移清单

- [ ] 在 GitHub 创建新仓库 `fastapi-jwt`
- [ ] 推送所有分支到新仓库
- [ ] 推送所有标签到新仓库
- [ ] 验证密钥已清除
- [ ] 更新 README.md 中的仓库链接
- [ ] 更新 package.json 的 repository 字段
- [ ] 通知团队成员重新 clone
- [ ] 归档旧仓库（Settings → Danger Zone → Archive）
- [ ] 撤销 xAI 泄露的密钥（https://console.x.ai/api-keys）

---

## 🔗 快速链接

- **新仓库**: https://github.com/mci77777/fastapi-jwt
- **创建仓库**: https://github.com/new
- **xAI Console**: https://console.x.ai/api-keys
- **安全指南**: [`docs/KEY_LEAK_RESPONSE.md`](docs/KEY_LEAK_RESPONSE.md)

---

**准备好了吗？** 访问 https://github.com/new 创建新仓库！

创建完成后执行：
```powershell
git push -u origin --all
git push origin --tags
```
