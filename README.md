# ⚡ ZeaControl

Панель управления веб-проектами — деплой, биллинг и мониторинг через Dashboard и Telegram бота.

## Возможности

- 🚀 **Деплой** — git pull + docker compose up через SSH на удалённые серверы
- ⚙️ **Nginx** — автоматическая генерация конфига и proxy_pass при деплое
- 💰 **Биллинг** — отслеживание оплаты, grace-период, автоматический suspend
- 🤖 **Telegram бот** — управление проектами через команды бота
- 📊 **Dashboard** — веб-панель с тёмной темой для управления проектами
- 🔄 **Celery** — фоновые задачи (деплой, suspend, resume, проверка биллинга)

## Стек

| Компонент | Технология |
|-----------|-----------|
| Backend | Django 5.2, Python 3.11 |
| БД | PostgreSQL 14 |
| Очереди | Celery + Redis |
| Бот | pyTelegramBotAPI |
| Деплой | Docker Compose, SSH |
| UI | Django Templates, CSS (dark theme) |

## Быстрый старт

### 1. Клонировать
```bash
git clone https://github.com/YOUR_USERNAME/ZeaControl.git
cd ZeaControl
```

### 2. Настроить `.env`
```bash
cp .env.example .env
nano .env
```

### 3. Запустить
```bash
# Dev
docker compose -f docker/docker-compose.yml up -d --build

# Prod
docker compose -f docker/docker-compose.prod.yml up -d --build
```

### 4. Создать суперюзера
```bash
docker exec -it django_web_zea python manage.py createsuperuser
```

### 5. Открыть
- **Dashboard**: http://localhost:8000/
- **Admin**: http://localhost:8000/admin/

## Telegram бот

| Команда | Описание |
|---------|----------|
| `/start` | Список команд |
| `/status` | Все проекты и их статусы |
| `/deploy <slug>` | Запустить деплой |
| `/suspend <slug>` | Остановить проект |
| `/resume <slug>` | Возобновить проект |
| `/logs <slug>` | Последний лог деплоя |
| `/billing` | Финансовый отчёт |
| `/servers` | Список серверов |
| `/info <slug>` | Детали проекта |

## Структура проекта

```
ZeaControl/
├── app/
│   ├── apps/
│   │   ├── base/           # URL routing
│   │   └── projects/       # Основная логика
│   │       ├── models.py       # Project, Server, Deployment
│   │       ├── views.py        # Dashboard views
│   │       ├── tasks.py        # Celery tasks
│   │       ├── admin.py        # Django Admin
│   │       ├── services/
│   │       │   ├── ssh_exec.py     # SSH выполнение команд
│   │       │   ├── nginx_config.py # Авто Nginx конфиг
│   │       │   └── notifications.py # Telegram уведомления
│   │       └── management/
│   │           └── commands/
│   │               └── bot.py      # Telegram бот
│   ├── core/               # Django settings
│   ├── templates/          # HTML шаблоны
│   └── static/             # CSS
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml      # Dev
│   └── docker-compose.prod.yml # Prod
├── scripts/
│   └── entrypoint.sh
├── .env
└── requirements.txt
```

## Жизненный цикл проекта

```
NEW → DEPLOYING → ACTIVE → GRACE (оплата истекла) → SUSPENDED
                    ↑                                    ↓
                    └──────────── RESUME ←───────────────┘
```

## Лицензия

MIT © ZeaTech
