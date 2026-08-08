from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    O UserAdmin padrão referencia `username`, que removemos — por isso
    precisamos redeclarar os fieldsets. Em troca ganhamos o Django Admin
    de graça, útil pra inspecionar o seed durante a demo.
    """

    ordering = ("email",)
    list_display = ("email", "full_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("email", "full_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Pessoal", {"fields": ("full_name",)}),
        ("Papel e acesso", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2"),
            },
        ),
    )
