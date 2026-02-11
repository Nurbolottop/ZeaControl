import subprocess
import logging

logger = logging.getLogger(__name__)

SSH_TIMEOUT = 600  # 10 минут максимум на выполнение SSH-команды


def run_ssh(host: str, user: str, port: int, command: str, timeout: int = SSH_TIMEOUT) -> str:
    """
    Выполняет команду на удалённом сервере через SSH.
    Возвращает stdout+stderr.
    Бросает RuntimeError если команда завершилась с ошибкой или по таймауту.
    """
    target = f"{user}@{host}"
    logger.info(f"SSH → {target}:{port} | Команда: {command[:100]}...")

    try:
        proc = subprocess.run(
            [
                "ssh",
                "-p", str(port),
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=10",
                target,
                command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        msg = f"SSH таймаут ({timeout}с) при выполнении команды на {target}"
        logger.error(msg)
        raise RuntimeError(msg)

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")

    if proc.returncode != 0:
        msg = f"SSH команда завершилась с ошибкой (code={proc.returncode}):\n{output}"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info(f"SSH ← {target} | OK")
    return output
