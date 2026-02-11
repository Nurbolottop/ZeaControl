from django.db import models
from django.utils import timezone


PORT_RANGE_START = 9001
PORT_RANGE_END = 9999


class Server(models.Model):
    name = models.CharField("Название", max_length=100)
    ip_address = models.GenericIPAddressField("IP адрес")
    ssh_user = models.CharField("SSH пользователь", max_length=50, default="root")
    ssh_port = models.PositiveIntegerField("SSH порт", default=22)
    base_path = models.CharField(
        "Базовый путь",
        max_length=255,
        default="/srv/projects",
        help_text="Базовая папка проектов на удалённом сервере",
    )

    class Meta:
        verbose_name = "Сервер"
        verbose_name_plural = "Серверы"

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class Project(models.Model):
    STATUS_CHOICES = [
        ("new", "🆕 Новый"),
        ("deploying", "🔄 Деплоится"),
        ("active", "🟢 Активный"),
        ("grace", "🟡 Grace-период"),
        ("suspended", "🔴 Приостановлен"),
        ("failed", "❌ Ошибка"),
    ]

    # === Основная информация ===
    name = models.CharField("Название проекта", max_length=150)
    slug = models.SlugField("Slug", unique=True)
    description = models.TextField("Описание", blank=True)

    # === Технические данные ===
    github_repo = models.URLField("GitHub репозиторий")
    github_branch = models.CharField("Ветка", max_length=50, default="main")
    server = models.ForeignKey(
        Server, on_delete=models.PROTECT, verbose_name="Сервер",
        related_name="projects",
    )
    domain = models.CharField("Домен", max_length=255, blank=True)
    remote_path = models.CharField(
        "Путь на сервере",
        max_length=255,
        blank=True,
        help_text="Если пусто — используется base_path/slug",
    )
    compose_file = models.CharField(
        "Docker-compose файл",
        max_length=255,
        default="docker-compose.prod.yml",
    )
    internal_port = models.PositiveIntegerField(
        "Внутренний порт",
        unique=True,
        blank=True,
        null=True,
        help_text="Назначается автоматически из диапазона 9001–9999",
    )

    # === Биллинг ===
    price_per_month = models.DecimalField(
        "Стоимость/мес", max_digits=12, decimal_places=2, default=0
    )
    paid_until = models.DateField("Оплачено до", null=True, blank=True)
    free_support_until = models.DateField(
        "Бесплатная поддержка до", null=True, blank=True
    )
    grace_until = models.DateField(
        "Grace до",
        null=True,
        blank=True,
        help_text="Дата окончания grace-периода",
    )

    # === Статус ===
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="new"
    )
    last_deploy_at = models.DateTimeField("Последний деплой", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.internal_port:
            self.internal_port = self._next_free_port()
        super().save(*args, **kwargs)

    @staticmethod
    def _next_free_port():
        used_ports = set(
            Project.objects.exclude(internal_port__isnull=True)
            .values_list("internal_port", flat=True)
        )
        for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
            if port not in used_ports:
                return port
        raise RuntimeError("Нет свободных портов в диапазоне 9001–9999")

    def get_remote_path(self):
        if self.remote_path:
            return self.remote_path
        return f"{self.server.base_path}/{self.slug}"

    def is_paid(self):
        return self.paid_until and self.paid_until >= timezone.now().date()

    def __str__(self):
        return self.name


class Deployment(models.Model):
    STATUS_CHOICES = [
        ("pending", "⏳ В очереди"),
        ("running", "🔄 Выполняется"),
        ("success", "✅ Успешно"),
        ("failed", "❌ Ошибка"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, verbose_name="Проект",
        related_name="deployments",
    )
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    action = models.CharField(
        "Действие", max_length=20, default="deploy",
        choices=[
            ("deploy", "Deploy"),
            ("suspend", "Suspend"),
            ("resume", "Resume"),
        ],
    )
    started_at = models.DateTimeField("Начат", auto_now_add=True)
    finished_at = models.DateTimeField("Завершён", null=True, blank=True)
    log = models.TextField("Лог", blank=True)

    class Meta:
        verbose_name = "Деплой"
        verbose_name_plural = "Деплои"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.project.slug} — {self.get_action_display()} — {self.get_status_display()}"
