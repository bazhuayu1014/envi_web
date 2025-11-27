from django.shortcuts import render, redirect  # 用于渲染模板和重定向
from django.contrib.auth import login, logout, authenticate  # 用户认证相关函数
from django.contrib.auth.decorators import login_required  # 登录要求装饰器
from django.contrib import messages  # 消息框架
from django.utils import timezone  # 时区工具
from .forms import LoginForm, RegisterForm  # 导入表单类
from .models import InvitationCode, UserProfile  # 导入模型
import logging  # 日志模块

# 获取logger实例
logger = logging.getLogger(__name__)

def login_view(request):
    """登录视图
    处理用户登录请求，包括：
    1. 验证用户凭据
    2. 检查邀请码状态
    3. 更新用户登录信息
    4. 设置会话
    """
    # 如果用户已登录，重定向到地图页面
    if request.user.is_authenticated:
        return redirect('geodata:map')
        
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me')
            
            # 验证用户凭据
            user = authenticate(username=username, password=password)
            if user is not None:
                # 检查用户权限
                if user.is_superuser or user.is_staff:
                    login(request, user)
                    messages.success(request, f'欢迎回来，{username}！')
                    return redirect('geodata:map')
                
                # 检查邀请码状态
                try:
                    profile = UserProfile.objects.get(user=user)
                    if profile.invitation_code and profile.invitation_code.expires_at:
                        if profile.invitation_code.expires_at < timezone.now():
                            messages.error(request, '您的账号已过期，请联系管理员')
                            return render(request, 'accounts/login.html', {'form': form})
                    
                    # 登录用户
                    login(request, user)
                    
                    # 更新用户配置信息
                    profile.last_login_ip = request.META.get('REMOTE_ADDR')
                    profile.login_count += 1
                    profile.save()
                    
                    # 设置会话过期时间
                    if not remember_me:
                        request.session.set_expiry(0)  # 浏览器关闭即过期
                    
                    messages.success(request, f'欢迎回来，{username}！')
                    return redirect('geodata:map')
                except UserProfile.DoesNotExist:
                    messages.error(request, '用户配置信息不存在')
                    return render(request, 'accounts/login.html', {'form': form})
            else:
                messages.error(request, '用户名或密码错误')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def register_view(request):
    """注册视图
    处理用户注册请求，包括：
    1. 验证邀请码
    2. 创建用户账号
    3. 创建用户配置
    4. 自动登录
    """
    # 如果用户已登录，重定向到地图页面
    if request.user.is_authenticated:
        return redirect('geodata:map')
        
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            # 获取并验证邀请码
            invitation_code = InvitationCode.objects.get(
                code=form.cleaned_data['invitation_code']
            )
            
            # 创建用户
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.save()
            
            # 创建用户配置文件
            UserProfile.objects.create(
                user=user,
                invitation_code=invitation_code,
                last_login_ip=request.META.get('REMOTE_ADDR')
            )
            
            # 标记邀请码为已使用
            invitation_code.is_used = True
            invitation_code.used_by = user
            invitation_code.save()
            
            # 自动登录
            login(request, user)
            messages.success(request, f'注册成功！欢迎加入，{user.username}！')
            return redirect('geodata:map')
    else:
        form = RegisterForm()
    
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def logout_view(request):
    """用户退出登录视图"""
    logout(request)
    messages.success(request, '您已成功退出登录')
    return redirect('accounts:login')

@login_required
def profile_view(request):
    """用户资料视图
    显示用户的详细信息和配置
    """
    return render(request, 'accounts/profile.html', {
        'user': request.user,
        'profile': request.user.profile,
        'now': timezone.now()
    })
