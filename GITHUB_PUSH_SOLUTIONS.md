# Git Push 认证问题解决方案

## 问题描述
```
error: failed to execute prompt script (exit code 57)
fatal: could not read Username for 'https://github.com': No such file or directory
```

## 🎯 解决方案（按推荐顺序）

### 方案 1：在 URL 中直接包含用户名（最简单）

```powershell
# 先移除现有的 origin
git remote remove origin

# 添加包含用户名的 URL（替换 YOUR_USERNAME 和 YOUR_REPO）
git remote add origin https://YOUR_USERNAME@github.com/YOUR_USERNAME/YOUR_REPO.git

# 推送（只需要输入 Personal Access Token）
git push -u origin main
```

**示例**：
```powershell
# 如果你的用户名是 zhangsan，仓库名是 envi-web
git remote add origin https://zhangsan@github.com/zhangsan/envi-web.git
```

---

### 方案 2：使用 Personal Access Token 作为密码

```powershell
# 1. 先获取你的 GitHub Personal Access Token
# GitHub → Settings → Developer settings → Personal access tokens → Generate new token

# 2. 推送时手动输入凭据
git push -u origin main

# 当提示输入时：
# Username: 你的GitHub用户名
# Password: 粘贴你的Personal Access Token（不是账号密码）
```

---

### 方案 3：使用 Git Credential Manager（已配置）

我已经为你配置了凭据管理器，现在再试一次：

```powershell
git push -u origin main
```

如果弹出登录窗口，选择 "Token" 方式登录，粘贴你的 Personal Access Token。

---

### 方案 4：使用 SSH 方式（更安全，但需要配置）

#### 4.1 生成 SSH 密钥
```powershell
ssh-keygen -t ed25519 -C "你的邮箱@example.com"
# 一路回车，使用默认设置
```

#### 4.2 复制公钥
```powershell
cat ~/.ssh/id_ed25519.pub
# 复制输出的内容
```

#### 4.3 添加到 GitHub
1. GitHub → Settings → SSH and GPG keys → New SSH key
2. 粘贴公钥内容
3. 保存

#### 4.4 修改远程仓库 URL
```powershell
git remote remove origin
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

---

## 🔐 如何获取 Personal Access Token

1. 登录 GitHub
2. 点击右上角头像 → **Settings**
3. 左侧菜单最下方 → **Developer settings**
4. **Personal access tokens** → **Tokens (classic)**
5. **Generate new token** → **Generate new token (classic)**
6. 设置：
   - Note: `envi-web-upload`
   - Expiration: `90 days`
   - Scopes: 勾选 **`repo`**（完整仓库访问权限）
7. 点击 **Generate token**
8. **立即复制 token**（只显示一次！）

---

## ✅ 推荐流程（最快）

```powershell
# 1. 检查当前远程仓库
git remote -v

# 2. 移除旧的 origin
git remote remove origin

# 3. 添加新的 origin（包含用户名）
git remote add origin https://YOUR_USERNAME@github.com/YOUR_USERNAME/YOUR_REPO.git

# 4. 推送（输入 Personal Access Token 作为密码）
git push -u origin main
```

---

## 🔍 验证配置

```powershell
# 查看远程仓库配置
git remote -v

# 查看凭据管理器配置
git config --list | Select-String credential

# 测试连接
git ls-remote origin
```

---

## ⚠️ 常见错误

### 错误 1: Authentication failed
**原因**: 使用了账号密码而不是 Token  
**解决**: 使用 Personal Access Token 作为密码

### 错误 2: Repository not found
**原因**: 仓库 URL 错误或没有权限  
**解决**: 检查仓库 URL 是否正确，确保仓库已创建

### 错误 3: Permission denied
**原因**: Token 权限不足  
**解决**: 重新生成 Token，确保勾选了 `repo` 权限

---

## 💡 小贴士

- **保存 Token**: 将 Token 保存到安全的地方（密码管理器）
- **Token 过期**: Token 过期后需要重新生成
- **多次输入**: 如果不想每次都输入，可以使用 SSH 方式
