import logging
from .ssh_exec import run_ssh

logger = logging.getLogger(__name__)

NGINX_TEMPLATE = """
server {{
    listen 80;
    server_name {domain};

    client_max_body_size 50M;

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }}

    location /static/ {{
        alias {remote_path}/app/static/;
    }}

    location /media/ {{
        alias {remote_path}/app/media/;
    }}
}}
"""


def generate_nginx_config(project) -> str:
    """Генерирует Nginx конфиг для проекта."""
    if not project.domain:
        return ""

    return NGINX_TEMPLATE.format(
        domain=project.domain,
        port=project.internal_port,
        remote_path=project.get_remote_path(),
    ).strip()


def deploy_nginx_config(project) -> str:
    """
    Отправляет Nginx конфиг на сервер проекта и перезагружает Nginx.
    Возвращает лог выполнения.
    """
    if not project.domain:
        logger.info(f"Проект {project.slug}: домен не указан, Nginx пропущен")
        return "Домен не указан — Nginx конфиг не создан\n"

    config = generate_nginx_config(project)
    s = project.server
    config_filename = f"{project.slug}.conf"

    # Экранируем конфиг для передачи через SSH
    escaped_config = config.replace("'", "'\\''")

    cmd = f"""
set -e
echo '{escaped_config}' > /etc/nginx/sites-available/{config_filename}
ln -sf /etc/nginx/sites-available/{config_filename} /etc/nginx/sites-enabled/{config_filename}
nginx -t
systemctl reload nginx
echo "Nginx конфиг для {project.domain} → порт {project.internal_port} установлен"
"""

    logger.info(f"Устанавливаем Nginx конфиг для {project.domain}")
    log = run_ssh(s.ip_address, s.ssh_user, s.ssh_port, cmd)
    return log


def remove_nginx_config(project) -> str:
    """Удаляет Nginx конфиг с сервера при suspend."""
    if not project.domain:
        return ""

    s = project.server
    config_filename = f"{project.slug}.conf"

    cmd = f"""
set -e
rm -f /etc/nginx/sites-enabled/{config_filename}
nginx -t && systemctl reload nginx
echo "Nginx конфиг для {project.domain} удалён"
"""

    logger.info(f"Удаляем Nginx конфиг для {project.domain}")
    log = run_ssh(s.ip_address, s.ssh_user, s.ssh_port, cmd)
    return log
