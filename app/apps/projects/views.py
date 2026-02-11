from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count

from .models import Project, Server, Deployment
from .tasks import deploy_project_task, suspend_project_task, resume_project_task


@login_required
def dashboard_view(request):
    projects = Project.objects.select_related("server").all()
    recent_deployments = Deployment.objects.select_related("project").order_by("-started_at")[:10]

    stats = {
        "total": projects.count(),
        "active": projects.filter(status="active").count(),
        "grace": projects.filter(status="grace").count(),
        "suspended": projects.filter(status="suspended").count(),
    }

    return render(request, "dashboard.html", {
        "projects": projects,
        "recent_deployments": recent_deployments,
        "stats": stats,
    })


@login_required
def project_detail_view(request, slug):
    project = get_object_or_404(
        Project.objects.select_related("server"),
        slug=slug,
    )
    deployments = Deployment.objects.filter(project=project).order_by("-started_at")[:20]

    return render(request, "project_detail.html", {
        "project": project,
        "deployments": deployments,
    })


@login_required
def project_action_view(request, slug, action):
    """Выполняет действие над проектом (deploy/suspend/resume)."""
    if request.method != "POST":
        return redirect("project_detail", slug=slug)

    project = get_object_or_404(Project, slug=slug)

    if action == "deploy":
        if project.status == "deploying":
            messages.warning(request, f"Проект {project.name} уже деплоится")
        else:
            deploy_project_task.delay(project.id)
            messages.success(request, f"🚀 Deploy для {project.name} запущен!")

    elif action == "suspend":
        suspend_project_task.delay(project.id)
        messages.success(request, f"⛔ Suspend для {project.name} запущен!")

    elif action == "resume":
        resume_project_task.delay(project.id)
        messages.success(request, f"✅ Resume для {project.name} запущен!")

    else:
        messages.error(request, f"Неизвестное действие: {action}")

    # Redirect back to wherever the user came from
    referer = request.META.get("HTTP_REFERER", "")
    if f"/project/{slug}" in referer:
        return redirect("project_detail", slug=slug)
    return redirect("dashboard")


@login_required
def servers_view(request):
    servers = Server.objects.annotate(project_count=Count("projects")).all()

    return render(request, "servers.html", {
        "servers": servers,
    })


@login_required
def billing_view(request):
    projects = Project.objects.select_related("server").all()

    total_revenue = projects.aggregate(total=Sum("price_per_month"))["total"] or 0
    paid_count = sum(1 for p in projects if p.is_paid())
    unpaid_count = sum(1 for p in projects if p.paid_until and not p.is_paid())

    return render(request, "billing.html", {
        "projects": projects,
        "total_revenue": total_revenue,
        "paid_count": paid_count,
        "unpaid_count": unpaid_count,
    })
