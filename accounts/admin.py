from django.contrib import admin
from django.utils import timezone
from .models import InvitationCode, UserProfile

@admin.register(InvitationCode)
class InvitationCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'created_at', 'expires_at', 'is_used', 'used_by', 'created_by')
    list_filter = ('is_used', 'created_at')
    search_fields = ('code', 'used_by__username', 'created_by__username')
    readonly_fields = ('created_at',)
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # 如果是新创建的邀请码
            obj.created_by = request.user
            if not obj.code:  # 如果没有手动设置邀请码
                obj.code = InvitationCode.generate_code()
        super().save_model(request, obj, form, change)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_login_ip', 'login_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'last_login_ip')
    readonly_fields = ('created_at', 'updated_at', 'login_count')
