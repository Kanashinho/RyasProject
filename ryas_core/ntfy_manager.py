import requests

# O tópico que você assinou no seu iPhone
NTFY_TOPIC = "wintter-ryas-yui-migucho"


def send_notification(
    title: str, message: str, priority: str = "high", tags: str = None
):
    """
    Envia uma notificação para o tópico ntfy configurado.

    Args:
        title (str): O título da notificação (suporta emojis).
        message (str): O corpo da mensagem.
        priority (str): "high", "default", "low", "min", "max".
        tags (str): Um emoji (tag) do ntfy. Ex: "rotating_light", "warning", "info".
                   Lista completa: https://ntfy.sh/docs/publish/#tags-emojis
    """
    headers = {
        "Title": title.encode("utf-8"),  # Garantir UTF-8 para emojis
        "Priority": priority,
    }

    if tags:
        headers["Tags"] = tags

    try:
        response = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),  # Garantir UTF-8
            headers=headers,
        )
        response.raise_for_status()  # Lança um erro se o status for 4xx ou 5xx
        print(f"LOG: Notificação ntfy enviada: {title}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Falha ao enviar notificação ntfy: {e}")
        return False
