from django import forms
from django.contrib.auth.forms import UserCreationForm  # Django内置的用户创建表单
from django.contrib.auth.models import User
from .models import InvitationCode

class LoginForm(forms.Form):
    """登录表单
    处理用户登录的表单，包含用户名、密码和记住我选项
    """
    # 用户名字段，使用Bootstrap样式
    username = forms.CharField(
        label='用户名',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '请输入用户名'
        })
    )
    # 密码字段，使用Bootstrap样式
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': '请输入密码'
        })
    )
    # 记住我选项，使用Bootstrap样式
    remember_me = forms.BooleanField(
        label='记住我',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

class RegisterForm(UserCreationForm):
    """注册表单
    继承Django内置的用户创建表单，添加邀请码和邮箱字段
    """
    # 邀请码字段，使用Bootstrap样式
    invitation_code = forms.CharField(
        label='邀请码',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '请输入邀请码'
        })
    )
    # 邮箱字段，必填，使用Bootstrap样式
    email = forms.EmailField(
        label='电子邮箱',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': '请输入电子邮箱'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'invitation_code')

    def __init__(self, *args, **kwargs):
        """初始化表单
        为所有输入字段添加Bootstrap样式
        """
        super().__init__(*args, **kwargs)
        # 为所有文本输入字段添加Bootstrap类
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.PasswordInput)):
                field.widget.attrs.update({'class': 'form-control'})

    def clean_invitation_code(self):
        """验证邀请码
        检查邀请码是否存在且有效
        """
        code = self.cleaned_data.get('invitation_code')
        try:
            invitation = InvitationCode.objects.get(code=code)
            if not invitation.is_valid():
                raise forms.ValidationError('邀请码已失效')
        except InvitationCode.DoesNotExist:
            raise forms.ValidationError('无效的邀请码')
        return code

    def clean_email(self):
        """验证邮箱
        检查邮箱是否已被其他用户使用
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('该邮箱已被注册')
        return email 