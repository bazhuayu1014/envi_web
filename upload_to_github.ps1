# ENVI Web 项目上传到 GitHub 脚本
# 请在执行前修改下面的用户信息

# ============================================
# 第一步：配置 Git 用户信息（首次使用需要）
# ============================================
Write-Host "正在配置 Git 用户信息..." -ForegroundColor Green

# 请修改为你的 GitHub 用户名和邮箱
$gitUsername = "bazhuayu1014"
$gitEmail = "1227187762@qq.com"

# 配置 Git
git config user.name "$gitUsername"
git config user.email "$gitEmail"

Write-Host "Git 用户信息配置完成！" -ForegroundColor Green
Write-Host ""

# ============================================
# 第二步：创建初始提交
# ============================================
Write-Host "正在创建初始提交..." -ForegroundColor Green
git commit -m "Initial commit: ENVI Web 遥感影像数据管理系统"

if ($LASTEXITCODE -eq 0) {
    Write-Host "初始提交创建成功！" -ForegroundColor Green
} else {
    Write-Host "提交失败，请检查错误信息" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================
# 第三步：连接到 GitHub 远程仓库
# ============================================
Write-Host "请输入你的 GitHub 仓库信息：" -ForegroundColor Yellow
Write-Host "示例：https://github.com/username/repo-name.git" -ForegroundColor Gray
$repoUrl = Read-Host "请输入完整的仓库 URL"

if ($repoUrl) {
    Write-Host "正在添加远程仓库..." -ForegroundColor Green
    git remote add origin $repoUrl
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "远程仓库添加成功！" -ForegroundColor Green
    } else {
        Write-Host "远程仓库可能已存在，尝试更新..." -ForegroundColor Yellow
        git remote set-url origin $repoUrl
    }
} else {
    Write-Host "未输入仓库 URL，跳过此步骤" -ForegroundColor Yellow
    Write-Host "你可以稍后手动执行：git remote add origin YOUR_REPO_URL" -ForegroundColor Gray
}

Write-Host ""

# ============================================
# 第四步：推送到 GitHub
# ============================================
Write-Host "是否现在推送到 GitHub？(y/n)" -ForegroundColor Yellow
$pushNow = Read-Host

if ($pushNow -eq "y" -or $pushNow -eq "Y") {
    Write-Host "正在推送到 GitHub..." -ForegroundColor Green
    Write-Host "注意：首次推送需要输入 GitHub 用户名和 Personal Access Token" -ForegroundColor Yellow
    
    # 尝试推送到 main 分支
    git branch -M main
    git push -u origin main
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "推送成功！" -ForegroundColor Green
        Write-Host "请访问你的 GitHub 仓库查看：$repoUrl" -ForegroundColor Cyan
    } else {
        Write-Host "推送失败，请检查：" -ForegroundColor Red
        Write-Host "1. 仓库 URL 是否正确" -ForegroundColor Gray
        Write-Host "2. 是否使用了 Personal Access Token 而不是密码" -ForegroundColor Gray
        Write-Host "3. 网络连接是否正常" -ForegroundColor Gray
    }
} else {
    Write-Host "跳过推送步骤" -ForegroundColor Yellow
    Write-Host "你可以稍后手动执行：" -ForegroundColor Gray
    Write-Host "  git branch -M main" -ForegroundColor Gray
    Write-Host "  git push -u origin main" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "脚本执行完成！" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "后续更新代码时，使用以下命令：" -ForegroundColor Yellow
Write-Host "  git add ." -ForegroundColor Gray
Write-Host "  git commit -m '描述你的修改'" -ForegroundColor Gray
Write-Host "  git push" -ForegroundColor Gray
