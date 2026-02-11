import os
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")


def notify_telegram(message: str) -> bool:
    """
    Отправляет уведомление в Telegram.
    Возвращает True если отправлено, False если ошибка или не настроен.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_CHAT_ID:
        logger.warning("Telegram уведомления не настроены (TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_CHAT_ID)")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"Telegram уведомление отправлено: {message[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки Telegram: {e}")
        return False


def notify_deploy_success(project):
    msg = (
        f"✅ <b>Deploy SUCCESS</b>\n"
        f"Проект: <b>{project.name}</b>\n"
        f"Домен: {project.domain or '—'}\n"
        f"Сервер: {project.server.name}"
    )
    notify_telegram(msg)


def notify_deploy_failed(project, error: str = ""):
    msg = (
        f"🔴 <b>Deploy FAILED</b>\n"
        f"Проект: <b>{project.name}</b>\n"
        f"Сервер: {project.server.name}\n"
        f"Ошибка: <code>{error[:200]}</code>"
    )
    notify_telegram(msg)


def notify_status_change(project, old_status: str, new_status: str):
    status_icons = {
        "active": "🟢",
        "grace": "🟡",
        "suspended": "🔴",
        "failed": "❌",
        "deploying": "🔄",
        "new": "🆕",
    }
    icon = status_icons.get(new_status, "ℹ️")
    msg = (
        f"{icon} <b>Статус изменён</b>\n"
        f"Проект: <b>{project.name}</b>\n"
        f"{old_status.upper()} → {new_status.upper()}"
    )
    notify_telegram(msg)


def notify_billing_warning(project, days_left: int):
    msg = (
        f"⚠️ <b>Оплата истекает</b>\n"
        f"Проект: <b>{project.name}</b>\n"
        f"Осталось дней: <b>{days_left}</b>\n"
        f"Оплачено до: {project.paid_until}"
    )
    notify_telegram(msg)
