import logging
from celery import shared_task
from django.utils import timezone

from .models import Deployment, Project
from .services.ssh_exec import run_ssh
from .services.nginx_config import deploy_nginx_config, remove_nginx_config
from .services.notifications import (
    notify_deploy_success,
    notify_deploy_failed,
    notify_status_change,
    notify_billing_warning,
)

logger = logging.getLogger(__name__)

GRACE_DAYS = 7


@shared_task
def deploy_project_task(project_id: int):
    """Деплоит проект на удалённый сервер через SSH."""
    project = Project.objects.select_related("server").get(id=project_id)

    # Проверяем, не деплоится ли уже
    if project.status == "deploying":
        logger.warning(f"Проект {project.slug} уже деплоится, пропускаем")
        return f"Проект {project.slug} уже деплоится"

    old_status = project.status
    project.status = "deploying"
    project.save(update_fields=["status"])

    dep = Deployment.objects.create(
        project=project, status="running", action="deploy"
    )

    s = project.server
    path = project.get_remote_path()
    port = project.internal_port

    cmd = f"""
set -e
mkdir -p {path}
cd {path}

if [ ! -d ".git" ]; then
  git clone {project.github_repo} .
fi

git fetch --all
git checkout {project.github_branch}
git reset --hard origin/{project.github_branch}
"""
    
    # Добавляем создание .env если есть переменные
    if project.env_vars:
        escaped_env = project.env_vars.replace("'", "'\\''")
        cmd += f"\necho '{escaped_env}' > .env\n"

    cmd += f"\ndocker compose -f {project.compose_file} up -d --build\n"

    log = ""
    try:
        log = run_ssh(s.ip_address, s.ssh_user, s.ssh_port, cmd)

        # Настраиваем Nginx если указан домен
        try:
            nginx_log = deploy_nginx_config(project)
            log += "\n--- NGINX ---\n" + nginx_log
        except Exception as e:
            log += f"\n--- NGINX ERROR ---\n{e}"
            logger.warning(f"Nginx конфиг не установлен: {e}")

        dep.status = "success"
        project.status = "active"
        project.last_deploy_at = timezone.now()

        notify_deploy_success(project)

    except Exception as e:
        log += f"\nDEPLOY ERROR: {e}"
        dep.status = "failed"
        project.status = "failed"
        project.last_deploy_at = timezone.now()

        notify_deploy_failed(project, str(e))

    dep.log = log
    dep.finished_at = timezone.now()
    dep.save()
    project.save(update_fields=["status", "last_deploy_at"])

    if project.status != old_status:
        notify_status_change(project, old_status, project.status)


@shared_task
def suspend_project_task(project_id: int):
    """Останавливает контейнеры проекта на удалённом сервере."""
    project = Project.objects.select_related("server").get(id=project_id)
    old_status = project.status
    dep = Deployment.objects.create(
        project=project, status="running", action="suspend"
    )

    s = project.server
    path = project.get_remote_path()

    cmd = f"""
set -e
cd {path}
docker compose -f {project.compose_file} stop
"""

    log = ""
    try:
        log = run_ssh(s.ip_address, s.ssh_user, s.ssh_port, cmd)

        # Удаляем Nginx конфиг
        try:
            nginx_log = remove_nginx_config(project)
            log += "\n--- NGINX ---\n" + nginx_log
        except Exception as e:
            log += f"\n--- NGINX REMOVE ERROR ---\n{e}"

        dep.status = "success"
        project.status = "suspended"

    except Exception as e:
        log += f"\nSUSPEND ERROR: {e}"
        dep.status = "failed"
        logger.error(f"Ошибка suspend {project.slug}: {e}")

    dep.log = log
    dep.finished_at = timezone.now()
    dep.save()
    project.save(update_fields=["status"])

    if project.status != old_status:
        notify_status_change(project, old_status, project.status)


@shared_task
def resume_project_task(project_id: int):
    """Возобновляет контейнеры проекта на удалённом сервере."""
    project = Project.objects.select_related("server").get(id=project_id)
    old_status = project.status
    dep = Deployment.objects.create(
        project=project, status="running", action="resume"
    )

    s = project.server
    path = project.get_remote_path()

    cmd = f"""
set -e
cd {path}
docker compose -f {project.compose_file} up -d
"""

    log = ""
    try:
        log = run_ssh(s.ip_address, s.ssh_user, s.ssh_port, cmd)

        # Восстанавливаем Nginx конфиг
        try:
            nginx_log = deploy_nginx_config(project)
            log += "\n--- NGINX ---\n" + nginx_log
        except Exception as e:
            log += f"\n--- NGINX ERROR ---\n{e}"

        dep.status = "success"
        project.status = "active"
        project.last_deploy_at = timezone.now()

    except Exception as e:
        log += f"\nRESUME ERROR: {e}"
        dep.status = "failed"
        logger.error(f"Ошибка resume {project.slug}: {e}")

    dep.log = log
    dep.finished_at = timezone.now()
    dep.save()
    project.save(update_fields=["status", "last_deploy_at"])

    if project.status != old_status:
        notify_status_change(project, old_status, project.status)


@shared_task
def check_billing_task():
    """
    Ежедневная проверка биллинга:
    1. Активные проекты с истёкшей оплатой → Grace (7 дней)
    2. Grace проекты с истёкшим grace-периодом → Suspend
    3. Предупреждение за 3 дня до окончания оплаты
    """
    from datetime import timedelta

    today = timezone.now().date()

    # 1. Предупреждения за 3 дня
    warning_date = today + timedelta(days=3)
    projects_warning = Project.objects.filter(
        status="active",
        paid_until=warning_date,
    )
    for project in projects_warning:
        days_left = (project.paid_until - today).days
        notify_billing_warning(project, days_left)

    # 2. Active → Grace
    projects_expired = Project.objects.filter(
        status__in=["active", "deploying"],
        paid_until__lt=today,
    ).exclude(paid_until__isnull=True)

    for project in projects_expired:
        old_status = project.status
        project.status = "grace"
        project.grace_until = today + timedelta(days=GRACE_DAYS)
        project.save(update_fields=["status", "grace_until"])
        notify_status_change(project, old_status, "grace")
        logger.info(f"Проект {project.slug} → GRACE до {project.grace_until}")

    # 3. Grace → Suspend
    projects_grace_expired = Project.objects.filter(
        status="grace",
        grace_until__lt=today,
    )

    for project in projects_grace_expired:
        suspend_project_task.delay(project.id)
        logger.info(f"Проект {project.slug} → SUSPEND (grace истёк)")
