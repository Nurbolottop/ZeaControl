import os
import logging
import telebot
from django.core.management.base import BaseCommand
from apps.projects.models import Project, Server, Deployment
from apps.projects.tasks import deploy_project_task, suspend_project_task, resume_project_task

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")


class Command(BaseCommand):
    help = "Запуск Telegram бота ZeaControl"

    def handle(self, *args, **options):
        if not TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR(
                "TELEGRAM_BOT_TOKEN не задан! Добавь его в .env"
            ))
            return

        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        self.stdout.write(self.style.SUCCESS("🤖 ZeaControl Bot запущен..."))

        def is_admin(message):
            """Проверяет что сообщение от админа."""
            return str(message.chat.id) == TELEGRAM_ADMIN_CHAT_ID

        @bot.message_handler(commands=["start"])
        def cmd_start(message):
            if not is_admin(message):
                bot.reply_to(message, "⛔ Доступ запрещён")
                return
            bot.reply_to(
                message,
                "👋 <b>ZeaControl Bot</b>\n\n"
                "Команды:\n"
                "/status — Все проекты\n"
                "/deploy &lt;slug&gt; — Деплой проекта\n"
                "/suspend &lt;slug&gt; — Остановить проект\n"
                "/resume &lt;slug&gt; — Возобновить проект\n"
                "/logs &lt;slug&gt; — Последний лог деплоя\n"
                "/billing — Биллинг проектов\n"
                "/servers — Список серверов\n"
                "/info &lt;slug&gt; — Детали проекта",
                parse_mode="HTML",
            )

        @bot.message_handler(commands=["status"])
        def cmd_status(message):
            if not is_admin(message):
                return

            projects = Project.objects.select_related("server").all()
            if not projects:
                bot.reply_to(message, "📭 Нет проектов")
                return

            status_icons = {
                "new": "🆕", "deploying": "🔄", "active": "🟢",
                "grace": "🟡", "suspended": "🔴", "failed": "❌",
            }

            lines = ["📊 <b>Все проекты:</b>\n"]
            for p in projects:
                icon = status_icons.get(p.status, "❓")
                domain = p.domain if p.domain else "—"
                lines.append(f"{icon} <b>{p.name}</b> | {domain} | :{p.internal_port}")

            bot.reply_to(message, "\n".join(lines), parse_mode="HTML")

        @bot.message_handler(commands=["deploy"])
        def cmd_deploy(message):
            if not is_admin(message):
                return

            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.reply_to(message, "❗ Использование: /deploy <slug>")
                return

            slug = parts[1]
            try:
                project = Project.objects.get(slug=slug)
            except Project.DoesNotExist:
                bot.reply_to(message, f"❌ Проект <b>{slug}</b> не найден", parse_mode="HTML")
                return

            if project.status == "deploying":
                bot.reply_to(message, f"⏳ Проект <b>{project.name}</b> уже деплоится", parse_mode="HTML")
                return

            deploy_project_task.delay(project.id)
            bot.reply_to(
                message,
                f"🚀 Деплой <b>{project.name}</b> запущен!\nСервер: {project.server.name}",
                parse_mode="HTML",
            )

        @bot.message_handler(commands=["suspend"])
        def cmd_suspend(message):
            if not is_admin(message):
                return

            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.reply_to(message, "❗ Использование: /suspend <slug>")
                return

            slug = parts[1]
            try:
                project = Project.objects.get(slug=slug)
            except Project.DoesNotExist:
                bot.reply_to(message, f"❌ Проект <b>{slug}</b> не найден", parse_mode="HTML")
                return

            suspend_project_task.delay(project.id)
            bot.reply_to(
                message,
                f"⛔ Suspend <b>{project.name}</b> запущен!",
                parse_mode="HTML",
            )

        @bot.message_handler(commands=["resume"])
        def cmd_resume(message):
            if not is_admin(message):
                return

            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.reply_to(message, "❗ Использование: /resume <slug>")
                return

            slug = parts[1]
            try:
                project = Project.objects.get(slug=slug)
            except Project.DoesNotExist:
                bot.reply_to(message, f"❌ Проект <b>{slug}</b> не найден", parse_mode="HTML")
                return

            resume_project_task.delay(project.id)
            bot.reply_to(
                message,
                f"✅ Resume <b>{project.name}</b> запущен!",
                parse_mode="HTML",
            )

        @bot.message_handler(commands=["logs"])
        def cmd_logs(message):
            if not is_admin(message):
                return

            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.reply_to(message, "❗ Использование: /logs <slug>")
                return

            slug = parts[1]
            try:
                project = Project.objects.get(slug=slug)
            except Project.DoesNotExist:
                bot.reply_to(message, f"❌ Проект <b>{slug}</b> не найден", parse_mode="HTML")
                return

            last_dep = Deployment.objects.filter(project=project).order_by("-started_at").first()
            if not last_dep:
                bot.reply_to(message, f"📭 Нет деплоев для <b>{project.name}</b>", parse_mode="HTML")
                return

            log_text = last_dep.log[:3000] if last_dep.log else "Лог пустой"
            bot.reply_to(
                message,
                f"📋 <b>{project.name}</b> — {last_dep.get_action_display()} — {last_dep.get_status_display()}\n"
                f"🕐 {last_dep.started_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"<pre>{log_text}</pre>",
                parse_mode="HTML",
            )

        @bot.message_handler(commands=["billing"])
        def cmd_billing(message):
            if not is_admin(message):
                return

            projects = Project.objects.exclude(
                price_per_month=0
            ).order_by("paid_until")

            if not projects:
                bot.reply_to(message, "📭 Нет проектов с биллингом")
                return

            lines = ["💰 <b>Биллинг:</b>\n"]
            for p in projects:
                paid = p.paid_until.strftime("%d.%m.%Y") if p.paid_until else "—"
                status_icon = "🟢" if p.is_paid() else "🔴"
                lines.append(
                    f"{status_icon} <b>{p.name}</b>\n"
                    f"   💵 {p.price_per_month} сом/мес | до: {paid}"
                )

            bot.reply_to(message, "\n".join(lines), parse_mode="HTML")

        @bot.message_handler(commands=["servers"])
        def cmd_servers(message):
            if not is_admin(message):
                return

            servers = Server.objects.all()
            if not servers:
                bot.reply_to(message, "📭 Нет серверов")
                return

            lines = ["🖧 <b>Серверы:</b>\n"]
            for s in servers:
                count = s.projects.count()
                lines.append(f"🖥️ <b>{s.name}</b> | {s.ip_address} | Проектов: {count}")

            bot.reply_to(message, "\n".join(lines), parse_mode="HTML")

        @bot.message_handler(commands=["info"])
        def cmd_info(message):
            if not is_admin(message):
                return

            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.reply_to(message, "❗ Использование: /info <slug>")
                return

            slug = parts[1]
            try:
                project = Project.objects.select_related("server").get(slug=slug)
            except Project.DoesNotExist:
                bot.reply_to(message, f"❌ Проект <b>{slug}</b> не найден", parse_mode="HTML")
                return

            paid = project.paid_until.strftime("%d.%m.%Y") if project.paid_until else "—"
            last_deploy = project.last_deploy_at.strftime("%d.%m.%Y %H:%M") if project.last_deploy_at else "—"

            status_icons = {
                "new": "🆕", "deploying": "🔄", "active": "🟢",
                "grace": "🟡", "suspended": "🔴", "failed": "❌",
            }
            icon = status_icons.get(project.status, "❓")

            bot.reply_to(
                message,
                f"📦 <b>{project.name}</b>\n\n"
                f"Статус: {icon} {project.get_status_display()}\n"
                f"Домен: {project.domain or '—'}\n"
                f"Сервер: {project.server.name} ({project.server.ip_address})\n"
                f"Порт: {project.internal_port}\n"
                f"GitHub: {project.github_repo}\n"
                f"Ветка: {project.github_branch}\n"
                f"Docker: {project.compose_file}\n\n"
                f"💰 Стоимость: {project.price_per_month} сом/мес\n"
                f"📅 Оплачено до: {paid}\n"
                f"🕐 Последний деплой: {last_deploy}",
                parse_mode="HTML",
            )

        # Запускаем бота
        logger.info("Telegram бот запущен, ожидаем сообщения...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
