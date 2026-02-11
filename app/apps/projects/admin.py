from django.contrib import admin
from django.utils.html import format_html

from .models import Deployment, Project, Server
from .tasks import deploy_project_task, resume_project_task, suspend_project_task


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ("name", "ip_address", "ssh_user", "ssh_port", "base_path", "project_count")
    search_fields = ("name", "ip_address")

    def project_count(self, obj):
        count = obj.projects.count()
        return count
    project_count.short_description = "Проектов"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "status_badge", "server", "internal_port", "paid_until", "last_deploy_at")
    list_filter = ("status", "server")
    search_fields = ("name", "slug", "domain")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("internal_port", "created_at", "last_deploy_at")

    fieldsets = (
        ("📦 Основное", {
            "fields": ("name", "slug", "description"),
        }),
        ("⚙️ Техническое", {
            "fields": (
                "github_repo", "github_branch", "server", "domain",
                "remote_path", "compose_file", "internal_port",
            ),
        }),
        ("💰 Биллинг", {
            "fields": ("price_per_month", "paid_until", "free_support_until", "grace_until"),
            "classes": ("collapse",),
        }),
        ("📊 Статус", {
            "fields": ("status", "last_deploy_at", "created_at"),
        }),
    )

    actions = ["deploy", "suspend", "resume"]

    def status_badge(self, obj):
        colors = {
            "new": "#6c757d",
            "deploying": "#0dcaf0",
            "active": "#198754",
            "grace": "#ffc107",
            "suspended": "#dc3545",
            "failed": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; '
            'border-radius:12px; font-size:11px; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Статус"

    @admin.action(description="🚀 Deploy")
    def deploy(self, request, queryset):
        for project in queryset:
            deploy_project_task.delay(project.id)
        self.message_user(request, f"Деплой запущен для {queryset.count()} проект(ов)")

    @admin.action(description="⛔ Suspend")
    def suspend(self, request, queryset):
        for project in queryset:
            suspend_project_task.delay(project.id)
        self.message_user(request, f"Suspend запущен для {queryset.count()} проект(ов)")

    @admin.action(description="✅ Resume")
    def resume(self, request, queryset):
        for project in queryset:
            resume_project_task.delay(project.id)
        self.message_user(request, f"Resume запущен для {queryset.count()} проект(ов)")


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ("project", "action", "status", "started_at", "finished_at")
    list_filter = ("status", "action", "project")
    readonly_fields = ("log",)
    ordering = ("-started_at",)
