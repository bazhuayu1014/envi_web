from django.db import models
from django.contrib.auth.models import User  # Django内置的用户模型
from django.utils import timezone  # 用于处理时间
import uuid  # 用于生成唯一标识符

class InvitationCode(models.Model):
    """邀请码模型
    用于管理用户注册的邀请码，控制用户访问权限
    """
    # 邀请码字段，最大长度20，必须唯一
    code = models.CharField('邀请码', max_length=20, unique=True)
    # 创建时间，自动设置为当前时间
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    # 过期时间，可以为空
    expires_at = models.DateTimeField('过期时间', null=True, blank=True)
    # 是否已被使用
    is_used = models.BooleanField('是否已使用', default=False)
    # 使用该邀请码的用户，可以为空
    used_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,  # 用户删除时设为空
        null=True, 
        blank=True, 
        related_name='used_invitation'
    )
    # 创建该邀请码的用户，可以为空
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_invitations'
    )

    class Meta:
        verbose_name = '邀请码'  # 模型在管理界面的显示名称
        verbose_name_plural = verbose_name  # 复数形式
        ordering = ['-created_at']  # 按创建时间倒序排序

    def __str__(self):
        """返回邀请码的字符串表示"""
        return f"{self.code} ({'已使用' if self.is_used else '未使用'})"

    @classmethod
    def generate_code(cls):
        """生成唯一的邀请码
        使用UUID生成8位大写字母数字组合
        """
        return str(uuid.uuid4())[:8].upper()

    def is_valid(self):
        """检查邀请码是否有效
        检查条件：
        1. 未被使用
        2. 未过期（如果设置了过期时间）
        """
        if self.is_used:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

class UserProfile(models.Model):
    """用户配置文件模型
    扩展Django内置用户模型，添加额外的用户信息
    """
    # 关联到Django用户模型，一对一关系
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,  # 用户删除时同时删除配置文件
        related_name='profile'
    )
    # 关联到邀请码
    invitation_code = models.ForeignKey(
        InvitationCode, 
        on_delete=models.SET_NULL,  # 邀请码删除时设为空
        null=True
    )
    # 记录用户最后登录的IP地址
    last_login_ip = models.GenericIPAddressField('最后登录IP', null=True, blank=True)
    # 记录用户登录次数
    login_count = models.IntegerField('登录次数', default=0)
    # 创建时间
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    # 更新时间，每次保存时自动更新
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '用户配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        """返回用户配置的字符串表示"""
        return f"{self.user.username}的配置" 