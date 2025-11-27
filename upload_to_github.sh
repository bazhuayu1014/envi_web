# ENVI Web 项目上传到 GitHub - 简化版脚本

# 第一步：配置 Git 用户信息
echo "配置 Git 用户信息..."
echo "请输入你的 GitHub 用户名："
read -p "用户名: " git_username
read -p "邮箱: " git_email

git config user.name "$git_username"
git config user.email "$git_email"

echo "Git 配置完成！"
echo ""

# 第二步：创建提交
echo "创建初始提交..."
git commit -m "Initial commit: ENVI Web 遥感影像数据管理系统"

if [ $? -eq 0 ]; then
    echo "提交成功！"
else
    echo "提交失败，请检查错误"
    exit 1
fi

echo ""

# 第三步：添加远程仓库
echo "请输入你的 GitHub 仓库 URL："
echo "示例：https://github.com/username/repo-name.git"
read -p "仓库 URL: " repo_url

if [ -n "$repo_url" ]; then
    git remote add origin "$repo_url" 2>/dev/null || git remote set-url origin "$repo_url"
    echo "远程仓库配置完成！"
fi

echo ""

# 第四步：推送到 GitHub
read -p "是否现在推送到 GitHub？(y/n): " push_now

if [ "$push_now" = "y" ] || [ "$push_now" = "Y" ]; then
    echo "推送到 GitHub..."
    git branch -M main
    git push -u origin main
    
    if [ $? -eq 0 ]; then
        echo "推送成功！"
    else
        echo "推送失败，请检查网络和认证信息"
    fi
else
    echo "跳过推送，你可以稍后手动执行："
    echo "  git branch -M main"
    echo "  git push -u origin main"
fi

echo ""
echo "脚本执行完成！"
